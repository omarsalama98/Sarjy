"""Vendor body and CSV row -> one identical shape (Contract 3).

The raw vendor body never reaches the model -- this module is the only
place that reads Travel Buddy's field names. Everything downstream (the
gate, the prompt's field catalogues, the fact card) reads OUR short, stable
paths (`visa.duration`, not `visa_rules.primary_rule.duration`) and never
sees the vendor's shape at all.

Three hard rules, restated from the block plan:
  1. A key the source has no value for is OMITTED, never set to null.
     Absent must stay distinguishable from null -- absent rejects a
     `sourced` segment, null resolves to the word "none".
  2. Free text is mapped to exactly the two QUOTED_FIELDS paths and to
     nothing else. Every other prose field stays unmapped.
  3. Every unmapped key is logged, every call. A normaliser that silently
     drops a field is a lossy filter, not a normaliser -- and the model
     cannot cite what it was never shown.
"""

import logging
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.tools.gate import get_path

logger = logging.getLogger("sarjy")

# `UK/Britain/England/Great Britain -> GB` etc -- the boring part that makes
# the interesting part work (the block plan's own framing). Keys are
# ASCII-folded, lowercased text; resolve_code() folds its input the same way
# before checking this table.
ALIASES: dict[str, str] = {
    "uk": "GB",
    "britain": "GB",
    "england": "GB",
    "great britain": "GB",
    "uae": "AE",
    "emirates": "AE",
    "usa": "US",
    "us": "US",
    "america": "US",
    "the states": "US",
    "ksa": "SA",
    "saudi": "SA",
    "korea": "KR",
}


@dataclass(frozen=True)
class Normalised:
    """`payload` is the field catalogue itself (Contract 3's nested shape --
    {"pair": {...}, "visa": {...}, "source": {...}}), ready to hand straight
    to gate.get_path(). `embassy_url` is carried separately: it is the
    refusal route, not a sourced/quoted field, so it never goes on either
    allowlist."""

    payload: dict[str, Any]
    embassy_url: str | None


def _set_path(payload: dict[str, Any], dotted: str, value: Any) -> None:
    """The inverse of gate.get_path() -- builds the same nested shape
    get_path() reads, one dotted write at a time."""
    parts = dotted.split(".")
    cur = payload
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _flatten_leaf_paths(obj: Any, prefix: str = "") -> list[str]:
    """Every leaf (non-dict) value's dotted path, for the unmapped-key log.
    The vendor body has no lists in the shapes this project reads, so a list
    is treated as a leaf rather than recursed into."""
    if isinstance(obj, dict) and obj:
        paths: list[str] = []
        for key, value in obj.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            paths.extend(_flatten_leaf_paths(value, child_prefix))
        return paths
    return [prefix] if prefix else []


