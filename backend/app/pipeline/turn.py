"""run_turn() -- the one place STT -> LLM -> tool -> gate -> TTS is
orchestrated.

Written entirely against the Protocols in app/providers/base.py (plus
app.tools.gate/card/prompts, which are pure stdlib+pydantic and carry no
provider SDK -- see those modules' own docstrings), so it is testable end
to end with fakes and no network (tests/test_turn.py). main.py is the only
caller and the only thing that knows which concrete providers are in play.

Every failure path in the block plan's "Failure paths" tables (F7-F12/F14
from Block 2, plus this block's V1-V11 and G1-G13/Q-a-h) is a branch here,
checked BEFORE its corresponding happy path -- this is a voice app, and the
failure paths are what break a demo.

The turn, after this block (Decision D5/D6):

    STT text
     |- LLM call 1 (decide, tools=[get_visa_requirements]) -> tool call or plain text
          |- tool.lookup()  -> ToolResult, stored under OUR id "tb_1"
     |- LLM call 2 (a FRESH stateless interaction) -> NDJSON, one segment per line
          |- gate -> kept + rejected segments -> one joined string -> one TTS request

The opener is cut in this block (no update(), no parallel function calling,
no second TTS request) -- opener_ready_ms/tts1_ttfb_ms/answer_gap_ms stay
null; that's Block C.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.memory.identity import (
    SIGNIN_ASK,
    SIGNIN_OK,
    SIGNIN_RETRY,
    parse_sign_in_request,
    parse_spoken_pin,
    spoken_digits,
)
from app.pipeline.protocol import (
    AudioEndOut,
    AudioStartOut,
    FactCardOut,
    FactRowOut,
    PlaceCardOut,
    PlacesOut,
    QuotaOut,
    ReplyOut,
    SegmentOut,
    SegmentsOut,
    TranscriptOut,
    TurnFailedOut,
    TurnFailedStage,
)
from app.pipeline.timings import TurnTimings, elapsed_ms
from app.prompts import NO_COVERAGE, SYSTEM_DECIDE, SYSTEM_SEGMENTS, VISA_TOOL, build_user_block
from app.providers.base import LLM, STT, TTS, ProviderUnavailable, ToolResult, VisaTool
from app.tools.card import FactCard, fact_card
from app.tools.gate import RenderedSegment, Segment, gate, spoken_text

logger = logging.getLogger("sarjy")

# Groq's Whisper window is a hard 30 s -- 30 s * 16 000 Hz * 2 bytes/sample.
MAX_TURN_BYTES = 30 * 16_000 * 2

TTS_SAMPLE_RATE = 24_000

TOOL_NAME = "get_visa_requirements"

TurnItem = (
    AudioEndOut
    | AudioStartOut
    | FactCardOut
    | PlacesOut
    | QuotaOut
    | ReplyOut
    | SegmentsOut
    | TranscriptOut
    | TurnFailedOut
    | bytes
)


class _SegmentLine(BaseModel):
    """One NDJSON line from call 2, validated before it becomes a
    gate.Segment. `extra="forbid"` -- a model that adds a stray key (e.g.
    writing `text` on a `quoted` line) fails validation here rather than
    silently passing an extra field through, which is exactly Q4's failure
    mode (quoted_text_supplied) and must reach the gate to be counted, not
    be swallowed by a lenient parser first."""

    model_config = ConfigDict(extra="forbid")

    # An unrecognised `kind` fails validation here -- counted as a
    # malformed line (G8), not silently downgraded to `judgement`.
    kind: Literal["sourced", "quoted", "judgement"]
    text: str | None = None
    tool_call_id: str | None = None
    fields: list[str] = []
    field: str | None = None
    place: str | None = None  # judgement only -- Wikipedia article title; ignored otherwise


def _parse_segment_line(line: str) -> tuple[Segment, str | None]:
    """Raises pydantic.ValidationError for anything that isn't a valid
    JSON object matching the shape above -- including JSON that doesn't
    parse at all (pydantic-core reports that as a ValidationError too, the
    same one-except-clause pattern protocol.py's parse_client_message()
    uses). The optional place title is returned alongside, collected only
    from judgement lines -- the gate never sees it."""
    parsed = _SegmentLine.model_validate_json(line)
    return Segment(
        kind=parsed.kind,
        text=parsed.text,
        tool_call_id=parsed.tool_call_id,
        fields=tuple(parsed.fields),
        field=parsed.field,
    ), (parsed.place.strip() if parsed.kind == "judgement" and parsed.place else None)


def _segment_to_wire(r: RenderedSegment) -> SegmentOut:
    return SegmentOut(
        kind=r.kind,
        text=r.text,
        ok=r.ok,
        reason=r.reason,
        attribution=r.attribution,
        field=r.field,
        citation=r.citation,
        source_url=r.source_url,
        source_date=r.source_date,
        layer=r.layer,  # type: ignore[arg-type]
    )


def _card_to_wire(card: FactCard, turn_id: str, *, seq: int, ts_ms: int) -> FactCardOut:
    return FactCardOut(
        turn_id=turn_id,
        passport=card.passport,
        passport_name=card.passport_name,
        destination=card.destination,
        destination_name=card.destination_name,
        covered=card.covered,
        facts=[
            FactRowOut(path=f.path, label=f.label, value=f.value, kind=f.register)
            for f in card.facts
        ],
        layer=card.layer,  # type: ignore[arg-type]
        degraded=card.degraded,
        source_name=card.source_name,
        source_url=card.source_url,
        source_date=card.source_date,
        retrieved=card.retrieved,
        embassy_url=card.embassy_url,
        seq=seq,
        ts_ms=ts_ms,
    )


async def run_turn(
    *,
    turn_id: str,
    pcm16: bytes,
    history: list[tuple[str, str]],
    next_seq: Callable[[], int],
    now_ms: Callable[[], int],
    get_stt: Callable[[], STT],
    get_llm: Callable[[], LLM],
    get_tts: Callable[[], TTS],
    get_tool: Callable[[], VisaTool],
    timings: TurnTimings,
    gate_demo: bool = False,
    memory_block: str = "",
    awaiting_pin: bool = False,
    on_sign_in: Callable[[str, str], None] | None = None,
    get_places: Callable[[], Any] | None = None,
) -> AsyncIterator[TurnItem]:
    """One full turn. `pcm16` is the whole utterance, already endpointed by
    the client's VAD. Providers are resolved lazily via the `get_*`
    callables, called only when that stage is reached -- a key missing for
    a LATER stage never stops an EARLIER one from running (F14), and
    nothing is built until a turn actually needs it.

    `system` is no longer a caller-supplied parameter (unlike Block 2): call
    1 and call 2 each have their own fixed system instruction
    (SYSTEM_DECIDE / SYSTEM_SEGMENTS, app/prompts.py) -- this block replaces
    the single freeform system prompt wholesale, exactly as that prompt's
    own comment always said it would.

    Block B additions:
      `memory_block` -- the rendered `<known_about_user>` block (D7), threaded
      into BOTH LLM calls unmodified. run_turn never touches app.memory.store
      itself: main.py renders the block from session.memory and hands over a
      plain string, which keeps this function testable with fakes and keeps
      the store's lazy `import modal` out of its import graph (Invariant 3).

      `awaiting_pin` / `on_sign_in` -- D8's voice sign-in sub-flow. Two
      callback-shaped parameters instead of a `Session`, so this function
      never imports app.session: `awaiting_pin` is the ONLY state read from
      the session, and `on_sign_in(name, pin)` is how a successfully parsed
      spoken PIN gets back out -- main.py resolves identity and touches the
      store AFTER this generator drains, the same pattern it already uses
      for session.remember_turn().
    """

    def failed(stage: TurnFailedStage, message: str) -> TurnFailedOut:
        return TurnFailedOut(
            turn_id=turn_id, stage=stage, message=message, seq=next_seq(), ts_ms=now_ms()
        )

    # F7 -- checked before any provider is touched: this turn is not salvageable.
    if len(pcm16) > MAX_TURN_BYTES:
        yield failed("audio", "That was too long for me to catch — try a shorter question.")
        return

    # -- STT -------------------------------------------------------------
    try:
        stt = get_stt()
    except ProviderUnavailable:
        yield failed("stt", "Speech-to-text is not configured.")
        return
    timings.stt_model = stt.model

    t0 = time.monotonic()
    try:
        text = await stt.transcribe(pcm16, language=None)
    except Exception:
        logger.exception("stt failed turn=%s", turn_id)
        yield failed(
            "stt", "I couldn't hear that clearly — my transcription service didn't answer."
        )
        return
    timings.stt_ms = elapsed_ms(t0)

    logger.info("stt_transcript turn=%s text=%r", turn_id, text)

    if not text.strip():
        yield failed("stt", "I didn't catch that — say it again?")
        return
    timings.transcript_chars = len(text)

    yield TranscriptOut(turn_id=turn_id, text=text, seq=next_seq(), ts_ms=now_ms())

    # -- D8: voice sign-in sub-flow, ahead of the STT-to-LLM path ------------
    # Deterministic, no model involved -- so the deep dive's prompts stay
    # untouched by an identity feature that has nothing to do with them.
    # Either branch below ends the turn: no LLM call is made, and nothing
    # here needs a tool or the gate.
    if awaiting_pin or parse_sign_in_request(text):
        async for item in _handle_sign_in_turn(
            text=text,
            awaiting_pin=awaiting_pin,
            turn_id=turn_id,
            get_tts=get_tts,
            failed=failed,
            next_seq=next_seq,
            now_ms=now_ms,
            timings=timings,
            on_sign_in=on_sign_in,
        ):
            yield item
        return

    # -- LLM call 1: decide -------------------------------------------------
    try:
        llm = get_llm()
    except ProviderUnavailable:
        yield failed("llm", "The language model is not configured.")
        return
    timings.llm_model = llm.model
    timings.llm_thinking_level = llm.thinking_level

    t0 = time.monotonic()
    try:
        # `text` is untrusted transcribed speech (Invariant 5) -- the `user`
        # parameter, never concatenated into `system`.
        decision = await llm.decide(
            system=SYSTEM_DECIDE,
            history=history,
            user=text,
            tools=[VISA_TOOL],
            memory_block=memory_block,
        )
    except Exception:
        logger.exception("llm decide() failed turn=%s", turn_id)
        yield failed("llm", "I couldn't come up with an answer just now — try asking again.")
        return
    timings.llm_ms = elapsed_ms(t0)
    timings.llm_ttft_ms = decision.first_delta_ms

    # -- tool (if call 1 asked for it) ---------------------------------------
    tool_result: ToolResult | None = None
    tool_call_id: str | None = None

    if decision.tool_name == TOOL_NAME:
        try:
            tool = get_tool()
        except ProviderUnavailable:
            yield failed("tool", "My visa lookup isn't configured right now.")
            return

        passport_arg = str(decision.tool_arguments.get("passport") or "").strip()
        destination_arg = str(decision.tool_arguments.get("destination") or "").strip()
        if not passport_arg or not destination_arg:
            # The model called the tool with nothing to look up -- the same
            # user-facing outcome as V8 (an unresolvable place).
            yield failed("tool", "I didn't catch which country you meant — can you say it again?")
            return

        t0 = time.monotonic()
        try:
            tool_result = await tool.lookup(passport=passport_arg, destination=destination_arg)
        except Exception:
            logger.exception("tool lookup failed turn=%s", turn_id)
            yield failed("tool", "My visa lookup didn't answer just now — try asking again.")
            return
        timings.tool_ms = elapsed_ms(t0)
        timings.tool_layer = tool_result.layer

        if tool_result.reason == "unknown_place":
            # V8 -- a graceful re-ask, never a guess. No pair was resolved
            # at all, so there's nothing for fact_card() to build either.
            yield failed("tool", "I didn't catch which country you meant — can you say it again?")
            return

        # fact_card() BEFORE call 2 starts -- it must not wait on the gated
        # answer (D15 / send-order contract). card.fact_card() returns None
        # only if no pair resolved; unknown_place (the only such case) is
        # already handled above, so this is non-None here.
        card = fact_card(tool_result)
        if card is not None:
            yield _card_to_wire(card, turn_id, seq=next_seq(), ts_ms=now_ms())

        if not tool_result.ok:
            # V3/V6 -- every layer exhausted, nothing covers this pair.
            # Never improvised, and never worth spending an LLM call to
            # re-derive what deterministic code already knows: there is
            # nothing to source an answer from.
            pair = tool_result.payload.get("pair", {})
            spoken = NO_COVERAGE.format(
                passport=pair.get("passport_name", passport_arg),
                destination=pair.get("destination_name", destination_arg),
            )
            timings.segments_ok = 0
            timings.segments_rejected = 0
            timings.lines_malformed = 0
            timings.hedged = False
            yield SegmentsOut(
                turn_id=turn_id,
                segments=[],
                spoken=spoken,
                hedged=False,
                seq=next_seq(),
                ts_ms=now_ms(),
            )
            yield ReplyOut(turn_id=turn_id, text=spoken, seq=next_seq(), ts_ms=now_ms())
            async for item in _speak(spoken, turn_id, get_tts, failed, next_seq, now_ms, timings):
                yield item
            return

        tool_call_id = "tb_1"
    elif decision.tool_name is not None:
        # Only one tool is ever declared -- an unrecognised name means the
        # model hallucinated a call. Treated as no tool: call 2 still runs,
        # and D6 makes any sourced/quoted segment reject on unknown_tool_call_id.
        logger.warning(
            "decide() returned unknown tool_name=%r turn=%s", decision.tool_name, turn_id
        )

    # -- LLM call 2: the gated NDJSON answer -----------------------------
    # D7 -- the SAME memory_block reaches this fresh, stateless call too:
    # call 1's plain text is never spoken (see this module's own docstring
    # diagram), so a memory-only question like "what's my favourite colour?"
    # can ONLY be answered here.
    user_block = build_user_block(
        user_question=text, tool_call_id=tool_call_id, result=tool_result, memory_block=memory_block
    )

    t0 = time.monotonic()
    try:
        raw_segments, lines_malformed, place_names = await _drain_segments(llm, user_block)
        if not raw_segments:
            # D11 -- the repair retry fires ONLY when the whole of call 2
            # produced zero valid segments, not per malformed line.
            #
            # F7 -- REPLACES, never adds to, the first attempt's malformed
            # count. The first attempt's segments are discarded wholesale
            # when the retry fires, so `lines_malformed` must describe only
            # the attempt that actually produced `raw_segments` -- otherwise
            # it counts malformed lines from a completion whose valid lines
            # were never counted anywhere, inflating measure.py's rate
            # (whose denominator is drawn from this same surviving attempt).
            raw_segments, lines_malformed, place_names = await _drain_segments(llm, user_block)
    except Exception:
        logger.exception("llm segments() failed turn=%s", turn_id)
        yield failed("gate", "I couldn't put that answer together — ask me again?")
        return
    timings.llm2_ms = elapsed_ms(t0)

    if gate_demo and tool_call_id is not None:
        # D12 -- one fabricated segment, appended to a REAL turn's output,
        # right before the gate sees it. The reviewer then watches an
        # actual rejection happen live (reason: no_placeholder -- a bare
        # digit with zero fields to substitute) rather than trusting a unit
        # test's word for it.
        raw_segments.append(
            Segment(
                kind="sourced",
                text="You can stay for 90 days.",
                tool_call_id=tool_call_id,
                fields=(),
            )
        )

    # -- gate ------------------------------------------------------------
    t0 = time.monotonic()
    tool_results: dict[str, ToolResult] = {}
    if tool_call_id is not None and tool_result is not None:
        tool_results[tool_call_id] = tool_result
    rendered = gate(raw_segments, tool_results)
    spoken = spoken_text(rendered)
    timings.gate_ms = elapsed_ms(t0)

    segments_ok = sum(1 for r in rendered if r.ok)
    timings.segments_ok = segments_ok
    timings.segments_rejected = len(rendered) - segments_ok
    timings.lines_malformed = lines_malformed
    # D4 -- a tool result existed and call 2 PRODUCED zero sourced AND zero
    # quoted segments. Never blocks; scored by hand in the eval, not enforced
    # here. F7 -- checked against what the model PRODUCED (raw_segments),
    # not what the gate KEPT (rendered, filtered on .ok): a model that
    # fabricated a sourced segment the gate then rejected did attempt a
    # sourced claim, so that turn is not a hedge -- it's a caught fabrication,
    # a different failure the gate-rejection rate already counts.
    timings.hedged = tool_result is not None and tool_result.ok and not any(
        s.kind in ("sourced", "quoted") for s in raw_segments
    )

    yield SegmentsOut(
        turn_id=turn_id,
        segments=[_segment_to_wire(r) for r in rendered],
        spoken=spoken,
        hedged=bool(timings.hedged),
        seq=next_seq(),
        ts_ms=now_ms(),
    )

    if not spoken.strip():
        # Should not happen -- spoken_text() always returns at least the
        # fixed REFUSAL sentence. Defensive, matching F10's original pattern.
        yield failed("llm", "I couldn't come up with an answer just now — try asking again.")
        return

    # Sent before any TTS is attempted -- F11's whole point.
    yield ReplyOut(turn_id=turn_id, text=spoken, seq=next_seq(), ts_ms=now_ms())

    places_task: asyncio.Task[list[Any]] | None = None
    if place_names and get_places is not None:
        # Starts NOW, concurrent with TTS -- must not be awaited before
        # first audio. PlacesOut is yielded after AudioStartOut, never before.
        places_task = asyncio.create_task(_lookup_places(get_places, place_names))

    emitted_places = False
    audio_started = False
    async for item in _speak(spoken, turn_id, get_tts, failed, next_seq, now_ms, timings):
        yield item
        if isinstance(item, AudioStartOut):
            audio_started = True
        if (
            places_task is not None
            and not emitted_places
            and audio_started
            and places_task.done()
        ):
            emitted_places = True
            yield _places_to_wire(places_task.result(), turn_id, next_seq(), now_ms())

    if places_task is not None and not emitted_places:
        yield _places_to_wire(await places_task, turn_id, next_seq(), now_ms())


async def _lookup_places(get_places: Callable[[], Any], names: list[str]) -> list[Any]:
    """Never raises -- a Wikimedia failure becomes failed PlaceCards so the
    strip can still render a visible 'couldn't source a photo' (I6/I7)."""
    try:
        cards: list[Any] = list(await get_places().lookup_many(names))
        return cards
    except Exception:
        logger.exception("places lookup failed")
        from app.tools.places import PlaceCard as PlaceCardModel

        return [
            PlaceCardModel(
                name=n,
                title=None,
                description=None,
                image_url=None,
                page_url=None,
                revision_date=None,
                ok=False,
                reason="http_error",
            )
            for n in names
        ]


