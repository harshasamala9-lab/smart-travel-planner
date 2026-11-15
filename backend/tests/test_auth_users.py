"""Neon Auth boundary, profile, preferences, and saved-place tests."""

from __future__ import annotations


def test_register_login_refresh_logout(client, auth_headers, fake_auth):
    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "password": "StrongPass123",
            "full_name": "New Traveler",
        },
    )
    assert register.status_code == 201
    body = register.json()
    assert body["user"]["email"] == "traveler@example.com"
    assert body["session"]["access_token"] == "fake-access-token"
    assert body["profile"]["email"] == "traveler@example.com"
    assert body["email_confirmation_required"] is False

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "traveler@example.com", "password": "StrongPass123"},
    )
    assert login.status_code == 200
    assert login.json()["session"]["refresh_token"] == "fake-refresh-token"

    refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "valid-session-token"}
    )
    assert refresh.status_code == 200
    assert refresh.json()["user"]["id"] == str(fake_auth.user_id)

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": "valid-session-token"})
    assert logout.status_code == 200
    assert logout.json()["message"] == "Logged out successfully."
    assert fake_auth.logged_out_tokens == ["valid-session-token"]


def test_logout_rejects_missing_session_token(client, auth_headers):
    response = client.post("/api/v1/auth/logout", headers=auth_headers, json={})
    assert response.status_code == 422


def test_google_authorization_url(client):
    url_response = client.get("/api/v1/auth/google/url")
    assert url_response.status_code == 200
    payload = url_response.json()
    assert payload["provider"] == "google"
    assert payload["redirect_to"] == "http://localhost:5173/auth/callback"
    assert "provider=google" in payload["authorization_url"]

    disallowed = client.get(
        "/api/v1/auth/google/url", params={"redirect_to": "https://evil.example.com"}
    )
    assert disallowed.status_code == 422


def test_profile_is_provisioned_and_updatable(client, auth_headers):
    me = client.get("/api/v1/users/me", headers=auth_headers)
    assert me.status_code == 200
    profile = me.json()
    assert profile["email"] == "traveler@example.com"
    assert profile["full_name"] == "Test Traveler"

    empty = client.patch("/api/v1/users/me", headers=auth_headers, json={})
    assert empty.status_code == 422

    updated = client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={
            "full_name": "Updated Traveler",
            "phone": "+1 555 0100",
            "date_of_birth": "1990-05-01",
            "preferred_currency": "eur",
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["full_name"] == "Updated Traveler"
    assert updated_body["preferred_currency"] == "EUR"
    assert updated_body["date_of_birth"] == "1990-05-01"


def test_travel_preferences_round_trip(client, auth_headers):
    missing = client.get("/api/v1/users/me/preferences", headers=auth_headers)
    assert missing.status_code == 404

    saved = client.put(
        "/api/v1/users/me/preferences",
        headers=auth_headers,
        json={
            "home_city": "Toronto",
            "interests": ["history", "food"],
            "activity_preferences": ["museums"],
            "accommodation_preference": "budget_hotel",
            "transportation_preference": "public_transport",
            "budget_level": "moderate",
            "dietary_preferences": ["vegetarian"],
            "currency": "cad",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["currency"] == "CAD"
    assert body["interests"] == ["history", "food"]

    fetched = client.get("/api/v1/users/me/preferences", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["home_city"] == "Toronto"
    assert fetched.json()["accommodation_preference"] == "budget_hotel"


def test_saved_destinations_use_verified_place_data(client, auth_headers):
    created = client.post(
        "/api/v1/users/me/saved-destinations",
        headers=auth_headers,
        json={"place_id": "dest_kyoto", "notes": "Cherry blossom season"},
    )
    assert created.status_code == 201
    saved = created.json()
    assert saved["place_id"] == "dest_kyoto"
    assert saved["name"] == "Kyoto"
    assert saved["category"] == "locality"
    assert saved["notes"] == "Cherry blossom season"

    listed = client.get(
        "/api/v1/users/me/saved-destinations", headers=auth_headers
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    deleted = client.delete(
        "/api/v1/users/me/saved-destinations/dest_kyoto", headers=auth_headers
    )
    assert deleted.status_code == 204
    second_delete = client.delete(
        "/api/v1/users/me/saved-destinations/dest_kyoto", headers=auth_headers
    )
    assert second_delete.status_code == 404


def test_saved_destination_rejects_unknown_place(client, auth_headers):
    response = client.post(
        "/api/v1/users/me/saved-destinations",
        headers=auth_headers,
        json={"place_id": "invented_place"},
    )
    assert response.status_code == 404


def test_history_initially_empty(client, auth_headers):
    response = client.get("/api/v1/users/me/history", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}
