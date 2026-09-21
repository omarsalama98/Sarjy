"""GroqLLM decide()/segments() against fake streamed Chat Completions chunks."""

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from app.providers import groq_llm
from app.providers.groq_llm import GroqLLM, _to_openai_tool


def _chunk(
    *,
    content: str | None = None,
    tool_name: str | None = None,
    tool_args: str | None = None,
) -> SimpleNamespace:
    tool_calls = None
    if tool_name is not None or tool_args is not None:
        tool_calls = [
            SimpleNamespace(
                function=SimpleNamespace(name=tool_name, arguments=tool_args or "")
            )
        ]
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


async def _as_stream(chunks: list[SimpleNamespace]) -> AsyncIterator[SimpleNamespace]:
    for c in chunks:
        yield c


class _FakeCompletions:
    def __init__(
        self,
        chunks: list[SimpleNamespace] | None = None,
        *,
        by_model: dict[str, list[SimpleNamespace] | Exception] | None = None,
    ) -> None:
        self._chunks = chunks or []
        self._by_model = by_model or {}
        self.received_kwargs: dict[str, Any] = {}
        self.models_seen: list[str] = []

    async def create(self, **kwargs: Any) -> AsyncIterator[SimpleNamespace]:
        self.received_kwargs = kwargs
        model = str(kwargs.get("model") or "")
        self.models_seen.append(model)
        if model in self._by_model:
            payload = self._by_model[model]
            if isinstance(payload, Exception):
                raise payload
            return _as_stream(payload)
        return _as_stream(self._chunks)


def _llm_with_chunks(
    chunks: list[SimpleNamespace],
    *,
    models: list[str] | None = None,
    by_model: dict[str, list[SimpleNamespace] | Exception] | None = None,
) -> tuple[GroqLLM, _FakeCompletions]:
    llm = GroqLLM.__new__(GroqLLM)
    chain = models or ["openai/gpt-oss-20b"]
    llm._models = chain  # type: ignore[attr-defined]
    llm._model_idx = 0  # type: ignore[attr-defined]
    llm.model = chain[0]
    llm.thinking_level = None
    completions = _FakeCompletions(chunks, by_model=by_model)
    llm._client = SimpleNamespace(  # type: ignore[attr-defined]
        chat=SimpleNamespace(completions=completions)
    )
    return llm, completions


def test_to_openai_tool_nests_visa_tool_shape() -> None:
    flat = {
        "type": "function",
        "name": "get_visa_requirements",
        "description": "look up",
        "parameters": {"type": "object", "properties": {}},
    }
    nested = _to_openai_tool(flat)
    assert nested["type"] == "function"
    assert nested["function"]["name"] == "get_visa_requirements"
    assert nested["function"]["description"] == "look up"


@pytest.mark.asyncio
async def test_decide_parses_streamed_tool_call() -> None:
    chunks = [
        _chunk(tool_name="get_visa_requirements", tool_args='{"passport":"EG",'),
        _chunk(tool_args='"destination":"JP"}'),
    ]
    llm, completions = _llm_with_chunks(chunks)

    decision = await llm.decide(
        system="sys",
        history=[],
        user="visa for japan",
        tools=[{"type": "function", "name": "get_visa_requirements", "parameters": {}}],
    )

    assert decision.tool_name == "get_visa_requirements"
    assert decision.tool_arguments == {"passport": "EG", "destination": "JP"}
    assert decision.text == ""
    assert decision.first_delta_ms is not None
    tools = completions.received_kwargs["tools"]
    assert tools[0]["function"]["name"] == "get_visa_requirements"
    assert completions.received_kwargs["parallel_tool_calls"] is False


@pytest.mark.asyncio
async def test_decide_returns_plain_text_when_no_tool() -> None:
    chunks = [_chunk(content="November is "), _chunk(content="a good time.")]
    llm, _ = _llm_with_chunks(chunks)

    decision = await llm.decide(system="sys", history=[], user="when?", tools=[])

    assert decision.tool_name is None
    assert decision.text == "November is a good time."


@pytest.mark.asyncio
async def test_decide_puts_memory_on_user_message() -> None:
    llm, completions = _llm_with_chunks([_chunk(content="ok")])
    await llm.decide(
        system="sys",
        history=[("hi", "hello")],
        user="colour?",
        tools=[],
        memory_block="<known_about_user>\nFavourite colour: blue\n</known_about_user>",
    )
    messages = completions.received_kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert "Favourite colour: blue" in messages[-1]["content"]
    assert messages[-1]["content"].endswith("colour?")


@pytest.mark.asyncio
async def test_segments_yields_complete_lines_only() -> None:
    chunks = [
        _chunk(content='{"kind":"jud'),
        _chunk(content='gement","text":"Hi"}\n{"ki'),
        _chunk(content='nd":"judgement","text":"Bye"}'),
    ]
    llm, _ = _llm_with_chunks(chunks)

    lines = [line async for line in llm.segments(system="sys", user_block="q")]

    assert lines == [
        '{"kind":"judgement","text":"Hi"}',
        '{"kind":"judgement","text":"Bye"}',
    ]


@pytest.mark.asyncio
async def test_decide_times_out_instead_of_hanging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(groq_llm, "LLM_TIMEOUT_S", 0.05)

    class _Hanging:
        async def create(self, **kwargs: Any) -> Any:
            await asyncio.sleep(10)
            raise AssertionError("unreachable")

    llm = GroqLLM.__new__(GroqLLM)
    llm._models = ["openai/gpt-oss-20b"]  # type: ignore[attr-defined]
    llm._model_idx = 0  # type: ignore[attr-defined]
    llm.model = "openai/gpt-oss-20b"
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=_Hanging()))  # type: ignore[attr-defined]

    with pytest.raises(TimeoutError):
        await llm.decide(system="sys", history=[], user="hello", tools=[])


@pytest.mark.asyncio
async def test_decide_rotates_on_rate_limit_and_sticks() -> None:
    """TheraSpace sticky rotator: 429 on model A → succeed on B → stay on B."""

    class _RateLimited(Exception):
        status_code = 429

    llm, completions = _llm_with_chunks(
        [],
        models=["model-a", "model-b", "model-c"],
        by_model={
            "model-a": _RateLimited("tpm"),
            "model-b": [_chunk(content="ok from b")],
            "model-c": [_chunk(content="should not use c")],
        },
    )

    first = await llm.decide(system="sys", history=[], user="hi", tools=[])
    assert first.text == "ok from b"
    assert llm.model == "model-b"
    assert completions.models_seen == ["model-a", "model-b"]

    second = await llm.decide(system="sys", history=[], user="again", tools=[])
    assert second.text == "ok from b"
    assert llm.model == "model-b"
    assert completions.models_seen == ["model-a", "model-b", "model-b"]


@pytest.mark.asyncio
async def test_decide_raises_after_full_chain_rate_limited() -> None:
    class _RateLimited(Exception):
        status_code = 429

    llm, _ = _llm_with_chunks(
        [],
        models=["a", "b"],
        by_model={"a": _RateLimited("tpm"), "b": _RateLimited("tpm")},
    )

    with pytest.raises(_RateLimited):
        await llm.decide(system="sys", history=[], user="hi", tools=[])
    assert llm.model == "a"  # wrapped fully; sticky idx back at start
