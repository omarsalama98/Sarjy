"""FastAPI app and the conversation WebSocket.

Block 1 built the pipe: a handshake, a session that outlives its connection,
transparent reconnect, and the static mount that serves the React shell from
this same origin (no CORS anywhere in this project). Block 2 puts the voice
turn through it -- start/end/barge, the binary audio channel, and run_turn().

This module still must not import app.config, groq, google-genai, or
websockets AT MODULE LEVEL: a missing key or a provider SDK regression must
never stop /health or the static mount from serving. app.pipeline.turn is
safe to import here (it only depends on Protocols, in app.providers.base,
which has no SDK imports of its own) -- but app.providers.factory, which
constructs the real STT/LLM/TTS clients, is imported lazily inside the
handler instead, right where a turn actually needs it (F14).

Block B's app.memory.store follows the same rule app.tools.quota already
set: `import modal` happens lazily, inside `_ModalDictStore.__init__`, never
at that module's top level -- so importing app.memory.store (and
app.session, which now imports it) here at module level is exactly as safe
as importing app.pipeline.turn was.

The handler is `async def`. With @modal.concurrent (modal_app.py), one
WebSocket is one input among several sharing a container; a *synchronous*
handler would die entirely when any one input is cancelled, and a closed
browser tab is a cancellation. One reviewer closing a tab must not be able
to take down everyone else's session.
"""

import asyncio
import contextlib
import itertools
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.memory.extract import extract_facts, looks_self_referential
from app.memory.identity import (
    MAX_PIN_ATTEMPTS,
    SIGNIN_BACK,
    SIGNIN_CLASH,
    SIGNIN_LOCKED,
    SIGNIN_NEW,
    normalise_name,
    parse_sign_in_request,
    pin_hash,
)
from app.memory.store import (
    MAX_FACTS,
    MemoryRecord,
    load_record,
    save_record,
    store_is_durable,
)
from app.pipeline.protocol import (
    PROTOCOL_VERSION,
    BargeIn,
    ByeIn,
    ClientTimingIn,
    ClosingOut,
    EndIn,
    ErrorOut,
    FactOut,
    ForgetIn,
    HelloIn,
    MemoryOut,
    PingIn,
    PongOut,
    QuotaOut,
    ReadyOut,
    ReplyOut,
    ServerMessage,
    SignInIn,
    SignOutIn,
    StartIn,
    StateOut,
    TranscriptOut,
    TurnFailedOut,
    parse_client_message,
)
from app.pipeline.timings import TurnTimings, elapsed_ms, emit
from app.pipeline.turn import MAX_TURN_BYTES, run_turn
from app.prompts import build_memory_block
from app.providers.base import ProviderUnavailable
from app.session import Session, SessionRegistry, now_ms

# Read directly from the environment, not app.config.load_settings(): this
# module must not import app.config at module level (see the docstring
# above), and this needs no secret -- just LOG_LEVEL, a plain string.
# Without this, every logger.info() call in this app -- including the
# stt_ms/tts_ttfb_ms/llm_first_text_delta_ms lines the block plan's own
# verification depends on -- is silently swallowed: Python's root logger
# defaults to WARNING with no handler, so `modal app logs` would show
# nothing. Discovered running task 15's own verification, not assumed.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "info").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("sarjy")

app = FastAPI(title="Sarjy")

# GZipMiddleware only touches HTTP responses (it checks scope["type"] ==
# "http" and passes anything else straight through), so it never touches
# the WebSocket -- this is a static-asset win on first load, not a
# voice-path change.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# In-process: one registry per container, and it STAYS in-process even
# after Block B gives memory its own durable modal.Dict (D6) -- only the
# facts a user taught Sarjy are durable; which connection is "live" for a
# session is not. max_containers=1 (modal_app.py) is what keeps a reconnect
# from landing on a container that has never heard of the session.
registry = SessionRegistry()

# Measured 301.6s with traffic (day1-spikes.md). Rotate at ~half that so a
# 5-minute demo is one silent reconnect, not a chip that flips every minute.
ROTATE_AFTER_MS = 150_000
HARD_MAX_MS = ROTATE_AFTER_MS + 40_000

# The client is required to send `hello` immediately on connecting. Bounding
# the wait keeps a silent connection from holding one of the container's
# limited concurrent input slots (modal_app.py's max_inputs) forever.
HELLO_TIMEOUT_S = 10

SERVER_STARTED_AT_MS = now_ms()

# Read directly from the environment for the same reason LOG_LEVEL is above:
# this module must not import app.config at load time. Set on the Modal
# image (modal_app.py's .env({"SARJY_ENV": "modal"})); defaults to "local"
# under `make dev` and in tests.
SARJY_ENV = os.environ.get("SARJY_ENV", "local")

