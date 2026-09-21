"""run_turn() against fakes -- every server-side failure path from Block 2's
table (F7-F12, F14) plus Block A's tool/gate wiring (V1-V9, D4-D6, D11-D12).
No network, no real provider.

This file proves the WIRING -- decide() -> tool.lookup() -> fact_card() ->
segments() -> gate() -> TTS, in that order, with the right message on the
right failure. It is not where every gate RULE is proven (tests/test_gate.py
owns G1-G13/Q-a-h exhaustively); a handful of representative segments are
enough here to prove the gate is actually being called with the right data.
"""

import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from app.pipeline.protocol import (
    AudioEndOut,
    AudioStartOut,
    FactCardOut,
    PlacesOut,
    ReplyOut,
    SegmentsOut,
    TranscriptOut,
    TurnFailedOut,
)
from app.pipeline.timings import TurnTimings
from app.pipeline.turn import MAX_TURN_BYTES, run_turn
from app.providers.base import LLM, STT, TTS, LLMDecision, ToolResult, VisaTool
from app.providers.factory import ProviderUnavailable
from app.tools.fake import FakeVisaTool, result_from_live_body

PCM = b"\x00\x01" * 100  # a small, well-under-the-cap "utterance"

TOOL_NAME = "get_visa_requirements"

_JUDGEMENT_TOKYO = '{"kind":"judgement","text":"Tokyo."}'


def _seq_counter() -> Callable[[], int]:
    n = 0

    def next_seq() -> int:
        nonlocal n
        n += 1
        return n

    return next_seq


def _now_ms() -> int:
    return 0


class FakeSTT:
    model = "fake-whisper"

    def __init__(self, text: str = "what's the capital of japan", *, raises: bool = False) -> None:
        self._text = text
        self._raises = raises
        self.last_language: str | None = None

    async def transcribe(self, pcm16: bytes, *, language: str | None = None) -> str:
        self.last_language = language
        if self._raises:
            raise TimeoutError("groq did not answer")
        return self._text


class FakeLLM:
    """`segment_batches` is a list of NDJSON-line lists, one per call() to
    segments() -- the SECOND entry is what a D11 repair retry sees. Past the
    end of the list, the last batch repeats."""

    model = "fake-gemini"
    thinking_level: str | None = "minimal"

    def __init__(
        self,
        *,
        tool_name: str | None = None,
        tool_arguments: dict[str, object] | None = None,
        decide_raises: bool = False,
        first_delta_ms: int | None = 5,
        segment_batches: list[list[str]] | None = None,
        segments_raises: bool = False,
    ) -> None:
        self._tool_name = tool_name
        self._tool_arguments = tool_arguments or {}
        self._decide_raises = decide_raises
        self._first_delta_ms = first_delta_ms
        default_batches = [[_JUDGEMENT_TOKYO]]
        self._segment_batches = segment_batches if segment_batches is not None else default_batches
        self._segments_raises = segments_raises
        self.segments_call_count = 0
        self.last_memory_block: str = ""
        self.last_user_block: str = ""

    async def decide(
        self,
        *,
        system: str,
        history: list[tuple[str, str]],
        user: str,
        tools: list[object],
        memory_block: str = "",
    ) -> LLMDecision:
        self.last_memory_block = memory_block
        if self._decide_raises:
            raise RuntimeError("gemini did not answer")
        return LLMDecision(
            tool_name=self._tool_name,
            tool_arguments=self._tool_arguments,
            text="",
            first_delta_ms=self._first_delta_ms,
        )

    async def segments(self, *, system: str, user_block: str) -> AsyncIterator[str]:
        self.last_user_block = user_block
        if self._segments_raises:
            raise RuntimeError("gemini segments failed")
        idx = min(self.segments_call_count, len(self._segment_batches) - 1)
        self.segments_call_count += 1
        for line in self._segment_batches[idx]:
            yield line


