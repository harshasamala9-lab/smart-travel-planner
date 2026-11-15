# Smart Travel Planner — Backend

A production-minded **FastAPI** backend for an AI travel planner. It combines
**Neon** (Postgres + Neon Auth + AI Gateway + Object Storage), Google Places and
Routes, OpenWeather, and Gemini to generate day-by-day itineraries, estimate
budgets, and support the surrounding travel workflow: profiles, preferences,
saved places, reviews, notifications, analytics, sharing, CSV reports, and PDF
export.

This repository contains the **backend only**. No React frontend is included.
The API is intended to run on the developer's laptop only (localhost-published
ports in `docker-compose.yml`).

---

## At a glance

| Area | Implementation |
|---|---|
| API framework | FastAPI + Uvicorn |
| Production database | Neon Postgres (branch `production`, AWS `ap-southeast-1`) |
| Test/offline database | SQLite (never production) |
| Authentication | Neon Auth (Managed Better Auth): email/password + Google social OAuth |
| Token verification | EdDSA/Ed25519 via the Neon Auth JWKS; optional HS256 for tests only |
| AI | Google Gemini structured JSON output, validated and retried; optional Neon AI Gateway override |
| Places / routes | Google Places API (New), Geocoding API, Routes API |
| Weather | OpenWeather current + forecast, with forecast-coverage honesty |
| Files | Neon Object Storage (S3-compatible, branches with the database) |
| Reports / export | Currency-safe analytics, CSV, ReportLab PDF with Unicode font |
| Tests | 106 passing, 90% coverage offline (no API quota or credentials required) |
| API docs | Swagger `/docs`, ReDoc `/redoc`, OpenAPI `/openapi.json` |

---

## Architecture

```
HTTP client
    │
    ▼
FastAPI routers / middleware
    │  request IDs, body limits, auth rate limit, timeouts, CORS,
    │  trusted hosts, security headers, log redaction
    ▼
Services (domain rules + integrations)
    │  neon auth • places • routes • weather • Gemini • budget • itinerary
    │  review • notification • analytics • sharing • PDF export • storage
    ▼
Repositories (parameterised SQL, ownership predicates)
    │
    ├── Neon Postgres (production; pooled connection)
    └── SQLite (tests / offline local development only)
```

External calls are made through pooled `httpx` clients with timeouts and
sanitised public errors. Gemini receives only real Google Places candidate IDs;
its output is structurally validated, checked against those IDs and the trip
dates, and retried once before anything is saved.

---

## Modules and endpoints

All routes are under `/api/v1` unless noted.

### Core

