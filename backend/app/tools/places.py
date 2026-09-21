"""Wikimedia place lookup -- the second justified API.

Entity lookup, not image search. A place name from a `judgement` segment
becomes a Wikipedia article: lead image, one-line extract, canonical URL,
revision date. No key, no quota.

Safety rejects (verified against the live API 2026-09-21):
  - HTTP 404 / missing page      -> not_found
  - disambiguation page          -> disambiguation
  - article with no lead image   -> no_image
  - timeout / transport error    -> timeout / http_error

The inappropriate-content surface is a place article's encyclopedic lead
image, not an open image search. Stated honestly in the README, not claimed
as sanitised.

`httpx` is imported here, not at main.py's module level -- same boundary as
vendor.py. Tests inject `httpx.MockTransport`.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Literal

import httpx

logger = logging.getLogger("sarjy")

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "Sarjy/0.1 (https://github.com; voice travel assistant take-home)"
TIMEOUT_S = 2.5
MAX_PLACES = 3

PlaceReason = Literal["not_found", "disambiguation", "no_image", "timeout", "http_error"]

# Article titles only -- rejects File:/Talk:/Wikipedia: and anything that
# looks like a URL. Letters, digits, spaces, common punctuation used in
# real English place names.
_TITLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,'’\-()]{0,79}$")


@dataclass(frozen=True)
class PlaceCard:
    name: str
    title: str | None
    description: str | None
    image_url: str | None
    page_url: str | None
    revision_date: str | None
    ok: bool
    reason: PlaceReason | None


def _failed(name: str, reason: PlaceReason) -> PlaceCard:
    return PlaceCard(
        name=name,
        title=None,
        description=None,
        image_url=None,
        page_url=None,
        revision_date=None,
        ok=False,
        reason=reason,
    )


class PlaceLookup:
    def __init__(
        self,
        *,
        timeout_s: float = TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._transport = transport
        self._cache: dict[str, PlaceCard] = {}

    async def lookup_many(self, names: list[str]) -> list[PlaceCard]:
        unique: list[str] = []
        seen: set[str] = set()
        for raw in names:
            name = " ".join(raw.split())
            key = name.lower()
            if not name or key in seen:
                continue
            seen.add(key)
            unique.append(name)
            if len(unique) >= MAX_PLACES:
                break
        if not unique:
            return []
        return list(await asyncio.gather(*[self.lookup(n) for n in unique]))

    async def lookup(self, name: str) -> PlaceCard:
        name = " ".join(name.split())
        cache_key = name.lower()
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        card = await self._fetch(name)
        self._cache[cache_key] = card
        return card

    async def _fetch(self, name: str) -> PlaceCard:
        if not _TITLE_RE.match(name):
            return _failed(name, "not_found")

        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "pageimages|extracts|info|pageprops",
            "ppprop": "disambiguation",
            "inprop": "url",
            "exintro": "1",
            "explaintext": "1",
            "exsentences": "1",
            "piprop": "thumbnail",
            "pithumbsize": "800",
            "redirects": "1",
            "titles": name,
        }
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_s, transport=self._transport, headers=headers
            ) as client:
                resp = await client.get(WIKI_API, params=params)
        except httpx.TimeoutException:
            logger.warning("places timeout name=%s", name)
            return _failed(name, "timeout")
        except httpx.HTTPError:
            logger.warning("places http error name=%s", name, exc_info=True)
            return _failed(name, "http_error")

        if resp.status_code == 404:
            return _failed(name, "not_found")
        if resp.status_code >= 400:
            logger.warning("places http_error status=%s name=%s", resp.status_code, name)
            return _failed(name, "http_error")

        try:
            body = resp.json()
        except ValueError:
            return _failed(name, "http_error")

        pages = (body.get("query") or {}).get("pages") or []
        if not pages:
            return _failed(name, "not_found")
        page = pages[0]
        if page.get("missing"):
            return _failed(name, "not_found")
        if "disambiguation" in (page.get("pageprops") or {}):
            return _failed(name, "disambiguation")

        title = page.get("title") or name
        extract = (page.get("extract") or "").strip() or None
        page_url = page.get("fullurl")
        touched = page.get("touched")
        thumb = (page.get("thumbnail") or {}).get("source")
        if not isinstance(thumb, str) or not thumb.startswith("https://"):
            return PlaceCard(
                name=name,
                title=title,
                description=extract,
                image_url=None,
                page_url=page_url if isinstance(page_url, str) else None,
                revision_date=touched if isinstance(touched, str) else None,
                ok=False,
                reason="no_image",
            )
        if "upload.wikimedia.org" not in thumb and "thumb.wikimedia.org" not in thumb:
            return _failed(name, "no_image")

        return PlaceCard(
            name=name,
            title=title,
            description=extract,
            image_url=thumb,
            page_url=page_url if isinstance(page_url, str) else None,
            revision_date=touched if isinstance(touched, str) else None,
            ok=True,
            reason=None,
        )


_singleton: PlaceLookup | None = None


def get_place_lookup() -> PlaceLookup:
    global _singleton
    if _singleton is None:
        _singleton = PlaceLookup()
    return _singleton