class FakeTTS:
    model = "fake-aura"

    def __init__(self, chunks: list[bytes] | None = None, *, fail_after: int | None = None) -> None:
        # fail_after=0 fails before any chunk is yielded (F11).
        # fail_after=N (N>0) yields N chunks then fails (F12).
        self._chunks = chunks if chunks is not None else [b"\x01\x02" * 10, b"\x03\x04" * 10]
        self._fail_after = fail_after
        self.last_language: str | None = None
        self.last_text: str | None = None

    async def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        self.last_language = language
        self.last_text = text
        for i, chunk in enumerate(self._chunks):
            if self._fail_after is not None and i >= self._fail_after:
                raise ConnectionError("deepgram socket dropped")
            yield chunk


def _empty_timings() -> TurnTimings:
    return TurnTimings(turn_id="t-1", session="abcd1234", connection_n=1, turn_index=1, env="local")


_SA_JP_BODY_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "reference" / "visa_reqs_SA_JP.json"
)


def _sa_jp_result() -> ToolResult:
    """A real committed body, normalised -- the same fixture the eval and
    the deployed app's warm cache would hold for this pair."""
    body = json.loads(_SA_JP_BODY_PATH.read_text())
    return result_from_live_body(body, retrieved="2026-09-20T09:00:00Z", layer="live")


async def _run(
    *,
    pcm16: bytes = PCM,
    get_stt: Callable[[], STT],
    get_llm: Callable[[], LLM],
    get_tts: Callable[[], TTS],
    get_tool: Callable[[], VisaTool] = lambda: FakeVisaTool(),
    gate_demo: bool = False,
    memory_block: str = "",
    awaiting_pin: bool = False,
    on_sign_in: Callable[[str, str], None] = lambda name, pin: None,
    get_places: Callable[[], object] | None = None,
    history: list[tuple[str, str]] | None = None,
    lang: str = "en",
) -> tuple[list[object], TurnTimings]:
    timings = _empty_timings()
    items: list[object] = []
    async for item in run_turn(
        turn_id="t-1",
        pcm16=pcm16,
        history=history or [],
        next_seq=_seq_counter(),
        now_ms=_now_ms,
        get_stt=get_stt,
        get_llm=get_llm,
        get_tts=get_tts,
        get_tool=get_tool,
        timings=timings,
        gate_demo=gate_demo,
        memory_block=memory_block,
        awaiting_pin=awaiting_pin,
        on_sign_in=on_sign_in,
        get_places=get_places,
        lang=lang,
    ):
        items.append(item)
    return items, timings


def _kinds(items: list[object]) -> list[str]:
    return [type(i).__name__ if not isinstance(i, bytes) else "bytes" for i in items]


# ---------------------------------------------------------------------------
# Happy path, no tool -- a pure judgement question.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_no_tool_yields_transcript_segments_reply_audio() -> None:
    items, timings = await _run(get_stt=FakeSTT, get_llm=FakeLLM, get_tts=FakeTTS)

    assert _kinds(items) == [
        "TranscriptOut",
        "SegmentsOut",
        "ReplyOut",
        "AudioStartOut",
        "bytes",
        "bytes",
        "AudioEndOut",
    ]
    transcript, segments, reply, audio_start, chunk1, chunk2, audio_end = items
    assert isinstance(transcript, TranscriptOut)
    assert transcript.text == "what's the capital of japan"
    assert isinstance(segments, SegmentsOut)
    assert segments.spoken == "Tokyo."
    assert segments.hedged is False
    assert len(segments.segments) == 1
    assert segments.segments[0].kind == "judgement"
    assert segments.segments[0].ok is True
    assert isinstance(reply, ReplyOut)
    assert reply.text == "Tokyo."
    assert isinstance(audio_start, AudioStartOut)
    assert audio_start.sample_rate == 24_000
    assert isinstance(audio_end, AudioEndOut)
    assert audio_end.samples == (len(chunk1) + len(chunk2)) // 2  # type: ignore[arg-type]

    for leg in (
        timings.stt_ms,
        timings.llm_ms,
        timings.llm_ttft_ms,
        timings.llm2_ms,
        timings.gate_ms,
        timings.tts_ttfb_ms,
        timings.tts_total_ms,
    ):
        assert leg is not None
        assert leg >= 0
    assert timings.tool_ms is None  # no tool called
    assert timings.tool_layer is None
    assert timings.segments_ok == 1
    assert timings.segments_rejected == 0
    assert timings.lines_malformed == 0
    assert timings.hedged is False


