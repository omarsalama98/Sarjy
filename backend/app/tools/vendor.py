"""TravelBuddyTool -- the real VisaTool. Four layers, fixed order, never
reordered (D7):

    warm cache (this pair, fetched live before -- zero cost)
      -> live /v2/visa/check (1 request, only above the reserve)
        -> cached VisaMap colour bucket (0 cost, category only, ambiguous)
          -> vendored passport-index CSV (0 cost, category only, community data)
            -> refuse, route to the embassy link. Never guess.

Map and CSV are cheap-and-complete-for-category but carry no duration, no
passport-validity rule and no registration -- only live and its warm cache
carry those. Layers 3/4 exist so a quota outage or a rate limit still
answers *something*, correctly labelled as degraded; they never substitute
for the live call, which is why live sits ABOVE them, not below (D7's
argument in full is in the block plan; the old cost-only waterfall made the
live call never fire, because the CSV alone answers every pair).

`httpx` is imported here, not anywhere main.py's module graph reaches at
load time -- Invariant 3 / this module's own docstring precedent in
gemini_llm.py. Resolved lazily via factory.get_tool().
"""

import csv as csv_module
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.providers.base import ToolResult
from app.tools.normalise import normalise_csv_row, normalise_live, normalise_map, resolve_code

logger = logging.getLogger("sarjy")

_APP_DIR = Path(__file__).resolve().parents[1]  # backend/app, or /root/app under Modal

# The vendored fork's own stated correction date (visualpharm/visa-free-dataset
# README: "corrections based on verified embassy and consular website
# announcements", applied 14 June 2026) -- spoken on every CSV-layer answer,
# per the "every answer states which layer served it and how fresh it is"
# rule (.claude/rules/tools/vendor-client.md).
CSV_CORRECTIONS_DATE = "2026-06-14"


def _resolve_data_dir() -> Path:
    """Mirrors main.py's _resolve_dist(): two_up for a normal checkout,
    one_up for Modal's add_local_dir layout (see modal_app.py's comment on
    why /root/data exists)."""
    two_up = _APP_DIR.parent.parent / "data"  # repo_root/data, local checkout
    one_up = _APP_DIR.parent / "data"  # /root/data, under Modal
    for candidate in (two_up, one_up):
        if candidate.is_dir():
            return candidate
    return two_up


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _embassy_url(destination_name: str) -> str:
    """F2 -- the refusal route, derived rather than left null. The live
    layer gets its embassy_url straight from the vendor body
    (normalise.py); the map/csv/no_coverage layers never call the vendor
    for this field at all, so without this they always spoke a refusal
    with nothing on screen to route to. Same host and slug shape as the
    one live example this codebase has seen (data/reference/visa_reqs_SA_JP.json:
    "saudiarabia" for Saudi Arabia) -- lowercase, non-alphanumeric characters
    dropped. Best-effort: a routing hint on screen, never a sourced fact,
    so an unresolved slug costs nothing but a dead link."""
    slug = "".join(ch for ch in destination_name.lower() if ch.isalnum())
    return f"https://www.embassypages.com/{slug}"


