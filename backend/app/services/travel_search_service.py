"""Travel-only destination search.

The search engine deliberately accepts two sources only:

* a curated catalog of 80 travel destinations with verified Wikimedia photos
  (works with no third-party keys), and
* Google Places results filtered through a strict travel allowlist.

General web or local-business results (electronics shops, plumbers, banks,
hospitals and similar) are never returned. If Google is unavailable the
curated catalog still answers city, country, landmark and travel-style queries.
"""

from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "destinations.json"

CATALOG_SOURCE = "Curated travel catalog"
GOOGLE_SOURCE = "Google Places API (New)"

# Query fragments that clearly describe something other than travel.
# The search engine is intentionally conservative: a travel planner should
# never surface repair shops, retailers, offices or local services.
NON_TRAVEL_TERMS = {
    "laptop", "laptop repair", "smartphone", "phone repair", "mobile repair",
    "mobile phone", "cell phone", "computer", "computer repair", "printer",
    "hardware", "electronics", "electronics store", "appliance", "appliances",
    "plumber", "electrician", "dentist", "doctor", "hospital", "clinic",
    "pharmacy", "bank", "atm", "money exchange", "currency exchange",
    "real estate", "property", "property rent", "car repair", "mechanic",
    "software", "job", "jobs", "resume", "cv", "insurance", "lawyer",
    "tax", "crypto", "wifi repair", "courier", "delivery", "delivery service",
    "supermarket", "grocery", "convenience store", "laundry", "tailor",
    "salon", "barber", "haircut", "gym", "school", "university", "tuition",
    "coaching", "office", "company", "repair", "repairs", "shop", "shops",
    "shopping", "shopping mall", "mall", "malls", "outlet", "outlets",
    "store", "stores", "retail", "furniture", "clothing", "fashion store",
    "jewelry", "jewellery", "boutique shop", "post office", "police",
    "government office", "visa office", "embassy", "sim card", "mobile data",
}

# Words that add no destination signal; used for a graceful fallback such as
# "restaurants in Tokyo" when Google Places is not configured.
STOPWORDS = {
    "a", "an", "the", "in", "at", "near", "to", "of", "for", "with", "and",
    "best", "top", "good", "great", "popular", "place", "places", "thing",
    "things", "do", "see", "visit", "guide", "guides", "travel", "trip",
    "trips", "tour", "tours", "destination", "destinations", "restaurant",
    "restaurants", "food", "hotel", "hotels", "stay", "stays", "attraction",
    "attractions", "museum", "museums", "activity", "activities", "spot",
    "spots", "around", "this", "that", "my", "your", "time", "weather",
    "when", "month", "months", "season", "seasons", "itinerary", "plan",
    "planner", "holiday", "holidays", "vacation", "vacations",
}

# Travel-style queries map onto catalog tags so discovery still works offline.
STYLE_TAGS = {
    "honeymoon": ["wellness", "beaches"],
    "romantic": ["wellness", "beaches"],
    "sun": ["beaches"],
    "sunny": ["beaches"],
    "warm": ["beaches"],
    "winter sun": ["beaches"],
    "snow": ["mountain"],
    "ski": ["mountain", "adventure"],
    "skiing": ["mountain", "adventure"],
    "trek": ["hiking", "adventure"],
    "trekking": ["hiking", "adventure"],
    "hike": ["hiking"],
    "hiking": ["hiking"],
    "party": ["nightlife"],
    "nightlife": ["nightlife"],
    "family": ["family"],
    "kids": ["family"],
    "luxury": ["wellness"],
    "budget": [],
    "backpacking": ["adventure"],
    "wildlife": ["wildlife"],
    "safari": ["wildlife"],
    "beach": ["beaches"],
    "beaches": ["beaches"],
    "island": ["beaches"],
    "islands": ["beaches"],
    "mountain": ["nature", "mountain"],
    "mountains": ["nature", "mountain"],
    "nature": ["nature"],
    "history": ["history"],
    "historic": ["history"],
    "culture": ["culture"],
    "art": ["art"],
    "museums": ["museums"],
    "food": ["food"],
    "coffee": ["coffee"],
    "photography": ["photography"],
    "adventure": ["adventure"],
    "wellness": ["wellness"],
    "yoga": ["wellness"],
    "festival": ["festivals"],
    "festivals": ["festivals"],
    "markets": ["markets"],
    "temples": ["temples"],
    "architecture": ["architecture"],
}

CATEGORY_TYPES = {
    "city": {"city"},
    "beach": {"beach", "island"},
    "nature": {"nature", "mountain"},
    "historical": {"historical"},
    "food": {"food"},
    "stay": {"stay"},
}

