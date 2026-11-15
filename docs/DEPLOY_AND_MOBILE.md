# Deploying & Mobile — Smart Travel Planner

Three targets are covered here:

1. **Local (PC)** — already working: `start-dev.cmd` runs backend (port 8000) + frontend (port 5173).
2. **Web hosting on Vercel** — hosts the React frontend.
3. **Android APK** — installs the same app as a real phone app (Capacitor).

---

## 1. Host the frontend on Vercel

`frontend/vercel.json` is already configured (SPA rewrites, asset caching).

### Option A — Vercel Dashboard (easiest)
1. Push this project to GitHub (or zip-upload).
2. Go to <https://vercel.com/new>, import the repo.
3. **Root Directory:** `frontend`
4. Framework preset: **Vite** (auto-detected from `vercel.json`).
5. Environment variable (Production):
   - `VITE_API_BASE_URL` → your public backend URL (see "About the backend" below).
6. Click **Deploy**. Done.
7. **After deploying:** copy your final URL (e.g. `https://your-app.vercel.app`)
   and append it to `CORS_ORIGINS` in `backend/.env` (comma-separated), then
   restart the backend — browsers enforce CORS against every origin.

### Option B — Vercel CLI
```cmd
cd frontend
npm install -g vercel
vercel login
set VITE_API_BASE_URL=https://YOUR-BACKEND.example.com
vercel --prod
```

### About the backend (important, honest note)
Vercel hosts **static frontends** — the FastAPI backend needs a long-running
server, so it cannot be "deployed to Vercel" as-is. The database (Neon
Postgres) and auth (Neon Auth) are already cloud-hosted, which is why the
backend itself is the only piece that must run somewhere reachable:

- **Easiest:** keep running it on your PC with `start-backend-lan.cmd`
  (reachable from your phone on the same Wi-Fi), or
- **Public URL (free):** deploy `backend/` to Render — the blueprint
  `backend/render.yaml` and `backend/Dockerfile` are ready; add the secret
  values (same ones as `backend/.env`) in the Render dashboard. Your public
  API URL becomes `https://<service>.onrender.com` — put that into
  `VITE_API_BASE_URL` on Vercel and in `ANDROID_API_BASE_URL` for the APK.

While the backend runs only on your PC, use the app from your PC in the
browser — the hosted Vercel site and phone APK need a reachable backend URL.

---

## 2. Android APK (Capacitor)

### One-time setup (~10 min, no admin rights, ~700 MB downloads)
```cmd
powershell -ExecutionPolicy Bypass -File tools\setup_android_sdk.ps1
```
Installs JDK 21 + Android SDK into `tools\` (verified versions for Capacitor 7).

### Build the APK
```cmd
build-apk.cmd
```
- Default `ANDROID_API_BASE_URL=http://10.0.2.2:8000` — for the **emulator**
  (10.0.2.2 is the PC's loopback seen from Android).
- For a **real phone** on the same Wi-Fi:
  ```cmd
  ipconfig                     REM find your IPv4, e.g. 192.168.1.5
  set ANDROID_API_BASE_URL=http://192.168.1.5:8000
  build-apk.cmd
  ```
- Start the backend so the phone can reach it: `start-backend-lan.cmd`

Result: `frontend\android\app\build\outputs\apk\debug\app-debug.apk`
Copy it to the phone and open it (allow "install unknown apps" once).

### Where the API URL lives
The web app is built with `VITE_API_BASE_URL` baked in (`frontend/src/lib/api.js`).
The APK build script sets it before `npm run build` and then runs
`npx cap sync android`. Changing the backend URL = rebuild the APK.

### Also available: install-as-PWA (no APK needed)
The frontend now ships a web manifest (`public/manifest.webmanifest`) with
branded icons. On Android Chrome open the site → ⋮ menu → **Add to Home
screen** → it launches full-screen like a native app. Same for iOS Safari via
Share → Add to Home Screen.

### Notes
- Debug APKs are for personal use; a signed release APK needs a keystore
  (`keytool -genkeypair` + `gradlew assembleRelease` with signing config).
- Google Sign-In from the APK/PWA requires the callback origin to be
  registered in Neon Auth (`neon neon-auth domain add`). Email/password works
  everywhere already.
- The backend's `CORS_ORIGINS` must include `https://localhost` (the APK
  origin). `backend/.env` has been updated for this.
