# Deployment & Mobile — Smart Travel Planner

The API and a ready-to-use web app run as **one Docker image on Render**. The
same React SPA is also deployed to **Vercel** as a static frontend that calls the
Render API. Vercel serves the UI; Render keeps the long-running FastAPI process,
database access and integrations.

| Target | URL / artifact | Status |
| --- | --- | --- |
| Vercel web app | <https://smart-travel-planner-nine-teal.vercel.app> | Live |
| Render all-in-one | <https://smart-travel-planner-nk60.onrender.com> | Live (API + SPA) |
| Local full stack | `http://127.0.0.1:8000` | `docker compose up -d --build` |
| Android APK | `frontend/android/app/build/outputs/apk/debug/app-debug.apk` | Debug-signed, installable |
| Installable PWA | Both production URLs | Install from Chrome / Safari |

---

## 0. Vercel (frontend)

Vercel hosts the static React build. The API stays on Render because FastAPI is
a long-running server, not a static site.

- **Project:** `smart-travel-planner` (Hobby plan)
- **Production URL:** <https://smart-travel-planner-nine-teal.vercel.app>
- **Root directory:** `frontend`
- **Framework:** Vite (`frontend/vercel.json` sets build, output and SPA rewrites)
- **Build command:** `npm run build` → `dist`
- **Environment variable:** `VITE_API_BASE_URL=https://smart-travel-planner-nk60.onrender.com`
  (set for Production and Preview in the Vercel project; also passed via
  `--build-env` so the value is baked into the bundle)

Redeploy after a frontend change:

```bash
./scripts/deploy_frontend.sh          # from the repo root
# or manually:
cd frontend
vercel deploy --prod --yes --project smart-travel-planner \
  --build-env VITE_API_BASE_URL=https://smart-travel-planner-nk60.onrender.com
```

**Hosting is permanent.** The production alias
<https://smart-travel-planner-nine-teal.vercel.app> always points at the latest
production deployment; Vercel keeps production deployments indefinitely on the
Hobby plan and the domain never changes between deploys.

**Auto-deploy on every push (optional, one-time setup):** GitHub rejects
workflow-file pushes from an OAuth credential without the `workflow` scope, so
pick ONE of these:

1. *GitHub Actions (recommended):* run `gh auth refresh -s workflow`, enter the
   one-time code at <https://github.com/login/device>, then run
   `gh auth setup-git` so pushes use the refreshed token. The prepared
   workflow lives at `.github/workflows/deploy-frontend.yml` (kept in the
   working tree); commit and push it — every subsequent push to `main` that
   touches `frontend/**` redeploys automatically. Repo secrets
   `VERCEL_TOKEN` and `VERCEL_ORG_ID` are already set.
2. *Vercel Git integration:* in the Vercel dashboard connect the GitHub
   account (Login Connection), then `vercel git connect
   https://github.com/harshasamala9-lab/smart-travel-planner`. Vercel then
   deploys on every push without any workflow file.

When the Vercel origin changes, add it to the Render `CORS_ORIGINS` variable and
to the Neon Auth trusted domains (`neon neon-auth domain add <origin>`), then
redeploy the Render service so the new CORS list takes effect.

---

## 1. Render (production)

The service is defined by `render.yaml` and built from the root `Dockerfile`:

- **Type:** Web Service, **runtime:** Docker
- **Plan:** Free (spins down after 15 minutes of inactivity; the next request
  takes ~50 seconds to wake it)
- **Region:** Singapore (same region as the Neon branch)
- **Health check:** `/health`
- **Repository:** `github.com/harshasamala9-lab/smart-travel-planner`, branch `main`
- **Deploys:** start a build with **Manual Deploy → Deploy latest commit** in the
  dashboard, or `POST /v1/services/<service-id>/deploys` with a Render API key.
  Automatic deploys on push require the Render GitHub App to be installed for
  the repository (Dashboard → Account Settings → GitHub).

### Environment variables (Render dashboard → Environment)