| Module | Endpoints |
|---|---|
| Health | `GET /`, `GET /health`, `GET /health/ready` |
| Authentication | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/google/url` |
| Users | `GET/PATCH /users/me`, `GET/PUT /users/me/preferences`, `GET /users/me/history`, saved-destination CRUD |
| Destinations | `GET /destinations/search`, `GET /destinations/{place_id}`, `GET /destinations/photo`, `POST /destinations/route`, nearby attractions/restaurants/type-filtered Places |
| Itineraries | `POST /itineraries/generate`, list/get/update/delete, share create/list/revoke, PDF export |
| Recommendations | `POST /recommendations/` (deterministic ranking of real Places data) |
| Weather | `GET /weather/{destination}` with optional date range |
| Reviews | `POST /reviews`, `GET /reviews/me`, `GET /reviews/place/{place_id}`, `PATCH/DELETE /reviews/{review_id}` |
| Notifications | `GET /notifications`, `POST /notifications/read-all`, `PATCH /notifications/{id}/read`, `DELETE /notifications/{id}` |
| Analytics / reports | `GET /analytics/me`, `GET /analytics/me/export.csv` |
| Sharing | Public `GET /shared/itineraries/{token}` |

See [docs/REST_API.md](backend/docs/REST_API.md) for request/response details,
error codes, and examples. Import both Postman files and select the
**Smart Travel Planner - Local** environment:

- [backend/postman/Smart_Travel_Planner.postman_collection.json](backend/postman/Smart_Travel_Planner.postman_collection.json)
- [backend/postman/Smart_Travel_Planner.postman_environment.json](backend/postman/Smart_Travel_Planner.postman_environment.json)

Its pre-request script generates future trip dates, and test scripts capture
access tokens, place IDs, itinerary/review/notification IDs, and share tokens as
responses arrive. Destructive requests are labelled and should run last.

---

## Data honesty

These rules are enforced in code and repeated in API responses:

- **No invented places.** Gemini may only reference exact `place_id` values from
  Google Places candidates supplied in the prompt. Unknown IDs, wrong dates,
  duplicate places in one day, overlapping times, and invalid day counts are
  rejected. A failed validation triggers one corrective retry, then a `502`.
- **No invented live facts.** Opening hours and ratings come from Google Places
  when present. The backend never fabricates hours, availability, ticket prices,
  or live hotel/flight prices.
- **Estimates are labelled.** Every monetary value produced by the planner is
  `cost_type: "estimated"` and carries a disclaimer. No provider in this
  integration returns a verified live price.
- **Budget categories are explicit:** transportation, accommodation, food,
  activities, and other. Responses include total, per-person, remaining, and an
  over-budget warning when applicable.
- **Weather coverage is honest.** `forecast_covers_requested_dates` is `true`,
  `false`, or `null` (forecast unavailable). Dates outside the provider horizon
  are never presented as a reliable forecast.
- **Reviews are user content.** They are separate from Google ratings and are
  not described as verified visits.
- **Analytics never mix currencies.** Amounts are grouped by ISO currency; no
  exchange-rate conversion or cross-currency summation occurs.

---

## Security

- Passwords are handled exclusively by Neon Auth (Managed Better Auth). This
  service never stores, hashes, or logs passwords.
- Access tokens are EdDSA (Ed25519) JWTs issued by Neon Auth and verified
  against its JWKS endpoint. `AUTH_HS256_SECRET` exists only for the offline
  test suite and is rejected when `APP_ENV=production`.
- Session model: register/login return a 15-minute access JWT **plus** a
  7-day session token (the `refresh_token`). `POST /auth/refresh` exchanges the
  session token for a fresh access JWT (the session does not rotate);
  `POST /auth/logout` revokes the session.
- Every user-owned SQL query includes `user_id` in the predicate. Row-level
  security is deliberately not configured: the backend is the only database
  client and enforces ownership itself.
- Share links use 32-byte URL-safe random tokens. Only a SHA-256 hash is stored.
  Links expire (1–365 days) and can be revoked. Public views exclude account,
  preference, and generation-metadata fields.
- Application access logs redact share tokens, and API responses set
  `Cache-Control: no-store`. See the deployment notes about proxy access logs.
- CORS uses exact origins; wildcards are rejected in production. Trusted hosts,
  HSTS (production), `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, and a restrictive `Permissions-Policy` are applied.
- Authentication endpoints are rate-limited per client IP. Request bodies are
  size-limited and requests have a configurable timeout.
- Secrets are wrapped in `SecretStr`, are read from environment variables or
  `backend/.env`, and are never returned by API or health endpoints.

---

## Repository layout

```
Project_Smart_Traveler_AI/
├── README.md
└── backend/
    ├── app/
    │   ├── api/v1/          # HTTP routers (auth, users, destinations, ...)
    │   ├── core/            # security, middleware, exceptions
    │   ├── database/        # PostgreSQL/SQLite connection + repositories + SQLite schema
    │   ├── models/          # enums and shared domain values
    │   ├── schemas/         # Pydantic request/response models
    │   ├── services/        # integrations, domain rules, PDF/CSV, sharing
    │   ├── utils/           # JSON, cache, interests, time helpers
    │   ├── assets/          # bundled DejaVu fonts + license for Unicode PDFs
    │   ├── config.py        # environment settings and production guards
    │   ├── dependencies.py  # FastAPI dependency providers
    │   └── main.py          # app factory, lifespan, middleware, health, errors
    ├── docs/
    │   └── REST_API.md
    ├── neon/
    │   └── schema.sql       # production tables, triggers, indexes (apply with psql)
    ├── postman/
    │   ├── Smart_Travel_Planner.postman_collection.json
    │   └── Smart_Travel_Planner.postman_environment.json
    ├── tests/               # offline endpoint + integration tests
    ├── Dockerfile
    ├── .env.example
    ├── requirements.txt
    ├── requirements-dev.txt
    └── pytest.ini
```

Legacy Supabase assets are kept for reference only (`backend/supabase/`,
the old schema); the Supabase auth service code itself has been removed.

---

## Prerequisites

- Python **3.11+** (the project was last tested on Python 3.14)
- A Neon project (AWS `ap-southeast-1` recommended) with the **Neon Auth**,
  **AI Gateway**, and **Object Storage** services enabled on the `production`
  branch (`neon.ts` declares the branch policy; `neon init` links the project)
- The Neon CLI (`neon`) with an authenticated profile; `neon env pull` writes
  branch secrets to the repo-root `.env.local`
- API keys for Google Maps Platform (Places API New, Geocoding API, Routes API),
  Google Gemini, and OpenWeather
