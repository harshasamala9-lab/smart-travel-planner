"""Itinerary generation, validation, persistence, editing, and ownership tests."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import jwt

from .conftest import TEST_AUTH_BASE_URL, TEST_JWT_SECRET


def _generate_payload(start: date, **overrides):
    payload = {
        "destination": "Kyoto, Japan",
        "destination_place_id": "dest_kyoto",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=1)).isoformat(),
        "travellers": 2,
        "total_budget": 5000,
        "currency": "USD",
        "interests": ["history", "food"],
        "activities": ["temples", "markets"],
        "accommodation_preference": "midrange_hotel",
        "transportation_preference": "mixed",
        "pace": "balanced",
        "include_routes": True,
    }
    payload.update(overrides)
    return payload


def _second_user_headers() -> dict[str, str]:
    subject = uuid.uuid4()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(subject),
            "email": "other@example.com",
            "name": "Other Traveler",
            "role": "authenticated",
            "aud": TEST_AUTH_BASE_URL,
            "iss": TEST_AUTH_BASE_URL,
            "iat": now.timestamp(),
            "exp": now.timestamp() + 900,
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_generate_itinerary_is_persisted_and_enriched(
    client, auth_headers, start_date, fake_maps
):
    response = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date),
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["title"] == "Kyoto in Bloom"
    assert body["destination_name"] == "Kyoto"
    assert body["status"] == "generated"
    assert len(body["days"]) == 2
    assert body["days"][0]["activities"][0]["name"] == "Kinkaku-ji"
    assert body["days"][0]["activities"][0]["address"]
    assert body["days"][0]["activities"][1]["category"] == "restaurant"
    assert body["days"][0]["activities"][0]["route_to_next"]["distance_meters"] == 2400
    assert body["days"][0]["activities"][0]["cost_type"] == "estimated"
    assert body["budget_estimate"]["cost_type"] == "estimated"
    assert body["budget_estimate"]["line_items"]["accommodation"] > 0
    assert body["budget_estimate"]["line_items"]["food"] > 0
    assert body["budget_estimate"]["within_budget"] is True
    assert body["weather_summary"]["available"] is True
    assert body["generation_metadata"]["ai_generation_attempts"] == 1
    assert body["generation_metadata"]["candidate_counts"]["attractions"] == 3
    assert body["recommendations"]["source"] == "Google Places API (New)"
    assert body["recommendations"]["recommended_hotel_place_id"] == "hotel_1"
    assert fake_maps.route_calls == 3

    listing = client.get("/api/v1/itineraries", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == body["id"]

    detail = client.get(
        f"/api/v1/itineraries/{body['id']}", headers=auth_headers
    )
    assert detail.status_code == 200
    assert detail.json()["days"][1]["activities"][0]["place_id"] == "attr_3"


def test_generate_without_routes(client, auth_headers, start_date, fake_maps):
    response = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date, include_routes=False),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["days"][0]["activities"][0]["route_to_next"] is None
    assert fake_maps.route_calls == 0


def test_generation_rejects_unsupported_currency(client, auth_headers, start_date):
    response = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date, currency="XYZ"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_generation_rejects_past_dates(client, auth_headers):
    past = date.today() - timedelta(days=1)
    response = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(past),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_generation_rejects_trip_over_configured_limit(
    client, auth_headers, start_date
):
    response = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(
            start_date, end_date=(start_date + timedelta(days=30)).isoformat()
        ),
    )
    assert response.status_code == 422
    assert "longer" in response.json()["error"]["message"].lower()


def test_ai_output_is_retried_then_accepted(
    client, auth_headers, start_date, fake_gemini
):
    fake_gemini.invalid_attempts = 1
    response = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date),
    )
    assert response.status_code == 201
    assert fake_gemini.calls == 2
    assert "PREVIOUS ATTEMPT WAS REJECTED" in fake_gemini.prompts[1]
    assert response.json()["generation_metadata"]["ai_generation_attempts"] == 2


def test_ai_output_rejected_after_retry_uses_deterministic_fallback(
    client, auth_headers, start_date, fake_gemini
):
    fake_gemini.invalid_attempts = 2
    response = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["generation_metadata"]["ai_model"].startswith("deterministic planner")
    assert any("built-in travel planner" in warning for warning in body["warnings"])
    listing = client.get("/api/v1/itineraries", headers=auth_headers)
    assert listing.json()["total"] == 1


def test_over_budget_is_reported_as_estimate(client, auth_headers, start_date):
    response = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(
            start_date,
            total_budget=10,
            accommodation_preference="luxury_hotel",
        ),
    )
    assert response.status_code == 201
    budget = response.json()["budget_estimate"]
    assert budget["over_budget"] is True
    assert budget["remaining"] < 0
    assert budget["warning"]
    assert any("exceeds" in warning.lower() for warning in response.json()["warnings"])


def test_budget_update_recalculates_estimate_and_warnings(
    client, auth_headers, start_date
):
    generated = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date, total_budget=10),
    ).json()
    itinerary_id = generated["id"]
    assert generated["budget_estimate"]["over_budget"] is True
    assert any("exceeds" in warning.lower() for warning in generated["warnings"])

    raised = client.patch(
        f"/api/v1/itineraries/{itinerary_id}",
        headers=auth_headers,
        json={"total_budget": 100_000},
    )
    assert raised.status_code == 200, raised.text
    raised_body = raised.json()
    assert raised_body["total_budget"] == 100_000
    assert raised_body["budget_estimate"]["total_budget"] == 100_000
    assert raised_body["budget_estimate"]["over_budget"] is False
    assert raised_body["budget_estimate"]["remaining"] > 0
    assert not any(
        "exceeds the total budget" in warning.lower()
        for warning in raised_body["warnings"]
    )

    lowered = client.patch(
        f"/api/v1/itineraries/{itinerary_id}",
        headers=auth_headers,
        json={"total_budget": 10},
    )
    assert lowered.status_code == 200, lowered.text
    lowered_body = lowered.json()
    assert lowered_body["budget_estimate"]["over_budget"] is True
    assert lowered_body["budget_estimate"]["warning"]
    assert sum(
        "exceeds the total budget" in warning.lower()
        for warning in lowered_body["warnings"]
    ) == 1


def test_update_can_clear_summary_and_rejects_empty_effective_patch(
    client, auth_headers, start_date
):
    itinerary_id = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date),
    ).json()["id"]

    cleared = client.patch(
        f"/api/v1/itineraries/{itinerary_id}",
        headers=auth_headers,
        json={"summary": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["summary"] is None

    no_op = client.patch(
        f"/api/v1/itineraries/{itinerary_id}",
        headers=auth_headers,
        json={"status": None},
    )
    assert no_op.status_code == 422
    assert no_op.json()["error"]["code"] == "validation_error"

    null_title = client.patch(
        f"/api/v1/itineraries/{itinerary_id}",
        headers=auth_headers,
        json={"title": None, "summary": "A valid summary must not mask a null title."},
    )
    assert null_title.status_code == 422
    assert null_title.json()["error"]["code"] == "validation_error"

    empty_days = client.patch(
        f"/api/v1/itineraries/{itinerary_id}",
        headers=auth_headers,
        json={"days": []},
    )
    assert empty_days.status_code == 422
    assert empty_days.json()["error"]["code"] == "validation_error"

    incomplete_days = client.patch(
        f"/api/v1/itineraries/{itinerary_id}",
        headers=auth_headers,
        json={
            "days": [
                {
                    "day_number": 1,
                    "date": start_date.isoformat(),
                    "title": "Only one of two days",
                    "activities": [],
                }
            ]
        },
    )
    assert incomplete_days.status_code == 422
    assert incomplete_days.json()["error"]["code"] == "validation_error"


def test_update_metadata_and_replace_days(
    client, auth_headers, start_date
):
    generated = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date),
    ).json()
    itinerary_id = generated["id"]

    title_update = client.patch(
        f"/api/v1/itineraries/{itinerary_id}",
        headers=auth_headers,
        json={"title": "Edited Kyoto Plan", "status": "saved"},
    )
    assert title_update.status_code == 200
    assert title_update.json()["title"] == "Edited Kyoto Plan"
    assert title_update.json()["status"] == "saved"

    days_payload = [
        {
            "day_number": 1,
            "date": start_date.isoformat(),
            "title": "Custom day one",
            "summary": "User-edited day.",
            "activities": [
                {
                    "place_id": "attr_1",
                    "name": "Kinkaku-ji",
                    "category": "attraction",
                    "start_time": "10:00",
                    "end_time": "12:00",
                    "estimated_cost": 100,
                }
            ],
        },
        {
            "day_number": 2,
            "date": (start_date + timedelta(days=1)).isoformat(),
            "title": "Custom day two",
            "activities": [
                {
                    "name": "Free walking tour",
                    "category": "other",
                    "estimated_cost": 20,
                }
            ],
        },
    ]
    updated = client.patch(
        f"/api/v1/itineraries/{itinerary_id}",
        headers=auth_headers,
        json={"title": "Rebuilt Plan", "days": days_payload, "total_budget": 4500},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["title"] == "Rebuilt Plan"
    assert body["days"][0]["title"] == "Custom day one"
    assert body["days"][0]["activities"][0]["rating"] == 4.8
    assert body["days"][1]["activities"][0]["name"] == "Free walking tour"
    assert body["budget_estimate"]["total_budget"] == 4500


def test_update_validates_contiguous_days(client, auth_headers, start_date):
    itinerary_id = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date),
    ).json()["id"]
    response = client.patch(
        f"/api/v1/itineraries/{itinerary_id}",
        headers=auth_headers,
        json={
            "days": [
                {
                    "day_number": 2,
                    "date": start_date.isoformat(),
                    "title": "Wrong numbering",
                    "activities": [],
                }
            ]
        },
    )
    assert response.status_code == 422


def test_ownership_is_enforced_for_reads_updates_and_deletes(
    client, auth_headers, start_date
):
    itinerary_id = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date),
    ).json()["id"]
    other_headers = _second_user_headers()

    assert (
        client.get(
            f"/api/v1/itineraries/{itinerary_id}", headers=other_headers
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/itineraries/{itinerary_id}",
            headers=other_headers,
            json={"title": "Hijacked"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/itineraries/{itinerary_id}", headers=other_headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/itineraries/{itinerary_id}", headers=auth_headers
        ).status_code
        == 200
    )


def test_delete_itinerary(client, auth_headers, start_date):
    itinerary_id = client.post(
        "/api/v1/itineraries/generate",
        headers=auth_headers,
        json=_generate_payload(start_date),
    ).json()["id"]
    deleted = client.delete(
        f"/api/v1/itineraries/{itinerary_id}", headers=auth_headers
    )
    assert deleted.status_code == 204
    assert (
        client.get(
            f"/api/v1/itineraries/{itinerary_id}", headers=auth_headers
        ).status_code
        == 404
    )


def test_saved_preferences_are_merged_into_generation(
    client, auth_headers, start_date
):
    client.put(
        "/api/v1/users/me/preferences",
        headers=auth_headers,
        json={
            "interests": ["nature"],
            "activity_preferences": ["hiking"],
            "accommodation_preference": "hostel",
            "transportation_preference": "walking",
            "dietary_preferences": ["vegan"],
            "currency": "EUR",
        },
    )
    payload = _generate_payload(start_date)
    payload.pop("interests")
    payload.pop("activities")
    payload.pop("accommodation_preference")
    payload.pop("transportation_preference")
    payload.pop("currency")
    response = client.post(
        "/api/v1/itineraries/generate", headers=auth_headers, json=payload
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["interests"] == ["nature"]
    assert body["currency"] == "EUR"
    assert body["accommodation_preference"] == "hostel"
    assert body["transportation_preference"] == "walking"
    assert any("Dietary suitability" in warning for warning in body["warnings"])