# 1-based, per container process -- turn 1 is the cold one. A plain
# itertools.count needs no lock: one container, one event loop, and
# .next_seq()-style access from a single coroutine at a time (the receive
# loop in _serve() is the only writer, same as session.next_seq()).
_TURN_INDEX = itertools.count(1)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _send(ws: WebSocket, msg: ServerMessage) -> None:
    await ws.send_text(msg.model_dump_json())


async def _read_hello(ws: WebSocket) -> HelloIn | None:
    """The one place a bad message is fatal: a missing, malformed, or
    non-hello first message closes the socket rather than replying with a
    recoverable error, because there is no session yet to attach one to.

    Broad `except` deliberately: a timeout, a client disconnect, a binary
    frame instead of text, bad JSON, or a well-formed non-hello message all
    collapse to the same outcome here -- "no valid hello arrived."
    """
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=HELLO_TIMEOUT_S)
        msg = parse_client_message(raw)
    except Exception:
        return None
    return msg if isinstance(msg, HelloIn) else None


def _rotate_ceiling_closing(session: Session) -> ClosingOut:
    return ClosingOut(
        reason="rotate_ceiling", reconnect=True, seq=session.next_seq(), ts_ms=now_ms()
    )


@dataclass
class _TurnState:
    """Per-connection turn bookkeeping. A turn never spans a connection
    (Block 1's invariant), so none of this needs to survive a reconnect --
    it lives and dies with one call to `_serve()`.

    Two phases, tracked separately, because a `start` or `barge` can
    interrupt either one:
      PHASE A -- `open_turn_id`/`buffer`: the client is still sending audio.
      PHASE B -- `task`/`task_turn_id`: run_turn() is processing what was sent.
    """

    open_turn_id: str | None = None
    buffer: bytearray | None = None
    task: "asyncio.Task[None] | None" = None
    task_turn_id: str | None = None

    # D12 -- `?gate_demo=1` on the connection URL. Set once, at connect
    # time, from the query string; read by _process_turn on every turn on
    # this connection. Server-side and query-param-gated on purpose: it
    # fabricates one bad segment into a REAL turn so a reviewer watches an
    # actual rejection happen live, rather than trusting a unit test.
    gate_demo: bool = False

    # StartIn.lang for the currently open turn -- set on `start`, read on `end`.
    lang: str = "en"

    # -- Block 3: the timing record for the turn currently in flight. Lives
    # here, not on the session, because a turn never spans a connection
    # (Block 1's invariant) -- nothing here needs to survive a reconnect.
    timings: TurnTimings | None = None
    turn_started_at: float = 0.0  # time.monotonic() at `start`
    end_received_at: float = 0.0  # time.monotonic() at `end`
    server_done: bool = False
    client_done: bool = False


async def _cancel_active_turn(turns: _TurnState) -> None:
    """Cancels phase B (a run_turn task in flight) if there is one.
    Idempotent -- safe to call whether or not a task is actually running.
    Used for both an explicit `barge` and an implicit one (a new `start`
    while a turn is still being processed) -- one code path for both, per
    the protocol's own framing of implicit barge.
    """
    if turns.task is not None and not turns.task.done():
        turns.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await turns.task
    turns.task = None
    turns.task_turn_id = None


def _maybe_emit_timings(turns: _TurnState) -> None:
    """Prints the record once both halves of the turn are done -- the
    server's last audio chunk and the client's first audible sound. Neither
    side alone knows the whole chain, so this is called from both
    completion points (_process_turn's `finally` and _handle_client_timing)
    and is a no-op until the second of the two has actually happened."""
    if turns.timings is None or not (turns.server_done and turns.client_done):
        return
    emit(turns.timings)
    turns.timings = None


def _flush_timings(turns: _TurnState, reason: Literal["next_turn", "connection_closed"]) -> None:
    """Prints an incomplete record rather than losing it. The client leg can
    legitimately never arrive: a barge before any audio, a closed tab, a
    stale bundle -- I2's "a turn never produces zero records"."""
    if turns.timings is None:
        return
    turns.timings.flush_reason = reason
    emit(turns.timings)
    turns.timings = None


# Extraction tasks (D4) are fire-and-forget from _process_turn's point of
# view, but a bare asyncio.create_task() result with no other reference can
# be garbage-collected mid-flight -- this set is that reference, and
# add_done_callback(discard) is what stops it growing forever.
_extraction_tasks: set["asyncio.Task[None]"] = set()


