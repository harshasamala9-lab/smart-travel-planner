"""Build the 25-slide educational presentation for the Smart Travel Planner AI project.

Output: docs/Smart_Travel_Planner_AI_Presentation.pptx
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# ---------------------------------------------------------------- palette
NAVY = RGBColor(0x14, 0x21, 0x3D)
NAVY_SOFT = RGBColor(0x1F, 0x2F, 0x55)
TEAL = RGBColor(0x2E, 0xC4, 0xB6)
AMBER = RGBColor(0xFC, 0xA3, 0x11)
LIGHT = RGBColor(0xF7, 0xF9, 0xFC)
INK = RGBColor(0x1B, 0x24, 0x30)
GREY = RGBColor(0x6B, 0x77, 0x86)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xDD, 0xE4, 0xEC)
GREEN = RGBColor(0x2A, 0x9D, 0x8F)
RED = RGBColor(0xE6, 0x39, 0x46)

FONT = "Calibri"
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

PROJECT = "Smart Travel Planner AI"
RENDER_URL = "https://smart-travel-planner-nk60.onrender.com"
VERCEL_URL = "https://smart-travel-planner-nine-teal.vercel.app"

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- helpers
def add_slide():
    return prs.slides.add_slide(BLANK)


def box(slide, x, y, w, h, *, fill=None, line=None, line_w=0.75, shadow=False,
        shape=MSO_SHAPE.RECTANGLE):
    sp = slide.shapes.add_shape(shape, x, y, w, h)
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(line_w)
    sp.shadow.inherit = False
    return sp


def text(slide, x, y, w, h, runs, *, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         wrap=True, shrink=False):
    """runs: list of paragraphs; each paragraph is list of (text, size, bold, color)."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Pt(2)
    tf.margin_top = tf.margin_bottom = Pt(2)
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        for t, size, bold, color in para:
            r = p.add_run()
            r.text = t
            r.font.name = FONT
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
    return tb


