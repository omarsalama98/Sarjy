"""Provider interfaces. Provider choice is configuration, not code.

Free tiers rate-limit and models get deprecated mid-build -- `playai-tts` was
deprecated during this project's own research week. These interfaces are what
make a swap a config change, and what make A/B latency comparison possible.

A provider SDK, model id, or provider-shaped payload outside its adapter is a
blocking review issue (.claude/rules/voice/pipeline.md).

Block A replaces the single `LLM.reply()` with two calls -- `decide()` (does
the model want the tool?) and `segments()` (the gated NDJSON answer) -- and
adds `VisaTool`, the interface every vendor client (real or fake) sits
behind, matching STT/LLM/TTS's own pattern (Invariant 3).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


class ProviderUnavailable(Exception):
    """A provider could not be constructed -- almost always a missing or
    empty API key. Lives here, next to the Protocols, rather than in
    factory.py: factory.py imports every concrete provider SDK, and
    app.pipeline.turn needs this exception without dragging those SDK
    imports into app.main's module graph (main.py must not import a
    provider SDK -- see main.py's module docstring). Callers (run_turn)
    turn this into a `turn_failed` with a plain "...is not configured"
    message rather than letting the app crash.
    """


@dataclass(frozen=True)
class LLMDecision:
    """Call 1's result. Either the model asked for the visa tool, or it
    answered in plain text with no tool involved (a judgement-only
    question, e.g. "when's a good time to visit Kyoto?")."""

    tool_name: str | None  # "get_visa_requirements", or None
    tool_arguments: dict[str, Any]  # {} when tool_name is None
    text: str  # the model's plain text, when no tool was called
    first_delta_ms: int | None  # to the first delta of ANY type that is not `thought`


class STT(Protocol):
    model: str

    async def transcribe(self, pcm16: bytes, *, language: str | None = None) -> str:
        """16 kHz PCM16 in, text out. Batch on Groq Whisper -- the turn is
        already endpointed client-side before this is called."""
        ...


class LLM(Protocol):
    model: str
    thinking_level: str | None

    async def decide(
        self,
        *,
        system: str,
        history: list[tuple[str, str]],
        user: str,
        tools: list[dict[str, Any]],
        memory_block: str = "",
    ) -> LLMDecision:
        """Call 1, streamed. Function-call arguments arrive as `step.delta`
        events with `delta.type == "arguments_delta"`, field `arguments` (a
        partial JSON string, concatenated then parsed once the step ends).
        NOT `delta.type == "arguments"` -- that shape never appears in the
        stream (verified live, day1-spikes.md S4 Q2).

        `memory_block` (Block B, D7) is the `<known_about_user>` block,
        rendered by app.prompts.build_memory_block() -- empty string when
        the caller has nothing to say. This is the ONLY LLM call that can
        fill in a passport from memory, since it's the only one that can
        decide to call the visa tool with it."""
        ...

    def segments(
        self, *, system: str, user_block: str
    ) -> AsyncIterator[str]:
        """Call 2. A FRESH stateless interaction -- no previous_interaction_id,
        no function_result replay (Decision D5: replaying a step under
        store=False is unproven and Invariant 5 wants the tool body as data
        in a delimited block anyway). Yields one COMPLETE line at a time:
        the adapter buffers text deltas and splits on '\\n', never emitting
        a partial line. A trailing fragment with no newline is yielded at
        the end of the stream.

        Two callers (Block B): the gated NDJSON answer, AND
        app.memory.extract's fact extraction -- both are "system + one data
        block in, one complete line out," so extraction reuses this exact
        method rather than growing an `LLM.extract()` of its own. When used
        for the gated answer, `user_block` already carries any
        `<known_about_user>` block (D7) -- this method itself does not
        distinguish the two callers in any way."""
        ...


class TTS(Protocol):
    model: str

    def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        """Text in, PCM out, streamed chunk by chunk as the provider produces it."""
        ...


# ---------------------------------------------------------------------------
# The visa tool -- Invariant 3: a vendor SDK/HTTP client sits behind this,
# exactly like STT/LLM/TTS. Resolved lazily via factory.get_tool().
# ---------------------------------------------------------------------------

ToolLayer = Literal["cache", "live", "map", "csv"]
ToolReason = Literal[
    "ok",
    "no_coverage",
    "unknown_place",
    "timeout",
    "http_error",
    "rate_limited",
    "empty",
    "malformed",
    "not_configured",
]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    payload: dict[str, Any] = field(default_factory=dict)  # the normalised shape; {} when not ok
    layer: ToolLayer | None = None
    citation: str | None = None  # "Travel Buddy -- visa requirements, checked 2026-09-20"
    source_url: str | None = None
    source_date: str | None = None  # the SOURCE's own date, never ours
    reason: ToolReason = "ok"
    embassy_url: str | None = None  # the refusal route; present even when ok is False, if known
    spent_request: bool = False  # True if a live call actually fired (barge-safe accounting)


@dataclass(frozen=True)
class QuotaStatus:
    total: int  # 120
    spent: int
    reserve: int  # 40
    remaining: int  # max(0, total - spent - reserve): live calls left ABOVE the reserve


class VisaTool(Protocol):
    name: str  # "travel-buddy" | "fake"

    async def lookup(self, *, passport: str, destination: str) -> ToolResult: ...
    def quota(self) -> QuotaStatus: ...
