-- Local development/testing schema only.
-- Production schema lives in backend/neon/schema.sql (Neon Postgres).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS profiles (
    id                 TEXT PRIMARY KEY,
    email              TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name          TEXT,
    phone              TEXT,
    avatar_url         TEXT,
    date_of_birth      TEXT,
    preferred_currency TEXT NOT NULL DEFAULT 'USD',
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS travel_preferences (
    user_id                    TEXT PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    home_city                  TEXT,
    interests                  TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(interests)),
    activity_preferences       TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(activity_preferences)),
    accommodation_preference   TEXT NOT NULL DEFAULT 'midrange_hotel',
    transportation_preference  TEXT NOT NULL DEFAULT 'mixed',
    budget_level               TEXT,
    dietary_preferences        TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(dietary_preferences)),
    accessibility_needs        TEXT,
    currency                   TEXT NOT NULL DEFAULT 'USD',
    created_at                 TEXT NOT NULL,
    updated_at                 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS itineraries (
    id                         TEXT PRIMARY KEY,
    user_id                    TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title                      TEXT NOT NULL,
    summary                    TEXT,
    destination_name           TEXT NOT NULL,
    destination_place_id       TEXT,
    destination_address        TEXT,
    destination_latitude       REAL,
    destination_longitude      REAL,
    start_date                 TEXT NOT NULL,
    end_date                   TEXT NOT NULL,
    travellers                 INTEGER NOT NULL CHECK (travellers BETWEEN 1 AND 50),
    total_budget               REAL NOT NULL CHECK (total_budget >= 0),
    currency                   TEXT NOT NULL,
    status                     TEXT NOT NULL DEFAULT 'generated'
                               CHECK (status IN ('draft', 'generated', 'saved', 'archived')),
    accommodation_preference   TEXT NOT NULL,
    transportation_preference  TEXT NOT NULL,
    pace                       TEXT NOT NULL
                               CHECK (pace IN ('relaxed', 'balanced', 'packed')),
    interests                  TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(interests)),
    preferences_snapshot       TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(preferences_snapshot)),
    budget_estimate            TEXT CHECK (budget_estimate IS NULL OR json_valid(budget_estimate)),
    weather_summary            TEXT CHECK (weather_summary IS NULL OR json_valid(weather_summary)),
    recommendations            TEXT CHECK (recommendations IS NULL OR json_valid(recommendations)),
    warnings                   TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(warnings)),
    generation_metadata        TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(generation_metadata)),
    created_at                 TEXT NOT NULL,
    updated_at                 TEXT NOT NULL,
    CHECK (end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_itineraries_user_created
    ON itineraries (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_itineraries_destination_place
    ON itineraries (destination_place_id);

CREATE TABLE IF NOT EXISTS itinerary_days (
    id                  TEXT PRIMARY KEY,
    itinerary_id        TEXT NOT NULL REFERENCES itineraries(id) ON DELETE CASCADE,
    day_number          INTEGER NOT NULL CHECK (day_number > 0),
    date                TEXT NOT NULL,
    title               TEXT NOT NULL,
    summary             TEXT,
    estimated_day_cost  REAL NOT NULL DEFAULT 0 CHECK (estimated_day_cost >= 0),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE (itinerary_id, day_number)
);

CREATE INDEX IF NOT EXISTS idx_itinerary_days_itinerary
    ON itinerary_days (itinerary_id, day_number);

CREATE TABLE IF NOT EXISTS itinerary_activities (
    id                TEXT PRIMARY KEY,
    itinerary_day_id  TEXT NOT NULL REFERENCES itinerary_days(id) ON DELETE CASCADE,
    place_id          TEXT,
    name              TEXT NOT NULL,
    category          TEXT NOT NULL
                      CHECK (category IN ('attraction', 'restaurant', 'hotel', 'transport', 'other')),
    description       TEXT,
    address           TEXT,
    latitude          REAL,
    longitude         REAL,
    rating            REAL,
    price_level       TEXT,
    opening_hours     TEXT CHECK (opening_hours IS NULL OR json_valid(opening_hours)),
    website_uri       TEXT,
    google_maps_uri   TEXT,
    start_time        TEXT,
    end_time          TEXT,
    estimated_cost    REAL NOT NULL DEFAULT 0 CHECK (estimated_cost >= 0),
    cost_type         TEXT NOT NULL DEFAULT 'estimated'
                      CHECK (cost_type IN ('estimated', 'verified')),
    route_to_next     TEXT CHECK (route_to_next IS NULL OR json_valid(route_to_next)),
    notes             TEXT,
    sort_order        INTEGER NOT NULL CHECK (sort_order >= 0),
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE (itinerary_day_id, sort_order)
);

CREATE INDEX IF NOT EXISTS idx_itinerary_activities_day
    ON itinerary_activities (itinerary_day_id, sort_order);

CREATE TABLE IF NOT EXISTS saved_destinations (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    place_id    TEXT NOT NULL,
    name        TEXT NOT NULL,
    address     TEXT,
    latitude    REAL,
    longitude   REAL,
    category    TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL,
    UNIQUE (user_id, place_id)
);

CREATE INDEX IF NOT EXISTS idx_saved_destinations_user
    ON saved_destinations (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS reviews (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    place_id    TEXT NOT NULL,
    place_name  TEXT NOT NULL,
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title       TEXT,
    comment     TEXT,
    visited_on  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (user_id, place_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_place
    ON reviews (place_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_user
    ON reviews (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS notifications (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    type       TEXT NOT NULL
               CHECK (type IN ('trip_generated', 'trip_reminder', 'system', 'offer', 'review', 'share')),
    title      TEXT NOT NULL,
    message    TEXT NOT NULL,
    metadata   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata)),
    read_at    TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notifications_user
    ON notifications (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_unread
    ON notifications (user_id, read_at);

CREATE TABLE IF NOT EXISTS itinerary_shares (
    id            TEXT PRIMARY KEY,
    itinerary_id  TEXT NOT NULL REFERENCES itineraries(id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    token_hash    TEXT NOT NULL UNIQUE,
    expires_at    TEXT,
    revoked_at    TEXT,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_itinerary_shares_itinerary
    ON itinerary_shares (itinerary_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_itinerary_shares_user
    ON itinerary_shares (user_id, created_at DESC);