# ---------------------------------------------------------------------------
# F7-F9 -- audio/STT failures, unchanged in shape from Block 2.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_f7_oversized_audio_fails_before_any_provider_is_touched() -> None:
    too_big = b"\x00" * (MAX_TURN_BYTES + 2)
    items, _timings = await _run(pcm16=too_big, get_stt=FakeSTT, get_llm=FakeLLM, get_tts=FakeTTS)

    assert len(items) == 1
    assert isinstance(items[0], TurnFailedOut)
    assert items[0].stage == "audio"


@pytest.mark.asyncio
async def test_f8_empty_transcript_skips_llm_and_tts() -> None:
    items, _timings = await _run(
        get_stt=lambda: FakeSTT(text="   "), get_llm=FakeLLM, get_tts=FakeTTS
    )

    assert len(items) == 1
    assert isinstance(items[0], TurnFailedOut)
    assert items[0].stage == "stt"
    assert "say it again" in items[0].message


@pytest.mark.asyncio
async def test_f9_stt_raises() -> None:
    items, timings = await _run(
        get_stt=lambda: FakeSTT(raises=True), get_llm=FakeLLM, get_tts=FakeTTS
    )

    assert len(items) == 1
    assert isinstance(items[0], TurnFailedOut)
    assert items[0].stage == "stt"
    assert "didn't answer" in items[0].message
    assert timings.stt_model == "fake-whisper"  # attempted -- get_stt() succeeded
    assert timings.stt_ms is None  # never completed -- the raise happened first
    assert timings.llm_model is None  # LLM was never reached


# ---------------------------------------------------------------------------
# Call 1 (decide) failures.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_raises_stage_llm() -> None:
    items, _timings = await _run(
        get_stt=FakeSTT, get_llm=lambda: FakeLLM(decide_raises=True), get_tts=FakeTTS
    )

    assert isinstance(items[0], TranscriptOut)  # STT already succeeded and was shown
    assert isinstance(items[1], TurnFailedOut)
    assert items[1].stage == "llm"


@pytest.mark.asyncio
async def test_f14_stt_not_configured() -> None:
    def _get_stt() -> STT:
        raise ProviderUnavailable("GROQ_API_KEY is not set")

    items, _timings = await _run(get_stt=_get_stt, get_llm=FakeLLM, get_tts=FakeTTS)

    assert len(items) == 1
    assert isinstance(items[0], TurnFailedOut)
    assert items[0].stage == "stt"
    assert "not configured" in items[0].message


@pytest.mark.asyncio
async def test_f14_llm_not_configured_after_stt_succeeded() -> None:
    def _get_llm() -> LLM:
        raise ProviderUnavailable("GEMINI_API_KEY is not set")

    items, _timings = await _run(get_stt=FakeSTT, get_llm=_get_llm, get_tts=FakeTTS)

    assert isinstance(items[0], TranscriptOut)
    assert isinstance(items[1], TurnFailedOut)
    assert items[1].stage == "llm"
    assert "not configured" in items[1].message


# ---------------------------------------------------------------------------
# V-series -- the tool.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v_tool_success_sourced_segment_and_fact_card() -> None:
    tool = FakeVisaTool()
    tool.add("SA", "JP", _sa_jp_result())
    llm = FakeLLM(
        tool_name=TOOL_NAME,
        tool_arguments={"passport": "SA", "destination": "JP"},
        segment_batches=[
            [
                json.dumps(
                    {
                        "kind": "sourced",
                        "text": "You'll need {visa.type} for up to {visa.duration}.",
                        "tool_call_id": "tb_1",
                        "fields": ["visa.type", "visa.duration"],
                    }
                )
            ]
        ],
    )
    items, timings = await _run(
        get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, get_tool=lambda: tool
    )

    kinds = _kinds(items)
    assert kinds[:3] == ["TranscriptOut", "FactCardOut", "SegmentsOut"]
    card = items[1]
    assert isinstance(card, FactCardOut)
    assert card.covered is True
    assert card.passport == "SA"
    assert card.destination == "JP"
    assert card.layer == "live"

    segments = items[2]
    assert isinstance(segments, SegmentsOut)
    assert segments.segments[0].ok is True
    assert "eVisa" in segments.spoken
    assert "90 days" in segments.spoken
    # D15 -- the card and the spoken answer read from the SAME substitution.
    duration_row = next(f for f in card.facts if f.path == "visa.duration")
    assert duration_row.value in segments.spoken

    assert timings.tool_layer == "live"
    assert timings.segments_ok == 1


