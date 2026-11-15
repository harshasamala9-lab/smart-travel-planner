"""Analytics, sharing, PDF export, and share-log-redaction tests."""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from contextlib import closing
from datetime import date, datetime, timedelta, timezone

import jwt

from app.core.middleware import _redact_path
from app.services.analytics_service import AnalyticsService
from app.services.export_service import ExportService

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


def _generate(client, headers, start_date, **overrides) -> dict:
    response = client.post(
        "/api/v1/itineraries/generate",
        headers=headers,
        json=_generate_payload(start_date, **overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _sqlite_path(client) -> str:
    dsn = client.app.state.settings.database_dsn
    return dsn[len("sqlite:///") :]


def test_analytics_are_currency_safe_and_reflect_usage(
    client, auth_headers, start_date
):
    _generate(client, auth_headers, start_date)
    _generate(client, auth_headers, start_date, currency="EUR", total_budget=3000)
    assert (
        client.get("/api/v1/users/me", headers=auth_headers).status_code == 200
    )
    assert (
        client.post(
            "/api/v1/reviews",
            headers=auth_headers,
            json={"place_id": "attr_1", "rating": 5, "comment": "Great."},
        ).status_code
        == 201
    )

    response = client.get("/api/v1/analytics/me", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_itineraries"] == 2
    assert body["upcoming_trips"] == 2
    assert body["active_trips"] == 0
    assert body["completed_trips"] == 0
    assert body["draft_trips"] == 0
    assert body["reviews_count"] == 1
    assert body["top_destinations"][0]["destination_name"] == "Kyoto"
    assert body["top_destinations"][0]["trip_count"] == 2
    assert sum(item["trip_count"] for item in body["monthly_itineraries"]) == 2
    assert body["activity_counts"]["attraction"] == 6
    assert body["activity_counts"]["restaurant"] == 4

    currencies = {item["currency"]: item for item in body["currencies"]}
    assert set(currencies) == {"EUR", "USD"}
    assert currencies["USD"]["planned_budget"] == 5000.0
    assert currencies["EUR"]["planned_budget"] == 3000.0
    assert currencies["USD"]["estimated_cost"] > 0
    assert currencies["USD"]["activity_estimate"] == 90.0
    assert currencies["EUR"]["activity_estimate"] == 90.0
    assert currencies["USD"]["line_items"]["accommodation"] > 0
    assert any("never summed" in note for note in body["notes"])

    unauthenticated = client.get("/api/v1/analytics/me")
    assert unauthenticated.status_code == 401


def test_analytics_numeric_parser_ignores_malformed_and_non_finite_values():
    assert AnalyticsService._number("12.5") == 12.5
    assert AnalyticsService._number("not-a-number") == 0.0
    assert AnalyticsService._number(None, default=7.0) == 7.0
    assert AnalyticsService._number(float("nan"), default=1.0) == 1.0
    assert AnalyticsService._number(float("inf"), default=2.0) == 2.0
    assert AnalyticsService._number(float("-inf"), default=3.0) == 3.0


def test_analytics_empty_state_and_csv_report(client, auth_headers, start_date):
    first = _generate(client, auth_headers, start_date)
    second = _generate(
        client, auth_headers, start_date, currency="EUR", total_budget=3000
    )
    injected_title = client.patch(
        f"/api/v1/itineraries/{first['id']}",
        headers=auth_headers,
        json={"title": "=2+2"},
    )
    assert injected_title.status_code == 200, injected_title.text

    report = client.get("/api/v1/analytics/me/export.csv", headers=auth_headers)
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/csv")
    assert "attachment" in report.headers["content-disposition"]
    lines = report.text.strip().splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("id,title,destination_name")
    assert first["id"] in report.text
    assert second["id"] in report.text
    assert "'=2+2" in report.text
    assert ",=2+2" not in report.text

    other = _second_user_headers()
    empty = client.get("/api/v1/analytics/me", headers=other)
    assert empty.status_code == 200
    assert empty.json()["total_itineraries"] == 0
    assert empty.json()["currencies"] == []
    assert empty.json()["top_destinations"] == []

    empty_csv = client.get("/api/v1/analytics/me/export.csv", headers=other)
    assert empty_csv.status_code == 200
    assert len(empty_csv.text.strip().splitlines()) == 1


def test_share_link_is_hashed_at_rest_and_public_projection_is_safe(
    client, auth_headers, start_date
):
    itinerary = _generate(client, auth_headers, start_date)
    created = client.post(
        f"/api/v1/itineraries/{itinerary['id']}/share",
        headers=auth_headers,
        json={"expires_in_days": 7},
    )
    assert created.status_code == 201, created.text
    share = created.json()
    token = share["token"]
    assert len(token) >= 43
    assert share["api_path"].endswith(token)
    assert share["share_url"].startswith("http://testserver/api/v1/shared/itineraries/")
    assert share["expires_at"]
    assert share["warning"]

    path = _sqlite_path(client)
    with closing(sqlite3.connect(path)) as connection:
        row = connection.execute(
            "SELECT token_hash FROM itinerary_shares WHERE id = ?",
            (share["id"],),
        ).fetchone()
    assert row is not None
    assert row[0] == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert row[0] != token

    public = client.get(f"/api/v1/shared/itineraries/{token}")
    assert public.status_code == 200, public.text
    assert public.headers["cache-control"] == "no-store"
    body = public.json()
    assert body["title"] == "Kyoto in Bloom"
    assert body["days"][0]["activities"][0]["name"] == "Kinkaku-ji"
    assert "preferences_snapshot" not in body
    assert "generation_metadata" not in body
    assert "user_id" not in body
    assert "reviewer" not in body

    wrong = client.get("/api/v1/shared/itineraries/not-a-real-token")
    assert wrong.status_code == 404

    listing = client.get(
        f"/api/v1/itineraries/{itinerary['id']}/shares", headers=auth_headers
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert "token" not in listing.json()["items"][0]
    assert "token_hash" not in listing.json()["items"][0]

    revoked = client.delete(
        f"/api/v1/itineraries/{itinerary['id']}/shares", headers=auth_headers
    )
    assert revoked.status_code == 204
    assert client.get(f"/api/v1/shared/itineraries/{token}").status_code == 404


def test_expired_share_and_share_ownership(client, auth_headers, start_date):
    itinerary = _generate(client, auth_headers, start_date)
    created = client.post(
        f"/api/v1/itineraries/{itinerary['id']}/share",
        headers=auth_headers,
        json={"expires_in_days": 1},
    )
    share = created.json()
    token = share["token"]

    with closing(sqlite3.connect(_sqlite_path(client))) as connection:
        connection.execute(
            "UPDATE itinerary_shares SET expires_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", share["id"]),
        )
        connection.commit()
    assert client.get(f"/api/v1/shared/itineraries/{token}").status_code == 404

    other = _second_user_headers()
    assert (
        client.post(
            f"/api/v1/itineraries/{itinerary['id']}/share",
            headers=other,
            json={"expires_in_days": 7},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/itineraries/{itinerary['id']}/shares", headers=other
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/itineraries/{itinerary['id']}/shares", headers=other
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/itineraries/{uuid.uuid4()}/share",
            headers=auth_headers,
            json={"expires_in_days": 7},
        ).status_code
        == 404
    )
    for invalid_days in (0, 366):
        assert (
            client.post(
                f"/api/v1/itineraries/{itinerary['id']}/share",
                headers=auth_headers,
                json={"expires_in_days": invalid_days},
            ).status_code
            == 422
        )


def test_deleting_an_itinerary_invalidates_its_share_links(
    client, auth_headers, start_date
):
    itinerary = _generate(client, auth_headers, start_date)
    token = client.post(
        f"/api/v1/itineraries/{itinerary['id']}/share",
        headers=auth_headers,
        json={},
    ).json()["token"]
    assert client.get(f"/api/v1/shared/itineraries/{token}").status_code == 200
    assert (
        client.delete(
            f"/api/v1/itineraries/{itinerary['id']}", headers=auth_headers
        ).status_code
        == 204
    )
    assert client.get(f"/api/v1/shared/itineraries/{token}").status_code == 404


def test_pdf_export_is_owner_scoped_and_unicode_safe(
    client, auth_headers, start_date
):
    itinerary = _generate(client, auth_headers, start_date)
    response = client.get(
        f"/api/v1/itineraries/{itinerary['id']}/export/pdf",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 2000

    assert (
        client.get(
            f"/api/v1/itineraries/{itinerary['id']}/export/pdf"
        ).status_code
        == 401
    )
    assert (
        client.get(
            f"/api/v1/itineraries/{itinerary['id']}/export/pdf",
            headers=_second_user_headers(),
        ).status_code
        == 404
    )

    pdf = ExportService().build_itinerary_pdf(
        {
            "id": str(uuid.uuid4()),
            "title": "Café, culture et gastronomie",
            "summary": "Un séjour avec des caractères accentués — and an em dash.",
            "destination_name": "Kyōto",
            "start_date": start_date.isoformat(),
            "end_date": (start_date + timedelta(days=1)).isoformat(),
            "travellers": 2,
            "currency": "EUR",
            "budget_estimate": {
                "line_items": {
                    "transportation": 20,
                    "accommodation": 300,
                    "food": 180,
                    "activities": 45,
                    "other": 40,
                },
                "total": 585,
                "per_person": 292.5,
                "total_budget": 1000,
                "remaining": 415,
                "warning": None,
            },
            "days": [
                {
                    "day_number": 1,
                    "date": start_date.isoformat(),
                    "title": "Vieille ville",
                    "summary": "Promenade et café.",
                    "activities": [
                        {
                            "name": "Café de Flore",
                            "category": "restaurant",
                            "start_time": "09:00",
                            "end_time": "10:00",
                            "estimated_cost": 12,
                            "address": "Rue Saint-Benoît",
                            "route_to_next": {
                                "distance_km": 1.2,
                                "duration_minutes": 8,
                                "travel_mode": "WALK",
                            },
                        }
                    ],
                }
            ],
            "warnings": ["Prices are estimates."],
        }
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000


def test_share_tokens_are_redacted_from_application_access_logs():
    path = "/api/v1/shared/itineraries/high-entropy-token-value"
    assert _redact_path(path) == "/api/v1/shared/itineraries/[redacted]"
    assert _redact_path("/api/v1/itineraries") == "/api/v1/itineraries"