def _places_to_wire(cards: list[Any], turn_id: str, seq: int, ts_ms: int) -> PlacesOut:
    return PlacesOut(
        turn_id=turn_id,
        places=[
            PlaceCardOut(
                name=c.name,
                title=c.title,
                description=c.description,
                image_url=c.image_url,
                page_url=c.page_url,
                revision_date=c.revision_date,
                ok=c.ok,
                reason=c.reason,
            )
            for c in cards
        ],
        seq=seq,
        ts_ms=ts_ms,
    )


async def _drain_segments(llm: LLM, user_block: str) -> tuple[list[Segment], int, list[str]]:
    """One full call-2 attempt: every valid line becomes a Segment; every
    line that fails validation is dropped and counted (G8) -- one bad line
    never loses the rest of a genuinely good answer. Place titles from
    judgement lines are collected here so the gate never has to know."""
    segments: list[Segment] = []
    places: list[str] = []
    seen: set[str] = set()
    malformed = 0
    async for line in llm.segments(system=SYSTEM_SEGMENTS, user_block=user_block):
        try:
            segment, place = _parse_segment_line(line)
        except ValidationError:
            malformed += 1
            continue
        segments.append(segment)
        if place:
            key = place.lower()
            if key not in seen and len(places) < 3:
                seen.add(key)
                places.append(place)
    return segments, malformed, places


