"""Review and in-app notification endpoint tests."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import jwt

from .conftest import TEST_AUTH_BASE_URL, TEST_JWT_SECRET
from .test_itineraries import _generate_payload


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


def _generate(client, headers, start_date) -> dict:
    response = client.post(
        "/api/v1/itineraries/generate",
        headers=headers,
        json=_generate_payload(start_date),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_review_crud_and_google_place_verification(client, auth_headers):
    # The profile must exist because reviews reference the profiles table.
    assert client.get("/api/v1/users/me", headers=auth_headers).status_code == 200

    created = client.post(
        "/api/v1/reviews",
        headers=auth_headers,
        json={
            "place_id": "attr_1",
            "rating": 5,
            "title": "Beautiful golden pavilion",
            "comment": "Go early; the reflection on the pond is stunning.",
            "visited_on": (date.today() - timedelta(days=3)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    review_id = body["id"]
    assert body["place_name"] == "Kinkaku-ji"
    assert body["rating"] == 5
    assert body["is_own"] is True
    assert body["reviewer_name"] == "Test Traveler"
    assert body["visited_on"] == (date.today() - timedelta(days=3)).isoformat()

    duplicate = client.post(
        "/api/v1/reviews",
        headers=auth_headers,
        json={"place_id": "attr_1", "rating": 4},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"

    place_reviews = client.get(
        "/api/v1/reviews/place/attr_1", headers=auth_headers
    )
    assert place_reviews.status_code == 200
    listing = place_reviews.json()
    assert listing["total"] == 1
    assert listing["average_rating"] == 5.0
    assert listing["items"][0]["is_own"] is True

    updated = client.patch(
        f"/api/v1/reviews/{review_id}",
        headers=auth_headers,
        json={"rating": 4, "comment": "Still excellent, slightly crowded."},
    )
    assert updated.status_code == 200
    assert updated.json()["rating"] == 4
    assert updated.json()["title"] == "Beautiful golden pavilion"

    null_rating = client.patch(
        f"/api/v1/reviews/{review_id}",
        headers=auth_headers,
        json={"rating": None},
    )
    assert null_rating.status_code == 422
    assert null_rating.json()["error"]["code"] == "validation_error"

    mine = client.get("/api/v1/reviews/me", headers=auth_headers)
    assert mine.status_code == 200
    assert mine.json()["total"] == 1

    deleted = client.delete(
        f"/api/v1/reviews/{review_id}", headers=auth_headers
    )
    assert deleted.status_code == 204
    assert (
        client.get("/api/v1/reviews/place/attr_1", headers=auth_headers)
        .json()["total"]
        == 0
    )


def test_review_validation_and_place_allowlist(client, auth_headers):
    assert client.get("/api/v1/users/me", headers=auth_headers).status_code == 200

    invented = client.post(
        "/api/v1/reviews",
        headers=auth_headers,
        json={"place_id": "invented_place", "rating": 5},
    )
    assert invented.status_code == 404
    assert invented.json()["error"]["code"] == "not_found"

    invalid_rating = client.post(
        "/api/v1/reviews",
        headers=auth_headers,
        json={"place_id": "attr_1", "rating": 6},
    )
    assert invalid_rating.status_code == 422

    future_visit = client.post(
        "/api/v1/reviews",
        headers=auth_headers,
        json={
            "place_id": "attr_1",
            "rating": 5,
            "visited_on": (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    assert future_visit.status_code == 422

    no_auth = client.post(
        "/api/v1/reviews", json={"place_id": "attr_1", "rating": 5}
    )
    assert no_auth.status_code == 401


def test_review_ownership_is_enforced(client, auth_headers):
    assert client.get("/api/v1/users/me", headers=auth_headers).status_code == 200
    review_id = client.post(
        "/api/v1/reviews",
        headers=auth_headers,
        json={"place_id": "attr_2", "rating": 5, "comment": "Wonderful."},
    ).json()["id"]
    other = _second_user_headers()
    assert client.get("/api/v1/users/me", headers=other).status_code == 200

    assert (
        client.patch(
            f"/api/v1/reviews/{review_id}", headers=other, json={"rating": 1}
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/reviews/{review_id}", headers=other).status_code
        == 404
    )

    second_review = client.post(
        "/api/v1/reviews",
        headers=other,
        json={"place_id": "attr_2", "rating": 4, "comment": "Also good."},
    )
    assert second_review.status_code == 201
    assert second_review.json()["is_own"] is True

    listing = client.get("/api/v1/reviews/place/attr_2", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 2
    assert listing.json()["average_rating"] == 4.5
    own_flags = {item["id"]: item["is_own"] for item in listing.json()["items"]}
    assert own_flags[review_id] is True
    assert own_flags[second_review.json()["id"]] is False


def test_generation_creates_an_unread_notification(
    client, auth_headers, start_date
):
    itinerary = _generate(client, auth_headers, start_date)

    response = client.get("/api/v1/notifications", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["unread_count"] == 1
    notification = body["items"][0]
    assert notification["type"] == "trip_generated"
    assert notification["read"] is False
    assert notification["metadata"]["itinerary_id"] == itinerary["id"]
    assert "Kyoto" in notification["message"]

    unread = client.get(
        "/api/v1/notifications", headers=auth_headers, params={"unread_only": True}
    )
    assert unread.json()["total"] == 1

    marked = client.patch(
        f"/api/v1/notifications/{notification['id']}/read",
        headers=auth_headers,
    )
    assert marked.status_code == 200
    assert marked.json()["read"] is True
    assert marked.json()["read_at"] is not None

    after = client.get("/api/v1/notifications", headers=auth_headers)
    assert after.json()["unread_count"] == 0
    unread_after = client.get(
        "/api/v1/notifications", headers=auth_headers, params={"unread_only": True}
    )
    assert unread_after.json()["total"] == 0


def test_mark_all_read_and_delete_notifications(
    client, auth_headers, start_date
):
    _generate(client, auth_headers, start_date)
    _generate(client, auth_headers, start_date)
    listing = client.get("/api/v1/notifications", headers=auth_headers).json()
    assert listing["total"] == 2
    assert listing["unread_count"] == 2

    marked = client.post("/api/v1/notifications/read-all", headers=auth_headers)
    assert marked.status_code == 200
    assert marked.json()["marked"] == 2
    assert marked.json()["unread_count"] == 0

    notification_id = listing["items"][0]["id"]
    deleted = client.delete(
        f"/api/v1/notifications/{notification_id}", headers=auth_headers
    )
    assert deleted.status_code == 204
    remaining = client.get("/api/v1/notifications", headers=auth_headers)
    assert remaining.json()["total"] == 1
    assert (
        client.delete(
            f"/api/v1/notifications/{notification_id}", headers=auth_headers
        ).status_code
        == 404
    )


def test_notifications_are_scoped_to_the_owner(client, auth_headers, start_date):
    _generate(client, auth_headers, start_date)
    notification_id = client.get(
        "/api/v1/notifications", headers=auth_headers
    ).json()["items"][0]["id"]
    other = _second_user_headers()
    assert client.get("/api/v1/users/me", headers=other).status_code == 200

    assert (
        client.get("/api/v1/notifications", headers=other).json()["total"] == 0
    )
    assert (
        client.patch(
            f"/api/v1/notifications/{notification_id}/read", headers=other
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/notifications/{notification_id}", headers=other
        ).status_code
        == 404
    )
