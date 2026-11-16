"""Unit tests for the keyless Wikipedia + OpenStreetMap discovery service.

Every HTTP exchange is faked with ``httpx.MockTransport`` so these tests prove
request shaping, blocklist filtering, caching and description budgeting without
touching the network.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.services.wikipedia_service import (
    USER_AGENT,
    WikipediaService,
    _sentences,
)

GEOCODE_BODY: list[dict[str, Any]] = [
    {
        "lat": "35.0116",
        "lon": "135.7681",
        "display_name": "Kyoto, Kyoto Prefecture, Japan",
        "name": "Kyoto",
    }
]

GEOSEARCH_BODY: dict[str, Any] = {
    "query": {
        "geosearch": [
            {"pageid": 1, "title": "Kinkaku-ji", "lat": 35.0394, "lon": 135.7292, "dist": 2100},
            {"pageid": 2, "title": "Kyoto Station", "lat": 34.9858, "lon": 135.7588, "dist": 3000},
            {"pageid": 3, "title": "Nijō Castle", "lat": 35.0142, "lon": 135.7481, "dist": 2400},
            {"pageid": 1, "title": "Kinkaku-ji", "lat": 35.0394, "lon": 135.7292, "dist": 2100},
        ]
    }
}

PAGES_BODY: dict[str, Any] = {
    "query": {
        "pages": [
            {
                "pageid": 1,
                "title": "Kinkaku-ji",
                "extract": (
                    "Kinkaku-ji is a Zen Buddhist temple in Kyoto, Japan. "
                    "It is one of the most popular buildings in Japan. "
                    "The top two floors are completely covered in gold leaf."
                ),
                "thumbnail": {"source": "https://upload.wikimedia.org/kinkaku.jpg"},
                "coordinates": [{"lat": 35.0394, "lon": 135.7292}],
            },
            {
                "pageid": 3,
                "title": "Nijō Castle",
                "extract": (
                    "Nijō Castle is a flat castle in Kyoto, Japan. "
                    "It was built in 1626 during the Edo period."
                ),
                "thumbnail": {"source": "https://upload.wikimedia.org/nijo.jpg"},
                "coordinates": [{"lat": 35.0142, "lon": 135.7481}],
            },
        ]
    }
}


class RequestLog:
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []

    def urls(self) -> list[str]:
        return [str(call.url) for call in self.calls]


def wikipedia_client(log: RequestLog, bodies: dict[str, Any]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        log.calls.append(request)
        for fragment, body in bodies.items():
            if fragment in str(request.url):
                return httpx.Response(200, json=body)
        return httpx.Response(404, json={})

    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "pytest"},
    )


def make_service(log: RequestLog, bodies: dict[str, Any]) -> WikipediaService:
    return WikipediaService(client=wikipedia_client(log, bodies))


@pytest.mark.asyncio
async def test_geocode_uses_nominatim_with_user_agent_and_caches():
    log = RequestLog()
    service = make_service(
        log,
        {"nominatim.openstreetmap.org": GEOCODE_BODY},
    )
    first = await service.geocode("Kyoto")
    assert first is not None
    assert first["latitude"] == 35.0116
    assert first["longitude"] == 135.7681
    assert first["name"] == "Kyoto"
    assert first["country"] == "Japan"
    second = await service.geocode("Kyoto")
    assert second == first
    assert len(log.calls) == 1  # served from the TTL cache


def test_default_client_sends_descriptive_user_agent():
    # Nominatim policy requires a descriptive User-Agent on the real client.
    service = WikipediaService()
    assert service._client.headers["User-Agent"] == USER_AGENT


@pytest.mark.asyncio
async def test_geocode_returns_none_on_failure_or_garbage():
    log = RequestLog()

    def handler(request: httpx.Request) -> httpx.Response:
        log.calls.append(request)
        return httpx.Response(503, json={"error": "overloaded"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), headers={"User-Agent": "pytest"}
    )
    service = WikipediaService(client=client)
    assert await service.geocode("Kyoto") is None
    assert await service.geocode("x") is None  # too short, no request made


@pytest.mark.asyncio
async def test_nearby_attractions_filters_non_travel_and_builds_wiki_ids():
    log = RequestLog()
    service = make_service(
        log,
        {
            "nominatim.openstreetmap.org": GEOCODE_BODY,
            "action=query&list=geosearch": GEOSEARCH_BODY,
            "prop=extracts": PAGES_BODY,
        },
    )
    items = await service.nearby_attractions(
        name="Kyoto", latitude=None, longitude=None, limit=5
    )
    names = [item["name"] for item in items]
    assert "Kyoto Station" not in names  # transit stop, never an attraction
    assert names == ["Kinkaku-ji", "Nijō Castle"]
    ids = [item["place_id"] for item in items]
    assert ids == ["wiki-1", "wiki-3"]
    for item in items:
        assert item["category"] == "attraction"
        assert item["source"] == "Wikipedia (open data)"
        assert item["image_url"]
        assert item["image_credit"].startswith("Wikipedia")
        assert item["description"]
        assert item["google_maps_uri"].startswith("https://www.google.com/maps")
    # One batched extracts request for both pages.
    page_requests = [url for url in log.urls() if "prop=extracts" in url]
    assert len(page_requests) == 1
    assert "pageids=1%7C3" in page_requests[0] or "pageids=1|3" in page_requests[0]


@pytest.mark.asyncio
async def test_nearby_attractions_is_cached():
    log = RequestLog()
    service = make_service(
        log,
        {
            "nominatim.openstreetmap.org": GEOCODE_BODY,
            "action=query&list=geosearch": GEOSEARCH_BODY,
            "prop=extracts": PAGES_BODY,
        },
    )
    first = await service.nearby_attractions(name="Kyoto", latitude=None, longitude=None)
    second = await service.nearby_attractions(name="Kyoto", latitude=None, longitude=None)
    assert len(first) == len(second) == 2
    assert len(log.calls) == 3  # geocode + geosearch + extracts, no repeats


@pytest.mark.asyncio
async def test_nearby_attractions_handles_empty_geosearch():
    log = RequestLog()
    service = make_service(
        log,
        {
            "nominatim.openstreetmap.org": GEOCODE_BODY,
            "action=query&list=geosearch": {"query": {"geosearch": []}},
        },
    )
    assert await service.nearby_attractions(name="Nowhere", latitude=None, longitude=None) == []


@pytest.mark.asyncio
async def test_article_summary_returns_budgeted_description_and_type():
    log = RequestLog()
    service = make_service(log, {"prop=extracts": PAGES_BODY})
    page = await service.article_summary(1)
    assert page is not None
    assert page["title"] == "Kinkaku-ji"
    assert page["travel_type"] == "heritage"  # temple in title/extract
    assert page["url"] == "https://en.wikipedia.org/?curid=1"
    assert len(page["description"]) <= 620
    assert page["description"].endswith(".")
    assert await service.article_summary(999) is None  # not in payload


@pytest.mark.asyncio
async def test_geosearch_radius_is_clamped():
    log = RequestLog()
    service = make_service(
        log,
        {"action=query&list=geosearch": GEOSEARCH_BODY},
    )
    await service.geosearch(latitude=35.0, longitude=135.7, radius_m=99_000, limit=99)
    request = log.calls[0]
    params = dict(request.url.params)
    assert params["gsradius"] == "10000"
    assert params["gslimit"] == "50"


def test_sentences_budgeting():
    text = "One. Two. Three. Four."
    assert _sentences(text, max_count=2) == "One. Two."
    assert _sentences("   A  very   long   sentence   ") == "A very long sentence"
    long_word = "x" * 600
    assert len(_sentences(long_word, max_chars=120)) <= 121
    assert _sentences("") == ""
