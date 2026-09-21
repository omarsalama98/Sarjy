"""Memoised provider construction.

Providers are built lazily -- on first turn, never at import (F14 /
docs/plans/blocks/02-voice-loop.md). `app.main` must not import `app.config`
or any provider SDK at module load time: a missing key or a provider SDK
regression must never stop `/health` or the static UI mount from serving.
Requirement #4 (a working deployed URL) stays banked even with a broken key.
"""

import functools

from app.config import load_settings
from app.providers.base import LLM, STT, TTS, ProviderUnavailable, VisaTool
from app.providers.deepgram_tts import DeepgramTTS
from app.providers.gemini_llm import GeminiLLM
from app.providers.groq_stt import GroqSTT
from app.tools.fake import FakeVisaTool
from app.tools.quota import QuotaLedger
from app.tools.vendor import TravelBuddyTool

__all__ = ["ProviderUnavailable", "get_llm", "get_stt", "get_tool", "get_tts"]


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
