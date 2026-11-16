"""Keyless open-data discovery: OpenStreetMap geocoding + Wikipedia.

Google Places and AI providers are optional integrations that need API keys.
This service keeps the app fully working without any of them by using free,
key-less open data:

- **Nominatim** (OpenStreetMap) geocodes a destination name to coordinates.
- **Wikipedia geosearch** returns the notable landmarks around those
  coordinates — temples, museums, parks, castles, beaches and so on.
- **Wikipedia extracts** supply an honest one-paragraph description and a
  freely-licensed thumbnail for each landmark.

Everything is cached with the same unbounded-entry TTL cache used for Maps and
Weather, so repeated requests never re-hit the network.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

import httpx

from app.core.exceptions import ExternalServiceError
from app.models.enums import ActivityCategory
from app.utils.cache import AsyncTTLCache

logger = logging.getLogger(__name__)

WIKIPEDIA_SOURCE = "Wikipedia (open data)"
USER_AGENT = (
    "SmartTravelPlanner/1.0 "
    "(https://github.com/harshasamala9-lab/smart-travel-planner; educational project)"
)

# Wikipedia geosearch returns every geolocated article around a point, including
# schools, depots, hotels and — worse — historical *events* (battles, famines,
# treaties) that happen to have coordinates. A travel planner should never
# surface those.
WIKI_BLOCKLIST_TERMS = {
    "school", "university", "college", "institute", "academy", "hospital",
    "clinic", "hotel", "hostel", "motel", "embassy", "consulate", "bank",
    "company", "office", "headquarters", "shopping", "mall", "store", "shop",
    "supermarket", "factory", "refinery", "power station", "power plant",
    "substation", "railway station", "metro station", "subway station",
    "train station", "bus station", "bus stop", "station", "airport", "air base",
    "airfield", "harbour", "harbor", "port", "dockyard", "shipyard",
    "depot", "yard", "warehouse", "prison", "cemetery", "crematorium",
    "parking", "garage", "list of", "disambiguation", "stub",
    # Historical events and other non-visitable articles that still carry
    # geocoordinates.
    "battle", "siege", "rebellion", "revolt", "uprising", "revolution",
    "massacre", "famine", "plague", "epidemic", "pandemic", "earthquake",
    "typhoon", "hurricane", "flood", "eruption", "bombing", "air raid",
    "world war", "civil war", "war of", "wars of", "conquest of",
    "occupation of", "annexation", "treaty of", "treaty", "incident",
    "riot of", "riots", "coup of", "coup d", "assassination", "genocide",
    "execution of", "disaster", "expedition", "timeline", "history of",
    "annals", "chronicle", "dynasty", "shogunate", "reign of", "era of",
    "attack", "protests", "protest of", "parade", "shooting of", "strike of",
    # Governments, agencies and administrative bodies.
    "department", "ministry", "agency", "bureau", "council", "prefecture",
    "government", "diocese", "archdiocese", "commissariat", "embassy",
    "municipal", "regiment", "battalion", "naval base", "garrison",
}

WIKI_TYPE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("museum", "gallery", "exhibition"), "museum"),
    (("temple", "shrine", "church", "cathedral", "basilica", "mosque",
      "synagogue", "monastery", "convent"), "heritage"),
    (("castle", "palace", "fort", "fortress", "citadel", "ruins", "tower",
      "monument", "memorial", "mausoleum", "tomb", "bridge"), "heritage"),
    (("park", "garden", "grove", "forest", "arboretum", "conservatory"), "park"),
    (("beach", "island", "bay", "cape", "coast", "lagoon", "peninsula"), "beach"),
    (("mountain", "hill", "volcano", "cave", "waterfall", "river", "lake",
      "valley", "canyon", "gorge", "peak"), "nature"),
    (("market", "bazaar", "food street"), "food"),
    (("stadium", "arena", "zoo", "aquarium", "observatory"), "family"),
)


def _sentences(text: str, *, max_chars: int = 480, max_count: int = 2) -> str:
    """Return the first ``max_count`` sentences of ``text`` within a budget."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    keep: list[str] = []
    used = 0
    for sentence in parts:
        if not sentence:
            continue
        if used + len(sentence) > max_chars:
            if keep:
                break
            # The first sentence alone is over budget: hard-truncate it.
            return sentence[: max_chars - 1].rsplit(" ", 1)[0] + "…"
        keep.append(sentence)
        used += len(sentence) + 1
        if len(keep) >= max_count:
            break
    if not keep:  # Extremely long first sentence.
        return cleaned[:max_chars].rsplit(" ", 1)[0] + "…"
    return " ".join(keep)


def _classify(title: str, extract: str) -> str:
    haystack = f"{title} {extract}".casefold()
    for needles, travel_type in WIKI_TYPE_RULES:
        if any(needle in haystack for needle in needles):
            return travel_type
    return "landmark"


