"""fact_card() -- the D15 payload. Block A owns the contract; Block C owns
the pixels (no rendering here, deliberately -- see the block plan's Out
table).

Derived from the SAME `ToolResult.payload` the gate substitutes from, using
the SAME value-rendering rules (`gate.render_value` / `gate.render_quoted_value`).
That is what makes "the card and the spoken answer cannot contradict each
other" a fact rather than a hope: there is exactly one place a value is
turned into a string, and both the gate and the card call it.

Takes ONLY the `ToolResult` (matching the block plan's Contract 4 signature)
-- which is why `pair.passport`/`pair.passport_name`/etc must always be
present on `result.payload` once a pair has been resolved, success or not.
`vendor.TravelBuddyTool` and `tools.fake.FakeVisaTool` both fill the pair in
on every failure reason except `unknown_place` (where, by definition,
nothing was resolved at all -- there is no pair to card, and turn.py
doesn't call this function for that reason).
"""

from dataclasses import dataclass
from typing import Literal

from app.prompts import LABELS
from app.providers.base import ToolResult
from app.tools.gate import (
    QUOTED_FIELDS,
    SOURCED_FIELDS,
    contains_injection_marker,
    get_path,
    quoted_shape_ok,
    render_quoted_value,
    render_value,
)


@dataclass(frozen=True)
class FactRow:
    path: str  # "visa.duration" -- the SAME path the gate substitutes from
    label: str  # "Maximum stay" -- from LABELS
    value: str  # the SAME string the gate would substitute
    register: Literal["sourced", "quoted"]


@dataclass(frozen=True)
class FactCard:
    """Wire-agnostic -- pipeline/turn.py wraps this into protocol.FactCardOut
    (adding turn_id/seq/ts_ms) at the yield site, the same way every other
    message in this codebase is built where it's sent, not inside a helper."""

    passport: str
    passport_name: str
    destination: str
    destination_name: str
    covered: bool
    facts: list[FactRow]
    layer: str | None
    degraded: bool
    source_name: str | None
    source_url: str | None
    source_date: str | None
    retrieved: str | None
    embassy_url: str | None


def _optional_path(payload: dict[str, object], path: str) -> str | None:
    try:
        value = get_path(payload, path)
    except KeyError:
        return None
    return None if value is None else str(value)


def fact_card(result: ToolResult) -> FactCard | None:
    """None only when the pair itself was never resolved (V8 -- turn.py
    doesn't reach this call in that case, since there's nothing to card).
    `covered=False, facts=[]` is the refusal card (V6/V3): Block C renders
    it as "nothing found" rather than having nothing to render at all."""
    passport = _optional_path(result.payload, "pair.passport")
    destination = _optional_path(result.payload, "pair.destination")
    if passport is None or destination is None:
        return None

    passport_name = _optional_path(result.payload, "pair.passport_name") or passport
    destination_name = _optional_path(result.payload, "pair.destination_name") or destination

    if not result.ok:
        return FactCard(
            passport=passport,
            passport_name=passport_name,
            destination=destination,
            destination_name=destination_name,
            covered=False,
            facts=[],
            layer=None,
            degraded=False,
            source_name=None,
            source_url=None,
            source_date=None,
            retrieved=None,
            embassy_url=result.embassy_url,
        )

    # The card header already reads "{passport_name} → {destination_name}".
    # Repeating those as rows (Passport / Destination) is the same pair twice.
    _header_paths = frozenset({"pair.passport_name", "pair.destination_name"})

    facts: list[FactRow] = []
    for path, label in LABELS.items():
        if path in _header_paths:
            continue
        register: Literal["sourced", "quoted"] | None = None
        if path in SOURCED_FIELDS:
            register = "sourced"
        elif path in QUOTED_FIELDS:
            register = "quoted"
        else:
            continue  # a LABELS entry not on either allowlist -- never happens; defensive

        try:
            value = get_path(result.payload, path)
        except KeyError:
            continue  # absent for this pair -- not every field applies to every layer

        rendered = render_quoted_value(value) if register == "quoted" else render_value(value)

        # F4 -- a `quoted` value the gate would refuse to speak (Q5's shape
        # cap, Q6's injection screen) must not reach the card either. Block
        # A never gates fact_card() itself -- this call happens BEFORE the
        # gate runs (D15's send-order contract) -- so it re-applies the same
        # two checks the gate would, via the shared predicates in gate.py,
        # rather than a second copy of the thresholds/markers.
        if register == "quoted" and not (
            quoted_shape_ok(rendered) and not contains_injection_marker(rendered)
        ):
            continue

        facts.append(FactRow(path=path, label=label, value=rendered, register=register))

    layer = result.layer
    degraded = layer in ("map", "csv")

    return FactCard(
        passport=passport,
        passport_name=passport_name,
        destination=destination,
        destination_name=destination_name,
        covered=True,
        facts=facts,
        layer=layer,
        degraded=degraded,
        source_name=_optional_path(result.payload, "source.name"),
        source_url=result.source_url,
        source_date=_optional_path(result.payload, "source.generated_at"),
        retrieved=_optional_path(result.payload, "source.retrieved"),
        embassy_url=result.embassy_url,
    )
