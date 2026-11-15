# Smart Travel Planner — Frontend

Premium React frontend for the **Smart Travel Planner** FastAPI backend.
React 18 + Vite 5 + Tailwind CSS 3 + Framer Motion + Lucide + React Router 6.

> The backend is a separate, completed service — see the repository README for
> its setup. This frontend only *consumes* the documented `/api/v1` contracts
> and never modifies them.

---

## 1. Run it (development)

```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000`, so the full
experience works as soon as the backend is running (`uvicorn app.main:app`
from `backend/`). CORS is already configured for port 5173 in the backend.

Production:

```bash
npm run build        # outputs dist/
npm run preview      # serves dist/ locally
```

## 2. Environment variables (`frontend/.env`)

Fill these in yourself — they are left empty on purpose:

| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Public origin of the FastAPI API. Empty = same-origin (dev proxy handles it). | *(empty)* |
| `VITE_GOOGLE_MAPS_API_KEY` | Optional. Shows a Google **Maps Embed** on destination pages. Restrict the key to your domain + "Maps Embed API". | *(empty)* |

**Never** put provider secrets (Gemini, OpenWeather, full Google Maps Platform
keys) in the frontend — `VITE_*` values are readable by every visitor. All
provider keys live in `backend/.env`.

## 3. What's inside

| Page | Route | Auth | Notes |
|---|---|---|---|
| Landing | `/` | public | Hero video, typewriter, destination showcase, features, how-it-works |
| Sign in / Register | `/login`, `/register` | guest | Validation mirrors backend rules (8+ chars, letter+digit) |
| Google OAuth callback | `/auth/callback` | public | Reads tokens Neon Auth attaches to the redirect when present |
| Dashboard | `/dashboard` | ✅ | Real analytics, upcoming trips, saved places, CSV export |
| Explore | `/explore` | ✅ | Debounced, cancelable Google Places search + category filters |
| Destination detail | `/destinations/:placeId` | ✅ | Photos via auth proxy, nearby spots, weather, optional map embed |
| AI Planner | `/planner` | ✅ | Full `GenerateItineraryRequest` schema, duplicate-submit guard |
| Itinerary | `/itineraries/:id` | ✅ | Day timeline, budget breakdown, weather, PDF/CSV export, share links, edit/delete |
| My Trips | `/itineraries` | ✅ | Status tabs (upcoming / active / completed / draft / archived), search |
| Profile | `/profile` | ✅ | Profile PATCH, preferences PUT, saved places, logout |
| Shared itinerary | `/shared/:token` | public | Read-only view of a private share link |
| 404 | `*` | public | — |

Session model: the backend returns a **15-minute access JWT** + a **7-day
session token**; the API client refreshes transparently on 401 and revokes the
session server-side on logout.

## 4. Media licensing

- **Photography** — hotlinked from **Wikimedia Commons** under CC / Public
  Domain licenses (each URL verified live). Full credits render in the footer
  (`imageCredits()`).
- **Hero video** — *"Stunning Tropical Beach Aerial View"*, Pexels, downloaded
  to `public/media/hero-travel.mp4` under the **Pexels License** (free to use,
  no attribution required — credited anyway).
- The hero video is muted, `preload="none"` with a poster fallback, and fully
  disabled for `prefers-reduced-motion` users.

## 5. Honest-data commitments honored by the UI

- Budget values always show the backend's `cost_type: "estimated"` badge and
  its disclaimer text.
- Weather panels state whether the forecast actually covers the requested
  dates (`forecast_covers_requested_dates`).
- When Google Maps / Gemini / OpenWeather keys are missing on the server,
  related features show a clear "not configured" message (HTTP 503) instead of
  pretending to work.
- No invented testimonials, user counts, or demo data anywhere.

## 6. Performance notes (low-end friendly)

- Route-level `React.lazy` code splitting + `Suspense` fallback.
- Vendor chunks split (`react`, `framer-motion`, `lucide`).
- All images lazy-loaded with aspect-ratio boxes (zero layout shift).
- Debounced search with `AbortController` cancellation.
- The only "video" is the single muted, poster-backed hero clip — no autoplay
  audio, no WebGL, no particle systems.
- Animations respect `prefers-reduced-motion` (CSS + Framer Motion).
