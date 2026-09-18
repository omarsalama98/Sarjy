"""Travel Buddy visa client. Quota-aware by design.

The free tier is 120 requests. Resolution order is fixed and never reordered:

    cached VisaMap (category, zero cost)
      -> warm cache (detail, previously fetched)
        -> vendored CSV (offline, unlimited)
          -> live VisaRequirements (1 request, only on a miss, only above reserve)

Every answer states which layer served it and how fresh that layer is.
Below QUOTA_RESERVE the client stops calling live and serves from the CSV,
saying so. A reviewer must never see a quota error.

Rules: .claude/rules/tools/vendor-client.md
"""

from dataclasses import dataclass
from typing import Any, Literal

Layer = Literal["map", "cache", "csv", "live"]


@dataclass(frozen=True)
class VisaAnswer:
    passport: str
    destination: str
    payload: dict[str, Any]
    layer: Layer
    generated_at: str | None  # the source's own timestamp, not ours
    citation: str


async def lookup(passport: str, destination: str) -> VisaAnswer | None:
    """Resolve a pair. None means no layer covers it — refuse and route to the
    embassy link. Never guess."""
    raise NotImplementedError


def remaining_quota() -> int:
    """Live requests left before the reserve. Surfaced in the UI."""
    raise NotImplementedError