def _fold(text: str) -> str:
    """Accent- and case-insensitive comparison key. NFKD + drop combining
    marks: 'Bahrain' and any accented spelling fold to the same key."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_only.strip().lower()


def resolve_code(text: str, *, countries: list[dict[str, Any]]) -> str | None:
    """`text` -> ISO alpha-2, or None if nothing matches (V8: an unresolvable
    place is a graceful re-ask, never a guess). Tries, in order: already a
    valid 2-letter code, the alias table, an exact case/accent-insensitive
    name match against `countries` (each a dict with "iso_alpha2"/"name",
    e.g. data/reference/passports.json + destinations.json)."""
    if not text or not text.strip():
        return None

    stripped = text.strip()
    if len(stripped) == 2 and stripped.isalpha():
        code = stripped.upper()
        if any(c.get("iso_alpha2") == code for c in countries):
            return code

    folded = _fold(stripped)
    if folded in ALIASES:
        return ALIASES[folded]

    for country in countries:
        name = country.get("name")
        if isinstance(name, str) and _fold(name) == folded:
            iso = country.get("iso_alpha2")
            return str(iso) if iso is not None else None

    return None


def normalise_live(body: dict[str, Any], *, retrieved: str) -> Normalised:
    """A `/v2/visa/check` response body -> Contract 3's shape. Verified
    against the real committed body, data/reference/visa_reqs_SA_JP.json --
    `primary_rule.duration` is a STRING ("90 days"), and there is no
    `exception_rule`/`full_text` in that particular pair's response, so
    `visa.exception` is legitimately absent for SA->JP (present when the
    vendor sends one -- handled here, not depended on)."""
    data = body.get("data", {})
    meta = body.get("meta", {})

    payload: dict[str, Any] = {}
    consumed: set[str] = set()

    def take(src_path: str, dest_path: str) -> None:
        try:
            value = get_path(data, src_path)
        except KeyError:
            return  # absent at the source -- stays absent here (rule 1)
        consumed.add(src_path)
        _set_path(payload, dest_path, value)

    take("passport.code", "pair.passport")
    take("passport.name", "pair.passport_name")
    take("destination.code", "pair.destination")
    take("destination.name", "pair.destination_name")
    take("visa_rules.primary_rule.name", "visa.type")
    take("visa_rules.primary_rule.duration", "visa.duration")
    take("destination.passport_validity", "visa.passport_validity")
    take("mandatory_registration.name", "visa.registration")
    # QUOTED ONLY (D3'/D14) -- never reachable from a `sourced` segment;
    # SOURCED_FIELDS and QUOTED_FIELDS are asserted disjoint in gate.py.
    take("visa_rules.exception_rule.full_text", "visa.exception")

    embassy_url: str | None = None
    try:
        embassy_url = get_path(data, "destination.embassy_url")
        consumed.add("destination.embassy_url")
    except KeyError:
        pass

    _set_path(payload, "source.layer", "live")
    _set_path(payload, "source.name", "Travel Buddy")
    if "generated_at" in meta:
        _set_path(payload, "source.generated_at", meta["generated_at"])
    _set_path(payload, "source.retrieved", retrieved)

    unmapped = sorted(set(_flatten_leaf_paths(data)) - consumed)
    if unmapped:
        # Rule 3 -- the difference between a normaliser and a lossy filter.
        # population/area_km2/exchange/currency/capital/etc land here on
        # every real call; that is expected and fine, not a bug to silence.
        logger.info("vendor_unmapped keys=%s", unmapped)

    return Normalised(payload=payload, embassy_url=embassy_url)


def normalise_map(
    *,
    passport_code: str,
    passport_name: str,
    destination_code: str,
    destination_name: str,
    category: str,
    map_date: str,
    retrieved: str,
) -> Normalised:
    """A cached VisaMap colour bucket -> Contract 3's shape. `category` is
    already the vendor's own published legend wording (D8) -- resolved by
    the caller against data/reference/colour-legend.json, not guessed here.
    Emits `visa.category` ONLY, never `visa.type`: the vendor's blue bucket
    means "visa on arrival or eVisa" (ambiguous), so this layer must never
    claim a specific visa type."""
    payload: dict[str, Any] = {}
    _set_path(payload, "pair.passport", passport_code)
    _set_path(payload, "pair.passport_name", passport_name)
    _set_path(payload, "pair.destination", destination_code)
    _set_path(payload, "pair.destination_name", destination_name)
    _set_path(payload, "visa.category", category)
    _set_path(payload, "source.layer", "map")
    _set_path(payload, "source.name", "Travel Buddy")
    _set_path(payload, "source.generated_at", map_date)
    _set_path(payload, "source.retrieved", retrieved)
    return Normalised(payload=payload, embassy_url=None)


def normalise_csv_row(
    *,
    passport_code: str,
    passport_name: str,
    destination_code: str,
    destination_name: str,
    requirement: str,
    csv_date: str,
    retrieved: str,
) -> Normalised | None:
    """One `passport-index-tidy-iso2.csv` row -> Contract 3's shape, or None
    for the `-1` self-reference artifact (filtered, never served -- V6 the
    CSV's own documented quirk). A numeric requirement is days of visa-free
    stay; anything else is the vendor's own category word, verbatim --
    passport_validity and registration are always absent on this layer, so a
    model naming them correctly rejects (this layer is visibly partial)."""
    value = requirement.strip()
    if value == "-1":
        return None

    payload: dict[str, Any] = {}
    _set_path(payload, "pair.passport", passport_code)
    _set_path(payload, "pair.passport_name", passport_name)
    _set_path(payload, "pair.destination", destination_code)
    _set_path(payload, "pair.destination_name", destination_name)

    if value.isdigit():
        _set_path(payload, "visa.type", "visa free")
        _set_path(payload, "visa.duration", f"{value} days")
    else:
        _set_path(payload, "visa.type", value)

    _set_path(payload, "source.layer", "csv")
    _set_path(payload, "source.name", "passport-index community dataset")
    _set_path(payload, "source.generated_at", csv_date)
    _set_path(payload, "source.retrieved", retrieved)
    return Normalised(payload=payload, embassy_url=None)
