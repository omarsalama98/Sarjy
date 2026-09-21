"""FakeVisaTool -- the fake behind VisaTool. Development, every test, and
the eval runner all use this; the real vendor (TravelBuddyTool) does not
exist until task 14, and nothing here or in tests ever reaches the network.

Two ways to build a result: `result_from_live_body()` turns a real (or
hand-constructed, clearly documented as such) vendor JSON body into a
ToolResult through the SAME normaliser the real client uses, so a fixture
and a live response are indistinguishable to everything downstream. A test
that wants a specific failure just asks for one by name.
"""

from dataclasses import dataclass, field
from typing import Any

from app.providers.base import QuotaStatus, ToolReason, ToolResult
from app.tools.normalise import normalise_live


def result_from_live_body(
    body: dict[str, Any], *, retrieved: str, layer: str = "live"
) -> ToolResult:
    """The one path every fixture and every hand-built test body goes
    through -- normalise_live() is exactly what TravelBuddyTool calls on a
    real response, so a fixture built this way exercises the real
    normaliser, not a second, parallel one written just for tests."""
    normalised = normalise_live(body, retrieved=retrieved)
    source_obj = normalised.payload.get("source", {})
    date = source_obj.get("generated_at")
    citation = f"Travel Buddy — visa requirements, checked {retrieved[:10]}"
    return ToolResult(
        ok=True,
        payload=normalised.payload,
        layer=layer,  # type: ignore[arg-type]
        citation=citation,
        source_url=None,  # the vendor body carries per-rule links, not one canonical source URL
        source_date=date,
        reason="ok",
        embassy_url=normalised.embassy_url,
        spent_request=(layer == "live"),
    )


@dataclass
class FakeVisaTool:
    name: str = "fake"
    fixtures: dict[tuple[str, str], ToolResult] = field(default_factory=dict)
    # When set, every lookup() call returns this failure regardless of
    # whether a fixture exists for the pair -- V1-V9's failure paths, on
    # demand, with no network and no stubbed transport.
    force_reason: ToolReason | None = None
    quota_status: QuotaStatus = field(
        default_factory=lambda: QuotaStatus(total=120, spent=0, reserve=40, remaining=71)
    )

    def add(self, passport: str, destination: str, result: ToolResult) -> None:
        self.fixtures[(passport, destination)] = result

    async def lookup(self, *, passport: str, destination: str) -> ToolResult:
        pair_only = {
            "pair": {
                "passport": passport,
                "passport_name": passport,
                "destination": destination,
                "destination_name": destination,
            }
        }
        if self.force_reason is not None:
            existing = self.fixtures.get((passport, destination))
            payload = {} if self.force_reason == "unknown_place" else pair_only
            return ToolResult(
                ok=False,
                reason=self.force_reason,
                payload=payload,
                embassy_url=existing.embassy_url if existing else None,
            )
        result = self.fixtures.get((passport, destination))
        if result is None:
            return ToolResult(ok=False, reason="no_coverage", payload=pair_only)
        return result

    def quota(self) -> QuotaStatus:
        return self.quota_status
