"""Groq LLM adapter -- Chat Completions, same two-call contract as Gemini.

Why this exists (2026-09-21): Gemini Interactions from Modal us-east was
measured at ~25 s TTFT on `decide()` and then timing out on `segments()`,
so live turns failed with `(llm)` / `(gate)` even after raising
LLM_TIMEOUT_S to 45. The same pair of calls against Groq
`openai/gpt-oss-20b` from the same region measured ~550 ms / ~220 ms.

Rate-limit failover: sticky model rotation patterned on
TheraSpace/generate_dpo_data.py's ModelRotator -- stay on the working
model; on 429 advance to the next in the chain and stick. Voice cannot
afford TheraSpace's 4×10 s sleeps, so rotation is immediate. Override the
chain with GROQ_LLM_MODELS=id1,id2,id3.

Tool schema conversion: `app.prompts.VISA_TOOL` is the Gemini Interactions
shape (`type`/`name`/`parameters` at the top level). Groq wants the OpenAI
Chat Completions nesting (`{"type":"function","function":{...}}`). The
adapter converts at the boundary so prompts.py stays provider-neutral.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypeVar

from groq import AsyncGroq, RateLimitError

from app.providers.base import LLMDecision

logger = logging.getLogger("sarjy")

# Free-tier chain as of 2026-09 (Llama ids are deprecated on Groq). Prefer
# the fast 20b; 120b shares the same family; qwen is a separate quota bucket.
DEFAULT_MODEL_CHAIN: tuple[str, ...] = (
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
)

HISTORY_TURNS = 6

# Groq from Modal is ~0.5 s; 15 s still fails fast on a real outage without
# letting a hung call eat the demo turn the way Gemini's 25 s TTFT did.
LLM_TIMEOUT_S = 15.0
MAX_RETRIES = 1

T = TypeVar("T")


def model_chain_from_env() -> list[str]:
    raw = os.environ.get("GROQ_LLM_MODELS", "").strip()
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    return list(DEFAULT_MODEL_CHAIN)


def _is_rate_limited(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return "429" in text or "rate limit" in text


def _create_extras(model: str) -> dict[str, Any]:
    """gpt-oss burns reasoning tokens unless effort is pinned low; other
    models in the chain do not take that kwarg."""
    if "gpt-oss" in model.lower():
        return {"reasoning_effort": "low"}
    return {}


class GroqLLM:
    thinking_level: str | None = None

    def __init__(
        self,
        api_key: str,
        *,
        models: list[str] | None = None,
    ) -> None:
        chain = list(models) if models is not None else model_chain_from_env()
        if not chain:
            raise ValueError("GroqLLM model chain must be non-empty")
        self._models = chain
        self._model_idx = 0
        self.model = chain[0]
        self._client = AsyncGroq(api_key=api_key, max_retries=MAX_RETRIES, timeout=LLM_TIMEOUT_S)

    def _advance(self) -> None:
        self._model_idx = (self._model_idx + 1) % len(self._models)
        self.model = self._models[self._model_idx]

    async def _with_model_rotation(
        self,
        op: Callable[[str], Awaitable[T]],
        *,
        label: str,
    ) -> T:
        """Sticky rotator: stay on the current model; on 429 advance and
        retry. After one full cycle with every model rate-limited, raise.
        Non-429 API errors propagate immediately (not a quota problem)."""
        last_rate: BaseException | None = None
        for attempt in range(len(self._models)):
            model = self.model
            try:
                result = await op(model)
                if attempt > 0:
                    logger.info("llm %s recovered on %s after rate-limit rotate", label, model)
                return result
            except Exception as exc:
                if not _is_rate_limited(exc):
                    raise
                last_rate = exc
                next_model = self._models[(self._model_idx + 1) % len(self._models)]
                logger.warning(
                    "llm %s rate-limited on %s; rotating to %s",
                    label,
                    model,
                    next_model,
                )
                self._advance()
        assert last_rate is not None
        raise last_rate

    async def decide(
        self,
        *,
        system: str,
        history: list[tuple[str, str]],
        user: str,
        tools: list[dict[str, Any]],
        memory_block: str = "",
    ) -> LLMDecision:
        messages = _decide_messages(system, history, user, memory_block)
        openai_tools = [_to_openai_tool(t) for t in tools]

        async def _once(model: str) -> LLMDecision:
            t0 = time.monotonic()
            first_delta_ms: int | None = None
            text_chunks: list[str] = []
            tool_name: str | None = None
            tool_args_text = ""

            async with asyncio.timeout(LLM_TIMEOUT_S):
                create_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0,
                    **_create_extras(model),
                }
                if openai_tools:
                    create_kwargs["tools"] = openai_tools
                    create_kwargs["tool_choice"] = "auto"
                    create_kwargs["parallel_tool_calls"] = False
                stream = await self._client.chat.completions.create(**create_kwargs)
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta is None:
                        continue

                    if first_delta_ms is None and (delta.content or delta.tool_calls):
                        first_delta_ms = round((time.monotonic() - t0) * 1000)

                    if delta.content:
                        text_chunks.append(delta.content)

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            fn = tc.function
                            if fn is None:
                                continue
                            if fn.name:
                                tool_name = fn.name
                            if fn.arguments:
                                tool_args_text += fn.arguments

            tool_arguments: dict[str, Any] = {}
            if tool_name is not None and tool_args_text:
                try:
                    tool_arguments = json.loads(tool_args_text)
                except json.JSONDecodeError:
                    logger.warning("decide: could not parse tool arguments %r", tool_args_text)
                    tool_name = None

            return LLMDecision(
                tool_name=tool_name,
                tool_arguments=tool_arguments,
                text="".join(text_chunks),
                first_delta_ms=first_delta_ms,
            )

        return await self._with_model_rotation(_once, label="decide")

    async def segments(self, *, system: str, user_block: str) -> AsyncIterator[str]:
        # Rotation must finish before we yield -- an AsyncIterator that
        # retries mid-yield would duplicate partial lines into the gate.
        lines = await self._with_model_rotation(
            lambda model: self._segments_once(model, system, user_block),
            label="segments",
        )
        for line in lines:
            yield line

    async def _segments_once(
        self, model: str, system: str, user_block: str
    ) -> list[str]:
        buffer = ""
        lines: list[str] = []
        async with asyncio.timeout(LLM_TIMEOUT_S):
            create_kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_block},
                ],
                "stream": True,
                "temperature": 0,
                **_create_extras(model),
            }
            stream = await self._client.chat.completions.create(**create_kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None or not delta.content:
                    continue
                buffer += delta.content
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        lines.append(line)
        if buffer.strip():
            lines.append(buffer)
        return lines


def _decide_messages(
    system: str,
    history: list[tuple[str, str]],
    user: str,
    memory_block: str,
) -> list[dict[str, str]]:
    """Chat Completions roles. Memory stays a DATA prefix on the user turn
    (same position Gemini's decide() used), never spliced into `system`."""
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for past_user, past_assistant in history[-HISTORY_TURNS:]:
        messages.append({"role": "user", "content": past_user})
        messages.append({"role": "assistant", "content": past_assistant})
    user_content = f"{memory_block}\n\n{user}" if memory_block else user
    messages.append({"role": "user", "content": user_content})
    return messages


def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Accept either the Gemini Interactions flat shape or an already-nested
    OpenAI tool dict. prompts.VISA_TOOL is the flat one."""
    if "function" in tool and isinstance(tool["function"], dict):
        return tool
    name = tool.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"tool declaration missing name: {tool!r}")
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": tool.get("description") or "",
            "parameters": tool.get("parameters") or {"type": "object", "properties": {}},
        },
    }


# Re-export helpers for tests.
__all__ = [
    "DEFAULT_MODEL_CHAIN",
    "GroqLLM",
    "model_chain_from_env",
    "_to_openai_tool",
]