@pytest.mark.asyncio
async def test_v3_v6_no_coverage_skips_call_2_and_speaks_no_coverage() -> None:
    """V3/V6 -- every layer exhausted. Deterministic refusal, and call 2 is
    never invoked at all (there's nothing to source an answer from)."""
    tool = FakeVisaTool()  # no fixtures -> every lookup() is no_coverage
    llm = FakeLLM(tool_name=TOOL_NAME, tool_arguments={"passport": "SA", "destination": "XX"})

    items, timings = await _run(
        get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, get_tool=lambda: tool
    )

    segments = next(i for i in items if isinstance(i, SegmentsOut))
    assert segments.segments == []
    assert "won't guess" in segments.spoken
    assert llm.segments_call_count == 0  # call 2 never ran
    assert timings.hedged is False


@pytest.mark.asyncio
async def test_v8_unknown_place_from_vendor_fails_stage_tool() -> None:
    tool = FakeVisaTool(force_reason="unknown_place")
    llm = FakeLLM(tool_name=TOOL_NAME, tool_arguments={"passport": "SA", "destination": "Narnia"})

    items, _timings = await _run(
        get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, get_tool=lambda: tool
    )

    failed = next(i for i in items if isinstance(i, TurnFailedOut))
    assert failed.stage == "tool"
    assert "didn't catch" in failed.message
    assert not any(isinstance(i, FactCardOut) for i in items)  # nothing to card


@pytest.mark.asyncio
async def test_v8_empty_tool_arguments_fails_stage_tool_without_calling_lookup() -> None:
    """The model called the tool but with nothing to look up -- caught
    before tool.lookup() is even reached."""

    class _RaisingTool:
        name = "fake"

        async def lookup(self, *, passport: str, destination: str) -> ToolResult:
            raise AssertionError("lookup() must not be reached with empty arguments")

        def quota(self) -> object:
            raise AssertionError

    llm = FakeLLM(tool_name=TOOL_NAME, tool_arguments={"passport": "", "destination": "JP"})
    items, _timings = await _run(
        get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, get_tool=lambda: _RaisingTool()
    )

    failed = next(i for i in items if isinstance(i, TurnFailedOut))
    assert failed.stage == "tool"


@pytest.mark.asyncio
async def test_tool_lookup_raises_fails_stage_tool() -> None:
    class _RaisingTool:
        name = "fake"

        async def lookup(self, *, passport: str, destination: str) -> ToolResult:
            raise RuntimeError("rapidapi did not answer")

        def quota(self) -> object:
            raise AssertionError

    llm = FakeLLM(tool_name=TOOL_NAME, tool_arguments={"passport": "SA", "destination": "JP"})
    items, _timings = await _run(
        get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, get_tool=lambda: _RaisingTool()
    )

    failed = next(i for i in items if isinstance(i, TurnFailedOut))
    assert failed.stage == "tool"
    assert "didn't answer" in failed.message


@pytest.mark.asyncio
async def test_tool_not_configured() -> None:
    def _get_tool() -> VisaTool:
        raise ProviderUnavailable("RAPIDAPI_KEY is not set")

    llm = FakeLLM(tool_name=TOOL_NAME, tool_arguments={"passport": "SA", "destination": "JP"})
    items, _timings = await _run(
        get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, get_tool=_get_tool
    )

    failed = next(i for i in items if isinstance(i, TurnFailedOut))
    assert failed.stage == "tool"
    assert "isn't configured" in failed.message


