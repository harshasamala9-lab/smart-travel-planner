# Smart Travel Planner — REST API

Base URL (local): `http://127.0.0.1:8000`

All application routes are under `/api/v1`. Interactive documentation is
available at `/docs` (Swagger) and `/redoc`.

---

## Authentication

Send the Neon Auth access token as a bearer token:

```http
Authorization: Bearer <access-token>
```

Tokens are EdDSA (Ed25519) JWTs issued by Neon Auth (Managed Better Auth) with
a 15-minute expiry, verified against `NEON_AUTH_JWKS_URL`. Passwords are sent
only to Neon Auth and are never stored by this backend.

**Session model:**

- `POST /auth/register` and `POST /auth/login` return a 15-minute
  `access_token` **plus** a 7-day `refresh_token` (the session token).
- `POST /auth/refresh` exchanges the session token for a fresh access JWT; the
  session token itself does not rotate.
- `POST /auth/logout` revokes the session. An already-issued access JWT stays
  valid until its own expiry (at most 15 minutes).

Public routes:

- `GET /`, `/health`, `/health/ready`
- `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`
- `GET /auth/google/url`
- `GET /shared/itineraries/{token}`

All other `/api/v1` routes require a valid bearer token.

---

## Common conventions

### Content types

- JSON requests: `Content-Type: application/json`
- JSON responses: `application/json`
- Photo proxy: `image/*`
- CSV report: `text/csv`
- PDF export: `application/pdf`

### Pagination

List endpoints use:

| Parameter | Meaning |
|---|---|
| `limit` | Page size, normally `1..100` (reviews/notifications) or `1..100` (itineraries) |
| `offset` | Zero-based offset |

Responses include `items`, `total`, `limit`, and `offset` where applicable.

### Error envelope

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request contains invalid or missing fields.",
    "details": { "errors": [] },
    "request_id": "b94b…"
  }
}
```

| Status | Typical code | Meaning |
|---|---|---|
| 400 | `invalid_content_length` | Malformed transport header |
| 401 | `authentication_required` | Missing/invalid/expired token |
| 403 | `permission_denied` | Authenticated but not permitted |
| 404 | `not_found` | Missing resource or not owned by the caller |
| 405 | `method_not_allowed` | Wrong HTTP method |
| 409 | `conflict` | Duplicate review or database constraint |
| 413 | `payload_too_large` | Request body exceeds the configured limit |
| 422 | `validation_error` | Schema/business-rule validation failure |
| 429 | `rate_limit_exceeded` | Too many auth attempts |
| 500 | `internal_error` | Unexpected server error |
| 502 | `ai_invalid_output` / external failure | Upstream returned unusable data |
| 503 | `service_unavailable` | Integration not configured |
| 504 | `request_timeout` | Server-side request deadline exceeded |

Every response includes `X-Request-ID`. You may send your own `X-Request-ID` to
correlate logs; otherwise one is generated.

---

## Health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | No | API name, version, environment, docs links |
| GET | `/health` | No | Process liveness and integration configuration flags |
| GET | `/health/ready` | No | Readiness including a database round trip |

`/health` does **not** call third parties. Integration flags indicate whether
credentials are configured, not whether a paid API is currently reachable.

---

## Authentication endpoints

### `POST /api/v1/auth/register`

```json
{
  "email": "traveler@example.com",
  "password": "StrongPass123",
  "full_name": "Test Traveler"
}
```

Password rules: 8–128 characters, at least one letter and one digit. Passwords
are sent only to Neon Auth and are never stored by this backend.

Response: `AuthResponse` with `user`, `session` (`access_token`,
`refresh_token`, `expires_in` ≈ 900), `profile`, and
`email_confirmation_required`.

### `POST /api/v1/auth/login`

```json
{ "email": "traveler@example.com", "password": "StrongPass123" }
```

Response: `TokenResponse` with `session`, `user`, and `profile`.

### `POST /api/v1/auth/refresh`

```json
{ "refresh_token": "<session-token>" }
```

Returns a fresh 15-minute access JWT (`TokenResponse`). Send the 7-day session
token returned by register/login; the session does not rotate. Returns `401`
once the session expires or is revoked.

### `POST /api/v1/auth/logout`

```json
{ "refresh_token": "<session-token>" }
```

Revokes the Neon Auth session identified by the session token. Returns
`{"message": "Logged out successfully."}`; `401` for an invalid/expired
session.

### `GET /api/v1/auth/google/url`

Query: `redirect_to` (optional; must be an allowed frontend origin registered
as a Neon Auth trusted domain). Returns:

```json
{
  "authorization_url": "https://<auth-host>.neonauth.<region>.aws.neon.tech/neondb/auth/sign-in/social/init?token=…",
  "provider": "google",
  "redirect_to": "http://localhost:5173/auth/callback"
}
```

Open the authorization URL in a browser; Neon Auth performs the OAuth exchange
itself and redirects the user to `redirect_to` when done. There is no client
exchange step to implement.

---

## Users

All routes require auth.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/users/me` | Get or lazily create the profile |
| PATCH | `/api/v1/users/me` | Update profile fields (`full_name`, `phone`, `avatar_url`, `date_of_birth`, `preferred_currency`) |
| GET | `/api/v1/users/me/preferences` | Get saved preferences; 404 if none |
| PUT | `/api/v1/users/me/preferences` | Create or replace preferences |
| GET | `/api/v1/users/me/history` | Paginated itineraries |
| GET | `/api/v1/users/me/saved-destinations` | List saved places |
| POST | `/api/v1/users/me/saved-destinations` | Save a place, verified through Google Places |
| DELETE | `/api/v1/users/me/saved-destinations/{place_id}` | Remove a saved place |