def bullets(slide, x, y, w, h, items, *, size=15, color=INK, gap=6, lead_color=TEAL,
            line_spacing=1.0):
    """items: list of str or (str, level) tuples."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        txt, lvl = item if isinstance(item, tuple) else (item, 0)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = line_spacing
        p.level = lvl
        marker = "•  " if lvl == 0 else "–  "
        r = p.add_run()
        r.text = marker + txt
        r.font.name = FONT
        r.font.size = Pt(size if lvl == 0 else size - 1.5)
        r.font.color.rgb = color if lvl == 0 else GREY
        if lvl > 0:
            r.font.color.rgb = RGBColor(0x44, 0x52, 0x62)
        # Colour the marker separately.
        first = p.runs[0]
        first.text = marker
        first.font.color.rgb = lead_color
        second = p.add_run()
        second.text = txt
        second.font.name = FONT
        second.font.size = Pt(size if lvl == 0 else size - 1.5)
        second.font.color.rgb = color if lvl == 0 else RGBColor(0x44, 0x52, 0x62)
    return tb


def footer(slide, number):
    box(slide, Inches(0.7), Inches(7.06), Inches(11.93), Pt(1), fill=LINE)
    text(slide, Inches(0.7), Inches(7.1), Inches(6), Inches(0.35),
         [[(PROJECT, 10, False, GREY)]])
    text(slide, Inches(11.6), Inches(7.1), Inches(1.03), Inches(0.35),
         [[(str(number), 10, True, GREY)]], align=PP_ALIGN.RIGHT)


def content_slide(title, subtitle=None, accent=TEAL):
    slide = add_slide()
    box(slide, 0, 0, SLIDE_W, SLIDE_H, fill=WHITE)
    box(slide, 0, 0, Inches(0.22), SLIDE_H, fill=NAVY)
    box(slide, Inches(0.7), Inches(0.52), Inches(0.55), Pt(4.5), fill=accent)
    text(slide, Inches(0.7), Inches(0.62), Inches(11.9), Inches(0.8),
         [[(title, 30, True, NAVY)]])
    if subtitle:
        text(slide, Inches(0.7), Inches(1.22), Inches(11.9), Inches(0.5),
             [[(subtitle, 14, False, GREY)]])
    return slide


def chip(slide, x, y, w, h, label, *, fill=TEAL, size=12, color=WHITE, bold=True):
    box(slide, x, y, w, h, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(slide, x, y, w, h, [[(label, size, bold, color)]],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def card(slide, x, y, w, h, title, lines, *, title_color=NAVY, fill=LIGHT,
         title_size=15, body_size=12.5, border=LINE):
    box(slide, x, y, w, h, fill=fill, line=border, line_w=1.0,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(slide, x + Inches(0.16), y + Inches(0.1), w - Inches(0.32), Inches(0.4),
         [[(title, title_size, True, title_color)]])
    bullets(slide, x + Inches(0.16), y + Inches(0.52), w - Inches(0.32),
            h - Inches(0.62), lines, size=body_size, gap=3)


def notes(slide, content):
    slide.notes_slide.notes_text_frame.text = content


# ================================================================ SLIDE 1
s = add_slide()
box(s, 0, 0, SLIDE_W, SLIDE_H, fill=NAVY)
box(s, 0, 0, SLIDE_W, Inches(0.18), fill=TEAL)
box(s, 0, SLIDE_H - Inches(0.18), SLIDE_W, Inches(0.18), fill=AMBER)
text(s, Inches(0.9), Inches(1.5), Inches(11.5), Inches(0.5),
     [[("EDUCATIONAL PROJECT PRESENTATION", 14, True, TEAL)]])
text(s, Inches(0.9), Inches(2.0), Inches(11.6), Inches(1.9),
     [[("Smart Travel Planner AI", 54, True, WHITE)],
      [("Production-ready trip planning with honest fallbacks", 22, False,
        RGBColor(0xC8, 0xD3, 0xE4))]])
box(s, Inches(0.95), Inches(3.85), Inches(2.2), Pt(3), fill=TEAL)
text(s, Inches(0.9), Inches(4.15), Inches(11.6), Inches(1.5),
     [[("FastAPI  ·  Neon Postgres  ·  Neon Auth  ·  React  ·  Docker  ·  Render  ·  Vercel  ·  Android",
        16, True, RGBColor(0xE8, 0xED, 0xF5))],
      [("Works perfectly with zero provider API keys — powered by Wikipedia + OpenStreetMap",
        14, False, RGBColor(0xC8, 0xD3, 0xE4))]])
text(s, Inches(0.9), Inches(6.0), Inches(11.6), Inches(1.0),
     [[("Web:  " + VERCEL_URL, 12, False, TEAL)],
      [("API:   " + RENDER_URL + "  ·  131 backend tests  ·  80 curated destinations",
        12, False, RGBColor(0xC8, 0xD3, 0xE4))]])
notes(s, "Welcome. This deck walks through the complete Smart Travel Planner AI project: "
         "architecture, database, keyless mode, AI planning, testing and deployment.")

# ================================================================ SLIDE 2
s = content_slide("Agenda", "What we will cover in 25 slides")
left = [
    "The problem and project goals",
    "System architecture and technology stack",
    "Neon Postgres: schema, pooling, resilience",
    "Neon Auth: managed authentication",
    "Travel-only search and the curated catalog",
    "Keyless open-data discovery (Wikipedia + OSM)",
]
right = [
    "AI itinerary generation with honest fallbacks",
    "Caching, weather, budget and analytics",
    "Security hardening",
    "Testing strategy — 131 automated tests",
    "Deployment: Docker → Render → Vercel → APK",
    "Results, live links and future work",
]
bullets(s, Inches(0.9), Inches(1.7), Inches(5.9), Inches(5.0), left, size=16, gap=12)
bullets(s, Inches(7.0), Inches(1.7), Inches(5.7), Inches(5.0), right, size=16, gap=12)
footer(s, 2)

# ================================================================ SLIDE 3
s = content_slide("The Problem", "Trip planning is fragmented and error-prone")
bullets(s, Inches(0.9), Inches(1.6), Inches(6.4), Inches(4.9), [
    "Travellers juggle 6–10 tabs: blogs, maps, weather, hotels, budgets",
    "AI chatbots invent places, ratings and opening hours",
    "Most apps silently fail when a third-party API is down or unpaid",
    "Retail noise: searching for attractions returns laptop repair shops",
    "Students need a full-stack reference that is honest about limits",
], size=16, gap=10)
card(s, Inches(7.6), Inches(1.6), Inches(5.1), Inches(4.9),
     "What users need", [
         "One trusted place: search → plan → budget → share",
         "Real, visitable places only — no hallucinations",
         "The app must never show 'service unavailable' for core flows",
         "Works even with no API keys at all",
     ], title_size=16)
footer(s, 3)

# ================================================================ SLIDE 4
s = content_slide("Project Goals", "What we promised — and delivered")
goals = [
    ("Strict travel-only search", "0 non-travel results in live regression tests"),
    ("Works without API keys", "Wikipedia + OSM keep every core flow alive"),
    ("Never blame the user for downtime", "deterministic planner returns 201, not 503"),
    ("Production deployment", "Docker, Render API, Vercel SPA, Android APK"),
    ("Honesty by design", "real photos, no invented ratings, labelled fallbacks"),
]
y = 1.55
for i, (t, d) in enumerate(goals):
    chip(s, Inches(0.9), Inches(y), Inches(0.42), Inches(0.42), str(i + 1), fill=TEAL, size=14)
    text(s, Inches(1.55), Inches(y - 0.03), Inches(11.0), Inches(0.9),
         [[(t + " —  ", 16, True, NAVY), (d, 14, False, GREY)]])
    y += 1.02
footer(s, 4)
notes(s, "Each goal maps to a concrete, testable guarantee — shown in the testing slide.")

# ================================================================ SLIDE 5
s = content_slide("The Solution at a Glance", "One API, three data tiers, zero hard failures")
tiers = [
    ("Tier 1 — Live integrations", [
        "Google Places & Routes (when a valid key exists)",
        "OpenWeather current + forecast",
        "Gemini / Grok AI itinerary drafts",
    ], TEAL),
    ("Tier 2 — Keyless open data", [
        "OpenStreetMap Nominatim geocoding",
        "Wikipedia geosearch → real landmarks",
        "Batched extracts with images and descriptions",
    ], AMBER),
    ("Tier 3 — Curated catalog", [
        "80 hand-verified destinations",
        "Wikipedia/Wikimedia imagery with attribution",
        "Always available, zero network required",
    ], NAVY_SOFT),
]
x = 0.9
for title, lines, color in tiers:
    box(s, Inches(x), Inches(1.65), Inches(3.85), Inches(4.6), fill=LIGHT,
        line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    box(s, Inches(x), Inches(1.65), Inches(3.85), Inches(0.55), fill=color,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(x + 0.15), Inches(1.7), Inches(3.6), Inches(0.5),
         [[(title, 14, True, WHITE)]])
    bullets(s, Inches(x + 0.2), Inches(2.4), Inches(3.5), Inches(3.7), lines,
            size=13, gap=8, color=INK, lead_color=color)
    x += 4.05
text(s, Inches(0.9), Inches(6.45), Inches(11.9), Inches(0.5),
     [[("If a tier fails, the next one answers — users see data, never downtime.",
        14, True, NAVY)]])
footer(s, 5)
notes(s, "The core idea: graceful degradation across three data tiers instead of hard 503 errors.")

# ================================================================ SLIDE 6
s = content_slide("System Architecture", "Single-origin FastAPI + SPA; everything stateless")
# Client boxes
clients = ["React SPA (Vercel)", "Android APK", "Share links (public)"]
x = 0.9
for c in clients:
    chip(s, Inches(x), Inches(1.55), Inches(3.6), Inches(0.55), c, fill=NAVY, size=13)
    x += 3.85
arrow_y = 2.25
for ax in (2.5, 6.35, 10.2):
    box(s, Inches(ax), Inches(arrow_y), Inches(0.4), Inches(0.45), fill=GREY,
        shape=MSO_SHAPE.DOWN_ARROW)
chip(s, Inches(3.2), Inches(2.85), Inches(6.9), Inches(0.6),
     "FastAPI + built React SPA  (same origin on Render)", fill=TEAL, size=15)
box(s, Inches(2.0), Inches(3.7), Inches(9.3), Inches(0.5), fill=LIGHT, line=LINE)
text(s, Inches(2.0), Inches(3.72), Inches(9.3), Inches(0.5),
     [[("Service layer:  search · itinerary · budget · reviews · sharing · analytics · export",
        12.5, True, NAVY)]], align=PP_ALIGN.CENTER)
arrow_row = 4.35
for ax in (2.5, 5.05, 7.6, 10.15):
    box(s, Inches(ax), Inches(arrow_row), Inches(0.4), Inches(0.4), fill=GREY,
        shape=MSO_SHAPE.DOWN_ARROW)
ext = [
    ("Neon Postgres\n(schema.sql)", NAVY),
    ("Neon Auth\n(JWT / JWKS)", TEAL),
    ("Optional APIs\nMaps · Weather · AI", AMBER),
    ("Open data\nWikipedia · OSM", GREEN),
]
x = 0.9
for label, color in ext:
    box(s, Inches(x), Inches(4.9), Inches(2.95), Inches(1.05), fill=color,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(x), Inches(4.95), Inches(2.95), Inches(1.0),
         [[(label, 12.5, True, WHITE)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    x += 3.07
footer(s, 6)
notes(s, "One Docker web service serves both the API and the built React SPA from the same "
         "origin — no CORS in production, one deploy unit.")

# ================================================================ SLIDE 7
s = content_slide("Technology Stack", "Every layer is free or has a working free tier")
rows = [
    ("Backend", "Python 3.12 · FastAPI · pydantic v2 · psycopg (pooling) · httpx"),
    ("Database", "Neon Lakebase Postgres — branching, autoscaling, instant restore"),
    ("Auth", "Neon Auth (Managed Better Auth) — email/password, JWT via JWKS"),
    ("AI", "Gemini + Grok (OpenAI-compatible) · deterministic planner fallback"),
    ("Frontend", "React 19 + Vite · custom SVG/CSS animated maps (no iframe)"),
    ("Mobile", "Capacitor — installable Android APK targeting API 36"),
    ("Caching", "In-process unbounded TTL caches with per-key locks"),
    ("DevOps", "Docker Compose · Render web service · Vercel static hosting"),
]
y = 1.6
for layer, detail in rows:
    chip(s, Inches(0.9), Inches(y), Inches(1.85), Inches(0.44), layer, fill=NAVY, size=12.5)
    text(s, Inches(2.95), Inches(y + 0.02), Inches(9.8), Inches(0.5),
         [[(detail, 13.5, False, INK)]])
    y += 0.63
footer(s, 7)

# ================================================================ SLIDE 8
s = content_slide("Backend Design", "Layered, typed, and testable")
card(s, Inches(0.9), Inches(1.55), Inches(5.75), Inches(4.9), "Layers", [
    "Routers (app/api/v1) — thin, schema-driven endpoints",
    "Service layer — all business rules and fallbacks",
    "Repositories — SQL only, parameterised",
    "Database facade — pool, transactions, health",
    "Schemas — pydantic v2 request/response contracts",
    "One lifespan wires every service into app.state",
], title_size=16)
card(s, Inches(6.95), Inches(1.55), Inches(5.75), Inches(4.9), "Conventions", [
    "Errors raise typed AppErrors → one uniform envelope",
    "Every external call wrapped: timeout, cache, fallback",
    "Deterministic UUIDs/tokens via stdlib, no magic",
    "Config: single pydantic Settings with validation",
    "Docs auto-generated OpenAPI for every route",
], title_size=16)
footer(s, 8)

# ================================================================ SLIDE 9
s = content_slide("Neon Postgres", "Serverless Lakebase with a branch-first workflow")
bullets(s, Inches(0.9), Inches(1.6), Inches(6.3), Inches(4.9), [
    "Autoscaling compute with scale-to-zero — free tier friendly",
    "Transaction-pooler endpoint (PgBouncer) for serverless apps",
    "Branching: schema applied on the main branch via schema.sql",
    "Instant restore — point-in-time recovery for free",
    "Cold starts are real: a sleeping compute takes seconds to wake",
    " idle sockets: the pooler closes them after a few minutes",
], size=15, gap=9)
card(s, Inches(7.5), Inches(1.6), Inches(5.2), Inches(4.9),
     "Why it matters here", [
         "Registration must work even right after the compute wakes",
         "Free tier means occasional cold starts in production",
         "That constraint drove the resilience engineering (next slide)",
     ], title_size=16, fill=RGBColor(0xFF, 0xF4, 0xDE), border=AMBER)
footer(s, 9)
notes(s, "Neon's scale-to-zero is a gift for a student project but a source of cold-start "
         "latency — the next slide shows how we made that invisible to users.")

# ================================================================ SLIDE 10
s = content_slide("Database Resilience", "Users never see 'database temporarily unavailable'")
left = [
    "AsyncConnectionPool.check_connection — the ASYNC validator",
    "  (the sync checker silently discards every pooled connection!)",
    "TCP keepalives + connect_timeout baked into conninfo",
    "max_lifetime=300s proactively rotates stale sockets",
    "4 connect attempts with 0.5 / 1 / 2 / 4 s backoff",
]
right = [
    "Checkout retried once before any user work has started",
    "  → a retry can never duplicate side effects",
    "Health check retried twice before reporting failure",
    "Pool timeout 30 s in production (cold compute wake-up)",
    "Verified live: register works right after Neon wakes",
]
card(s, Inches(0.9), Inches(1.55), Inches(5.75), Inches(3.6), "Connection layer", left,
     title_size=15, body_size=12.5)
card(s, Inches(6.95), Inches(1.55), Inches(5.75), Inches(3.6), "Transaction layer", right,
     title_size=15, body_size=12.5)
box(s, Inches(0.9), Inches(5.45), Inches(11.8), Inches(1.25), fill=RGBColor(0xEA, 0xF7, 0xF4),
    line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, Inches(1.15), Inches(5.62), Inches(11.3), Inches(1.0),
     [[("Bug we caught: using ConnectionPool.check_connection (sync) inside an async pool "
        "made every checkout discard its connection and time out. One-line fix — and a new "
        "dedicated test file (8 tests) locks it in.", 13.5, False, INK)]])
footer(s, 10)
notes(s, "This is the slide to linger on: it shows real production debugging — a subtle "
         "psycopg_pool API misuse that produced the exact 'temporarily unavailable' error "
         "the user reported.")

# ================================================================ SLIDE 11
s = content_slide("Authentication — Neon Auth", "Managed Better Auth with zero server cost")
bullets(s, Inches(0.9), Inches(1.6), Inches(6.3), Inches(4.7), [
    "Email + password sign-up with session tokens",
    "JWTs verified against the tenant's JWKS endpoint",
    "HS256 fallback for local/dev with a proper secret",
    "Profiles created on first authenticated request",
    "Trusted-domain allowlist: localhost, Render, Vercel, https",
    "Rate-limited auth endpoints (429 after N attempts)",
], size=15, gap=9)
card(s, Inches(7.5), Inches(1.6), Inches(5.2), Inches(4.7), "Flow", [
    "1 · SPA posts credentials to /auth/register|login",
    "2 · Neon Auth returns session + user record",
    "3 · Backend verifies JWT (JWKS) on every request",
    "4 · user_id links profiles, itineraries, reviews",
], title_size=16)
footer(s, 11)

# ================================================================ SLIDE 12
s = content_slide("Data Model", "Small, relational, ownership-enforced")
tables = [
    ("profiles", "user_id PK, email, name, avatar, preferences (JSONB)"),
    ("itineraries", "id, user_id FK, destination, dates, budget, plan (JSONB), model metadata"),
    ("itinerary_days / activities", "normalised days with ordered activities and costs"),
    ("reviews", "place_id + user unique pair, rating 1–5, text, edits tracked"),
    ("notifications", "user-scoped in-app messages with read state"),
    ("itinerary_shares", "expiring, revocable public tokens for read-only views"),
    ("analytics_events", "currency-safe aggregates for CSV reports"),
]
y = 1.55
for name, cols in tables:
    chip(s, Inches(0.9), Inches(y), Inches(3.0), Inches(0.46), name, fill=TEAL, size=12.5)
    text(s, Inches(4.1), Inches(y + 0.03), Inches(8.6), Inches(0.5),
         [[(cols, 13, False, INK)]])
    y += 0.66
text(s, Inches(0.9), Inches(6.3), Inches(11.9), Inches(0.5),
     [[("Every query filters by user_id — ownership is enforced in SQL, not just in code.",
        13.5, True, NAVY)]])
footer(s, 12)

# ================================================================ SLIDE 13
s = content_slide("Travel-Only Search Engine", "Retail noise never reaches the user")
card(s, Inches(0.9), Inches(1.55), Inches(5.75), Inches(4.9), "How results are filtered", [
    "Curated catalog matches first (photo + guide page)",
    "Google Places results filtered to travel categories",
    "Wikipedia landmarks filtered by a keyword blocklist",
    "Blocklist: schools, transit, retail, hospitals, offices…",
    "Even events: battles, famines, timelines excluded",
    "Verified live: 'laptop repair', 'shopping mall' → 0 results",
], title_size=16)
card(s, Inches(6.95), Inches(1.55), Inches(5.75), Inches(4.9), "Three merge sources", [
    "CATALOG  — 80 destinations, always available",
    "GOOGLE  — live places when the key is valid",
    "WIKIPEDIA  — live landmarks, no key needed",
    "Source string tells the truth, e.g.",
    " 'Curated travel catalog + Wikipedia (open data)'",
    "Users always see where every result came from",
], title_size=16)
footer(s, 13)

# ================================================================ SLIDE 14
s = content_slide("Keyless Open-Data Layer", "Real attractions with zero API keys")
steps = [
    ("1 · Geocode", "Nominatim resolves any destination to coordinates", GREEN),
    ("2 · Geosearch", "Wikipedia returns geolocated articles nearby", TEAL),
    ("3 · Filter", "Blocklist drops non-travel and event articles", AMBER),
    ("4 · Enrich", "Batched extracts: description, image, coordinates", NAVY_SOFT),
]
x = 0.9
for t, d, color in steps:
    box(s, Inches(x), Inches(1.6), Inches(2.85), Inches(2.1), fill=LIGHT, line=LINE,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    box(s, Inches(x), Inches(1.6), Inches(2.85), Inches(0.5), fill=color,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(x), Inches(1.63), Inches(2.85), Inches(0.5),
         [[(t, 13, True, WHITE)]], align=PP_ALIGN.CENTER)
    text(s, Inches(x + 0.15), Inches(2.25), Inches(2.55), Inches(1.4),
         [[(d, 12, False, INK)]])
    x += 3.02
bullets(s, Inches(0.9), Inches(4.0), Inches(11.9), Inches(2.6), [
    "wiki-{pageid} destinations: details, nearby attractions and itineraries all work",
    "Never invents ratings — Wikipedia results show rating: null by design",
    "Images from Wikimedia Commons with contributor attribution",
    "Cached with the same unbounded TTL cache — repeat visits cost zero requests",
    "Live check: Kyoto → Honnō-ji, Sanjō Ōhashi, Ponto-chō… all with photos",
], size=14, gap=7)
footer(s, 14)
notes(s, "This is the answer to 'it should work instead of API key perfectly' — the app's "
         "core flows run entirely on open data.")

# ================================================================ SLIDE 15
s = content_slide("The Curated Catalog", "80 destinations, verified imagery, zero drift")
bullets(s, Inches(0.9), Inches(1.6), Inches(6.3), Inches(4.8), [
    "80 destinations across cities, beaches, nature, heritage, food",
    "Every image returns HTTP 200 — sampled and verified",
    "Wikipedia/Wikimedia sources with visible credit lines",
    "Rich fields: country, best time, travel type, description",
    "Sorted 'featured' endpoint powers the public landing page",
    "Catalog doubles as the deterministic planner's material",
], size=15, gap=9)
card(s, Inches(7.5), Inches(1.6), Inches(5.2), Inches(4.8),
     "Why curated at all?", [
         "Google key can expire, be rate-limited or be billed",
         "A catalog is a guaranteed baseline: the app is NEVER empty",
         "Same records feed search, details, planning and share pages",
         "Regeneration is a script, not a manual chore",
     ], title_size=16, fill=RGBColor(0xFF, 0xF4, 0xDE), border=AMBER)
footer(s, 15)

# ================================================================ SLIDE 16
s = content_slide("AI Itinerary Generation", "Structured, validated, and candidate-grounded")
steps = [
    "Discover candidates: attractions, restaurants, hotels (Google → text → Wikipedia)",
    "Build a prompt with real candidate IDs, weather, budget, user preferences",
    "AI returns strict JSON (pydantic-validated AIItinerary model)",
    "Every referenced place must exist in the candidate index",
    "Invalid output → retry with the rejection appended to the prompt",
    "After retries fail → deterministic planner takes over (next slide)",
]
y = 1.7
for i, step in enumerate(steps, 1):
    chip(s, Inches(0.9), Inches(y), Inches(0.42), Inches(0.42), str(i), fill=NAVY, size=13)
    text(s, Inches(1.55), Inches(y - 0.02), Inches(11.2), Inches(0.8),
         [[(step, 14.5, False, INK)]])
    y += 0.78
text(s, Inches(0.9), Inches(6.4), Inches(11.9), Inches(0.5),
     [[("Providers: Gemini first, then Grok — provider order is configuration, not code.",
        13.5, True, NAVY)]])
footer(s, 16)

# ================================================================ SLIDE 17
s = content_slide("Deterministic Planner Fallback", "No AI? Still 201 — with honest labels")
card(s, Inches(0.9), Inches(1.55), Inches(5.75), Inches(4.9), "When it activates", [
    "All AI providers missing, throttled or invalid",
    "AI output rejected after the retry budget",
    "Response still created — status 201, never 503",
    "Label: 'deterministic planner (AI unavailable)'",
    "Warning added: 'Review each stop before booking'",
], title_size=16)
card(s, Inches(6.95), Inches(1.55), Inches(5.75), Inches(4.9), "What it builds", [
    "Day-by-day plan from attraction + food pools",
    "Paced days: morning stop, meal stop, afternoon stop",
    "Curated themes clearly say 'confirm opening hours locally'",
    "Costs are conservative estimates, flagged as estimates",
    "Users get a usable plan instead of an error page",
], title_size=16)
footer(s, 17)
notes(s, "Philosophy: degrade gracefully and label honestly. A plan built without AI is "
         "still valuable if it says so.")

# ================================================================ SLIDE 18
s = content_slide("Caching Strategy", '"No limit" was the requirement — so we made it safe')
card(s, Inches(0.9), Inches(1.55), Inches(5.75), Inches(4.9), "Design", [
    "Unbounded entry count (max_entries = 0)",
    "Per-key asyncio locks prevent cache stampedes",
    "Expired entries purged (every ~64 writes)",
    "Dead per-key locks removed after use",
    "Optional cap kept for tests / constrained hosts",
], title_size=16)
card(s, Inches(6.95), Inches(1.55), Inches(5.75), Inches(4.9), "Where it is used", [
    "Google Places search, details, nearby, photos",
    "Routes cached for 1 hour",
    "Weather 10 min · geocoding 24 h",
    "Wikipedia geo 6 h · article extracts 24 h",
    "Travel data is repetitive → hit rates are very high",
], title_size=16)
footer(s, 18)

# ================================================================ SLIDE 19
s = content_slide("Weather Integration", "Real observations, honest forecast coverage")
bullets(s, Inches(0.9), Inches(1.6), Inches(6.3), Inches(4.8), [
    "OpenWeather current conditions + 5-day forecast",
    "Requests cover the trip dates and say so explicitly",
    "forecast_covers_requested_dates flag — never fake",
    "Geocoding cached for 24 h; conditions for 10 min",
    "Missing key → 503 with a clear message, not a crash",
    "Itinerary prompts embed the forecast for packing tips",
], size=15, gap=9)
card(s, Inches(7.5), Inches(1.6), Inches(5.2), Inches(4.8),
     "Honesty features", [
         "Disclaimer text always attached",
         "Attribution: 'Weather data by OpenWeather'",
         "Suggestions derived only from real data",
     ], title_size=16)
footer(s, 19)

# ================================================================ SLIDE 20
s = content_slide("Budget, Reviews, Sharing, Analytics", "The features that make it a real app")
feats = [
    ("Budget engine", "Per-person estimates, over-budget warnings, currency-safe"),
    ("Reviews", "Only for visited (planned) places; unique per user+place; edit history"),
    ("Public sharing", "Expiring, revocable tokens → read-only share pages"),
    ("Analytics", "Aggregates + CSV export for the user's own trips"),
    ("Notifications", "In-app list with read state and deletion"),
    ("Export", "Clean itinerary exports for printing or sharing"),
]
y = 1.6
for t, d in feats:
    box(s, Inches(0.9), Inches(y), Inches(11.85), Inches(0.72), fill=LIGHT, line=LINE,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(1.15), Inches(y + 0.08), Inches(3.3), Inches(0.6),
         [[(t, 14, True, NAVY)]])
    text(s, Inches(4.6), Inches(y + 0.1), Inches(8.0), Inches(0.6),
         [[(d, 12.5, False, INK)]])
    y += 0.84
footer(s, 20)

# ================================================================ SLIDE 21
s = content_slide("Security", "Defense in depth, configured in one place")
card(s, Inches(0.9), Inches(1.55), Inches(5.75), Inches(4.9), "Identity & access", [
    "JWT verification via JWKS (audience + issuer checked)",
    "Ownership checks in SQL for every user resource",
    "Auth rate limiting + request body size limits",
    "Secrets only in gitignored env files / Render env",
    "Quoted env values bug found and fixed in production",
], title_size=16)
card(s, Inches(6.95), Inches(1.55), Inches(5.75), Inches(4.9), "Transport & headers", [
    "CORS allowlist: localhost, Render, Vercel",
    "Trusted-host middleware rejects unknown hosts",
    "CSP, X-Frame-Options, no-sniff, HSTS headers",
    "Photo proxy keeps API keys server-side only",
    "Share tokens expire and can be revoked",
], title_size=16)
footer(s, 21)

# ================================================================ SLIDE 22
s = content_slide("Testing", "131 automated tests — every fallback is a test")
counts = [
    ("Database resilience", 8, GREEN),
    ("Wikipedia service", 9, TEAL),
    ("Itineraries & AI", 18, NAVY_SOFT),
    ("Destinations & weather", 18, AMBER),
    ("Auth & users", 26, TEAL),
    ("Rest (reviews, sharing, security, config…)", 52, NAVY),
]
y = 1.55
for label, n, color in counts:
    text(s, Inches(0.9), Inches(y - 0.04), Inches(4.6), Inches(0.5),
         [[(label, 13.5, True, INK)]])
    bar_w = 4.0 * (n / 52.0)
    box(s, Inches(5.6), Inches(y), Inches(bar_w), Inches(0.34), fill=color)
    text(s, Inches(5.6 + bar_w + 0.12), Inches(y - 0.06), Inches(1.0), Inches(0.45),
         [[(str(n), 13, True, NAVY)]])
    y += 0.62
box(s, Inches(0.9), Inches(5.6), Inches(11.8), Inches(1.1), fill=RGBColor(0xEA, 0xF7, 0xF4),
    line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, Inches(1.15), Inches(5.75), Inches(11.3), Inches(0.9),
     [[("Highlights: stale-socket checkout retry · sync-vs-async checker bug · wiki blocklist "
        "· travel-only regression ('laptop repair' → 0) · deterministic fallback returns 201 · "
        "share-link invalid message exact-match.", 13, False, INK)]])
footer(s, 22)
notes(s, "External APIs are faked at the service boundary (httpx.MockTransport for the "
         "Wikipedia layer) so tests stay offline, fast and deterministic.")

# ================================================================ SLIDE 23
s = content_slide("Deployment — Docker → Render", "One container, one origin, one deploy unit")
bullets(s, Inches(0.9), Inches(1.6), Inches(6.3), Inches(4.8), [
    "Multi-stage Dockerfile: build React, then serve with FastAPI",
    "docker-compose with DNS fix for local development",
    "Render free web service in Singapore region",
    "Health check endpoint /health gates the deploy",
    "Env vars on Render (quotes stripped — a real bug we fixed)",
    "Env changes alone do NOT restart — deploys are explicit",
], size=15, gap=9)
card(s, Inches(7.5), Inches(1.6), Inches(5.2), Inches(4.8),
     "Production checklist", [
         "Push to GitHub → Render auto-deploy",
         "DATABASE_URL (unquoted) + pool timeout 30 s",
         "CORS origins: Vercel domain + localhost",
         "Verified end-to-end: login, search, generate, share",
     ], title_size=16)
footer(s, 23)

# ================================================================ SLIDE 24
s = content_slide("Frontend & Mobile", "Vercel SPA + installable Android APK")
card(s, Inches(0.9), Inches(1.55), Inches(5.75), Inches(4.9), "React SPA on Vercel", [
    "Vite build, static hosting on Vercel (Hobby tier)",
    "VITE_API_BASE_URL points at the Render API",
    "CORS + Neon trusted domains updated for the origin",
    "Verified from the network: login, search, weather, 201",
    "Custom animated SVG/CSS maps — no Google iframe",
], title_size=16)
card(s, Inches(6.95), Inches(1.55), Inches(5.75), Inches(4.9), "Android APK (Capacitor)", [
    "Wrapper around the SPA with the Render URL baked in",
    "com.smarttravelai.planner, targetSdk 36",
    "Debug-signed Smart-Traveler-AI-debug.apk (~13 MB)",
    "Built with JDK 21 + Android SDK 36",
    "Installs and runs against the production API",
], title_size=16)
footer(s, 24)

# ================================================================ SLIDE 25
s = content_slide("Results & What's Next", "Live today, honest always, room to grow")
card(s, Inches(0.9), Inches(1.5), Inches(5.75), Inches(4.9), "Shipped", [
    "131 passing backend tests; zero-downtime fallbacks",
    "Register works right after a cold Neon wake",
    "Travel-only search verified against abuse cases",
    "Keyless mode: search, details, plans — no keys",
    "Docker → Render → Vercel → APK, all live",
], title_size=16)
card(s, Inches(6.95), Inches(1.5), Inches(5.75), Inches(4.9), "Future work", [
    "Redis (Upstash) layer in front of in-process caches",
    "AI gateway routing with cost tracking",
    "Multi-city itineraries and transport bookings",
    "Wikidata enrichment: opening hours, ticket prices",
    "Play-store signed release + CI for mobile builds",
], title_size=16)
text(s, Inches(0.9), Inches(6.55), Inches(11.9), Inches(0.5),
     [[("Web:  " + VERCEL_URL + "     ·     API:  " + RENDER_URL,
        13.5, True, NAVY)]])
footer(s, 25)
notes(s, "Thank you. Live demo: register a user, search Kyoto (curated + Wikipedia results), "
         "generate a 3-day plan with the deterministic planner, open the share link.")

# ---------------------------------------------------------------- save
out = Path(__file__).resolve().parent / "Smart_Travel_Planner_AI_Presentation.pptx"
prs.save(out)
print(f"Saved {out} with {len(prs.slides.slides if hasattr(prs.slides, 'slides') else prs.slides._sldIdLst)} slides")