@pytest.mark.asyncio
async def test_unrecognised_tool_name_falls_through_to_call_2() -> None:
    """decide() hallucinated a tool name -- treated as no tool; call 2 still
    runs (D6), and any sourced segment it emits will reject on
    unknown_tool_call_id (proven at the gate level, not re-proven here)."""
    llm = FakeLLM(tool_name="not_a_real_tool", tool_arguments={})
    items, _timings = await _run(get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS)

    assert llm.segments_call_count == 1
    segments = next(i for i in items if isinstance(i, SegmentsOut))
    assert segments.spoken == "Tokyo."


# ---------------------------------------------------------------------------
# Gate wiring: D6 (unknown_tool_call_id when no tool ran), D4 (hedged),
# D11 (repair retry), D12 (?gate_demo=1).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_d6_sourced_segment_with_no_tool_run_rejects_and_refuses() -> None:
    """"A factual question with no tool behind it -> refuse" is mechanical,
    not prompted: call 2 still runs (D6), but the ONLY segment it produced
    names a tool_call_id nothing stored this turn, so it rejects and the
    turn ends in REFUSAL."""
    llm = FakeLLM(
        tool_name=None,
        segment_batches=[
            [
                json.dumps(
                    {
                        "kind": "sourced",
                        "text": "You'll need {visa.type}.",
                        "tool_call_id": "tb_1",
                        "fields": ["visa.type"],
                    }
                )
            ]
        ],
    )
    items, timings = await _run(get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS)

    segments = next(i for i in items if isinstance(i, SegmentsOut))
    assert segments.segments[0].ok is False
    assert segments.segments[0].reason == "unknown_tool_call_id"
    assert "rather not guess" in segments.spoken
    assert timings.segments_rejected == 1


@pytest.mark.asyncio
async def test_d4_hedged_when_tool_succeeded_but_only_judgement_came_back() -> None:
    tool = FakeVisaTool()
    tool.add("SA", "JP", _sa_jp_result())
    llm = FakeLLM(
        tool_name=TOOL_NAME,
        tool_arguments={"passport": "SA", "destination": "JP"},
        segment_batches=[[_JUDGEMENT_TOKYO]],
    )
    items, timings = await _run(
        get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, get_tool=lambda: tool
    )

    segments = next(i for i in items if isinstance(i, SegmentsOut))
    assert segments.hedged is True
    assert timings.hedged is True


@pytest.mark.asyncio
async def test_f7_hedged_reflects_what_the_model_produced_not_what_the_gate_kept() -> None:
    """F7 -- a model that DID attempt a sourced claim, which the gate then
    rejected, is a caught fabrication, not a hedge: `hedged` must be False.
    Before the fix this was True, because it was computed from `rendered`
    filtered on `.ok`, so a rejected sourced/quoted segment was invisible
    to it -- the exact opposite of what actually happened on this turn."""
    tool = FakeVisaTool()
    tool.add("SA", "JP", _sa_jp_result())
    llm = FakeLLM(
        tool_name=TOOL_NAME,
        tool_arguments={"passport": "SA", "destination": "JP"},
        # No placeholder at all -- rejects on `no_placeholder`, D12's own
        # fabricated-segment example, but produced by the "model" here.
        segment_batches=[
            ['{"kind":"sourced","text":"You can stay for 90 days.","tool_call_id":"tb_1"}']
        ],
    )
    items, timings = await _run(
        get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, get_tool=lambda: tool
    )

    segments = next(i for i in items if isinstance(i, SegmentsOut))
    assert segments.segments[0].kind == "sourced"
    assert segments.segments[0].ok is False
    assert segments.hedged is False
    assert timings.hedged is False


