"""PlaceLookup -- Wikimedia entity lookup against a stubbed httpx transport.
Zero live requests. A handler that's never supposed to fire raises
AssertionError if it's reached.
"""

import json

import httpx
import pytest

from app.tools.places import PlaceLookup

_KYOTO_PAGE = {
    "query": {
        "pages": [
            {
                "pageid": 1,
                "title": "Kyoto",
                "extract": "Kyoto is a city in the Kansai region of Japan.",
                "fullurl": "https://en.wikipedia.org/wiki/Kyoto",
                "touched": "2026-09-14T15:53:35Z",
                "thumbnail": {
                    "source": "https://upload.wikimedia.org/wikipedia/commons/thumb/k/kyoto.jpg/800px-kyoto.jpg",
                    "width": 800,
                    "height": 533,
                },
            }
        ]
    }
}

_SPRINGFIELD_PAGE = {
    "query": {
        "pages": [
            {
                "pageid": 2,
                "title": "Springfield",
                "pageprops": {"disambiguation": ""},
                "fullurl": "https://en.wikipedia.org/wiki/Springfield",
            }
        ]
    }
}

_MISSING_PAGE = {"query": {"pages": [{"title": "Zzzqqxnotaplace", "missing": True}]}}

_NO_IMAGE_PAGE = {
    "query": {
        "pages": [
            {
                "pageid": 3,
                "title": "Quiet Hamlet",
                "extract": "A small place with no lead image.",
                "fullurl": "https://en.wikipedia.org/wiki/Quiet_Hamlet",
                "touched": "2026-01-01T00:00:00Z",
            }
        ]
    }
}


def _transport_for(title: str, body: object, *, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        got = request.url.params.get("titles")
        if got != title:
            raise AssertionError(f"unexpected titles={got!r}, wanted {title!r}")
        assert "Sarjy/" in request.headers.get("user-agent", "")
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_happy_path_returns_sourced_photo() -> None:
    lookup = PlaceLookup(transport=_transport_for("Kyoto", _KYOTO_PAGE))
    card = await lookup.lookup("Kyoto")
    assert card.ok is True
    assert card.title == "Kyoto"
    assert card.description and "Kansai" in card.description
    assert card.image_url and card.image_url.startswith("https://upload.wikimedia.org/")
    assert card.page_url == "https://en.wikipedia.org/wiki/Kyoto"
    assert card.revision_date == "2026-09-14T15:53:35Z"
    assert card.reason is None


@pytest.mark.asyncio
async def test_missing_page_is_not_found() -> None:
    lookup = PlaceLookup(transport=_transport_for("Zzzqqxnotaplace", _MISSING_PAGE))
    card = await lookup.lookup("Zzzqqxnotaplace")
    assert card.ok is False
    assert card.reason == "not_found"
    assert card.image_url is None


@pytest.mark.asyncio
async def test_disambiguation_is_rejected() -> None:
    lookup = PlaceLookup(transport=_transport_for("Springfield", _SPRINGFIELD_PAGE))
    card = await lookup.lookup("Springfield")
    assert card.ok is False
    assert card.reason == "disambiguation"
    assert card.image_url is None


@pytest.mark.asyncio
async def test_no_thumbnail_is_no_image() -> None:
    lookup = PlaceLookup(transport=_transport_for("Quiet Hamlet", _NO_IMAGE_PAGE))
    card = await lookup.lookup("Quiet Hamlet")
    assert card.ok is False
    assert card.reason == "no_image"
    assert card.title == "Quiet Hamlet"
    assert card.description is not None
    assert card.image_url is None


@pytest.mark.asyncio
async def test_timeout_is_visible() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    lookup = PlaceLookup(transport=httpx.MockTransport(handler), timeout_s=0.01)
    card = await lookup.lookup("Kyoto")
    assert card.ok is False
    assert card.reason == "timeout"


@pytest.mark.asyncio
async def test_http_404_is_not_found() -> None:
    lookup = PlaceLookup(transport=_transport_for("Nowhere", {}, status=404))
    card = await lookup.lookup("Nowhere")
    assert card.ok is False
    assert card.reason == "not_found"


@pytest.mark.asyncio
async def test_invalid_title_never_hits_the_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"must not fetch {request.url}")

    lookup = PlaceLookup(transport=httpx.MockTransport(handler))
    card = await lookup.lookup("https://evil.example/x")
    assert card.ok is False
    assert card.reason == "not_found"


@pytest.mark.asyncio
async def test_cache_does_not_refetch() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_KYOTO_PAGE)

    lookup = PlaceLookup(transport=httpx.MockTransport(handler))
    a = await lookup.lookup("Kyoto")
    b = await lookup.lookup("kyoto")
    assert a.ok and b.ok
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_lookup_many_caps_at_three_and_dedupes() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        title = request.url.params.get("titles") or ""
        seen.append(title)
        page = json.loads(json.dumps(_KYOTO_PAGE))
        page["query"]["pages"][0]["title"] = title
        return httpx.Response(200, json=page)

    lookup = PlaceLookup(transport=httpx.MockTransport(handler))
    cards = await lookup.lookup_many(["Kyoto", "kyoto", "Osaka", "Nara", "Kobe"])
    assert [c.name for c in cards] == ["Kyoto", "Osaka", "Nara"]
    assert seen == ["Kyoto", "Osaka", "Nara"]
