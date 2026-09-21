"""Both directions of the normaliser -- vendor body and CSV row into the
identical Contract 3 shape -- plus the alias table and the CSV's `-1`
self-reference filter. Hand-built fixtures matching the REAL committed
body's shape (data/reference/visa_reqs_SA_JP.json), not re-fetched.
"""

import json
import logging
from pathlib import Path

import pytest

from app.tools.gate import get_path
from app.tools.normalise import normalise_csv_row, normalise_live, normalise_map, resolve_code

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"

COUNTRIES = [
    {"iso_alpha2": "SA", "iso_alpha3": "SAU", "name": "Saudi Arabia"},
    {"iso_alpha2": "JP", "iso_alpha3": "JPN", "name": "Japan"},
    {"iso_alpha2": "GB", "iso_alpha3": "GBR", "name": "United Kingdom"},
]


def test_normalise_live_against_the_real_committed_body() -> None:
    """The exact file task 12 committed -- reading it, never re-fetching it
    (a blocking review issue per the block plan)."""
    body = json.loads((_DATA_DIR / "visa_reqs_SA_JP.json").read_text())

    normalised = normalise_live(body, retrieved="2026-09-20T09:14:00Z")

    assert get_path(normalised.payload, "pair.passport") == "SA"
    assert get_path(normalised.payload, "pair.destination_name") == "Japan"
    assert get_path(normalised.payload, "visa.type") == "eVisa"
    # Closed by Omar's correction: duration is a STRING, "90 days", not a number.
    assert get_path(normalised.payload, "visa.duration") == "90 days"
    assert isinstance(get_path(normalised.payload, "visa.duration"), str)
    assert get_path(normalised.payload, "visa.passport_validity") == "Valid on arrival"
    assert get_path(normalised.payload, "visa.registration") == "Customs declaration"
    assert get_path(normalised.payload, "source.layer") == "live"
    assert get_path(normalised.payload, "source.retrieved") == "2026-09-20T09:14:00Z"
    assert normalised.embassy_url == "https://www.embassypages.com/saudiarabia#titlePlaceholder2"
    # This pair's real body carries no exception_rule -- confirmed absent,
    # not silently defaulted.
    try:
        get_path(normalised.payload, "visa.exception")
        raise AssertionError("expected KeyError -- SA->JP carries no exception_rule")
    except KeyError:
        pass


def test_normalise_live_maps_exception_rule_when_present() -> None:
    body = {
        "data": {
            "passport": {"code": "SA", "name": "Saudi Arabia"},
            "destination": {
                "code": "BH", "name": "Bahrain", "passport_validity": "Valid on arrival"
            },
            "mandatory_registration": {"name": "None", "color": "green"},
            "visa_rules": {
                "primary_rule": {"name": "Visa free", "duration": "90 days", "color": "green"},
                "exception_rule": {"full_text": "Nationals of GCC states are exempt."},
            },
        },
        "meta": {"generated_at": "2026-09-19T00:00:00Z"},
    }
    normalised = normalise_live(body, retrieved="2026-09-20T09:14:00Z")
    assert get_path(normalised.payload, "visa.exception") == "Nationals of GCC states are exempt."


def test_normalise_live_omits_a_key_the_source_never_sent_never_sets_null() -> None:
    """Rule 1 -- absent must stay distinguishable from null."""
    body = {"data": {"passport": {"code": "SA"}}, "meta": {}}
    normalised = normalise_live(body, retrieved="2026-09-20T09:00:00Z")
    try:
        get_path(normalised.payload, "visa.type")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


def test_normalise_live_forwards_a_genuine_null_as_null_not_absent() -> None:
    body = {
        "data": {"passport": {"code": "SA"}, "visa_rules": {"primary_rule": {"name": None}}},
        "meta": {},
    }
    normalised = normalise_live(body, retrieved="2026-09-20T09:00:00Z")
    assert get_path(normalised.payload, "visa.type") is None


