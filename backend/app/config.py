"""Configuration. Every secret is read here and nowhere else.

No provider key ever reaches the browser — see .claude/rules/voice/pipeline.md.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    gemini_api_key: str
    rapidapi_key: str
    rapidapi_host: str

    # Live vendor requests held back for the demo and the reviewer's own exploration.
    # Below this, the client stops calling live and serves from cache/CSV, saying so.
    # See .claude/rules/tools/vendor-client.md.
    quota_reserve: int = 40

    log_level: str = "info"


def load_settings() -> Settings:
    return Settings(
        groq_api_key=_require("GROQ_API_KEY"),
        gemini_api_key=_require("GEMINI_API_KEY"),
        rapidapi_key=_require("RAPIDAPI_KEY"),
        rapidapi_host=os.environ.get("RAPIDAPI_HOST", "visa-requirement.p.rapidapi.com"),
        quota_reserve=int(os.environ.get("QUOTA_RESERVE", "40")),
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