### Preferences body

```json
{
  "home_city": "London",
  "interests": ["history", "food"],
  "activity_preferences": ["museums", "walking tours"],
  "accommodation_preference": "midrange_hotel",
  "transportation_preference": "mixed",
  "budget_level": "moderate",
  "dietary_preferences": ["vegetarian"],
  "accessibility_needs": "Step-free access where possible",
  "currency": "USD"
}
```

Valid accommodation values: `none`, `hostel`, `budget_hotel`, `midrange_hotel`,
`luxury_hotel`, `apartment`, `homestay`.

Valid transportation values: `none`, `walking`, `public_transport`,
`taxi_rideshare`, `rental_car`, `mixed`.

### Saved destination body

```json
{
  "place_id": "<Google Places place_id>",
  "notes": "Visit in the morning"
}
```

The backend resolves the place through Google Places before saving it. Arbitrary
or invented place IDs are rejected with `404`.

---

## Destinations and routes

All routes require auth and require `GOOGLE_MAPS_API_KEY` except where noted.

### `GET /api/v1/destinations/search`

Query parameters:

| Name | Required | Notes |
|---|---|---|
| `query` | Yes | 2–200 characters |
| `limit` | No | 1–20, default 10 |
| `language` | No | 2–10 characters; overrides configured language |

Response: `query`, `items` (`PlaceSummary`), `count`, and
`source: "Google Places API (New)"`.

### `GET /api/v1/destinations/{place_id}`

Returns `PlaceDetails`: canonical name, address, coordinates, Google rating and
review count, price level, types, open status, opening hours (when provided),
Google Maps URI, photo names, website, phone, and editorial summary.

### `GET /api/v1/destinations/photo`

Query:

- `photo_name` — Google Places photo resource name (the value from
  `photo_names`), 10–500 characters.
- `max_width` — 100–1600, default 1200.

Returns image bytes proxied from Google. The API key is never exposed. The
response uses `Cache-Control: private, max-age=86400`.

### `POST /api/v1/destinations/route`

Provide exactly one location form per endpoint: `place_id`, `address`, or
`latitude` + `longitude`.

```json
{
  "origin": { "latitude": 35.0, "longitude": 135.7, "name": "Hotel" },
  "destination": { "place_id": "ChIJ…" },
  "travel_mode": "WALK",
  "include_steps": false
}
```

`travel_mode`: `DRIVE`, `WALK`, `BICYCLE`, `TRANSIT`.

Response includes resolved origin/destination, distance in meters/km, duration
seconds/minutes, encoded polyline, optional steps, `calculated_at`, and
`source: "Google Routes API"`.

### Nearby places

| Method | Path | Defaults |
|---|---|---|
| GET | `/api/v1/destinations/{place_id}/attractions` | `radius_m=10000`, `limit=15` |
| GET | `/api/v1/destinations/{place_id}/restaurants` | `radius_m=5000`, `limit=15` |
| GET | `/api/v1/destinations/{place_id}/nearby?types=tourist_attraction,museum` | `radius_m=10000`, `limit=15` |

`radius_m` range: 500–50,000; `limit`: 1–20. The `nearby` endpoint accepts only
Google Places types on the backend allowlist; unsupported types return `422`
with the invalid and allowed values.

---

## Itineraries

### `POST /api/v1/itineraries/generate`

Requires Google Maps and Gemini. Weather is optional, but failure is reported as
a warning rather than a fabricated forecast.