@pytest.mark.asyncio
async def test_d11_repair_retry_fires_only_when_zero_segments_survived() -> None:
    llm = FakeLLM(
        tool_name=None,
        segment_batches=[["not-json-at-all"], [_JUDGEMENT_TOKYO]],
    )
    items, timings = await _run(get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS)

    assert llm.segments_call_count == 2  # the repair retry actually fired
    segments = next(i for i in items if isinstance(i, SegmentsOut))
    assert segments.spoken == "Tokyo."
    # F7 -- lines_malformed describes ONLY the surviving attempt (the
    # retry), never the discarded first attempt's malformed line added on
    # top of it. The retry itself parsed cleanly, so this is 0, not 1 --
    # summing both would inflate measure.py's rate against a denominator
    # (segments_ok/segments_rejected) that only ever reflects the retry.
    assert timings.lines_malformed == 0


@pytest.mark.asyncio
async def test_g12_segments_raises_fails_stage_gate() -> None:
    llm = FakeLLM(tool_name=None, segments_raises=True)
    items, _timings = await _run(get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS)

    failed = next(i for i in items if isinstance(i, TurnFailedOut))
    assert failed.stage == "gate"
    assert "ask me again" in failed.message


@pytest.mark.asyncio
async def test_d12_gate_demo_injects_a_rejected_segment_into_a_real_turn() -> None:
    tool = FakeVisaTool()
    tool.add("SA", "JP", _sa_jp_result())
    llm = FakeLLM(
        tool_name=TOOL_NAME,
        tool_arguments={"passport": "SA", "destination": "JP"},
        segment_batches=[[_JUDGEMENT_TOKYO]],
    )
    items, _timings = await _run(
        get_stt=FakeSTT,
        get_llm=lambda: llm,
        get_tts=FakeTTS,
        get_tool=lambda: tool,
        gate_demo=True,
    )

    segments = next(i for i in items if isinstance(i, SegmentsOut))
    rejected = [s for s in segments.segments if not s.ok]
    assert len(rejected) == 1
    assert rejected[0].reason == "no_placeholder"
    assert "90 days" not in segments.spoken


# ---------------------------------------------------------------------------
# F11/F12 -- TTS failures, now driven off `spoken` rather than a raw reply.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_f11_tts_fails_before_first_chunk_reply_already_sent() -> None:
    items, _timings = await _run(
        get_stt=FakeSTT, get_llm=FakeLLM, get_tts=lambda: FakeTTS(fail_after=0)
    )

    kinds = _kinds(items)
    assert kinds == ["TranscriptOut", "SegmentsOut", "ReplyOut", "TurnFailedOut"]
    assert items[-1].stage == "tts"  # type: ignore[union-attr]
    assert "couldn't speak it" in items[-1].message  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_f12_tts_fails_mid_stream_sends_audio_end_before_failing() -> None:
    items, _timings = await _run(
        get_stt=FakeSTT, get_llm=FakeLLM, get_tts=lambda: FakeTTS(fail_after=1)
    )

    kinds = _kinds(items)
    assert kinds == [
        "TranscriptOut",
        "SegmentsOut",
        "ReplyOut",
        "AudioStartOut",
        "bytes",
        "AudioEndOut",
        "TurnFailedOut",
    ]
    audio_end = items[-2]
    assert isinstance(audio_end, AudioEndOut)
    assert audio_end.samples == 10  # one 20-byte chunk = 10 PCM16 samples


@pytest.mark.asyncio
async def test_f14_tts_not_configured_reply_still_shown() -> None:
    def _get_tts() -> TTS:
        raise ProviderUnavailable("DEEPGRAM_API_KEY is not set")

    items, _timings = await _run(get_stt=FakeSTT, get_llm=FakeLLM, get_tts=_get_tts)

    kinds = _kinds(items)
    assert kinds == ["TranscriptOut", "SegmentsOut", "ReplyOut", "TurnFailedOut"]
    assert items[-1].stage == "tts"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# D7 -- the single most important thing in Block B's plan: the memory block
# must reach BOTH LLM calls. Call 1's own text is never spoken (it either
# asks for the tool or is discarded), so a memory-only question like "what's
# my favourite colour?" can ONLY be answered by call 2 -- put the block in
# call 1 alone and the passport is never auto-filled; put it in call 2 alone
# and the favourite-colour question can't be answered at all.
# ---------------------------------------------------------------------------

