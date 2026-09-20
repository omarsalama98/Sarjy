"""FastAPI app and the conversation WebSocket.

Block 1 builds the pipe, not what flows through it: a handshake, a session
that outlives its connection, transparent reconnect, and the static mount
that serves the React shell from this same origin (no CORS anywhere in this
project). No audio, no STT/LLM/TTS -- see docs/plans/blocks/01-skeleton-deploy.md
"Out of scope".

This module must not import app.config, groq, or google-genai: Block 1 needs
no provider key and no provider SDK, so a missing key or a provider SDK
change cannot break the deploy, and the container starts faster.

The handler is `async def`. With @modal.concurrent (modal_app.py), one
WebSocket is one input among several sharing a container; a *synchronous*
handler would die entirely when any one input is cancelled, and a closed
browser tab is a cancellation. One reviewer closing a tab must not be able
to take down everyone else's session.
"""

import asyncio
import contextlib
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.pipeline.protocol import (
    PROTOCOL_VERSION,
    ByeIn,
    ClosingOut,
    ErrorOut,
    HelloIn,
    PingIn,
    PongOut,
    ReadyOut,
    ServerMessage,
    StateOut,
    parse_client_message,
)
from app.session import Session, SessionRegistry, now_ms

logger = logging.getLogger("sarjy")

app = FastAPI(title="Sarjy")

# In-process: one registry per container. Block 7 moves this to modal.Dict;
# until then max_containers=1 (modal_app.py) is what keeps a reconnect from
# landing on a container that has never heard of the session.
registry = SessionRegistry()

# Measured against this deployment (backend/scripts/ws_lifetime.py; full story
# in docs/measurements/day1-spikes.md S1's Block 1 addendum): an actively-used
# connection (real traffic every 5-15s, not just idle) survived a clean 301.6s
# before the server closed it -- D >= 140s, so the plan's decision table says
# ship 75s/110s. Comfortable margin: rotation happens at 1/4 of the observed
# lifetime, not against a number we're hoping holds.
ROTATE_AFTER_MS = 75_000
HARD_MAX_MS = ROTATE_AFTER_MS + 35_000

# The client is required to send `hello` immediately on connecting. Bounding
# the wait keeps a silent connection from holding one of the container's
# limited concurrent input slots (modal_app.py's max_inputs) forever.
HELLO_TIMEOUT_S = 10

SERVER_STARTED_AT_MS = now_ms()


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


async def _serve(ws: WebSocket, session: Session, my_generation: int) -> None:
    """The receive loop for one connection.

    A turn never spans a connection (Block 1 never starts one, so that
    invariant costs nothing to hold here) -- so this loop only ever has to
    handle control messages: ping/pong, bye, and the failure paths. The
    server ceiling is enforced by an absolute deadline, not a per-message
    idle timeout, because a chatty stale client should still be capped.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + HARD_MAX_MS / 1000

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
            # Superseded by a newer hello elsewhere (S1's late-finally case,
            # or two tabs). Drop further writes; the caller's cleanup is
            # already guarded by the same generation check and will no-op.
            return

        if message.get("bytes") is not None:
            await _send(
                ws,
                ErrorOut(
                    code="unsupported",
                    message="binary audio arrives in Block 2",
                    recoverable=True,
                    seq=session.next_seq(),
                    ts_ms=now_ms(),
                ),
            )
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
            # Not politeness -- capacity. Closing now (rather than waiting
            # for the client's own close to be noticed) frees the Modal
            # input slot immediately instead of ~2 minutes late.
            return
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