def _now_iso() -> str:
    return datetime.fromtimestamp(now_ms() / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _send_memory(ws: WebSocket, session: Session, *, message: str | None = None) -> None:
    """The ONLY place MemoryOut is constructed -- sent after `ready`, after
    any sign-in attempt (success or refusal), after sign-out, after a
    forget, and after an extraction that changed something (D5). There is
    no client-side memory state to drift: every change re-sends the WHOLE
    record, never a diff."""
    record = session.memory
    facts = [
        FactOut(
            key=f.key,
            label=f.label,
            value=f.value,
            kind=f.kind,
            learned_at=f.learned_at,
            turn_id=f.turn_id,
            quote=f.quote,
        )
        for f in record.facts
    ]
    await _send(
        ws,
        MemoryOut(
            tier="signed_in" if record.signed_in else "anonymous",
            name=record.name if record.signed_in else None,
            facts=facts,
            used=len(record.facts),
            capacity=MAX_FACTS,
            persisted=record.persisted,
            degraded=record.degraded,
            message=message,
            seq=session.next_seq(),
            ts_ms=now_ms(),
        ),
    )


async def _resolve_sign_in(session: Session, *, raw_name: str, pin: str) -> str | None:
    """D3's three outcomes, checked in the order that matters -- M13 before
    M3 before the happy path. Shared by BOTH the typed `sign_in` message
    (_handle_sign_in) and D8's voice sub-flow (_process_turn, above): the
    same identity rules apply regardless of which channel supplied the
    name/PIN. Mutates session.memory (and, on a mismatch, session.pin_attempts)
    in place; returns a panel message, or None on a quiet success."""
    name_key = normalise_name(raw_name)
    if name_key is None:  # M13 -- Pydantic's min_length=1 catches "", this catches "   "
        return "I need a name to remember you by."

    computed_hash = pin_hash(name_key, pin)
    existing = await load_record(name_key)

    if existing is not None and existing.pin_hash != computed_hash:
        # M3 -- refuse. Do not create, do not load, do not hint at content.
        session.pin_attempts += 1
        return SIGNIN_CLASH.format(name=raw_name.strip())

    is_new = existing is None
    display_name = raw_name.strip()
    iso_now = _now_iso()
    record = (
        existing
        if existing is not None
        else MemoryRecord(
            name=display_name, name_key=name_key, pin_hash=computed_hash, created_at=iso_now
        )
    )
    record.name = display_name
    record.updated_at = iso_now

    # D2 -- the anonymous tier's facts migrate in, union by key, higher
    # learned_at wins. Runs on every sign-in, not only the first: the demo
    # flow is "talk first, then sign in," and this is what stops that fact
    # from vanishing at the sign-in boundary.
    for fact in session.memory.facts:
        current = next((f for f in record.facts if f.key == fact.key), None)
        if current is None or fact.learned_at > current.learned_at:
            record.remember(fact)

    ok = await save_record(record)
    # `ok and store_is_durable()`, never `ok` alone: the M1 fallback happily
    # returns True from a process-local dict, so a save that "succeeded"
    # still evaporates on the next container restart (B1).
    record.persisted = ok and store_is_durable()
    record.degraded = not record.persisted
    session.memory = record
    session.pin_attempts = 0  # a successful sign-in resets the lockout counter

    if not ok:  # M1 -- a turn is never blocked on this; sign-in still "succeeds"
        return (
            "Signed in, but I can't reach my long-term memory — these are "
            "kept for this session only."
        )
    return SIGNIN_NEW.format(name=display_name) if is_new else SIGNIN_BACK.format(name=display_name)


async def _handle_sign_in(ws: WebSocket, session: Session, msg: SignInIn) -> None:
    if session.pin_attempts >= MAX_PIN_ATTEMPTS:  # M4
        await _send_memory(ws, session, message=SIGNIN_LOCKED)
        return
    message = await _resolve_sign_in(session, raw_name=msg.name, pin=msg.pin)
    await _send_memory(ws, session, message=message)


async def _handle_sign_out(ws: WebSocket, session: Session) -> None:
    """Back to a fresh, empty anonymous record -- signing out does not
    leave the previous facts visible under no identity at all."""
    session.memory = MemoryRecord()
    session.awaiting_pin = False
    await _send_memory(ws, session)


async def _handle_forget(ws: WebSocket, session: Session, msg: ForgetIn) -> None:
    """M9 -- a key that doesn't exist is a no-op, never an error; the panel
    is re-sent regardless so it resyncs with the server's own state."""
    session.memory.forget(msg.key)
    if session.memory.signed_in:
        ok = await save_record(session.memory)
        session.memory.persisted = ok and store_is_durable()
        session.memory.degraded = not session.memory.persisted
    await _send_memory(ws, session)


async def _extract_memory(
    ws: WebSocket,
    session: Session,
    my_generation: int,
    turns: "_TurnState",
    turn_id: str,
    user_text: str,
) -> None:
    """D4 -- runs well after the turn that triggered it has already spoken
    its answer. `extract_facts` itself never raises (its own docstring);
    what's guarded here is everything AROUND that call -- getting an LLM,
    writing to the store, and sending on a socket that may since have gone
    away, none of which may turn into a visible failure for a turn that
    already succeeded (M5)."""
    from app.providers import factory

    try:
        llm = factory.get_llm()
    except ProviderUnavailable:
        return  # no LLM configured -- extraction just doesn't run this turn

    known_keys = [f.key for f in session.memory.facts]
    facts, dropped = await extract_facts(
        llm=llm, user_text=user_text, turn_id=turn_id, known_keys=known_keys
    )

    if session.generation != my_generation:
        return  # the session moved on (a reconnect) -- nothing to attach this to

    # The turn's OWN timing record, if it's still the one sitting on this
    # connection -- it may already have printed (the common case, since
    # extraction runs well after `state: idle`); filling it in anyway is
    # harmless, and the alternative (delaying the emit to wait for this) is
    # exactly what D4 exists to prevent (a third LLM call back on the
    # measured latency path).
    same_turn = turns.timings is not None and turns.timings.turn_id == turn_id
    if same_turn and turns.timings is not None:
        turns.timings.memory_extracted = len(facts)
        turns.timings.memory_dropped = dropped

    if not facts:
        return

    for fact in facts:
        session.memory.remember(fact)

    if session.memory.signed_in:
        ok = await save_record(session.memory)
        session.memory.persisted = ok and store_is_durable()
        session.memory.degraded = not session.memory.persisted
        if same_turn and turns.timings is not None:
            turns.timings.memory_persisted = ok

    with contextlib.suppress(Exception):
        await _send_memory(ws, session)


async def _process_turn(
    ws: WebSocket,
    session: Session,
    my_generation: int,
    turn_id: str,
    pcm16: bytes,
    turns: _TurnState,
) -> None:
    """Runs as its own asyncio.Task (started on `end`) so the connection's
    receive loop stays free to notice a `barge` or a `bye` while STT/LLM/TTS
    are in flight. Consumes run_turn()'s generator and puts each item on the
    wire in the exact order it was yielded: JSON messages as text, bytes as
    a binary frame.

    `app.providers.factory` is imported here, not at module level -- see
    this module's docstring. A missing key surfaces as a normal
    ProviderUnavailable inside run_turn(), not an import-time crash.
    """
    from app.providers import factory

    last_transcript: str | None = None
    last_reply: str | None = None

    # D8's voice sign-in sub-flow. `was_awaiting_pin` is read BEFORE run_turn
    # runs (it's this turn's INPUT); `sign_in_attempt` is filled DURING the
    # turn by the on_sign_in callback and resolved against the store AFTER
    # the generator drains -- run_turn itself never touches app.memory.store
    # (Invariant 3; see turn.py's own docstring on this parameter pair).
    was_awaiting_pin = session.awaiting_pin
    sign_in_attempt: tuple[str, str] | None = None

    def on_sign_in(name: str, pin: str) -> None:
        nonlocal sign_in_attempt
        sign_in_attempt = (name, pin)

    timings = turns.timings
    if timings is None:
        # Should never happen -- _handle_start always builds the record
        # before _handle_end can create this task, and nothing else runs
        # between the two on a single-threaded receive loop. Defensive
        # fallback rather than a crash if that invariant is ever violated.
        logger.error("run_turn started with no timings record for turn %s", turn_id)
        timings = TurnTimings(
            turn_id=turn_id,
            session=session.session_id[:8],
            connection_n=session.connection_n,
            turn_index=next(_TURN_INDEX),
            env=SARJY_ENV,
        )
        turns.timings = timings

    # D7 -- rendered HERE, from session.memory, and handed to run_turn as a
    # plain string. Keeps run_turn testable with fakes and keeps the store's
    # lazy `import modal` out of its import graph.
    context_facts = session.memory.context_facts()
    memory_block = build_memory_block(context_facts)
    timings.memory_facts = len(context_facts)

    def _get_places() -> object:
        from app.tools.places import get_place_lookup

        return get_place_lookup()

    try:
        async for item in run_turn(
            turn_id=turn_id,
            pcm16=pcm16,
            history=session.history,
            next_seq=session.next_seq,
            now_ms=now_ms,
            get_stt=factory.get_stt,
            get_llm=factory.get_llm,
            get_tts=factory.get_tts,
            get_tool=factory.get_tool,
            gate_demo=turns.gate_demo,
            timings=timings,
            memory_block=memory_block,
            awaiting_pin=was_awaiting_pin,
            on_sign_in=on_sign_in,
            get_places=_get_places,
            lang=turns.lang,
        ):
            if session.generation != my_generation:
                return  # superseded mid-turn -- nothing left to write to

            if isinstance(item, bytes):
                if timings.server_ms is None:
                    timings.server_ms = elapsed_ms(turns.end_received_at)
                await ws.send_bytes(item)
                continue

            if isinstance(item, TranscriptOut):
                last_transcript = item.text
            elif isinstance(item, ReplyOut):
                last_reply = item.text
            elif isinstance(item, TurnFailedOut):
                timings.outcome = "failed"
                timings.failed_stage = item.stage
            await _send(ws, item)

        if last_transcript is not None and last_reply is not None:
            # Recorded even if TTS then failed (F11/F12) -- the reply was
            # real and shown; the next turn should still see it as context.
            session.remember_turn(last_transcript, last_reply)

        if session.generation == my_generation:
            if sign_in_attempt is not None:
                # D8 step 2 succeeded at PARSING a name+PIN -- turn.py has
                # already spoken SIGNIN_OK optimistically (it cannot await
                # the store without importing it, Invariant 3); the actual
                # identity resolution -- including a possible M3 clash --
                # happens here, and the panel is the correction path if the
                # two disagree. Documented as a known trade in PR_MEMORY.md.
                name, pin = sign_in_attempt
                session.awaiting_pin = False
                message = await _resolve_sign_in(session, raw_name=name, pin=pin)
                timings.memory_persisted = session.memory.persisted
                await _send_memory(ws, session, message=message)
            elif was_awaiting_pin:
                # M11/D8 -- one retry only: a spoken PIN that didn't parse
                # clears the flag rather than trapping the user in a state
                # they can only escape by reloading.
                session.awaiting_pin = False
            elif last_transcript is not None and parse_sign_in_request(last_transcript):
                # Step 1 fired THIS turn (SIGNIN_ASK was just spoken) -- arm
                # the next turn to listen for a spoken PIN instead of the LLM.
                session.awaiting_pin = True

            if last_transcript is not None and looks_self_referential(last_transcript):
                # D4 -- fired AFTER dispatch, never awaited before `state:
                # idle`. Held in a module-level set (with add_done_callback
                # discarding it) purely so asyncio doesn't garbage-collect a
                # task with no other live reference before it runs.
                extraction_task = asyncio.create_task(
                    _extract_memory(ws, session, my_generation, turns, turn_id, last_transcript)
                )
                _extraction_tasks.add(extraction_task)
                extraction_task.add_done_callback(_extraction_tasks.discard)

        if timings.tool_layer == "live" and session.generation == my_generation:
            # "sent once after ready, and again after any turn in which a
            # live request fired" (Contract 6) -- the chip only needs to
            # move when a request was actually spent.
            with contextlib.suppress(ProviderUnavailable):
                status = factory.get_tool().quota()
                await _send(
                    ws,
                    QuotaOut(
                        total=status.total,
                        spent=status.spent,
                        reserve=status.reserve,
                        remaining=status.remaining,
                        seq=session.next_seq(),
                        ts_ms=now_ms(),
                    ),
                )

        if timings.outcome == "incomplete":
            # Neither a TurnFailedOut nor a cancellation happened -- the
            # generator drained cleanly, so this is a real success.
            timings.outcome = "ok"

        if session.generation == my_generation:
            await _send(ws, StateOut(value="idle", seq=session.next_seq(), ts_ms=now_ms()))

    except asyncio.CancelledError:
        # Barge, or the connection itself closing (F13). The client already
        # knows it caused this -- it sent `barge`, or it's gone -- and in
        # the barge case it is already showing its own local state for the
        # NEW utterance. Sending `idle` here would clobber that with a
        # stale value, so this path deliberately sends nothing.
        #
        # Sync assignment only -- never `await` inside a cancellation
        # handler -- and it must happen before `raise`, not in `finally`,
        # so a later `except Exception` below never overwrites it.
        timings.outcome = "barged"
        raise
    except Exception:
        logger.exception("unhandled error processing turn %s", turn_id)
    finally:
        # One place covers the superseded-mid-turn early `return` above
        # too -- `finally` always runs, whichever way this function exits.
        turns.server_done = True
        _maybe_emit_timings(turns)


async def _serve(ws: WebSocket, session: Session, my_generation: int) -> None:
    """The receive loop for one connection.

    A turn never spans a connection (Block 1's invariant) -- so a `start`
    can open a turn and an `end` can close it here, but the run_turn() task
    it hands off to is always torn down (see the `finally` below) before
    this function returns, whatever the reason. The server ceiling is
    enforced by an absolute deadline, not a per-message idle timeout,
    because a chatty stale client should still be capped.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + HARD_MAX_MS / 1000
    turns = _TurnState()
    # D12 -- read once, from the connection's own query string. A reconnect
    # (Block 1's transparent rotation) opens a fresh WebSocket to the same
    # URL, so the flag survives a rotation without any extra wiring.
    turns.gate_demo = ws.query_params.get("gate_demo") == "1"

    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                if session.generation == my_generation:
                    await _send(ws, _rotate_ceiling_closing(session))
                return

            try:
                message = await asyncio.wait_for(ws.receive(), timeout=remaining)
            except TimeoutError:
                if session.generation == my_generation:
                    await _send(ws, _rotate_ceiling_closing(session))
                return

            if message["type"] == "websocket.disconnect":
                return

            if session.generation != my_generation:
                # Superseded by a newer hello elsewhere (S1's late-finally
                # case, or two tabs). Drop further writes; the caller's
                # cleanup is already guarded by the same generation check
                # and will no-op.
                return

            if message.get("bytes") is not None:
                await _handle_binary_frame(ws, session, turns, message["bytes"])
                continue

            raw = message.get("text")
            if raw is None:
                continue

            try:
                msg = parse_client_message(raw)
            except ValidationError:
                await _send(
                    ws,
                    ErrorOut(
                        code="bad_message",
                        message="could not parse that message",
                        recoverable=True,
                        seq=session.next_seq(),
                        ts_ms=now_ms(),
                    ),
                )
                continue

            if isinstance(msg, PingIn):
                pong = PongOut(
                    id=msg.id, client_ts_ms=msg.client_ts_ms, seq=session.next_seq(), ts_ms=now_ms()
                )
                await _send(ws, pong)
            elif isinstance(msg, ByeIn):
                # Not politeness -- capacity. Closing now (rather than
                # waiting for the client's own close to be noticed) frees
                # the Modal input slot immediately instead of ~2 minutes late.
                return
            elif isinstance(msg, StartIn):
                await _handle_start(session, turns, msg)
            elif isinstance(msg, EndIn):
                await _handle_end(ws, session, my_generation, turns, msg)
            elif isinstance(msg, BargeIn):
                await _handle_barge(turns, msg)
            elif isinstance(msg, ClientTimingIn):
                _handle_client_timing(turns, msg)
            elif isinstance(msg, SignInIn):
                await _handle_sign_in(ws, session, msg)
            elif isinstance(msg, SignOutIn):
                await _handle_sign_out(ws, session)
            elif isinstance(msg, ForgetIn):
                await _handle_forget(ws, session, msg)
            else:  # a second `hello` mid-connection -- never valid after the first
                await _send(
                    ws,
                    ErrorOut(
                        code="bad_message",
                        message="hello is only valid as the first message",
                        recoverable=True,
                        seq=session.next_seq(),
                        ts_ms=now_ms(),
                    ),
                )
    finally:
        # F13: whatever ended this loop -- a clean bye, the hard ceiling, a
        # dropped socket -- a turn still being processed is cancelled here,
        # not left running against a connection that no longer exists.
        await _cancel_active_turn(turns)
        # Whatever's left of the current turn's record -- the client leg
        # can never arrive now, the connection is gone -- is flushed rather
        # than dropped on the floor (I2).
        _flush_timings(turns, "connection_closed")


async def _handle_binary_frame(
    ws: WebSocket, session: Session, turns: _TurnState, data: bytes
) -> None:
    """F15 (no open turn) and F7's server-side half (a turn too long to be
    Whisper's 30 s window, checked as bytes arrive rather than waiting for
    `end` -- a client bug must not be able to buffer an unbounded upload).
    """
    if turns.buffer is None:
        await _send(
            ws,
            ErrorOut(
                code="bad_message",
                message="audio arrived with no open turn",
                recoverable=True,
                seq=session.next_seq(),
                ts_ms=now_ms(),
            ),
        )
        return

    turns.buffer.extend(data)
    if len(turns.buffer) > MAX_TURN_BYTES:
        turn_id = turns.open_turn_id
        turns.buffer = None
        turns.open_turn_id = None
        await _send(
            ws,
            TurnFailedOut(
                turn_id=turn_id or "",
                stage="audio",
                message="That was too long for me to catch — try a shorter question.",
                seq=session.next_seq(),
                ts_ms=now_ms(),
            ),
        )
        await _send(ws, StateOut(value="idle", seq=session.next_seq(), ts_ms=now_ms()))


async def _handle_start(session: Session, turns: _TurnState, msg: StartIn) -> None:
    """A `start` while a turn is already open (still recording) or still
    being processed is an implicit barge -- one code path, shared with the
    explicit `{"t":"barge"}` message (see _handle_barge)."""
    # First line, deliberately: whatever's left of the PREVIOUS turn's
    # record -- one whose client leg never arrived (I2: closed tab, stale
    # bundle, a barge before any audio) -- gets flushed before this turn
    # touches anything. A turn always produces exactly one record; this is
    # what stops one from silently surviving into the next.
    _flush_timings(turns, "next_turn")

    if (turns.task is not None and not turns.task.done()) or turns.buffer is not None:
        logger.info(
            "session %s: turn %s implicitly barged by %s",
            session.session_id[:8],
            turns.task_turn_id or turns.open_turn_id,
            msg.turn_id,
        )
        await _cancel_active_turn(turns)

    turns.open_turn_id = msg.turn_id
    turns.buffer = bytearray()
    turns.lang = msg.lang
    turns.timings = TurnTimings(
        turn_id=msg.turn_id,
        session=session.session_id[:8],
        connection_n=session.connection_n,
        turn_index=next(_TURN_INDEX),
        env=SARJY_ENV,
    )
    turns.turn_started_at = time.monotonic()
    turns.server_done = False
    turns.client_done = False


async def _handle_end(
    ws: WebSocket, session: Session, my_generation: int, turns: _TurnState, msg: EndIn
) -> None:
    if turns.buffer is None or turns.open_turn_id != msg.turn_id:
        await _send(
            ws,
            ErrorOut(
                code="bad_message",
                message="end received with no matching open turn",
                recoverable=True,
                seq=session.next_seq(),
                ts_ms=now_ms(),
            ),
        )
        return

    pcm16 = bytes(turns.buffer)
    turns.buffer = None
    turns.open_turn_id = None

    turns.end_received_at = time.monotonic()
    if turns.timings is not None:
        turns.timings.upload_ms = elapsed_ms(turns.turn_started_at)

    if msg.samples * 2 != len(pcm16):
        # Not a named failure path -- logged so a real network drop is
        # visible in the logs rather than silently transcribing short audio.
        logger.info(
            "turn %s: client reported %d samples, server has %d bytes",
            msg.turn_id,
            msg.samples,
            len(pcm16),
        )

    await _send(ws, StateOut(value="thinking", seq=session.next_seq(), ts_ms=now_ms()))

    turns.task_turn_id = msg.turn_id
    turns.task = asyncio.create_task(
        _process_turn(ws, session, my_generation, msg.turn_id, pcm16, turns)
    )


async def _handle_barge(turns: _TurnState, msg: BargeIn) -> None:
    if turns.task is not None and turns.task_turn_id == msg.turn_id:
        await _cancel_active_turn(turns)
    else:
        logger.info("barge for unknown/stale turn %s (active=%s)", msg.turn_id, turns.task_turn_id)


def _handle_client_timing(turns: _TurnState, msg: ClientTimingIn) -> None:
    """I3: a `client_timing` for a turn that isn't the one currently open is
    a legitimate race (a barge racing a reconnect), not a client bug --
    ignored, not a `bad_message`."""
    if turns.timings is None or turns.timings.turn_id != msg.turn_id:
        logger.info("client timing for unknown turn %s", msg.turn_id)
        return

    turns.timings.endpoint_ms = msg.endpoint_ms
    turns.timings.first_audio_ms = msg.first_audio_ms
    turns.timings.redemption_ms = msg.redemption_ms
    turns.timings.output_latency_ms = msg.output_latency_ms
    turns.client_done = True
    _maybe_emit_timings(turns)


@app.websocket("/ws")
async def conversation(ws: WebSocket) -> None:
    await ws.accept()

    session: Session | None = None
    my_generation = 0

    try:
        hello = await _read_hello(ws)
        if hello is None:
            return

        if hello.v != PROTOCOL_VERSION:
            # No session exists yet at this point, so there is no seq
            # counter to draw from -- 0 is a fine constant for a handshake
            # that never gets any further.
            await _send(
                ws,
                ErrorOut(
                    code="protocol_version",
                    message=f"server speaks protocol v{PROTOCOL_VERSION}",
                    recoverable=False,
                    seq=0,
                    ts_ms=now_ms(),
                ),
            )
            closing = ClosingOut(reason="protocol_version", reconnect=False, seq=0, ts_ms=now_ms())
            await _send(ws, closing)
            return

        session, resumed, old_live = registry.bind(hello.session_id, ws)
        my_generation = session.generation

        if old_live is not None:
            # Two tabs, or a reconnect racing ahead of the old socket's own
            # teardown. Best-effort: the old socket may already be dead.
            with contextlib.suppress(Exception):
                await old_live.send_text(
                    ClosingOut(
                        reason="superseded", reconnect=False, seq=session.next_seq(), ts_ms=now_ms()
                    ).model_dump_json()
                )
                await old_live.close(code=1000)

        await _send(
            ws,
            ReadyOut(
                v=PROTOCOL_VERSION,
                session_id=session.session_id,
                resumed=resumed,
                connection_n=session.connection_n,
                rotate_after_ms=ROTATE_AFTER_MS,
                hard_max_ms=HARD_MAX_MS,
                server_started_at_ms=SERVER_STARTED_AT_MS,
                seq=session.next_seq(),
                ts_ms=now_ms(),
            ),
        )
        await _send(ws, StateOut(value="idle", seq=session.next_seq(), ts_ms=now_ms()))

        # "sent once after `ready`" (Contract 6) -- imported here, not at
        # module level, for the same F14 reason every other factory.get_*
        # call in this file is lazy. A missing/misconfigured vendor key must
        # not stop the handshake from completing.
        from app.providers import factory

        with contextlib.suppress(ProviderUnavailable):
            status = factory.get_tool().quota()
            await _send(
                ws,
                QuotaOut(
                    total=status.total,
                    spent=status.spent,
                    reserve=status.reserve,
                    remaining=status.remaining,
                    seq=session.next_seq(),
                    ts_ms=now_ms(),
                ),
            )

        # Block B -- "sent after ready" (protocol.py's own docstring on
        # `memory`). A resumed connection re-sends the SAME session's record
        # -- nothing to reload, since session.memory already lives on it.
        await _send_memory(ws, session)

        logger.info(
            "session %s connection #%d ready (resumed=%s)",
            session.session_id[:8],
            session.connection_n,
            resumed,
        )

        await _serve(ws, session, my_generation)

    except Exception:
        logger.exception(
            "unhandled error in /ws (session=%s)", session.session_id[:8] if session else "-"
        )
        if session is not None and session.generation == my_generation:
            with contextlib.suppress(Exception):
                await _send(
                    ws,
                    ErrorOut(
                        code="internal",
                        message="internal error",
                        recoverable=False,
                        seq=session.next_seq(),
                        ts_ms=now_ms(),
                    ),
                )
    finally:
        if session is not None and session.generation == my_generation:
            session.live = None
        with contextlib.suppress(Exception):
            await ws.close()


# ---------------------------------------------------------------------------
# Static UI -- mounted last. Starlette matches routes in registration order;
# a mount at "/" registered before /health or /ws would swallow both.
# ---------------------------------------------------------------------------

_APP_DIR = Path(__file__).resolve().parent


def _resolve_dist() -> Path:
    """Locally (repo/backend/app/main.py) frontend/dist is two directories
    up from here. Under Modal, `add_local_python_source("app")` mounts this
    package straight to /root/app -- dropping the backend/ prefix -- while
    `add_local_dir` places the built UI at /root/frontend/dist: one
    directory up, not two. Rather than hard-code either offset, check both
    and use whichever actually exists. Verified against the installed modal
    client's own docstrings (Image.add_local_python_source, Image.add_local_dir
    -- both say exactly this), not assumed.
    """
    two_up = _APP_DIR.parent.parent / "frontend" / "dist"
    one_up = _APP_DIR.parent / "frontend" / "dist"
    for candidate in (two_up, one_up):
        if candidate.is_dir():
            return candidate
    return two_up


DIST = _resolve_dist()


class _NoCacheHTMLStaticFiles(StaticFiles):
    """Vite hashes JS/CSS filenames, so those are safe to cache forever --
    but a cached index.html after a redeploy would serve an old bundle
    against a new protocol version, mid-demo."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.media_type == "text/html":
            response.headers["Cache-Control"] = "no-cache"
        return response


if DIST.is_dir():
    app.mount("/", _NoCacheHTMLStaticFiles(directory=DIST, html=True), name="frontend")
else:
    logger.warning("frontend/dist not found at %s -- serving a placeholder at /", DIST)

    @app.get("/")
    async def _frontend_not_built() -> PlainTextResponse:
        return PlainTextResponse(
            "Sarjy backend is running. Run `npm run build` in frontend/ to serve the UI."
        )