MEMORY_BLOCK = "<known_about_user>\nFavourite colour: green\n</known_about_user>"


@pytest.mark.asyncio
async def test_d7_memory_block_reaches_call_1_with_no_tool_involved() -> None:
    llm = FakeLLM(tool_name=None)
    await _run(get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, memory_block=MEMORY_BLOCK)

    assert llm.last_memory_block == MEMORY_BLOCK


@pytest.mark.asyncio
async def test_d7_memory_block_reaches_call_2_the_only_call_whose_text_is_ever_spoken() -> None:
    llm = FakeLLM(tool_name=None)
    await _run(get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, memory_block=MEMORY_BLOCK)

    assert MEMORY_BLOCK in llm.last_user_block


@pytest.mark.asyncio
async def test_d7_memory_block_reaches_both_calls_even_when_a_tool_ran() -> None:
    tool = FakeVisaTool()
    tool.add("SA", "JP", _sa_jp_result())
    llm = FakeLLM(tool_name=TOOL_NAME, tool_arguments={"passport": "SA", "destination": "JP"})

    await _run(
        get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS, get_tool=lambda: tool,
        memory_block=MEMORY_BLOCK,
    )

    assert llm.last_memory_block == MEMORY_BLOCK  # call 1 -- could have filled the passport from it
    assert MEMORY_BLOCK in llm.last_user_block  # call 2 -- still gets it too


@pytest.mark.asyncio
async def test_call_2_sees_prior_turns_as_conversation_data() -> None:
    """The live-run bug: call 1 had history, call 2 did not, so 'suggest
    cities' after a Germany visa turn recommended Cairo (home_city=Egypt)."""
    llm = FakeLLM(tool_name=None)
    await _run(
        get_stt=lambda: FakeSTT(text="suggest cities"),
        get_llm=lambda: llm,
        get_tts=FakeTTS,
        history=[
            (
                "I'm planning a trip to Germany from Egypt, visa status?",
                "Holders of Egypt passports: visa required.",
            )
        ],
    )
    assert "<conversation>" in llm.last_user_block
    assert "Germany" in llm.last_user_block
    assert "<user_question>\nsuggest cities\n</user_question>" in llm.last_user_block


@pytest.mark.asyncio
async def test_no_memory_block_is_the_default_and_costs_nothing() -> None:
    """The plan's default: memory_block="" when the caller has nothing to
    say. build_user_block() must not insert an empty leading block."""
    llm = FakeLLM(tool_name=None)
    await _run(get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS)

    assert llm.last_memory_block == ""
    assert "<known_about_user>" not in llm.last_user_block


# ---------------------------------------------------------------------------
# D8 -- voice sign-in, a deterministic sub-flow. No model involved: FakeLLM
# would raise AssertionError-shaped confusion if it were ever reached here,
# so `llm.segments_call_count == 0` is the actual proof "no LLM call was
# made," not just an assertion about what got spoken.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_d8_sign_in_request_speaks_the_ask_phrase_with_no_llm_call() -> None:
    llm = FakeLLM(tool_name=None)
    items, _timings = await _run(
        get_stt=lambda: FakeSTT(text="remember me please"), get_llm=lambda: llm, get_tts=FakeTTS
    )

    assert llm.segments_call_count == 0
    reply = next(i for i in items if isinstance(i, ReplyOut))
    assert "tell me a name" in reply.text
    assert "four seven one two" in reply.text  # SIGNIN_ASK's own example


@pytest.mark.asyncio
async def test_d8_awaiting_pin_parses_a_valid_pin_and_calls_on_sign_in() -> None:
    llm = FakeLLM(tool_name=None)
    seen: list[tuple[str, str]] = []
    items, _timings = await _run(
        get_stt=lambda: FakeSTT(text="Omar four seven one two"),
        get_llm=lambda: llm,
        get_tts=FakeTTS,
        awaiting_pin=True,
        on_sign_in=lambda name, pin: seen.append((name, pin)),
    )

    assert llm.segments_call_count == 0
    assert seen == [("Omar", "4712")]
    reply = next(i for i in items if isinstance(i, ReplyOut))
    assert "Omar" in reply.text
    assert "four seven one two" in reply.text


