"""Memoised provider construction.

Providers are built lazily -- on first turn, never at import (F14 /
docs/plans/blocks/02-voice-loop.md). `app.main` must not import `app.config`
or any provider SDK at module load time: a missing key or a provider SDK
regression must never stop `/health` or the static UI mount from serving.
Requirement #4 (a working deployed URL) stays banked even with a broken key.
"""

import functools
from collections.abc import AsyncIterator

from app.config import load_settings
from app.providers.base import LLM, STT, TTS, ProviderUnavailable, VisaTool
from app.providers.deepgram_tts import DeepgramTTS
from app.providers.gemini_llm import GeminiLLM
from app.providers.groq_stt import GroqSTT
from app.tools.fake import FakeVisaTool
from app.tools.quota import QuotaLedger
from app.tools.vendor import TravelBuddyTool

__all__ = ["ProviderUnavailable", "RoutedTTS", "get_llm", "get_stt", "get_tool", "get_tts"]


class RoutedTTS:
    """Parked. `get_tts()` returns Deepgram only — the demo is English.

    Arabic TTS is not half-wired: the Orpheus adapter in groq_tts.py and this
    dispatcher stay in tree so a later pass can re-attach them after the gate
    covers Arabic number-words. Do not construct this from get_tts() until
    then; a reviewer who toggles a language chip deserves a gated answer."""

    def __init__(self, *, en: TTS, ar: TTS) -> None:
        self._en = en
        self._ar = ar
        self.model = f"routed(en={en.model}, ar={ar.model})"

    def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        adapter = self._ar if language == "ar" else self._en
        # timings.tts_model is read after synthesize() starts -- pin the
        # adapter that will actually speak, not the routed(en=..., ar=...) label.
        self.model = adapter.model
        return adapter.synthesize(text, language=language)


@functools.lru_cache(maxsize=1)
def get_stt() -> STT:
    try:
        settings = load_settings()
    except RuntimeError as e:
        raise ProviderUnavailable(str(e)) from e
    return GroqSTT(api_key=settings.groq_api_key)


@functools.lru_cache(maxsize=1)
def get_llm() -> LLM:
    try:
        settings = load_settings()
    except RuntimeError as e:
        raise ProviderUnavailable(str(e)) from e
    return GeminiLLM(api_key=settings.gemini_api_key)


@functools.lru_cache(maxsize=1)
def get_tts() -> TTS:
    try:
        settings = load_settings()
    except RuntimeError as e:
        raise ProviderUnavailable(str(e)) from e
    return DeepgramTTS(api_key=settings.deepgram_api_key, model=settings.deepgram_tts_model)


@functools.lru_cache(maxsize=1)
def get_tool() -> VisaTool:
    """Invariant 3, applied to the vendor exactly like STT/LLM/TTS above.
    `SARJY_FAKE_VENDOR=1` swaps in FakeVisaTool with no fixtures loaded
    (V6's no_coverage path on every pair) -- a deliberate, visible degrade
    for demoing "pull the network" without actually pulling it."""
    try:
        settings = load_settings()
    except RuntimeError as e:
        raise ProviderUnavailable(str(e)) from e

    if settings.fake_vendor:
        return FakeVisaTool()

    ledger = QuotaLedger(
        total=120, reserve=settings.quota_reserve, seed_spent=settings.quota_spent_seed
    )
    return TravelBuddyTool(
        api_key=settings.rapidapi_key,
        host=settings.rapidapi_host,
        timeout_s=settings.vendor_timeout_s,
        ledger=ledger,
    )