- Optional: a frontend at `FRONTEND_URL`; `GET /auth/google/url` redirects
  there after Neon Auth completes the OAuth exchange

---

## Setup

### 1. Create the virtual environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
```

### 2. Link Neon and pull branch secrets

```bash
neon init     # links project/branch, writes neon.ts, installs the Neon MCP server
neon deploy   # creates bucket `assets` and function `hello` from neon.ts
neon env pull # writes DATABASE_URL (pooled) and DATABASE_URL_UNPOOLED to .env.local
```

### 3. Configure environment variables

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`. Never commit it. At minimum, set:

- `DATABASE_URL` — Neon **pooled** connection string (copy from `.env.local`)
- `NEON_AUTH_BASE_URL`, `NEON_AUTH_JWKS_URL`, `NEON_AUTH_ORIGIN` — Neon Auth
- `GEMINI_API_KEY` (or enable the Neon AI Gateway and set
  `NEON_AI_GATEWAY_BASE_URL` + `NEON_AI_GATEWAY_TOKEN`)
- `GOOGLE_MAPS_API_KEY`, `OPENWEATHER_API_KEY`
- exact `CORS_ORIGINS` and `ALLOWED_HOSTS` for your deployment
- `FRONTEND_URL` and `GOOGLE_OAUTH_REDIRECT_URL`

Use the pooled connection string for `DATABASE_URL`. Use
`DATABASE_URL_UNPOOLED` only for migrations (step 4).

### 4. Apply the Neon schema

From the repository root (uses the direct, non-pooled URL):

```bash
set -a && source .env.local && set +a
psql "$DATABASE_URL_UNPOOLED" -f backend/neon/schema.sql
```

This creates profiles, preferences, itineraries/days/activities, saved
destinations, reviews, notifications, share links, updated-at triggers, and
indexes. It is idempotent (safe to re-run). No RLS and no Supabase
realtime publication: the backend is the sole database client.

### 5. Google Cloud / OpenWeather / Gemini

- Enable **Places API (New)**, **Geocoding API**, and **Routes API** on the
  Google Cloud project used by `GOOGLE_MAPS_API_KEY`.
- Restrict the key by API and, where possible, by server IP.
- Enable the OpenWeather **Current Weather** and **5 day / 3 hour Forecast**
  APIs for `OPENWEATHER_API_KEY`.
- Create a Gemini API key and choose a model with structured output support
  (`GEMINI_MODEL`, default `gemini-2.5-flash`), or route through the Neon AI
  Gateway (`NEON_AI_GATEWAY_BASE_URL` ends in `/gemini`; the gateway token is
  the API key). Gateway models need Neon Billing credits.

### 6. Run the API

From `backend/`:

```bash
../.venv/bin/uvicorn app.main:app --reload --no-access-log --host 127.0.0.1 --port 8000
```

`--no-access-log` prevents Uvicorn from writing share-link tokens to its own
access log. If a reverse proxy fronts the API, redact or disable access logging
for `/api/v1/shared/itineraries/*` there as well. The application logger already
redacts those tokens.

Then open:

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- Health: <http://127.0.0.1:8000/health>
- Readiness: <http://127.0.0.1:8000/health/ready>

`/health` only reports whether credentials are configured; it does not spend
third-party quota. `/health/ready` performs a database round trip against Neon.

### 7. Or run it in Docker (laptop-local)

From the repository root:

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

`docker-compose.yml` publishes `127.0.0.1:8000:8000` — even though uvicorn
binds `0.0.0.0` inside the container, the API is reachable from this machine
alone. Secrets come from `backend/.env`; nothing else is duplicated locally.

---

## Tests

Tests are fully offline: external services are faked at the service boundary,
and SQLite is created per test in a temporary directory. No API keys or network
access are required.

```bash
cd backend
../.venv/bin/python -m pytest -q
../.venv/bin/python -m pytest --cov=app --cov-report=term-missing -q
```

Current result: **106 passed**, **90% coverage** (full offline suite; no
network required).

Coverage includes authentication/JWT failures (EdDSA JWKS + algorithm-confusion
rejection), ownership enforcement, generation validation and retry, budget
warnings, Places/Routes/weather normalisation, Neon Auth integration error
mapping, reviews, notifications, analytics currency separation, share
expiry/revocation, PDF generation, CORS, body limits, and error envelopes.

---

## Quick smoke test

