"""Gemini adapter -- two calls, never one.

`decide()` (call 1) asks whether the visa tool is needed and streams a
function call's name/arguments if so. `segments()` (call 2) is a FRESH
stateless interaction that returns the gated NDJSON answer -- no
`previous_interaction_id`, no replayed `function_result` (Decision D5:
`store=False` makes replaying a step unproven, day1-spikes.md S4 Q3 got a
generic "Invalid input received." on the one attempt made, and Invariant 5
wants the tool body handed over as a delimited DATA block regardless).

Event shapes below are verified live, not read off documentation --
`scratch/spikes/parallel_fc.py` + `docs/measurements/day1-spikes.md` S4:
  - `step.start`: `event.step.type == "function_call"` carries `.name`
    before any arguments exist yet.
  - `step.delta`: `event.delta.type == "arguments_delta"`, field
    `.arguments` -- a partial JSON string, concatenated then parsed once
    the stream ends. NOT `.type == "arguments"` -- that shape never
    appears (the trap the docs page would have led straight into).
  - A `thought` step (and its `thought_signature` deltas) always arrives
    first, even at `thinking_level: "minimal"` -- ignored, not timed.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, cast

from google import genai
from google.genai import types
from google.genai.interactions import InteractionSSEEvent

from app.providers.base import LLMDecision

logger = logging.getLogger("sarjy")

MODEL = "gemini-3.5-flash-lite"
API_REVISION = "2026-05-20"

# Also exposed as an attribute so a TurnTimings record can say what it
# measured without turn.py importing this module (base.py's Protocol note:
# main.py's import graph must never gain a provider SDK through a model-id
# lookup).
THINKING_LEVEL = "minimal"

HISTORY_TURNS = 6

# See the original note on LLM_TIMEOUT_S (Block 2): HttpOptions.timeout
# defaults to None, so nothing upstream of asyncio.timeout() bounds either
# call's total duration. Measured 2026-09-21 from Modal us-east: bare
# `interactions.create` alone can take ~20s before the first SSE event
# (local laptop: ~1.5–2s). 10s therefore kills every live decide() with
# TimeoutError and the user-facing "(llm) I couldn't come up with an
# answer". 45s covers a slow create + a real multi-sentence call-2 stream
# while still failing inside main.py's HARD_MAX_MS (~190s).
LLM_TIMEOUT_S = 45.0

# Deltas this adapter ignores for BOTH calls -- thinking overhead that
# always arrives first, even at thinking_level="minimal" (verified live,
# day1-spikes.md S4). Timing to the first of these would record a fiction.
_IGNORED_DELTA_TYPES = frozenset({"thought", "thought_signature"})


class GeminiLLM:
    model = MODEL
    thinking_level: str | None = THINKING_LEVEL

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(
            api_key=api_key,
            # One attempt; run_turn's except turns a failure into a fast,
            # visible turn_failed instead of a silent SDK backoff loop.
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
        )

    async def decide(
        self,
        *,
        system: str,
        history: list[tuple[str, str]],
        user: str,
        tools: list[dict[str, Any]],
        memory_block: str = "",
    ) -> LLMDecision:
        # `user` is untrusted transcribed speech (Invariant 5) -- the `input`
        # text itself, never spliced into `system`.
        input_text = _format_input(history[-HISTORY_TURNS:], user)
        # D7 -- the memory block goes ahead of the conversation, same
        # position build_user_block() gives it in call 2, so a reviewer
        # reading both prompts side by side sees one consistent convention.
        if memory_block:
            input_text = f"{memory_block}\n\n{input_text}"

        t0 = time.monotonic()
        first_delta_ms: int | None = None
        text_chunks: list[str] = []
        tool_name: str | None = None
        tool_args_text = ""

        async with asyncio.timeout(LLM_TIMEOUT_S):
            stream = await self._client.aio.interactions.create(
                model=MODEL,
                input=input_text,
                stream=True,
                store=False,  # mandatory on the free tier -- otherwise input trains Google
                system_instruction=system,
                generation_config={"thinking_level": THINKING_LEVEL},
                tools=tools,
                extra_headers={"Api-Revision": API_REVISION},
            )
            events = cast(AsyncIterator[InteractionSSEEvent], stream)

            async for event in events:
                if event.event_type == "step.start":
                    # The function's NAME arrives here, before its arguments
                    # stream -- see the module docstring's verified shape.
                    step = event.step
                    if getattr(step, "type", None) == "function_call":
                        tool_name = getattr(step, "name", None)
                    continue

                if event.event_type != "step.delta":
                    continue
                delta = event.delta
                if delta.type in _IGNORED_DELTA_TYPES:
                    continue
                if first_delta_ms is None:
                    first_delta_ms = round((time.monotonic() - t0) * 1000)

                if delta.type == "text":
                    text_chunks.append(delta.text or "")
                elif delta.type == "arguments_delta":
                    tool_args_text += delta.arguments or ""

        tool_arguments: dict[str, Any] = {}
        if tool_name is not None and tool_args_text:
            try:
                tool_arguments = json.loads(tool_args_text)
            except json.JSONDecodeError:
                # Can't call a tool with arguments that don't parse -- treat
                # this as "no tool was actually usable" rather than crashing
                # the turn; run_turn falls through to the no-tool path,
                # which D6 makes safe by construction (no tool_call_id ->
                # every `sourced` segment rejects, and Sarjy refuses).
                logger.warning("decide: could not parse tool arguments %r", tool_args_text)
                tool_name = None

        return LLMDecision(
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            text="".join(text_chunks),
            first_delta_ms=first_delta_ms,
        )

    async def segments(self, *, system: str, user_block: str) -> AsyncIterator[str]:
        # A FRESH interaction -- `user_block` (built by
        # prompts.build_user_block, including prior turns as a DATA block)
        # is the WHOLE input; nothing from call 1 is replayed as a native
        # function response (D5).
        buffer = ""
        async with asyncio.timeout(LLM_TIMEOUT_S):
            stream = await self._client.aio.interactions.create(
                model=MODEL,
                input=user_block,
                stream=True,
                store=False,
                system_instruction=system,
                generation_config={"thinking_level": THINKING_LEVEL},
                extra_headers={"Api-Revision": API_REVISION},
            )
            events = cast(AsyncIterator[InteractionSSEEvent], stream)

            async for event in events:
                if event.event_type != "step.delta":
                    continue
                delta = event.delta
                if delta.type != "text":
                    continue
                buffer += delta.text
                # Never emit a partial line -- a line is only handed to the
                # caller once its trailing '\n' has actually arrived.
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        yield line

        # A trailing fragment with no newline (the model's last line, or a
        # stream that ended mid-line) is still real content -- yielded once
        # the stream itself is done rather than dropped on the floor.
        if buffer.strip():
            yield buffer


def _format_input(history: list[tuple[str, str]], user: str) -> str:
    """Plain turns, oldest first, then the current one. Not a chat-template
    DSL -- this model takes a single input string per call, so history is
    spelled out in prose. Call 2 never calls this -- it takes no history at
    all (D5: a fresh interaction, gated purely on this turn's tool result)."""
    lines = []
    for past_user, past_assistant in history:
        lines.append(f"User: {past_user}")
        lines.append(f"Sarjy: {past_assistant}")
    lines.append(f"User: {user}")
    return "\n".join(lines)
