"""TravelBuddyTool -- the four layers in D7's order, V1-V6/V9 against a
stubbed httpx transport. Zero live requests, ever -- `httpx.MockTransport`
answers every call; a handler that's never supposed to fire raises
AssertionError if it's reached, so "never called" is actually proven, not
just unasserted.

Reference data comes from the REAL committed files, copied into a tmp dir
so the vendor's warm-cache writes never touch the real data/cache/.
"""

import json
import shutil
from pathlib import Path

import httpx
import pytest

from app.providers.base import QuotaStatus
from app.tools.quota import QuotaLedger, _InProcessStore
from app.tools.vendor import TravelBuddyTool

_REAL_REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    shutil.copytree(_REAL_REFERENCE_DIR, tmp_path / "reference")
    (tmp_path / "cache").mkdir()
    return tmp_path


def _fixed_ledger(*, remaining: int = 71) -> QuotaLedger:
    reserve = 40
    spent = 120 - reserve - remaining
    return QuotaLedger(total=120, reserve=reserve, store=_InProcessStore(spent))


def _never_called_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"live request must not have been sent: {request.url}")

    return httpx.MockTransport(handler)


def _fixed_response_transport(
    *, status: int = 200, json_body: object = None, text: str | None = None
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if text is not None:
            return httpx.Response(status, text=text)
        return httpx.Response(status, json=json_body)

    return httpx.MockTransport(handler)


def _raising_transport(exc: Exception) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return httpx.MockTransport(handler)


_SA_JP_PATH = Path(__file__).resolve().parents[2] / "data" / "reference" / "visa_reqs_SA_JP.json"
SA_JP_LIVE_BODY = json.loads(_SA_JP_PATH.read_text())


def _tool(
    data_dir: Path,
    *,
    transport: httpx.AsyncBaseTransport,
    api_key: str | None = "key",
    ledger: QuotaLedger | None = None,
) -> TravelBuddyTool:
    return TravelBuddyTool(
        api_key=api_key,
        host="travel-buddy.p.rapidapi.com",
        timeout_s=4.0,
        ledger=ledger or _fixed_ledger(),
        data_dir=data_dir,
        transport=transport,
    )


# ---------------------------------------------------------------------------
# The happy path -- live succeeds.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_success_lands_on_the_live_layer(data_dir: Path) -> None:
    transport = _fixed_response_transport(status=200, json_body=SA_JP_LIVE_BODY)
    tool = _tool(data_dir, transport=transport)

    result = await tool.lookup(passport="SA", destination="JP")

    assert result.ok is True
    assert result.layer == "live"
    assert result.spent_request is True
    assert result.payload["visa"]["type"] == "eVisa"


@pytest.mark.asyncio
async def test_a_successful_live_call_writes_the_warm_cache(data_dir: Path) -> None:
    transport = _fixed_response_transport(status=200, json_body=SA_JP_LIVE_BODY)
    tool = _tool(data_dir, transport=transport)
    await tool.lookup(passport="SA", destination="JP")

    cache_file = data_dir / "cache" / "SA_JP.json"
    assert cache_file.is_file()


@pytest.mark.asyncio
async def test_warm_cache_serves_without_touching_live(data_dir: Path) -> None:
    (data_dir / "cache" / "SA_JP.json").write_text(
        json.dumps(
            {
                "payload": {
                    "pair": {"passport": "SA", "destination": "JP"},
                    "visa": {"type": "eVisa"},
                },
                "citation": "Travel Buddy — checked 2026-09-19",
                "source_url": None,
                "source_date": "2026-09-19T00:00:00Z",
                "embassy_url": "https://example.com/embassy",
            }
        )
    )
    tool = _tool(data_dir, transport=_never_called_transport())

    result = await tool.lookup(passport="SA", destination="JP")

    assert result.ok is True
    assert result.layer == "cache"
    assert result.spent_request is False
    assert result.embassy_url == "https://example.com/embassy"


# ---------------------------------------------------------------------------
# V1-V4 -- live fails, falls to the map layer (SA has a committed map).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v1_rate_limited_falls_to_map_layer(data_dir: Path) -> None:
    transport = _fixed_response_transport(status=429)
    tool = _tool(data_dir, transport=transport)

    result = await tool.lookup(passport="SA", destination="JP")

    assert result.ok is True
    assert result.layer == "map"
    assert result.spent_request is False  # V1 never counts a 429 as a successful spend... but the
    # attempt itself still incremented the ledger (V7) -- checked separately below.


@pytest.mark.asyncio
async def test_v1_still_counts_the_spend_even_though_it_failed(data_dir: Path) -> None:
    """V7 -- an attempt that fired counts, whether or not it succeeded."""
    ledger = _fixed_ledger(remaining=71)
    transport = _fixed_response_transport(status=429)
    tool = _tool(data_dir, transport=transport, ledger=ledger)

    await tool.lookup(passport="SA", destination="JP")

    assert ledger.status().remaining == 70


@pytest.mark.asyncio
async def test_v2_timeout_falls_to_map_layer(data_dir: Path) -> None:
    transport = _raising_transport(httpx.TimeoutException("timed out"))
    tool = _tool(data_dir, transport=transport)

    result = await tool.lookup(passport="SA", destination="JP")

    assert result.ok is True
    assert result.layer == "map"


@pytest.mark.asyncio
async def test_v3_200_with_no_usable_rule_falls_to_map_layer(data_dir: Path) -> None:
    body = {"data": {"passport": {"code": "SA"}, "destination": {"code": "JP"}}, "meta": {}}
    transport = _fixed_response_transport(status=200, json_body=body)
    tool = _tool(data_dir, transport=transport)

    result = await tool.lookup(passport="SA", destination="JP")

    assert result.ok is True
    assert result.layer == "map"


@pytest.mark.asyncio
async def test_v4_malformed_body_falls_to_map_layer(data_dir: Path) -> None:
    transport = _fixed_response_transport(status=200, text="not json at all")
    tool = _tool(data_dir, transport=transport)

    result = await tool.lookup(passport="SA", destination="JP")

    assert result.ok is True
    assert result.layer == "map"


@pytest.mark.asyncio
async def test_v4_http_error_falls_to_map_layer(data_dir: Path) -> None:
    transport = _fixed_response_transport(status=500)
    tool = _tool(data_dir, transport=transport)

    result = await tool.lookup(passport="SA", destination="JP")

    assert result.ok is True
    assert result.layer == "map"


# ---------------------------------------------------------------------------
# V5 -- below the reserve, live is never called at all.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v5_below_reserve_never_calls_live_serves_from_map(data_dir: Path) -> None:
    ledger = _fixed_ledger(remaining=0)
    tool = _tool(data_dir, transport=_never_called_transport(), ledger=ledger)

    result = await tool.lookup(passport="SA", destination="JP")

    assert result.ok is True
    assert result.layer == "map"
    assert ledger.status().spent == ledger.status().total - ledger.status().reserve  # unchanged


# ---------------------------------------------------------------------------
# V6 -- nothing covers the pair at all.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v6_no_layer_covers_it_refuses(data_dir: Path) -> None:
    # JP->JP: a genuinely resolvable pair (both real codes), live fails,
    # JP has no committed VisaMap, and the CSV's own row for this pair is
    # the documented "-1" self-reference artifact -- filtered, never
    # served (V6's real-data case, not a synthetic one).
    transport = _fixed_response_transport(status=500)
    tool = _tool(data_dir, transport=transport, api_key="key")

    result = await tool.lookup(passport="JP", destination="JP")

    assert result.ok is False
    assert result.reason == "no_coverage"
    assert result.payload["pair"]["passport"] == "JP"  # the pair still carried for card.fact_card()


# ---------------------------------------------------------------------------
# V8 -- unresolvable place.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v8_unresolvable_place_is_unknown_place(data_dir: Path) -> None:
    tool = _tool(data_dir, transport=_never_called_transport())

    result = await tool.lookup(passport="SA", destination="Narnia")

    assert result.ok is False
    assert result.reason == "unknown_place"


# ---------------------------------------------------------------------------
# V9 -- no RAPIDAPI_KEY configured.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v9_no_api_key_never_calls_live_serves_from_map(data_dir: Path) -> None:
    tool = _tool(data_dir, transport=_never_called_transport(), api_key=None)

    result = await tool.lookup(passport="SA", destination="JP")

    assert result.ok is True
    assert result.layer == "map"


# ---------------------------------------------------------------------------
# CSV fallback -- a passport with no committed map at all.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_csv_layer_serves_when_no_map_is_committed_for_the_passport(data_dir: Path) -> None:
    transport = _fixed_response_transport(status=500)  # live fails
    tool = _tool(data_dir, transport=transport)

    # JP has no committed VisaMap in data/reference/ -- only SA does.
    result = await tool.lookup(passport="JP", destination="GB")

    assert result.ok is True
    assert result.layer == "csv"


def test_quota_reflects_the_ledger(data_dir: Path) -> None:
    ledger = _fixed_ledger(remaining=55)
    tool = _tool(data_dir, transport=_never_called_transport(), ledger=ledger)
    status = tool.quota()
    assert isinstance(status, QuotaStatus)
    assert status.remaining == 55


# ---------------------------------------------------------------------------
# F2 -- every layer routes a refusal to a known embassy link, not null.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_f2_no_coverage_carries_a_derived_embassy_url(data_dir: Path) -> None:
    transport = _fixed_response_transport(status=500)
    tool = _tool(data_dir, transport=transport, api_key="key")

    result = await tool.lookup(passport="JP", destination="JP")  # V6's real no-coverage case

    assert result.ok is False
    assert result.reason == "no_coverage"
    assert result.embassy_url == "https://www.embassypages.com/japan"


@pytest.mark.asyncio
async def test_f2_map_layer_carries_a_derived_embassy_url(data_dir: Path) -> None:
    transport = _raising_transport(httpx.TimeoutException("timed out"))
    tool = _tool(data_dir, transport=transport)

    result = await tool.lookup(passport="SA", destination="JP")

    assert result.ok is True
    assert result.layer == "map"
    assert result.embassy_url == "https://www.embassypages.com/japan"


@pytest.mark.asyncio
async def test_f2_csv_layer_carries_a_derived_embassy_url(data_dir: Path) -> None:
    transport = _fixed_response_transport(status=500)
    tool = _tool(data_dir, transport=transport)

    result = await tool.lookup(passport="JP", destination="GB")  # SA has no map -- falls to CSV

    assert result.ok is True
    assert result.layer == "csv"
    assert result.embassy_url == "https://www.embassypages.com/unitedkingdom"