@pytest.mark.asyncio
async def test_m11_awaiting_pin_with_no_pin_heard_speaks_retry_and_skips_on_sign_in() -> None:
    llm = FakeLLM(tool_name=None)
    seen: list[tuple[str, str]] = []
    items, _timings = await _run(
        get_stt=lambda: FakeSTT(text="sorry I don't remember it"),
        get_llm=lambda: llm,
        get_tts=FakeTTS,
        awaiting_pin=True,
        on_sign_in=lambda name, pin: seen.append((name, pin)),
    )

    assert llm.segments_call_count == 0
    assert seen == []  # on_sign_in never fired -- main.py clears awaiting_pin on this
    reply = next(i for i in items if isinstance(i, ReplyOut))
    assert "didn't catch" in reply.text


class FakePlaces:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def lookup_many(self, names: list[str]) -> list[object]:
        self.calls.append(names)
        from app.tools.places import PlaceCard

        return [
            PlaceCard(
                name=n,
                title=n,
                description=f"{n} is a place.",
                image_url=f"https://upload.wikimedia.org/wikipedia/commons/{n}.jpg",
                page_url=f"https://en.wikipedia.org/wiki/{n}",
                revision_date="2026-09-14T15:53:35Z",
                ok=True,
                reason=None,
            )
            for n in names
        ]


@pytest.mark.asyncio
async def test_places_yielded_after_audio_start_never_before() -> None:
    """Judgement `place` keys become a PlacesOut AFTER AudioStartOut --
    Wikimedia must not sit on the first-audio path."""
    llm = FakeLLM(
        segment_batches=[[
            '{"kind":"judgement","text":"Walk Gion at dusk.","place":"Kyoto"}'
        ]]
    )
    fake = FakePlaces()
    items, _timings = await _run(
        get_stt=FakeSTT,
        get_llm=lambda: llm,
        get_tts=FakeTTS,
        get_places=lambda: fake,
    )
    kinds = _kinds(items)
    assert "PlacesOut" in kinds
    assert kinds.index("AudioStartOut") < kinds.index("PlacesOut")
    places = next(i for i in items if isinstance(i, PlacesOut))
    assert places.places[0].name == "Kyoto"
    assert places.places[0].ok is True
    assert fake.calls == [["Kyoto"]]


@pytest.mark.asyncio
async def test_places_skipped_when_get_places_is_none() -> None:
    llm = FakeLLM(
        segment_batches=[[
            '{"kind":"judgement","text":"Walk Gion at dusk.","place":"Kyoto"}'
        ]]
    )
    items, _timings = await _run(get_stt=FakeSTT, get_llm=lambda: llm, get_tts=FakeTTS)
    assert "PlacesOut" not in _kinds(items)


@pytest.mark.asyncio
async def test_lang_is_handed_to_stt_and_recorded_on_timings() -> None:
    stt = FakeSTT()
    items, timings = await _run(
        get_stt=lambda: stt, get_llm=FakeLLM, get_tts=FakeTTS, lang="ar"
    )
    assert stt.last_language == "ar"
    assert timings.lang == "ar"
    assert "TranscriptOut" in _kinds(items)


@pytest.mark.asyncio
async def test_sign_in_fixed_phrase_stays_on_english_tts_during_arabic_turn() -> None:
    tts = FakeTTS()
    await _run(
        get_stt=lambda: FakeSTT("remember me please"),
        get_llm=FakeLLM,
        get_tts=lambda: tts,
        lang="ar",
    )
    assert tts.last_language == "en"


@pytest.mark.asyncio
async def test_gated_answer_tts_uses_the_turn_lang() -> None:
    tts = FakeTTS()
    await _run(get_stt=FakeSTT, get_llm=FakeLLM, get_tts=lambda: tts, lang="ar")
    assert tts.last_language == "ar"

