"""GeminiLLM's decide()/segments() against recorded event sequences.

Event shapes below are copied from the VERIFIED live capture
(scratch/spikes/out/s4-dryrun.json, scratch/spikes/parallel_fc.py,
day1-spikes.md S4) rather than the docs page -- this is the file that would
have caught the `arguments_delta` vs `arguments` trap before a real call
ever ran. Fake events are plain SimpleNamespace objects: gemini_llm.py only
ever reads `.event_type`, `.step.type`/`.name`, `.delta.type`/`.text`/
`.arguments` off whatever the SDK hands it (the `cast(...)` in the adapter
is a type-checker annotation, not a runtime isinstance check), so nothing
here needs the real SDK's event classes.
"""

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from app.providers import gemini_llm
from app.providers.gemini_llm import GeminiLLM


def _step_start(step_type: str, *, name: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(event_type="step.start", step=SimpleNamespace(type=step_type, name=name))


def _delta(delta_type: str, **kwargs: Any) -> SimpleNamespace:
    delta = SimpleNamespace(type=delta_type, **kwargs)
    return SimpleNamespace(event_type="step.delta", delta=delta)


async def _as_stream(events: list[SimpleNamespace]) -> AsyncIterator[SimpleNamespace]:
    for e in events:
        yield e


class _FakeInteractions:
    def __init__(self, events: list[SimpleNamespace]) -> None:
        self._events = events
        self.received_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> AsyncIterator[SimpleNamespace]:
        self.received_kwargs = kwargs
        return _as_stream(self._events)


def _llm_with_events(events: list[SimpleNamespace]) -> tuple[GeminiLLM, _FakeInteractions]:
    llm = GeminiLLM.__new__(GeminiLLM)  # skip __init__: no real API key needed
    interactions = _FakeInteractions(events)
    llm._client = SimpleNamespace(aio=SimpleNamespace(interactions=interactions))  # type: ignore[attr-defined]
    return llm, interactions


# ---------------------------------------------------------------------------
# decide()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_parses_a_function_call_split_across_deltas() -> None:
    """The exact verified shape: `step.start` carries the NAME before any
    arguments delta, and `arguments_delta` (never `arguments`) carries the
    partial JSON string, split across two deltas here on purpose."""
    events = [
        _step_start("thought"),
        _delta("thought_signature"),
        _step_start("function_call", name="get_visa_requirements"),
        _delta("arguments_delta", arguments='{"passport":"SA",'),
        _delta("arguments_delta", arguments='"destination":"JP"}'),
    ]
    llm, interactions = _llm_with_events(events)

    decision = await llm.decide(
        system="sys", history=[], user="visa for japan", tools=[{"name": "x"}]
    )

    assert decision.tool_name == "get_visa_requirements"
    assert decision.tool_arguments == {"passport": "SA", "destination": "JP"}
    assert decision.text == ""
    assert decision.first_delta_ms is not None
    assert interactions.received_kwargs["tools"] == [{"name": "x"}]


@pytest.mark.asyncio
async def test_decide_returns_plain_text_when_no_tool_is_called() -> None:
    events = [
        _step_start("thought"),
        _delta("thought_signature"),
        _delta("text", text="November is "),
        _delta("text", text="a good time to visit."),
    ]
    llm, _interactions = _llm_with_events(events)

    decision = await llm.decide(system="sys", history=[], user="when should I go?", tools=[])

    assert decision.tool_name is None
    assert decision.tool_arguments == {}
    assert decision.text == "November is a good time to visit."


@pytest.mark.asyncio
async def test_decide_ignores_the_leading_thought_step_for_first_delta_ms() -> None:
    """day1-spikes.md S4: a `thought` step always arrives first, even at
    thinking_level="minimal". Timing to it would record a fiction."""
    events = [
        _step_start("thought"),
        _delta("thought_signature"),
        _delta("text", text="Tokyo."),
    ]
    llm, _interactions = _llm_with_events(events)

    decision = await llm.decide(system="sys", history=[], user="hi", tools=[])

    # The only timed delta is the text one -- proven indirectly: text landed
    # and first_delta_ms is set (there's no earlier timestamp available to
    # assert against without mocking time.monotonic, so this asserts the
    # OUTCOME the ordering produces rather than the clock itself).
    assert decision.text == "Tokyo."
    assert decision.first_delta_ms is not None


@pytest.mark.asyncio
async def test_decide_unparseable_arguments_falls_back_to_no_tool() -> None:
    events = [
        _step_start("function_call", name="get_visa_requirements"),
        _delta("arguments_delta", arguments="{not valid json"),
    ]
    llm, _interactions = _llm_with_events(events)

    decision = await llm.decide(system="sys", history=[], user="visa for japan", tools=[])

    assert decision.tool_name is None
    assert decision.tool_arguments == {}


@pytest.mark.asyncio
async def test_decide_times_out_instead_of_hanging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_llm, "LLM_TIMEOUT_S", 0.05)

    class _HangingInteractions:
        async def create(self, **kwargs: Any) -> Any:
            await asyncio.sleep(10)
            raise AssertionError("unreachable -- the timeout must fire first")

    llm = GeminiLLM.__new__(GeminiLLM)
    llm._client = SimpleNamespace(aio=SimpleNamespace(interactions=_HangingInteractions()))  # type: ignore[attr-defined]

    with pytest.raises(TimeoutError):
        await llm.decide(system="sys", history=[], user="hello", tools=[])


# ---------------------------------------------------------------------------
# segments()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_segments_yields_one_line_per_newline_never_a_partial_line() -> None:
    """A JSON object split across three text deltas, with the newline
    landing in the MIDDLE delta -- proves the buffer only ever releases a
    complete line, exactly as task 8's own check demands."""
    events = [
        _delta("text", text='{"kind":"jud'),
        _delta("text", text='gement","text":"Hi"}\n{"ki'),
        _delta("text", text='nd":"judgement","text":"Bye"}'),
    ]
    llm, _interactions = _llm_with_events(events)

    block = "<user_question>hi</user_question>"
    lines = [line async for line in llm.segments(system="sys", user_block=block)]

    assert lines == [
        '{"kind":"judgement","text":"Hi"}',
        '{"kind":"judgement","text":"Bye"}',
    ]


@pytest.mark.asyncio
async def test_segments_ignores_non_text_deltas() -> None:
    events = [
        _step_start("thought"),
        _delta("thought_signature"),
        _delta("text", text='{"kind":"judgement","text":"ok"}\n'),
    ]
    llm, _interactions = _llm_with_events(events)

    lines = [line async for line in llm.segments(system="sys", user_block="x")]

    assert lines == ['{"kind":"judgement","text":"ok"}']


@pytest.mark.asyncio
async def test_segments_never_replays_history_its_input_is_the_user_block_alone() -> None:
    """D5 -- a fresh, stateless interaction. segments() takes no `history`
    parameter at all; this proves the exact string handed to `input` is
    `user_block`, unmodified."""
    events = [_delta("text", text='{"kind":"judgement","text":"ok"}\n')]
    llm, interactions = _llm_with_events(events)

    block = "<user_question>hi</user_question>\n\n<tool_result>NONE</tool_result>"
    async for _line in llm.segments(system="sys", user_block=block):
        pass

    assert interactions.received_kwargs["input"] == block
    assert "history" not in interactions.received_kwargs