```bash
# Liveness
curl http://127.0.0.1:8000/health

# Register (Neon Auth must be configured)
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"traveler@example.com","password":"StrongPass123","full_name":"Test Traveler"}'

# Save the returned access_token and refresh_token (the 7-day session token)
export TOKEN='<access-token>'
export SESSION='<refresh_token>'
curl -s "http://127.0.0.1:8000/api/v1/destinations/search?query=Kyoto&limit=5" \
  -H "Authorization: Bearer $TOKEN"

# Refresh the access JWT with the session token
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$SESSION\"}"

# Generate an itinerary (requires Maps + Gemini keys)
curl -s -X POST http://127.0.0.1:8000/api/v1/itineraries/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "destination": "Kyoto, Japan",
    "start_date": "2026-12-10",
    "end_date": "2026-12-12",
    "travellers": 2,
    "total_budget": 2500,
    "currency": "USD",
    "interests": ["history", "food"],
    "accommodation_preference": "midrange_hotel",
    "transportation_preference": "mixed",
    "pace": "balanced"
  }'
```

The generation request uses `destination_place_id` when supplied; otherwise
the destination is resolved with Google Places first.

---

## Database and ownership model

Production tables are defined in `backend/neon/schema.sql` (applied with
`psql "$DATABASE_URL_UNPOOLED"`):

- `profiles` — `id` matches the Neon Auth user UUID (no FK by design)
- `travel_preferences`
- `itineraries` → `itinerary_days` → `itinerary_activities` (cascade deletes)
- `saved_destinations`
- `reviews`
- `notifications`
- `itinerary_shares` (SHA-256 token hashes only)

The backend connects with the Neon pooled connection string. It does not rely
on RLS for authorization; every repository method that touches user data
includes an owner predicate. Neon Auth's own tables live in the `neon_auth`
schema and are managed by Neon.

`AUTO_CREATE_SCHEMA` only has an effect for SQLite. In Postgres, apply
`neon/schema.sql` explicitly and leave the flag `false`.

---

## Error format

All application errors use a stable envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "Itinerary not found.",
    "details": null,
    "request_id": "…"
  }
}
```

Validation errors use `code: "validation_error"` with safe field locations and
messages. Unexpected errors return `internal_error` without internal details;
the full exception is logged with the request ID for support.

Common status codes: `401` missing/invalid token, `403` forbidden, `404`
missing or not owned, `409` conflict/duplicate, `422` validation or
AI-constraint rejection, `429` rate limit, `502` unusable external/AI response,
`503` unconfigured integration, `504` request timeout.

---

## Production checklist

- [ ] `APP_ENV=production`, `DEBUG=false`
- [ ] `DATABASE_URL` is the Neon **pooled** URL (SQLite is rejected)
- [ ] `AUTO_CREATE_SCHEMA=false`; `neon/schema.sql` applied via `DATABASE_URL_UNPOOLED`
- [ ] `NEON_AUTH_BASE_URL` + `NEON_AUTH_JWKS_URL` set (EdDSA verification)
- [ ] `AUTH_HS256_SECRET` unset (it is rejected in production)
- [ ] Google/other social providers configured in Neon Auth; trusted domains
      registered with `neon neon-auth domain add`
- [ ] Gemini, Maps, and OpenWeather keys configured with least privilege
- [ ] `CORS_ORIGINS` and `ALLOWED_HOSTS` contain exact production values
- [ ] Reverse proxy terminates TLS and forwards `X-Forwarded-Proto`
- [ ] Uvicorn runs with `--no-access-log`; proxy access logs redact
      `/api/v1/shared/itineraries/*` tokens
- [ ] Rate limits and request-size limits also enforced at the proxy
- [ ] Database backups/point-in-time recovery enabled (Neon instant restore)
- [ ] Monitoring/alerts on `/health/ready`, 5xx rates, and external latency
- [ ] Share-link expiry/revocation policy agreed with the product owner
- [ ] Budget estimates and AI disclaimers preserved in any client UI

### Known limitations

- No React frontend is included.
- No live booking, flight, train, ticket, or hotel-price API is integrated.
  Hotels/restaurants come from Google Places; routes from Google Routes. Any
  price is a planning estimate.
- OpenWeather forecast coverage is limited to the provider's horizon.
- Notification records are created when an itinerary is generated. Scheduled
  trip reminders and delivery workers are not included; clients can poll the
  notifications API or subscribe via Neon Realtime.
- Analytics reports are derived from saved records and do not convert currencies.
- Share tokens are bearer secrets in a URL. Use HTTPS, avoid placing links in
  logs, and revoke links when no longer needed.
- `reportlab` and the bundled DejaVu fonts are used for Unicode-capable PDFs;
  see `backend/app/assets/DejaVuSans-LICENSE.txt`.

---

## License

The bundled DejaVu font files are licensed under the DejaVu Fonts license
included at `backend/app/assets/DejaVuSans-LICENSE.txt`. Application source
licensing is not specified by this deliverable.