```json
{
  "destination": "Kyoto, Japan",
  "destination_place_id": "ChIJ…",
  "start_date": "2026-12-10",
  "end_date": "2026-12-12",
  "travellers": 2,
  "total_budget": 2500,
  "currency": "USD",
  "activities": ["temples", "markets"],
  "interests": ["history", "food"],
  "accommodation_preference": "midrange_hotel",
  "transportation_preference": "mixed",
  "pace": "balanced",
  "origin": "London",
  "dietary_preferences": ["vegetarian"],
  "accessibility_needs": "Step-free access where possible",
  "additional_notes": "Avoid very early starts.",
  "include_routes": true
}
```

Rules:

- `start_date` cannot be in the past; `end_date >= start_date`.
- Requests longer than 60 days or the configured `MAX_TRIP_DAYS` (default 30)
  are rejected.
- `currency` must be a three-letter ISO code supported by the configured budget
  rate profiles.
- `travellers` is 1–20 (schema) and is also checked against `MAX_TRAVELLERS`.

The response is `ItineraryDetailResponse`, containing:

- `budget_estimate` with `currency`, `line_items` (`transportation`,
  `accommodation`, `food`, `activities`, `other`), `total`, `per_person`,
  `total_budget`, `remaining`, `over_budget`, `within_budget`,
  `utilization_percent`, `warning`, `assumptions`, `cost_type: "estimated"`,
  and a disclaimer.
- `days[]` with activities, Google Places metadata, timings, estimated costs,
  and optional `route_to_next`.
- `weather_summary` with forecast coverage honesty.
- `recommendations` sourced from real Places candidates.
- `warnings` for unavailable weather, route failures, dietary/accessibility
  verification limits, and over-budget conditions.
- `generation_metadata` with AI attempts, candidate counts, data sources, and
  generation time.

Generation is persisted atomically. A `trip_generated` notification is created
after a successful save; notification failure does not fail the trip.

### Other itinerary endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/itineraries?limit=20&offset=0` | List owned itineraries |
| GET | `/api/v1/itineraries/{itinerary_id}` | Get owned itinerary with days |
| PATCH | `/api/v1/itineraries/{itinerary_id}` | Update title/summary/status/budget, or replace days |
| DELETE | `/api/v1/itineraries/{itinerary_id}` | Delete itinerary and cascade days/activities/shares |
| POST | `/api/v1/itineraries/{itinerary_id}/share` | Create share link |
| GET | `/api/v1/itineraries/{itinerary_id}/shares` | List active share links |
| DELETE | `/api/v1/itineraries/{itinerary_id}/shares` | Revoke all active links |
| GET | `/api/v1/itineraries/{itinerary_id}/export/pdf` | Download PDF |

PATCH with `days` replaces all days/activities and recalculates the budget. Supply
exactly one day for every date from the itinerary start through end, with unique
`day_number` values contiguous from 1 and unique ascending dates. At least one
field must be supplied; `title`, `status`, `total_budget`, and `days` cannot be
explicit `null` (omit them to keep the current value). User-edited costs remain
`estimated`.

### Share link request

```json
{ "expires_in_days": 7 }
```

`expires_in_days` is 1–365 and defaults to 7. The response returns the raw token
**once**; only its SHA-256 hash is stored. The response also includes
`share_url`, `api_path`, `expires_at`, and a warning.

```json
{
  "id": "…",
  "itinerary_id": "…",
  "token": "high-entropy-secret",
  "share_url": "http://127.0.0.1:8000/api/v1/shared/itineraries/high-entropy-secret",
  "api_path": "/api/v1/shared/itineraries/high-entropy-secret",
  "expires_at": "2026-11-19T12:00:00+00:00",
  "created_at": "2026-11-12T12:00:00+00:00",
  "warning": "Anyone with this link can view..."
}
```

Listing shares never returns the token or hash.

### `GET /api/v1/shared/itineraries/{token}` — public

No authentication. Returns a read-only projection of the itinerary: title,
summary, destination, dates, travellers, currency, status, preferences that are
relevant to the trip, budget estimate, warnings, days, recommendations, and
weather summary.

It deliberately excludes:

- `user_id` and profile information
- `preferences_snapshot`
- `generation_metadata`, including `profile_id`
- review/account data

Invalid, expired, revoked, or deleted-itinerary links return `404`.

---

## Recommendations

### `POST /api/v1/recommendations/`

```json
{
  "destination": "Kyoto",
  "interests": ["history", "food"],
  "budget_level": "moderate",
  "include_hotels": true,
  "limit": 5
}
```

Returns ranked attractions, restaurants, and hotels sourced from Google Places.
Ranking is deterministic (interest match, rating, review volume, price-level
alignment, open status); no LLM invents place data. Each item includes a score
and a short reason.

---

## Weather

### `GET /api/v1/weather/{destination}`

Query:

| Name | Notes |
|---|---|
| `start_date` | ISO date; must be supplied with `end_date` |
| `end_date` | ISO date; must be on/after `start_date` |
| `units` | `metric` (default) or `imperial` |