def test_normalise_live_logs_unmapped_keys(caplog: pytest.LogCaptureFixture) -> None:
    """Rule 3 -- the difference between a normaliser and a lossy filter.
    The real body carries plenty we deliberately never map (population,
    area_km2, exchange, ...); every one of those keys must show up in the
    log line, not just silently vanish."""
    body = json.loads((_DATA_DIR / "visa_reqs_SA_JP.json").read_text())
    with caplog.at_level(logging.INFO, logger="sarjy"):
        normalise_live(body, retrieved="2026-09-20T09:14:00Z")

    unmapped_lines = [r.message for r in caplog.records if "vendor_unmapped" in r.message]
    assert len(unmapped_lines) == 1
    assert "destination.population" in unmapped_lines[0]
    assert "destination.area_km2" in unmapped_lines[0]


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_normalise_csv_row_numeric_requirement_becomes_visa_free_with_days() -> None:
    normalised = normalise_csv_row(
        passport_code="SA", passport_name="Saudi Arabia",
        destination_code="GB", destination_name="United Kingdom",
        requirement="30", csv_date="2026-06-14", retrieved="2026-09-20T09:00:00Z",
    )
    assert normalised is not None
    assert get_path(normalised.payload, "visa.type") == "visa free"
    assert get_path(normalised.payload, "visa.duration") == "30 days"
    assert get_path(normalised.payload, "source.layer") == "csv"


def test_normalise_csv_row_non_numeric_requirement_is_verbatim_with_no_duration() -> None:
    normalised = normalise_csv_row(
        passport_code="SA", passport_name="Saudi Arabia",
        destination_code="JP", destination_name="Japan",
        requirement="e-visa", csv_date="2026-06-14", retrieved="2026-09-20T09:00:00Z",
    )
    assert normalised is not None
    assert get_path(normalised.payload, "visa.type") == "e-visa"
    try:
        get_path(normalised.payload, "visa.duration")
        msg = "expected KeyError -- the CSV layer never carries a duration for prose values"
        raise AssertionError(msg)
    except KeyError:
        pass
    # This layer never carries these -- correctly absent, not guessed.
    for missing in ("visa.passport_validity", "visa.registration"):
        try:
            get_path(normalised.payload, missing)
            raise AssertionError(f"expected {missing} to be absent on the csv layer")
        except KeyError:
            pass


def test_normalise_csv_row_self_reference_is_filtered() -> None:
    normalised = normalise_csv_row(
        passport_code="SA", passport_name="Saudi Arabia",
        destination_code="SA", destination_name="Saudi Arabia",
        requirement="-1", csv_date="2026-06-14", retrieved="2026-09-20T09:00:00Z",
    )
    assert normalised is None


# ---------------------------------------------------------------------------
# map layer
# ---------------------------------------------------------------------------


def test_normalise_map_emits_category_never_type() -> None:
    """D8/D7 -- the map layer may never claim a specific visa type from an
    ambiguous colour; it emits `visa.category` and nothing under `visa.type`."""
    normalised = normalise_map(
        passport_code="SA", passport_name="Saudi Arabia",
        destination_code="JP", destination_name="Japan",
        category="visa on arrival or eVisa", map_date="2026-09-18T14:54:38+00:00",
        retrieved="2026-09-20T09:00:00Z",
    )
    assert get_path(normalised.payload, "visa.category") == "visa on arrival or eVisa"
    try:
        get_path(normalised.payload, "visa.type")
        raise AssertionError("map layer must never emit visa.type")
    except KeyError:
        pass
    assert get_path(normalised.payload, "source.layer") == "map"


# ---------------------------------------------------------------------------
# resolve_code() -- the alias table
# ---------------------------------------------------------------------------


def test_resolve_code_accepts_a_valid_two_letter_code() -> None:
    assert resolve_code("SA", countries=COUNTRIES) == "SA"


def test_resolve_code_resolves_a_country_name_case_and_accent_insensitively() -> None:
    assert resolve_code("japan", countries=COUNTRIES) == "JP"
    assert resolve_code("JAPAN", countries=COUNTRIES) == "JP"


def test_resolve_code_resolves_uk_alias() -> None:
    assert resolve_code("UK", countries=COUNTRIES) == "GB"
    assert resolve_code("Britain", countries=COUNTRIES) == "GB"


def test_resolve_code_resolves_ksa_alias() -> None:
    assert resolve_code("KSA", countries=COUNTRIES) == "SA"
    assert resolve_code("Saudi", countries=COUNTRIES) == "SA"


def test_resolve_code_returns_none_for_nonsense() -> None:
    assert resolve_code("Narnia", countries=COUNTRIES) is None


def test_resolve_code_returns_none_for_empty_string() -> None:
    assert resolve_code("", countries=COUNTRIES) is None
