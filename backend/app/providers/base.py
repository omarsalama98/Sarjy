"""Provider interfaces. Provider choice is configuration, not code.

Free tiers rate-limit and models get deprecated mid-build — `playai-tts` was
deprecated during this project's own research week. These interfaces are what
make a swap a config change, and what make A/B latency comparison possible.

A provider SDK, model id, or provider-shaped payload outside its adapter is a
blocking review issue (.claude/rules/voice/pipeline.md).
"""

from collections.abc import AsyncIterator
from typing import Any, Protocol


class STT(Protocol):
    async def transcribe(self, pcm16: bytes, *, language: str | None = None) -> str:
        """16 kHz PCM16 in, text out. Batch on Groq Whisper — the turn is
        already endpointed client-side before this is called."""
        ...


class LLM(Protocol):
    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Schema-validated structured output. Never parsed prose."""
        ...


class TTS(Protocol):
    def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        """Text in, PCM out. Day 1 may buffer the whole thing; streaming is the
        upgrade if time allows."""
        ...
