"""Configuration. Every secret is read here and nowhere else.

No provider key ever reaches the browser — see .claude/rules/voice/pipeline.md.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Two .env files exist: backend/.env (the live one) and a stale root /.env
# with no Deepgram key. Bare load_dotenv() searches upward from this file
# and stops at the FIRST hit -- backend/.env -- so if a key only lived in
# the root file, load_settings() would raise on a key plainly sitting on
# disk. Load both paths explicitly, backend/.env first; override=False
# means a key already set (by backend/.env, or by the real environment --
# e.g. Modal's injected secret) is never clobbered by the root file.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_BACKEND_DIR.parent / ".env", override=False)


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    gemini_api_key: str
    deepgram_api_key: str
    # Block 5 owns this key. Optional here so a missing RapidAPI key -- which
    # this block has no use for -- cannot stop the whole app from starting
    # (F14: providers are built lazily, on first turn, never at import).
    rapidapi_key: str | None
    rapidapi_host: str
    deepgram_tts_model: str = "aura-2-thalia-en"
    # Parked with groq_tts.py / RoutedTTS. get_tts() does not read these.
    orpheus_tts_model: str = "canopylabs/orpheus-arabic-saudi"
    orpheus_voice: str = "noura"

    # Live vendor requests held back for the demo and the reviewer's own exploration.
    # Below this, the client stops calling live and serves from cache/CSV, saying so.
    # See .claude/rules/tools/vendor-client.md.
    quota_reserve: int = 40

    # F3 -- seeds the PERSISTENT quota ledger (modal.Dict) the FIRST time it
    # is ever touched; every later read/restart sees the real accumulated
    # count and this default is never consulted again (QuotaLedger seeds
    # once, via modal.Dict.put(skip_if_exists=True)). Defaults to the full
    # 120-request budget -- the worst case, not the optimistic one -- so a
    # container that starts before Omar has checked the RapidAPI dashboard
    # can never fire a live request it can't take back. Set QUOTA_SPENT_SEED
    # to the dashboard's real count before the first deploy/run that touches
    # the ledger; after that, this number is locked in for good.
    quota_spent_seed: int = 120

    # httpx's own default has no read timeout at all -- explicit and short,
    # never the SDK/library default (the same trap gemini_llm.py's
    # LLM_TIMEOUT_S comment names). V2's failure path depends on this firing.
    vendor_timeout_s: float = 4.0

    # SARJY_FAKE_VENDOR=1 swaps factory.get_tool() to FakeVisaTool without
    # touching any call site -- the same escape hatch a dropped network
    # connection gives a reviewer at verification turn 4 (F14's pattern,
    # applied to the vendor instead of a provider key).
    fake_vendor: bool = False

    log_level: str = "info"


def load_settings() -> Settings:
    return Settings(
        groq_api_key=_require("GROQ_API_KEY"),
        gemini_api_key=_require("GEMINI_API_KEY"),
        deepgram_api_key=_require("DEEPGRAM_API_KEY"),
        rapidapi_key=os.environ.get("RAPIDAPI_KEY") or None,
        rapidapi_host=os.environ.get("RAPIDAPI_HOST", "visa-requirement.p.rapidapi.com"),
        deepgram_tts_model=os.environ.get("DEEPGRAM_TTS_MODEL", "aura-2-thalia-en"),
        orpheus_tts_model=os.environ.get(
            "ORPHEUS_TTS_MODEL", "canopylabs/orpheus-arabic-saudi"
        ),
        orpheus_voice=os.environ.get("ORPHEUS_VOICE", "noura"),
        quota_reserve=int(os.environ.get("QUOTA_RESERVE", "40")),
        quota_spent_seed=int(os.environ.get("QUOTA_SPENT_SEED", "120")),
        vendor_timeout_s=float(os.environ.get("VENDOR_TIMEOUT_S", "4.0")),
        fake_vendor=os.environ.get("SARJY_FAKE_VENDOR", "") not in ("", "0", "false", "False"),
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