Set these as secret values; never commit them.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Neon **pooled** Postgres URL (`postgresql://…`) |
| `NEON_AUTH_BASE_URL`, `NEON_AUTH_JWKS_URL` | Neon Auth (Managed Better Auth) |
| `NEON_AUTH_ORIGIN` | Public app origin, e.g. `https://smart-travel-planner-nk60.onrender.com` |
| `CORS_ORIGINS` | Comma-separated exact origins (web + `https://localhost` for the APK) |
| `ALLOWED_HOSTS` | `smart-travel-planner-nk60.onrender.com` |
| `FRONTEND_URL`, `GOOGLE_OAUTH_REDIRECT_URL` | Public app origin and `/auth/callback` |
| `GOOGLE_MAPS_API_KEY` | Places, Geocoding, Routes |
| `OPENWEATHER_API_KEY` | Current weather + forecast |
| `GEMINI_API_KEY`, `GROK_API_KEY` | AI itinerary providers (optional) |
| `AI_PROVIDER_ORDER` | `gemini,grok` (falls through on failure) |
| `NEON_AI_GATEWAY_*`, `AWS_*`, `NEON_REALTIME_*` | Optional Lakebase primitives |

Optional integrations are genuinely optional: without Maps/AI the app still
serves the curated 80-destination catalog and generates a deterministic,
clearly-labelled travel plan.

After changing the public URL, update `CORS_ORIGINS`, `ALLOWED_HOSTS`,
`FRONTEND_URL`, `GOOGLE_OAUTH_REDIRECT_URL` and `NEON_AUTH_ORIGIN`, then add the
new origin as a Neon Auth trusted domain:

```bash
neon neon-auth domain add https://<new-host>
```

### Deploying manually

```bash
gh repo view harshasamala9-lab/smart-travel-planner --web   # or push to main
# Render rebuilds automatically; watch the deploy in the dashboard.
```

---

## 2. Local full stack (Docker)

```bash
cp backend/.env.example backend/.env   # then fill in real values
docker compose up -d --build
open http://127.0.0.1:8000
```

The image builds the React app in a Node stage and copies `dist/` into the
Python runtime. `backend/.env` is mounted at runtime, never baked into the
image (`.dockerignore` excludes it). `docker compose` also pins public DNS
resolvers because some Linux desktops run `systemd-resolved` on `127.0.0.53`,
which containers cannot reach.

---

## 3. Android APK (Capacitor 8)

Requirements: **JDK 21** and Android SDK **platform 36 / build-tools 36.0.0**.

```bash
export JAVA_HOME=/path/to/jdk-21
export ANDROID_HOME=/path/to/android-sdk

cd frontend
VITE_API_BASE_URL=https://smart-travel-planner-nk60.onrender.com npm run build
npx cap sync android
cd android
./gradlew assembleDebug
```

Result: `frontend/android/app/build/outputs/apk/debug/app-debug.apk`

Copy it to the phone and open it (allow "install unknown apps" once).

- The API URL is baked into the JS bundle at build time, so changing hosts means
  rebuilding the APK.
- The Capacitor WebView origin is `https://localhost`; it is already present in
  `CORS_ORIGINS` and Neon Auth trusted domains.
- `assembleDebug` is signed with the local debug keystore, which is fine for
  personal installation. For Play Store distribution, create a release keystore
  (`keytool -genkeypair`) and a `signingConfig`, then run `assembleRelease`.

---

## 4. Install as a PWA (no APK needed)

Open the production URL in Chrome (Android) or Safari (iOS) → **Add to Home
screen**. The app ships a web manifest and branded icons, and launches
full-screen with the same functionality as the APK.

---

## 5. Verification checklist

```bash
curl -s https://smart-travel-planner-nk60.onrender.com/health | jq
# → status ok, environment production, integrations flagged individually

curl -s -o /dev/null -w '%{http_code}\n' https://smart-travel-planner-nk60.onrender.com/explore
# → 200 (SPA fallback route)

# Travel-only search, authenticated
curl -s "https://smart-travel-planner-nk60.onrender.com/api/v1/destinations/search?query=laptop%20repair" \
  -H "Authorization: Bearer $TOKEN"
# → {"count": 0, "message": "Smart Travel Planner searches travel only. …"}
```

The same endpoints were exercised end-to-end on the deployed service:
login, travel-only search, featured destinations, curated detail, weather and
itinerary generation (returns `201` with the deterministic planner when AI
providers are unavailable).

---

## Notes

- Google Places/Routes and Grok require valid, unrestricted provider keys. When
  they fail, the app degrades honestly instead of erroring: curated catalog for
  search, deterministic planner for itineraries, and explicit warnings.
- OpenWeather forecast coverage is limited to the provider's horizon.
- Secrets live only in `backend/.env` locally and Render environment variables in
  production. `backend/.env`, `.env.local`, `frontend/.env` and `tools/` are
  gitignored.