# Google Places types that count as travel discovery.
GOOGLE_TRAVEL_TYPES = {
    "tourist_attraction", "museum", "art_gallery", "park", "national_park",
    "beach", "hiking_area", "historical_landmark", "historical_place",
    "monument", "zoo", "aquarium", "amusement_park", "water_park",
    "wildlife_park", "garden", "botanical_garden", "observation_deck",
    "scenic_point", "plaza", "market", "restaurant", "cafe", "bar",
    "bakery", "lodging", "hotel", "resort_hotel", "motel", "campground",
    "rv_park", "visitor_center", "tour_agency", "travel_agency",
    "library", "place_of_worship", "church", "mosque", "synagogue",
    "hindu_temple", "buddhist_temple", "castle", "palace",
}

GOOGLE_GEO_TYPES = {
    "locality", "administrative_area_level_1", "administrative_area_level_2",
    "administrative_area_level_3", "country", "colloquial_area",
    "neighborhood", "sublocality", "sublocality_level_1",
}

GOOGLE_FOOD_TYPES = {"restaurant", "cafe", "bar", "bakery", "food"}
GOOGLE_STAY_TYPES = {"lodging", "hotel", "resort_hotel", "motel", "campground", "rv_park"}
GOOGLE_HISTORY_TYPES = {
    "museum", "art_gallery", "historical_landmark", "historical_place",
    "monument", "castle", "palace", "place_of_worship", "church", "mosque",
    "synagogue", "hindu_temple", "buddhist_temple",
}
GOOGLE_NATURE_TYPES = {
    "park", "national_park", "hiking_area", "garden", "botanical_garden",
    "zoo", "aquarium", "wildlife_park", "scenic_point", "observation_deck",
}
GOOGLE_BEACH_TYPES = {"beach"}

# If any of these appear, the result is a local business or service, not a
# travel discovery. A travel type alone is not enough to rescue it.
GOOGLE_NON_TRAVEL_TYPES = {
    "electronics_store", "hardware_store", "home_goods_store",
    "furniture_store", "clothing_store", "shoe_store", "jewelry_store",
    "book_store", "sporting_goods_store", "department_store",
    "shopping_mall", "supermarket", "grocery_store", "convenience_store",
    "liquor_store", "pet_store", "florist", "gift_shop", "store",
    "car_repair", "car_dealer", "car_rental", "car_wash", "gas_station",
    "bank", "atm", "finance", "insurance_agency", "real_estate_agency",
    "laundry", "beauty_salon", "hair_salon", "barber_shop", "spa",
    "dentist", "doctor", "hospital", "pharmacy", "drugstore",
    "veterinary_care", "school", "university", "primary_school",
    "secondary_school", "local_government_office", "post_office",
    "courthouse", "police", "fire_station", "embassy", "courthouse",
    "lawyer", "accounting", "moving_company", "storage", "courier",
    "plumber", "electrician", "roofing_contractor", "painter",
    "travel_agency", "tour_agency",
}

# Names containing these words are almost always shops or services even when
# Google attaches a broad "point_of_interest" type.
NON_TRAVEL_NAME_TERMS = {
    "repair", "repairs", "shop", "shops", "store", "stores", "mall",
    "outlet", "electronics", "mobile phone", "cell phone", "laptop",
    "computer", "printer", "hardware", "furniture", "plumber", "electrician",
    "dentist", "clinic", "pharmacy", "bank", "atm", "real estate",
    "insurance", "lawyer", "laundry", "tailor", "salon", "barber",
    "supermarket", "grocery", "convenience", "courier", "office",
}

DEFAULT_SUGGESTIONS = [
    "Kyoto", "Santorini", "Jaipur", "Bali", "Rome", "Cape Town",
    "Machu Picchu", "Maldives",
]

NON_TRAVEL_MESSAGE = (
    "Smart Travel Planner searches travel only. Try a city, country, "
    "landmark, beach, island or a travel style such as food or hiking."
)

NO_MATCH_MESSAGE = (
    "No travel matches found. Try a destination name or a travel style "
    "such as beaches, history, food or adventure."
)