def _is_blocked(title: str) -> bool:
    folded = title.casefold()
    return any(term in folded for term in WIKI_BLOCKLIST_TERMS)


def _raise_on_api_error(data: dict[str, Any]) -> None:
    """MediaWiki reports request problems inside HTTP 200 bodies."""
    error = data.get("error")
    if error:
        info = str(error.get("info") or error.get("code") or "unknown error")
        raise ExternalServiceError(f"Wikipedia API rejected the request: {info}")


class WikipediaService:
    """Open-data discovery used when key-based providers are unavailable."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        geo_cache_ttl_seconds: int = 21_600,
        extract_cache_ttl_seconds: int = 86_400,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://en.wikipedia.org/w/api.php",
        geocoder_url: str = "https://nominatim.openstreetmap.org/search",
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._base_url = base_url
        self._geocoder_url = geocoder_url
        self._geo_cache = AsyncTTLCache(geo_cache_ttl_seconds)
        self._article_cache = AsyncTTLCache(extract_cache_ttl_seconds)
        self._geocode_cache = AsyncTTLCache(geo_cache_ttl_seconds)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------ HTTP
    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise ExternalServiceError("Open-data lookup timed out.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalServiceError("Open-data lookup is unavailable.") from exc

    # -------------------------------------------------------------- geocoding
    async def geocode(self, query: str) -> dict[str, Any] | None:
        """Resolve a free-text destination to coordinates via OpenStreetMap."""
        cleaned = (query or "").strip()
        if len(cleaned) < 2:
            return None
        key = ("geocode", cleaned.casefold())

        def _fetch() -> dict[str, Any] | None:
            return self._geocode_once(cleaned)

        try:
            return await self._geocode_cache.get_or_set(key, _fetch)
        except ExternalServiceError:
            return None

    async def _geocode_once(self, query: str) -> dict[str, Any] | None:
        data = await self._get_json(
            self._geocoder_url,
            {
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "accept-language": "en",
                "addressdetails": 0,
            },
        )
        if not data:
            return None
        top = data[0]
        try:
            latitude = float(top["lat"])
            longitude = float(top["lon"])
        except (KeyError, TypeError, ValueError):
            return None
        if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
            return None
        display = str(top.get("display_name") or query)
        parts = display.split(",")
        return {
            "name": str(top.get("name") or parts[0].strip() or query),
            "display_name": display,
            "country": (parts[-1].strip() if len(parts) > 1 else None) or None,
            "latitude": latitude,
            "longitude": longitude,
        }

    # ------------------------------------------------------------- geosearch
    async def geosearch(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int = 10_000,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Notable geolocated Wikipedia articles around a coordinate."""
        radius = max(1_000, min(int(radius_m), 10_000))
        wanted = max(1, min(int(limit), 50))
        key = ("geosearch", round(latitude, 4), round(longitude, 4), radius, wanted)

        def _fetch() -> list[dict[str, Any]]:
            return self._geosearch_once(
                latitude=latitude, longitude=longitude,
                radius_m=radius, limit=wanted,
            )

        try:
            return await self._geo_cache.get_or_set(key, _fetch)
        except ExternalServiceError:
            return []

    async def _geosearch_once(
        self, *, latitude: float, longitude: float, radius_m: int, limit: int
    ) -> list[dict[str, Any]]:
        data = await self._get_json(
            self._base_url,
            {
                "action": "query",
                "list": "geosearch",
                "gscoord": f"{latitude}|{longitude}",
                "gsradius": radius_m,
                "gslimit": limit,
                # Only primary (main subject) coordinates — keeps landmarks,
                # drops satellite points of interest clutter.
                "gsprimary": "primary",
                "format": "json",
                "formatversion": "2",
            },
        )
        _raise_on_api_error(data)
        results = data.get("query", {}).get("geosearch", [])
        places: list[dict[str, Any]] = []
        seen: set[int] = set()
        for item in results:
            try:
                page_id = int(item["pageid"])
                lat = float(item["lat"])
                lon = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if page_id in seen:
                continue
            seen.add(page_id)
            places.append(
                {
                    "pageid": page_id,
                    "title": str(item.get("title") or ""),
                    "latitude": lat,
                    "longitude": lon,
                    "distance_m": item.get("dist"),
                }
            )
        return places

    # --------------------------------------------------------------- extracts
    async def _pages_payload(self, *, pageids: list[int]) -> dict[int, dict[str, Any]]:
        """Fetch intro extracts, thumbnails and coordinates in one batch."""
        if not pageids:
            return {}

        def _fetch() -> dict[int, dict[str, Any]]:
            return self._pages_payload_once(pageids=pageids)

        return await self._article_cache.get_or_set(
            ("pages", tuple(sorted(pageids))), _fetch
        )

    async def _pages_payload_once(self, *, pageids: list[int]) -> dict[int, dict[str, Any]]:
        data = await self._get_json(
            self._base_url,
            {
                "action": "query",
                "pageids": "|".join(str(pid) for pid in pageids),
                "prop": "extracts|pageimages|coordinates",
                "exintro": 1,
                "explaintext": 1,
                "exlimit": "max",
                "piprop": "thumbnail",
                "pithumbsize": 480,
                "format": "json",
                "formatversion": "2",
            },
        )
        _raise_on_api_error(data)
        pages: dict[int, dict[str, Any]] = {}
        for page in data.get("query", {}).get("pages", []):
            try:
                page_id = int(page["pageid"])
            except (KeyError, TypeError, ValueError):
                continue
            coordinates = page.get("coordinates") or []
            thumbnail = (page.get("thumbnail") or {}).get("source")
            pages[page_id] = {
                "pageid": page_id,
                "title": str(page.get("title") or ""),
                "extract": str(page.get("extract") or ""),
                "image_url": thumbnail,
                "latitude": float(coordinates[0]["lat"]) if coordinates else None,
                "longitude": float(coordinates[0]["lon"]) if coordinates else None,
                "url": f"https://en.wikipedia.org/?curid={page_id}",
            }
        return pages

    async def article_summary(self, pageid: int) -> dict[str, Any] | None:
        """Description, image and coordinates for one Wikipedia article."""
        try:
            pages = await self._pages_payload(pageids=[int(pageid)])
        except ExternalServiceError:
            return None
        page = pages.get(int(pageid))
        if not page:
            return None
        page = dict(page)
        page["travel_type"] = _classify(page["title"], page["extract"])
        page["description"] = _sentences(page["extract"], max_chars=600, max_count=3)
        return page

    # ------------------------------------------------------- public shorthands
    async def nearby_attractions(
        self,
        *,
        name: str,
        latitude: float | None,
        longitude: float | None,
        limit: int = 12,
        radius_m: int = 10_000,
    ) -> list[dict[str, Any]]:
        """Travel-ready attraction summaries near a destination, no keys needed."""
        if latitude is None or longitude is None:
            located = await self.geocode(name)
            if located is None:
                return []
            latitude, longitude = located["latitude"], located["longitude"]

        raw = await self.geosearch(
            latitude=latitude, longitude=longitude,
            radius_m=radius_m, limit=min(40, limit * 4),
        )
        own_name = name.casefold().strip()
        travel = [
            item
            for item in raw
            if not _is_blocked(item["title"])
            and item["title"].casefold().strip() != own_name
        ]
        if not travel:
            return []
        travel = travel[: max(limit, 1)]
        try:
            pages = await self._pages_payload(pageids=[item["pageid"] for item in travel])
        except ExternalServiceError:
            pages = {}

        summaries: list[dict[str, Any]] = []
        for item in travel:
            page = pages.get(item["pageid"], {})
            title = page.get("title") or item["title"]
            extract = page.get("extract") or ""
            travel_type = _classify(title, extract)
            summaries.append(
                {
                    "place_id": f"wiki-{item['pageid']}",
                    "name": title,
                    "formatted_address": f"{title} ({name})",
                    "latitude": page.get("latitude") or item["latitude"],
                    "longitude": page.get("longitude") or item["longitude"],
                    "rating": None,
                    "user_rating_count": None,
                    "price_level": None,
                    "types": [travel_type, "wikipedia", "tourist_attraction"],
                    "category": ActivityCategory.ATTRACTION.value,
                    "open_now": None,
                    "business_status": "OPERATIONAL",
                    "google_maps_uri": (
                        "https://www.google.com/maps/search/?api=1&query="
                        f"{item['latitude']},{item['longitude']}"
                    ),
                    "photo_names": [],
                    "opening_hours": [],
                    "description": _sentences(extract, max_chars=400, max_count=2),
                    "editorial_summary": _sentences(extract, max_chars=400, max_count=2),
                    "country": None,
                    "image_url": page.get("image_url"),
                    "image_alt": title,
                    "image_credit": "Wikipedia / Wikimedia Commons contributors",
                    "best_time": None,
                    "travel_type": travel_type,
                    "source": WIKIPEDIA_SOURCE,
                }
            )
        return summaries


@lru_cache(maxsize=1)
def get_wikipedia_service() -> WikipediaService:
    from app.config import get_settings

    settings = get_settings()
    return WikipediaService(
        timeout_seconds=settings.wikipedia_timeout_seconds,
        geo_cache_ttl_seconds=settings.wikipedia_geo_cache_ttl_seconds,
        extract_cache_ttl_seconds=settings.wikipedia_extract_cache_ttl_seconds,
    )