class TravelBuddyTool:
    name = "travel-buddy"

    def __init__(
        self,
        *,
        api_key: str | None,
        host: str,
        timeout_s: float,
        ledger: Any,  # QuotaLedger -- Any here so this module never imports app.tools.quota's
        # modal.Dict-touching import path unless it's actually constructed (kept simple: quota.py
        # itself has no provider SDK import at module level, so this is a style choice, not a
        # correctness one -- typed loosely to keep this constructor's own import list short).
        data_dir: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,  # tests inject httpx.MockTransport
        # here; production leaves this None, httpx's own "make a real connection" default.
    ) -> None:
        self._api_key = api_key
        self._host = host
        self._timeout_s = timeout_s
        self._ledger = ledger
        self._transport = transport

        data_dir = data_dir if data_dir is not None else _resolve_data_dir()
        self._cache_dir = data_dir / "cache"
        self._reference_dir = data_dir / "reference"

        self._countries = self._load_countries()
        self._colour_legend = self._load_colour_legend()
        self._visa_maps = self._load_visa_maps()
        self._csv_index, self._csv_rows_loaded = self._load_csv()

    # -- reference data, loaded once at construction ------------------------

    def _load_countries(self) -> list[dict[str, Any]]:
        countries: list[dict[str, Any]] = []
        for name in ("passports.json", "destinations.json"):
            path = self._reference_dir / name
            if not path.is_file():
                logger.warning("travel_buddy: reference file missing: %s", path)
                continue
            body = json.loads(path.read_text())
            entries = body.get("data") or body.get("destinations") or []
            countries.extend(entries)
        return countries

    def _load_colour_legend(self) -> dict[str, str]:
        path = self._reference_dir / "colour-legend.json"
        if not path.is_file():
            logger.warning("travel_buddy: colour-legend.json missing -- map layer disabled")
            return {}
        body = json.loads(path.read_text())
        legend: dict[str, str] = body.get("legend", {})
        return legend

    def _load_visa_maps(self) -> dict[str, dict[str, Any]]:
        """Keyed by passport code. Only SA is committed today (D7/D9's
        1-request-per-passport rule) -- any other passport simply has no
        map-layer coverage and falls straight to the CSV."""
        maps: dict[str, dict[str, Any]] = {}
        path = self._reference_dir / "visa_map_SA.json"
        if path.is_file():
            body = json.loads(path.read_text())
            data = body.get("data", {})
            meta = body.get("meta", {})
            maps["SA"] = {
                "colors": data.get("colors", {}),
                "generated_at": meta.get("generated_at"),
            }
        return maps

    def _load_csv(self) -> tuple[dict[tuple[str, str], str], bool]:
        path = self._reference_dir / "passport-index-tidy-iso2.csv"
        index: dict[tuple[str, str], str] = {}
        if not path.is_file():
            logger.warning("travel_buddy: passport-index CSV missing -- csv layer disabled")
            return index, False
        with path.open(newline="", encoding="utf-8") as f:
            # Read the REAL header line rather than assuming its case/order
            # (Open Question #2) -- confirmed live: "Passport,Destination,Requirement".
            reader = csv_module.DictReader(f)
            for row in reader:
                index[(row["Passport"], row["Destination"])] = row["Requirement"]
        return index, True

    def _country_name(self, code: str) -> str:
        for c in self._countries:
            if c.get("iso_alpha2") == code:
                name = c.get("name")
                return str(name) if name else code
        return code

    def _pair_only(self, passport: str, destination: str) -> dict[str, Any]:
        """A resolved pair with nothing else -- what a `no_coverage` result
        carries so card.fact_card() has something to build a refusal card
        from. Never a `sourced`/`quoted` field: this dict has no `visa.*` or
        `source.*` keys at all, so a `sourced` segment naming one still
        correctly rejects on absent_path."""
        return {
            "pair": {
                "passport": passport,
                "passport_name": self._country_name(passport),
                "destination": destination,
                "destination_name": self._country_name(destination),
            }
        }

    # -- the four layers ------------------------------------------------

    async def lookup(self, *, passport: str, destination: str) -> ToolResult:
        passport_code = resolve_code(passport, countries=self._countries)
        destination_code = resolve_code(destination, countries=self._countries)
        if passport_code is None or destination_code is None:
            # V8 -- a graceful re-ask, never a guess.
            return ToolResult(ok=False, reason="unknown_place")

        cached = self._from_cache(passport_code, destination_code)
        if cached is not None:
            return cached

        if self._api_key and self._ledger.can_spend():
            live = await self._from_live(passport_code, destination_code)
            if live is not None:
                self._write_cache(passport_code, destination_code, live)
                return live
            # Falls through to layers 3/4 -- every failure branch inside
            # _from_live already logged which V-row it hit.
        elif not self._api_key:
            logger.info("travel_buddy: RAPIDAPI_KEY not configured -- live layer skipped (V9)")
        else:
            logger.info("travel_buddy: below quota reserve -- live layer skipped (V5)")

        mapped = self._from_map(passport_code, destination_code)
        if mapped is not None:
            return mapped

        csv_result = self._from_csv(passport_code, destination_code)
        if csv_result is not None:
            return csv_result

        # V6 -- nothing covers this pair. Refuse, but still route to an
        # embassy link (F2) -- the destination is known even though its
        # coverage isn't, so the link is derived rather than left null. The
        # pair itself WAS resolved, so it still goes in `payload` --
        # card.fact_card() needs it to build the covered=False refusal card
        # (V8 is the only failure with no pair to report at all).
        pair_payload = self._pair_only(passport_code, destination_code)
        return ToolResult(
            ok=False,
            reason="no_coverage",
            payload=pair_payload,
            embassy_url=_embassy_url(self._country_name(destination_code)),
        )

    def quota(self) -> Any:
        return self._ledger.status()

    # -- layer 1: warm cache ---------------------------------------------

    def _cache_path(self, passport: str, destination: str) -> Path:
        return self._cache_dir / f"{passport}_{destination}.json"

    def _from_cache(self, passport: str, destination: str) -> ToolResult | None:
        path = self._cache_path(passport, destination)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError):
            logger.warning("travel_buddy: unreadable warm cache entry %s", path, exc_info=True)
            return None
        citation = raw.get("citation") or "Travel Buddy"
        return ToolResult(
            ok=True,
            payload=raw.get("payload", {}),
            layer="cache",
            citation=f"{citation} (cached)",
            source_url=raw.get("source_url"),
            source_date=raw.get("source_date"),
            reason="ok",
            embassy_url=raw.get("embassy_url"),
            spent_request=False,
        )

    def _write_cache(self, passport: str, destination: str, result: ToolResult) -> None:
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path(passport, destination).write_text(
                json.dumps(
                    {
                        "payload": result.payload,
                        "citation": result.citation,
                        "source_url": result.source_url,
                        "source_date": result.source_date,
                        "embassy_url": result.embassy_url,
                    }
                )
            )
        except OSError:
            # A cache-write failure must not fail the turn that just
            # succeeded -- it only means the NEXT lookup for this pair
            # spends a request it could have saved.
            logger.warning("travel_buddy: failed to write warm cache", exc_info=True)

    # -- layer 2: live -----------------------------------------------------

    async def _from_live(self, passport: str, destination: str) -> ToolResult | None:
        # Spent the instant we commit to firing -- V7: a request that's in
        # flight when a barge cancels this coroutine still counts, so the
        # ledger never drifts optimistic.
        self._ledger.spend(1)

        url = f"https://{self._host}/v2/visa/check"
        headers = {"X-RapidAPI-Key": self._api_key or "", "X-RapidAPI-Host": self._host}
        body_in = {"passport": passport, "destination": destination}

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_s, transport=self._transport
            ) as client:
                resp = await client.post(url, headers=headers, json=body_in)
        except httpx.TimeoutException:
            logger.warning(
                "travel_buddy live timeout passport=%s destination=%s after %dms",
                passport, destination, round((time.monotonic() - t0) * 1000),
            )
            return None  # V2
        except httpx.HTTPError:
            logger.warning("travel_buddy live network error", exc_info=True)
            return None  # V4-adjacent -- a transport failure, not a parse failure

        if resp.status_code == 429:
            logger.warning("travel_buddy live rate limited (429)")
            return None  # V1
        if resp.status_code >= 400:
            logger.warning("travel_buddy live http_error status=%d", resp.status_code)
            return None

        try:
            raw_body = resp.json()
        except ValueError:
            logger.warning("travel_buddy live: response body did not parse as JSON")
            return None  # V4

        retrieved = _now_iso()
        try:
            normalised = normalise_live(raw_body, retrieved=retrieved)
        except Exception:
            logger.warning("travel_buddy live: normalise_live() raised", exc_info=True)
            return None  # V4

        if "type" not in normalised.payload.get("visa", {}):
            # V3 -- a 200 with no usable rule. Never improvised.
            logger.info("travel_buddy live: 200 but no usable visa rule in body")
            return None

        citation = f"Travel Buddy — visa requirements, checked {retrieved[:10]}"
        return ToolResult(
            ok=True,
            payload=normalised.payload,
            layer="live",
            citation=citation,
            source_url=None,
            source_date=normalised.payload.get("source", {}).get("generated_at"),
            reason="ok",
            embassy_url=normalised.embassy_url,
            spent_request=True,
        )

    # -- layer 3: cached VisaMap -------------------------------------------

    def _from_map(self, passport: str, destination: str) -> ToolResult | None:
        bucket = self._visa_maps.get(passport)
        if bucket is None:
            return None  # no committed map for this passport -- fall to CSV

        colour = next(
            (c for c, codes in bucket["colors"].items() if destination in codes.split(",")), None
        )
        if colour is None:
            return None

        category = self._colour_legend.get(colour, colour)
        map_date = bucket.get("generated_at") or "an unknown date"
        retrieved = _now_iso()
        normalised = normalise_map(
            passport_code=passport,
            passport_name=self._country_name(passport),
            destination_code=destination,
            destination_name=self._country_name(destination),
            category=category,
            map_date=map_date,
            retrieved=retrieved,
        )
        citation = f"Travel Buddy — cached visa map, {map_date[:10]}"
        return ToolResult(
            ok=True,
            payload=normalised.payload,
            layer="map",
            citation=citation,
            source_url=None,
            source_date=map_date,
            reason="ok",
            embassy_url=_embassy_url(self._country_name(destination)),  # F2
            spent_request=False,
        )

    # -- layer 4: vendored CSV ----------------------------------------------

    def _from_csv(self, passport: str, destination: str) -> ToolResult | None:
        requirement = self._csv_index.get((passport, destination))
        if requirement is None:
            return None

        retrieved = _now_iso()
        normalised = normalise_csv_row(
            passport_code=passport,
            passport_name=self._country_name(passport),
            destination_code=destination,
            destination_name=self._country_name(destination),
            requirement=requirement,
            csv_date=CSV_CORRECTIONS_DATE,
            retrieved=retrieved,
        )
        if normalised is None:
            return None  # the "-1" self-reference artifact -- never served

        citation = f"passport-index community dataset, corrections to {CSV_CORRECTIONS_DATE}"
        return ToolResult(
            ok=True,
            payload=normalised.payload,
            layer="csv",
            citation=citation,
            source_url=None,
            source_date=CSV_CORRECTIONS_DATE,
            reason="ok",
            embassy_url=_embassy_url(self._country_name(destination)),  # F2
            spent_request=False,
        )
