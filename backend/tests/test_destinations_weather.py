"""Destination, route, recommendation, and weather endpoint tests."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import create_app


def test_destination_search(client, auth_headers):
    response = client.get(
        "/api/v1/destinations/search",
        headers=auth_headers,
        params={"query": "Kyoto", "limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    # Curated Kyoto wins the de-duplication against the live "Kyoto" result.
    assert body["count"] == 1
    assert body["items"][0]["place_id"] == "curated-kyoto"
    assert body["items"][0]["image_url"].startswith("https://")
    assert body["travel_only"] is True
    assert "Curated travel catalog" in body["source"]


def test_travel_only_search_blocks_non_travel_queries(client, auth_headers):
    response = client.get(
        "/api/v1/destinations/search",
        headers=auth_headers,
        params={"query": "laptop repair", "limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["travel_only"] is True
    assert "travel only" in body["message"].lower()
    assert body["suggestions"]


def test_featured_destinations_are_public(client):
    response = client.get("/api/v1/destinations/featured", params={"limit": 6})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 6
    assert all(item["place_id"].startswith("curated-") for item in body["items"])
    assert all(item["image_url"] for item in body["items"])


def test_destination_details_and_missing_place(client, auth_headers):
    details = client.get(
        "/api/v1/destinations/attr_1", headers=auth_headers
    )
    assert details.status_code == 200
    body = details.json()
    assert body["name"] == "Kinkaku-ji"
    assert body["opening_hours"] == ["Monday: 9:00 AM – 5:00 PM"]
    assert body["website_uri"] == "https://example.com/attr_1"

    missing = client.get(
        "/api/v1/destinations/unknown_place", headers=auth_headers
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_photo_proxy_requires_auth_and_returns_image(client, auth_headers):
    no_auth = client.get(
        "/api/v1/destinations/photo",
        params={"photo_name": "places/dest_kyoto/photos/photo1"},
    )
    assert no_auth.status_code == 401

    response = client.get(
        "/api/v1/destinations/photo",
        headers=auth_headers,
        params={"photo_name": "places/dest_kyoto/photos/photo1", "max_width": 800},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"].startswith("private")
    assert response.content.startswith(b"\xff\xd8")


def test_route_calculation(client, auth_headers):
    response = client.post(
        "/api/v1/destinations/route",
        headers=auth_headers,
        json={
            "origin": {"latitude": 35.0, "longitude": 135.7, "name": "Hotel"},
            "destination": {"place_id": "attr_1"},
            "travel_mode": "WALK",
            "include_steps": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["distance_meters"] == 2400
    assert body["distance_km"] == 2.4
    assert body["duration_minutes"] == 10.0
    assert body["travel_mode"] == "WALK"
    assert body["source"] == "Google Routes API"


def test_route_requires_exactly_one_location_form(client, auth_headers):
    response = client.post(
        "/api/v1/destinations/route",
        headers=auth_headers,
        json={
            "origin": {
                "place_id": "attr_1",
                "latitude": 35.0,
                "longitude": 135.7,
            },
            "destination": {"address": "Kyoto Station"},
        },
    )
    assert response.status_code == 422


def test_nearby_attractions_and_restaurants(client, auth_headers):
    attractions = client.get(
        "/api/v1/destinations/dest_kyoto/attractions",
        headers=auth_headers,
        params={"limit": 2},
    )
    assert attractions.status_code == 200
    assert attractions.json()["count"] == 2
    assert attractions.json()["destination_name"] == "Kyoto"
    assert all(
        item["category"] == "attraction" for item in attractions.json()["items"]
    )

    restaurants = client.get(
        "/api/v1/destinations/dest_kyoto/restaurants",
        headers=auth_headers,
    )
    assert restaurants.status_code == 200
    assert restaurants.json()["count"] == 2
    assert all(
        item["category"] == "restaurant" for item in restaurants.json()["items"]
    )


def test_nearby_type_allowlist(client, auth_headers):
    invalid = client.get(
        "/api/v1/destinations/dest_kyoto/nearby",
        headers=auth_headers,
        params={"types": "not_a_real_google_type"},
    )
    assert invalid.status_code == 422
    assert "not_a_real_google_type" in str(invalid.json()["error"]["details"])

    valid = client.get(
        "/api/v1/destinations/dest_kyoto/nearby",
        headers=auth_headers,
        params={"types": "tourist_attraction,museum"},
    )
    assert valid.status_code == 200
    assert valid.json()["included_types"] == ["tourist_attraction", "museum"]


def test_recommendations_are_ranked_with_real_places_data(client, auth_headers):
    response = client.post(
        "/api/v1/recommendations/",
        headers=auth_headers,
        json={
            "destination": "Kyoto",
            "interests": ["history"],
            "budget_level": "moderate",
            "include_hotels": True,
            "limit": 5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["destination"] == "Kyoto"
    assert len(body["attractions"]) == 3
    assert len(body["restaurants"]) == 2
    assert len(body["hotels"]) == 1
    assert body["attractions"][0]["score"] >= body["attractions"][-1]["score"]
    assert body["attractions"][0]["reason"]
    assert body["source"] == "Google Places API (New)"
    assert body["ranking_method"].startswith("Deterministic")


def test_recommendations_can_exclude_hotels(client, auth_headers):
    response = client.post(
        "/api/v1/recommendations/",
        headers=auth_headers,
        json={"destination": "Kyoto", "include_hotels": False},
    )
    assert response.status_code == 200
    assert response.json()["hotels"] == []


def test_weather_with_forecast_coverage(client, auth_headers, start_date):
    response = client.get(
        "/api/v1/weather/Kyoto",
        headers=auth_headers,
        params={
            "start_date": start_date.isoformat(),
            "end_date": (start_date + timedelta(days=1)).isoformat(),
            "units": "metric",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["destination"] == "Kyoto"
    assert body["forecast_covers_requested_dates"] is True
    assert body["current"]["condition"]["description"] == "clear sky"
    assert body["forecast"][0]["summary"] == "Clear skies"
    assert "OpenWeather" in body["source"]


def test_weather_date_validation(client, auth_headers):
    partial = client.get(
        "/api/v1/weather/Kyoto",
        headers=auth_headers,
        params={"start_date": date.today().isoformat()},
    )
    assert partial.status_code == 422

    reversed_dates = client.get(
        "/api/v1/weather/Kyoto",
        headers=auth_headers,
        params={
            "start_date": (date.today() + timedelta(days=2)).isoformat(),
            "end_date": date.today().isoformat(),
        },
    )
    assert reversed_dates.status_code == 422


def test_unconfigured_integrations_return_503(settings, auth_headers):
    unconfigured = settings.model_copy(
        update={
            "google_maps_api_key": None,
            "openweather_api_key": None,
            "gemini_api_key": None,
        }
    )
    application = create_app(unconfigured)
    with TestClient(application) as client:
        search = client.get(
            "/api/v1/destinations/search",
            headers=auth_headers,
            params={"query": "Kyoto"},
        )
        assert search.status_code == 200
        assert search.json()["count"] >= 1
        assert search.json()["items"][0]["place_id"] == "curated-kyoto"
        assert search.json()["source"] == "Curated travel catalog"

        # Curated detail pages keep working without Google Maps.
        curated = client.get(
            "/api/v1/destinations/curated-kyoto", headers=auth_headers
        )
        assert curated.status_code == 200
        assert curated.json()["best_time"]
        assert curated.json()["image_url"].startswith("https://")

        weather = client.get("/api/v1/weather/Kyoto", headers=auth_headers)
        assert weather.status_code == 503

        photo = client.get(
            "/api/v1/destinations/photo",
            headers=auth_headers,
            params={"photo_name": "places/dest_kyoto/photos/photo1"},
        )
        assert photo.status_code == 503

        generate = client.post(
            "/api/v1/itineraries/generate",
            headers=auth_headers,
            json={
                "destination": "Kyoto",
                "start_date": (date.today() + timedelta(days=10)).isoformat(),
                "end_date": (date.today() + timedelta(days=11)).isoformat(),
                "total_budget": 1000,
            },
        )
        # The deterministic planner keeps generation usable without Google/AI.
        assert generate.status_code == 201
        assert generate.json()["generation_metadata"]["ai_model"].startswith(
            "deterministic planner"
        )