Returns current observed weather and whatever forecast the provider exposes.
`forecast_covers_requested_dates` is:

- `true` — provider forecast covers the requested range
- `false` — requested dates extend beyond the available forecast horizon
- `null` — forecast data was unavailable

The response includes source attribution and a disclaimer. No future weather is
invented.

---

## Reviews

Reviews are independent user content. They are **not** Google ratings and are not
verified visit records. Creation resolves the place through Google Places, so
invented place IDs are rejected.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/reviews/me?limit=20&offset=0` | Own reviews |
| GET | `/api/v1/reviews/place/{place_id}?limit=20&offset=0` | Reviews for a place, with average |
| POST | `/api/v1/reviews` | Create a review |
| PATCH | `/api/v1/reviews/{review_id}` | Update owned review |
| DELETE | `/api/v1/reviews/{review_id}` | Delete owned review |

### Create body

```json
{
  "place_id": "ChIJ…",
  "rating": 5,
  "title": "Beautiful golden pavilion",
  "comment": "Go early; the reflection on the pond is stunning.",
  "visited_on": "2026-11-01"
}
```

`rating` is 1–5. `visited_on` cannot be in the future. Title ≤160 characters;
comment ≤2000. One review per user per place; duplicates return `409`.

Place listings include `average_rating`, `total`, and `is_own` for each item.
Ownership is enforced for update/delete.

---

## Notifications

Notifications are created when an itinerary is generated. Clients can poll these
endpoints or subscribe to Neon Realtime for live updates (the Neon deployment
declares realtime in `neon.ts`).

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/notifications?unread_only=false&limit=20&offset=0` | List notifications and unread count |
| POST | `/api/v1/notifications/read-all` | Mark all as read |
| PATCH | `/api/v1/notifications/{notification_id}/read` | Mark one as read |
| DELETE | `/api/v1/notifications/{notification_id}` | Delete one |

Notification types: `trip_generated`, `trip_reminder`, `system`, `offer`,
`review`, `share`. The `metadata` object contains contextual IDs (for example,
the generated `itinerary_id`).

---

## Analytics and reports

### `GET /api/v1/analytics/me`

Returns:

- `total_itineraries`, `upcoming_trips`, `active_trips`, `completed_trips`,
  `draft_trips`, `archived_trips`, `reviews_count`
- `currencies[]` — one entry per ISO currency, each with `planned_budget`,
  `estimated_cost`, `activity_estimate`, `line_items`, and `itinerary_count`
- `top_destinations[]`
- `monthly_itineraries[]` (last 12 months represented)
- `activity_counts` by category
- `generated_at`, `notes`, and `metadata`

**Currencies are never converted or summed across codes.** Amounts are planning
estimates, not live prices.

### `GET /api/v1/analytics/me/export.csv`

Returns `text/csv` with one row per itinerary:

`id,title,destination_name,start_date,end_date,travellers,status,currency,total_budget,estimated_total,created_at`

All pages of the user's itineraries are included.

---

## PDF export

### `GET /api/v1/itineraries/{itinerary_id}/export/pdf`

Owner only. Returns `application/pdf` with a printable itinerary, activity
schedule, budget estimate, warnings, disclaimers, and an embedded Unicode font.
The file is generated in-process with ReportLab; no external rendering service
is called.

---

## Data sources and honesty summary

| Data | Source |
|---|---|
| Places, addresses, coordinates, ratings, hours, photos | Google Places API (New) |
| Distance/duration and optional steps | Google Routes API |
| Current weather/forecast | OpenWeather |
| Itinerary structure, activity ordering, activity cost estimates | Gemini, validated against real candidates |
| Budget line items and total | Backend budget service (configurable planning estimates) |
| Reviews | Authenticated users (not verified visits) |
| Notifications | Backend-created records |
| Analytics | Derived from saved Neon Postgres records |

Every monetary field from this API is an **estimate** unless a future provider
explicitly returns a verified live price. The only current `cost_type` produced
is `estimated`.

---

## Security notes for share links

Share tokens are bearer secrets in the URL. The backend:

- stores only SHA-256 hashes,
- defaults links to 7-day expiry (maximum 365 days),
- supports revocation by the owner,
- sets `Cache-Control: no-store` and `Referrer-Policy: no-referrer`,
- redacts the token from its own application access log.

Operators must also redact this URL path from reverse-proxy/uvicorn access logs.
The documented run command disables Uvicorn's access log with `--no-access-log`.
If a proxy terminates requests, configure equivalent redaction or disable
access logging for `/api/v1/shared/itineraries/*` at the proxy.
Use HTTPS and revoke links that were accidentally exposed.