async def _handle_sign_in_turn(
    *,
    text: str,
    awaiting_pin: bool,
    turn_id: str,
    get_tts: Callable[[], TTS],
    failed: Callable[[TurnFailedStage, str], TurnFailedOut],
    next_seq: Callable[[], int],
    now_ms: Callable[[], int],
    timings: TurnTimings,
    on_sign_in: Callable[[str, str], None] | None,
) -> AsyncIterator[TurnItem]:
    """D8's two turns, both handled here since both end the same way -- a
    fixed phrase spoken through the shared _speak() tail, no LLM, no gate.

    Turn 1 (awaiting_pin False, text asks to be remembered): speaks
    SIGNIN_ASK. main.py sets session.awaiting_pin=True for the NEXT turn by
    re-running parse_sign_in_request() on the same transcript AFTER this
    generator drains -- a second call to a pure function, not duplicated
    state, and it keeps this function from needing a third callback just to
    report "please flip a bool on the session."

    Turn 2 (awaiting_pin True): parse_spoken_pin() runs INSTEAD of the LLM.
    Success calls on_sign_in(name, pin) so main.py can resolve identity
    against the store (M3/M4/M13) after this generator drains, mirroring
    how last_transcript/last_reply are already captured and acted on
    post-hoc. Failure speaks SIGNIN_RETRY -- one retry only; main.py clears
    awaiting_pin whenever on_sign_in was NOT called on an awaiting_pin turn.
    """
    if awaiting_pin:
        parsed = parse_spoken_pin(text)
        if parsed is None:
            spoken = SIGNIN_RETRY
        else:
            name, pin = parsed
            if on_sign_in is not None:
                on_sign_in(name, pin)
            spoken = SIGNIN_OK.format(name=name, spoken=spoken_digits(pin))
    else:
        spoken = SIGNIN_ASK

    yield ReplyOut(turn_id=turn_id, text=spoken, seq=next_seq(), ts_ms=now_ms())
    async for item in _speak(spoken, turn_id, get_tts, failed, next_seq, now_ms, timings):
        yield item