def _normalise(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _contains_term(haystack: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack) is not None


@dataclass(slots=True)
class SearchOutcome:
    items: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    message: str | None = None
    matched: bool = False
    blocked: bool = False


class TravelSearchService:
    """Deterministic travel-only ranking with no external dependencies."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or CATALOG_PATH
        self._items = self._load()
        self._by_id = {item["id"]: item for item in self._items}

    def _load(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:  # pragma: no cover - packaging guard
            logger.error("Curated destination catalog could not be loaded: %s", exc)
            return []
        if not isinstance(raw, list):
            logger.error("Curated destination catalog must be a JSON list")
            return []
        for item in raw:
            item["_name"] = _normalise(item.get("name", ""))
            item["_country"] = _normalise(item.get("country", ""))
            item["_region"] = _normalise(item.get("region", ""))
            item["_tags"] = _normalise(" ".join(item.get("tags", [])))
            item["_text"] = _normalise(
                " ".join(
                    [
                        item.get("name", ""),
                        item.get("country", ""),
                        item.get("region", ""),
                        " ".join(item.get("tags", [])),
                        item.get("description", ""),
                        item.get("best_time", ""),
                    ]
                )
            )
        return raw

    # ------------------------------------------------------------- catalog
    def get(self, place_id: str) -> dict[str, Any] | None:
        return self._by_id.get(place_id)

    def all(self, *, category: str | None = None) -> list[dict[str, Any]]:
        return [item for item in self._items if self._matches_category(item, category)]

    def featured(self, limit: int = 12, *, category: str | None = None) -> list[dict[str, Any]]:
        items = [item for item in self._items if item.get("featured")]
        items += [item for item in self._items if not item.get("featured")]
        return [self.to_place(item) for item in items if self._matches_category(item, category)][:limit]

    def popular(self, limit: int = 12, *, category: str | None = None) -> list[dict[str, Any]]:
        items = sorted(
            self._items,
            key=lambda item: (not item.get("featured"), item.get("name", "")),
        )
        return [self.to_place(item) for item in items if self._matches_category(item, category)][:limit]

    @staticmethod
    def _matches_category(item: dict[str, Any], category: str | None) -> bool:
        if not category or category == "all":
            return True
        allowed = CATEGORY_TYPES.get(category)
        if allowed is None:
            return True
        return item.get("travel_type") in allowed

    # ------------------------------------------------------------- search
    def search(
        self,
        query: str,
        *,
        limit: int = 12,
        category: str | None = None,
    ) -> SearchOutcome:
        normalised = _normalise(query)
        if not normalised:
            return SearchOutcome(
                items=self.popular(limit, category=category),
                suggestions=DEFAULT_SUGGESTIONS[:6],
            )

        if self._is_non_travel(normalised):
            return SearchOutcome(
                suggestions=DEFAULT_SUGGESTIONS[:6],
                message=NON_TRAVEL_MESSAGE,
                blocked=True,
            )

        scored: list[tuple[float, dict[str, Any]]] = []
        for item in self._items:
            score = self._score(item, normalised, query)
            if score > 0:
                scored.append((score, item))

        # Travel-style discovery ("beaches", "honeymoon", "food").
        style_tags = STYLE_TAGS.get(normalised)
        if style_tags:
            for item in self._items:
                if set(style_tags) & set(item.get("tags", [])):
                    scored.append((75.0, item))

        # Merge duplicate items, keeping the best score.
        best: dict[str, tuple[float, dict[str, Any]]] = {}
        for score, item in scored:
            current = best.get(item["id"])
            if current is None or score > current[0]:
                best[item["id"]] = (score, item)

        ranked = sorted(
            best.values(),
            key=lambda pair: (
                -pair[0],
                not pair[1].get("featured"),
                pair[1].get("name", ""),
            ),
        )
        items = [
            self.to_place(item)
            for _, item in ranked
            if self._matches_category(item, category)
        ][:limit]

        if items:
            return SearchOutcome(items=items, matched=True)

        # Graceful fallback: strip travel filler words and retry the catalog.
        tokens = [token for token in normalised.split() if token not in STOPWORDS]
        if tokens and " ".join(tokens) != normalised:
            retry = self.search(" ".join(tokens), limit=limit, category=category)
            if retry.items:
                retry.message = (
                    "Live place search needs a Google Maps key; showing the "
                    "curated destination guide instead."
                )
                return retry

        return SearchOutcome(
            suggestions=DEFAULT_SUGGESTIONS[:6],
            message=NO_MATCH_MESSAGE,
        )

    def _is_non_travel(self, normalised: str) -> bool:
        for term in NON_TRAVEL_TERMS:
            if _contains_term(normalised, term):
                return True
        return False

    def _score(self, item: dict[str, Any], query: str, raw_query: str) -> float:
        name = item["_name"]
        tokens = [token for token in query.split() if token not in STOPWORDS]
        if not tokens:
            return 0.0
        searchable = " ".join(
            (name, item["_country"], item["_region"], item["_tags"])
        )
        matched_tokens = sum(
            1 for token in tokens if _contains_term(searchable, token)
        )
        required = max(1, math.ceil(len(tokens) * 0.6))
        if matched_tokens < required:
            return 0.0
        score = 0.0

        if query == name:
            score += 240
        elif name.startswith(query):
            score += 150
        elif _contains_term(name, query):
            score += 110
        if all(_contains_term(name, token) for token in tokens):
            score += 45

        for token in tokens:
            if _contains_term(name, token):
                score += 42
                if name.startswith(token):
                    score += 8
            if _contains_term(item["_country"], token):
                score += 20
            if _contains_term(item["_region"], token):
                score += 17
            if _contains_term(item["_tags"], token):
                score += 14
            if _contains_term(item["_text"], token):
                score += 3

        # Multi-word phrase match in description helps "Amalfi Coast" style names.
        if len(tokens) > 1 and _contains_term(item["_text"], query):
            score += 25
        return score

    # ----------------------------------------------------- Google filtering
    def filter_google(
        self, places: Iterable[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Keep only travel-relevant Google Places results.

        Shops, repair services, offices, banks and other local businesses are
        rejected even when Google attaches a broad type such as
        ``point_of_interest``. Remaining results are ranked by travel quality.
        """
        kept: list[dict[str, Any]] = []
        seen: set[str] = set()
        for place in places:
            types = {str(value) for value in (place.get("types") or [])}
            if place.get("business_status") == "CLOSED_PERMANENTLY":
                continue
            if types.intersection(GOOGLE_NON_TRAVEL_TYPES):
                continue
            if not types.intersection(GOOGLE_TRAVEL_TYPES | GOOGLE_GEO_TYPES):
                continue
            name_key = _normalise(str(place.get("name") or ""))
            if not name_key or name_key in seen:
                continue
            if any(_contains_term(name_key, term) for term in NON_TRAVEL_NAME_TERMS):
                continue
            travel_type = self.classify_google_types(types)
            if travel_type is None:
                continue
            seen.add(name_key)
            place = dict(place)
            place["travel_type"] = travel_type
            place["source"] = GOOGLE_SOURCE
            place["country"] = None
            kept.append(place)
        return self.rank_google(kept)

    @staticmethod
    def rank_google(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Prefer highly-rated, well-reviewed, strongly travel-typed places."""

        def score(place: dict[str, Any]) -> float:
            rating = float(place.get("rating") or 0)
            reviews = int(place.get("user_rating_count") or 0)
            types = {str(value) for value in (place.get("types") or [])}
            core = 3 if types.intersection(
                {"tourist_attraction", "museum", "national_park", "beach"}
            ) else 2 if types.intersection(
                {"park", "hiking_area", "historical_landmark", "zoo", "aquarium"}
            ) else 1
            return rating * 10 + min(reviews, 100_000) ** 0.5 + core * 5

        return sorted(places, key=score, reverse=True)

    @staticmethod
    def classify_google_types(types: set[str]) -> str | None:
        if types & GOOGLE_GEO_TYPES:
            return "city"
        if types & GOOGLE_STAY_TYPES:
            return "stay"
        if types & GOOGLE_FOOD_TYPES:
            return "food"
        if types & GOOGLE_HISTORY_TYPES:
            return "historical"
        if types & GOOGLE_BEACH_TYPES:
            return "beach"
        if types & GOOGLE_NATURE_TYPES:
            return "nature"
        if types & GOOGLE_TRAVEL_TYPES:
            return "attraction"
        return None

    # ----------------------------------------------------------- mapping
    @staticmethod
    def to_place(item: dict[str, Any]) -> dict[str, Any]:
        """Map a catalog entry onto the public PlaceSummary shape."""
        return {
            "place_id": item["id"],
            "name": item["name"],
            "formatted_address": item.get("address"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "rating": None,
            "user_rating_count": None,
            "price_level": None,
            "types": ["travel_destination", item.get("travel_type", "city"), *item.get("tags", [])[:4]],
            "category": None,
            "open_now": None,
            "business_status": "OPERATIONAL",
            "google_maps_uri": None,
            "photo_names": [],
            "opening_hours": [],
            "description": item.get("description"),
            "country": item.get("country"),
            "image_url": item.get("image_url"),
            "image_alt": item.get("image_alt"),
            "image_credit": item.get("image_credit"),
            "best_time": item.get("best_time"),
            "travel_type": item.get("travel_type"),
            "source": CATALOG_SOURCE,
        }


@lru_cache(maxsize=1)
def get_travel_search() -> TravelSearchService:
    return TravelSearchService()
