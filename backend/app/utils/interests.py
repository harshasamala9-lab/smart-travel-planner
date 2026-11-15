"""Map travel interests to Google Places (New) place types."""

from __future__ import annotations

from app.models.enums import TransportationPreference, TravelMode

INTEREST_PLACE_TYPES: dict[str, list[str]] = {
    "food": ["restaurant", "cafe"],
    "foodie": ["restaurant", "cafe"],
    "culinary": ["restaurant", "cafe"],
    "history": ["tourist_attraction", "museum", "historical_landmark"],
    "historical": ["tourist_attraction", "museum", "historical_landmark"],
    "culture": ["museum", "art_gallery", "performing_arts_theater"],
    "art": ["art_gallery", "museum"],
    "museum": ["museum"],
    "nature": ["park", "national_park", "hiking_area"],
    "outdoors": ["park", "national_park", "hiking_area"],
    "hiking": ["hiking_area", "national_park"],
    "beach": ["beach"],
    "adventure": ["hiking_area", "amusement_park", "zoo"],
    "family": ["zoo", "aquarium", "amusement_park"],
    "kids": ["zoo", "aquarium", "amusement_park"],
    "shopping": ["shopping_mall", "market"],
    "nightlife": ["bar", "night_club"],
    "entertainment": ["performing_arts_theater", "amusement_park", "night_club"],
    "religion": ["church", "mosque", "hindu_temple", "synagogue"],
    "wellness": ["spa", "park"],
    "architecture": ["tourist_attraction", "historical_landmark"],
    "photography": ["tourist_attraction", "park", "art_gallery"],
    "sports": ["stadium", "sports_complex"],
}

RESTAURANT_TYPES = ["restaurant", "cafe"]
HOTEL_TYPES = ["lodging"]
DEFAULT_ATTRACTION_TYPES = [
    "tourist_attraction",
    "museum",
    "park",
    "art_gallery",
    "historical_landmark",
]

# Google Places rejects unknown includedTypes. Keep a conservative allowlist.
ALLOWED_NEARBY_TYPES = {
    "tourist_attraction",
    "museum",
    "park",
    "national_park",
    "hiking_area",
    "beach",
    "art_gallery",
    "historical_landmark",
    "performing_arts_theater",
    "restaurant",
    "cafe",
    "bar",
    "night_club",
    "shopping_mall",
    "market",
    "zoo",
    "aquarium",
    "amusement_park",
    "church",
    "mosque",
    "hindu_temple",
    "synagogue",
    "spa",
    "stadium",
    "sports_complex",
    "lodging",
}


def place_types_for_interests(
    interests: list[str],
    *,
    default: list[str] | None = None,
) -> list[str]:
    types: list[str] = []
    for interest in interests:
        key = interest.strip().lower()
        candidates = INTEREST_PLACE_TYPES.get(key)
        if candidates is None:
            # Allow simple substring matches such as "local food" -> food.
            for keyword, mapped in INTEREST_PLACE_TYPES.items():
                if keyword in key:
                    candidates = mapped
                    break
        for place_type in candidates or []:
            if place_type in ALLOWED_NEARBY_TYPES and place_type not in types:
                types.append(place_type)
    if not types:
        types = list(default or DEFAULT_ATTRACTION_TYPES)
    return types[:10]


def travel_mode_for_preference(preference: TransportationPreference | str) -> TravelMode:
    value = preference.value if isinstance(preference, TransportationPreference) else str(preference)
    return {
        "walking": TravelMode.WALK,
        "public_transport": TravelMode.TRANSIT,
        "taxi_rideshare": TravelMode.DRIVE,
        "rental_car": TravelMode.DRIVE,
        "mixed": TravelMode.DRIVE,
        "none": TravelMode.WALK,
    }.get(value, TravelMode.DRIVE)


def matched_interests(place_types: list[str], interests: list[str]) -> list[str]:
    matches: list[str] = []
    type_set = set(place_types)
    for interest in interests:
        key = interest.strip().lower()
        mapped = INTEREST_PLACE_TYPES.get(key, [])
        if not mapped:
            for keyword, values in INTEREST_PLACE_TYPES.items():
                if keyword in key:
                    mapped = values
                    break
        if type_set.intersection(mapped) and interest not in matches:
            matches.append(interest)
    return matches