async def _speak(
    text: str,
    turn_id: str,
    get_tts: Callable[[], TTS],
    failed: Callable[[TurnFailedStage, str], TurnFailedOut],
    next_seq: Callable[[], int],
    now_ms: Callable[[], int],
    timings: TurnTimings,
) -> AsyncIterator[TurnItem]:
    """The TTS tail shared by both the deterministic no_coverage refusal and
    the gated answer -- one implementation, so F11/F12's barge/failure
    semantics can't drift between the two callers."""
    try:
        tts = get_tts()
    except ProviderUnavailable:
        yield failed("tts", "I have an answer but couldn't speak it.")
        return
    timings.tts_model = tts.model

    audio = tts.synthesize(text, language=None)

    t_tts = time.monotonic()
    samples_sent = 0
    audio_started = False
    try:
        async for chunk in audio:
            if not audio_started:
                timings.tts_ttfb_ms = elapsed_ms(t_tts)
                yield AudioStartOut(
                    turn_id=turn_id, sample_rate=TTS_SAMPLE_RATE, seq=next_seq(), ts_ms=now_ms()
                )
                audio_started = True
            samples_sent += len(chunk) // 2  # PCM16 = 2 bytes/sample
            yield chunk
        timings.tts_total_ms = elapsed_ms(t_tts)
    except Exception:
        logger.exception("tts failed turn=%s (audio_started=%s)", turn_id, audio_started)
        if audio_started:
            yield AudioEndOut(turn_id=turn_id, samples=samples_sent, seq=next_seq(), ts_ms=now_ms())
            yield failed(
                "tts", "My voice cut out partway through — the answer above is still correct."
            )
        else:
            yield failed("tts", "I have an answer but couldn't speak it.")
        return

    if not audio_started:
        yield failed("tts", "I have an answer but couldn't speak it.")
        return

    yield AudioEndOut(turn_id=turn_id, samples=samples_sent, seq=next_seq(), ts_ms=now_ms())
