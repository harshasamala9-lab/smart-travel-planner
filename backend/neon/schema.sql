-- ============================================================================
-- Smart Travel Planner - Neon (Lakebase PostgreSQL) production schema
-- Apply to the branch's database with the DIRECT (unpooled) connection string:
--   psql "$DATABASE_URL_UNPOOLED" -f backend/neon/schema.sql
-- Neon Auth (Managed Better Auth) owns credentials in the neon_auth schema.
-- This schema stores application data only.
-- ============================================================================

-- Existing-deployment note: `create table if not exists` does not alter
-- columns on an already-created table. If an earlier version of this schema
-- used numeric(14,2) for money, widen the columns before redeploying:
--   alter table public.itineraries
--       alter column total_budget type numeric(18,2);
--   alter table public.itinerary_days
--       alter column estimated_day_cost type numeric(18,2);
--   alter table public.itinerary_activities
--       alter column estimated_cost type numeric(18,2);

create extension if not exists pgcrypto;

-- ----------------------------------------------------------------- profiles
-- Neon Auth user ids are UUIDs, so profiles.id keeps the same type the app
-- used with Supabase Auth. There is deliberately no foreign key to
-- neon_auth."user": the backend provisions and owns this row (see
-- ProfileRepository.ensure_from_auth), and Neon Auth manages its own schema.
create table if not exists public.profiles (
    id                 uuid primary key,
    email              text not null,
    full_name          text,
    phone              text,
    avatar_url         text,
    date_of_birth      date,
    preferred_currency varchar(3) not null default 'USD',
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

create unique index if not exists profiles_email_lower_idx
    on public.profiles (lower(email));

-- -------------------------------------------------------- travel preferences
create table if not exists public.travel_preferences (
    user_id                   uuid primary key references public.profiles(id) on delete cascade,
    home_city                 text,
    interests                 jsonb not null default '[]'::jsonb,
    activity_preferences      jsonb not null default '[]'::jsonb,
    accommodation_preference  text not null default 'midrange_hotel',
    transportation_preference text not null default 'mixed',
    budget_level              text,
    dietary_preferences       jsonb not null default '[]'::jsonb,
    accessibility_needs       text,
    currency                  varchar(3) not null default 'USD',
    created_at                timestamptz not null default now(),
    updated_at                timestamptz not null default now(),
    constraint travel_preferences_interests_array check (jsonb_typeof(interests) = 'array'),
    constraint travel_preferences_activities_array check (jsonb_typeof(activity_preferences) = 'array'),
    constraint travel_preferences_dietary_array check (jsonb_typeof(dietary_preferences) = 'array')
);

-- --------------------------------------------------------------- itineraries
create table if not exists public.itineraries (
    id                        uuid primary key default gen_random_uuid(),
    user_id                   uuid not null references public.profiles(id) on delete cascade,
    title                     text not null,
    summary                   text,
    destination_name          text not null,
    destination_place_id      text,
    destination_address       text,
    destination_latitude      numeric(9, 6),
    destination_longitude     numeric(9, 6),
    start_date                date not null,
    end_date                  date not null,
    travellers                smallint not null check (travellers between 1 and 50),
    total_budget              numeric(18, 2) not null check (total_budget >= 0),
    currency                  varchar(3) not null,
    status                    text not null default 'generated'
                              check (status in ('draft', 'generated', 'saved', 'archived')),
    accommodation_preference  text not null,
    transportation_preference text not null,
    pace                      text not null check (pace in ('relaxed', 'balanced', 'packed')),
    interests                 jsonb not null default '[]'::jsonb,
    preferences_snapshot      jsonb not null default '{}'::jsonb,
    budget_estimate           jsonb,
    weather_summary           jsonb,
    recommendations           jsonb,
    warnings                  jsonb not null default '[]'::jsonb,
    generation_metadata       jsonb not null default '{}'::jsonb,
    created_at                timestamptz not null default now(),
    updated_at                timestamptz not null default now(),
    constraint itineraries_dates_valid check (end_date >= start_date),
    constraint itineraries_interests_array check (jsonb_typeof(interests) = 'array'),
    constraint itineraries_warnings_array check (jsonb_typeof(warnings) = 'array')
);

create index if not exists idx_itineraries_user_created
    on public.itineraries (user_id, created_at desc);
create index if not exists idx_itineraries_destination_place
    on public.itineraries (destination_place_id);

-- ------------------------------------------------------------ itinerary days
create table if not exists public.itinerary_days (
    id                 uuid primary key default gen_random_uuid(),
    itinerary_id       uuid not null references public.itineraries(id) on delete cascade,
    day_number         integer not null check (day_number > 0),
    date               date not null,
    title              text not null,
    summary            text,
    estimated_day_cost numeric(18, 2) not null default 0 check (estimated_day_cost >= 0),
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),
    unique (itinerary_id, day_number)
);

create index if not exists idx_itinerary_days_itinerary
    on public.itinerary_days (itinerary_id, day_number);

-- ------------------------------------------------------ itinerary activities
create table if not exists public.itinerary_activities (
    id               uuid primary key default gen_random_uuid(),
    itinerary_day_id uuid not null references public.itinerary_days(id) on delete cascade,
    place_id         text,
    name             text not null,
    category         text not null
                     check (category in ('attraction', 'restaurant', 'hotel', 'transport', 'other')),
    description      text,
    address          text,
    latitude         numeric(9, 6),
    longitude        numeric(9, 6),
    rating           numeric(3, 2) check (rating is null or (rating >= 0 and rating <= 5)),
    price_level      text,
    opening_hours    jsonb,
    website_uri      text,
    google_maps_uri  text,
    start_time       text,
    end_time         text,
    estimated_cost   numeric(18, 2) not null default 0 check (estimated_cost >= 0),
    cost_type        text not null default 'estimated'
                     check (cost_type in ('estimated', 'verified')),
    route_to_next    jsonb,
    notes            text,
    sort_order       integer not null check (sort_order >= 0),
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    unique (itinerary_day_id, sort_order)
);

create index if not exists idx_itinerary_activities_day
    on public.itinerary_activities (itinerary_day_id, sort_order);

-- -------------------------------------------------------- saved destinations
create table if not exists public.saved_destinations (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid not null references public.profiles(id) on delete cascade,
    place_id   text not null,
    name       text not null,
    address    text,
    latitude   numeric(9, 6),
    longitude  numeric(9, 6),
    category   text,
    notes      text,
    created_at timestamptz not null default now(),
    unique (user_id, place_id)
);

create index if not exists idx_saved_destinations_user
    on public.saved_destinations (user_id, created_at desc);

-- ------------------------------------------------------------------- reviews
create table if not exists public.reviews (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid not null references public.profiles(id) on delete cascade,
    place_id   text not null,
    place_name text not null,
    rating     smallint not null check (rating between 1 and 5),
    title      text,
    comment    text,
    visited_on date,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, place_id)
);

create index if not exists idx_reviews_place
    on public.reviews (place_id, created_at desc);
create index if not exists idx_reviews_user
    on public.reviews (user_id, created_at desc);

-- ------------------------------------------------------------- notifications
create table if not exists public.notifications (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid not null references public.profiles(id) on delete cascade,
    type       text not null
               check (type in ('trip_generated', 'trip_reminder', 'system', 'offer', 'review', 'share')),
    title      text not null,
    message    text not null,
    metadata   jsonb not null default '{}'::jsonb,
    read_at    timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists idx_notifications_user
    on public.notifications (user_id, created_at desc);
create index if not exists idx_notifications_unread
    on public.notifications (user_id, read_at);

-- ------------------------------------------------------------- share links
create table if not exists public.itinerary_shares (
    id           uuid primary key default gen_random_uuid(),
    itinerary_id uuid not null references public.itineraries(id) on delete cascade,
    user_id      uuid not null references public.profiles(id) on delete cascade,
    token_hash   text not null unique,
    expires_at   timestamptz,
    revoked_at   timestamptz,
    created_at   timestamptz not null default now()
);

create index if not exists idx_itinerary_shares_itinerary
    on public.itinerary_shares (itinerary_id, created_at desc);
create index if not exists idx_itinerary_shares_user
    on public.itinerary_shares (user_id, created_at desc);

-- ----------------------------------------------------------- updated_at fn
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
    before update on public.profiles
    for each row execute function public.set_updated_at();

drop trigger if exists preferences_set_updated_at on public.travel_preferences;
create trigger preferences_set_updated_at
    before update on public.travel_preferences
    for each row execute function public.set_updated_at();

drop trigger if exists itineraries_set_updated_at on public.itineraries;
create trigger itineraries_set_updated_at
    before update on public.itineraries
    for each row execute function public.set_updated_at();

drop trigger if exists itinerary_days_set_updated_at on public.itinerary_days;
create trigger itinerary_days_set_updated_at
    before update on public.itinerary_days
    for each row execute function public.set_updated_at();

drop trigger if exists itinerary_activities_set_updated_at on public.itinerary_activities;
create trigger itinerary_activities_set_updated_at
    before update on public.itinerary_activities
    for each row execute function public.set_updated_at();

drop trigger if exists reviews_set_updated_at on public.reviews;
create trigger reviews_set_updated_at
    before update on public.reviews
    for each row execute function public.set_updated_at();

-- ============================================================================
-- Row Level Security
-- Deliberately NOT enabled. Unlike Supabase, application tables here are only
-- reachable through this backend, which connects as the database owner and
-- enforces ownership in every query (see repositories.py). Neon Auth identity
-- data lives in the managed neon_auth schema, which Neon controls; do not add
-- triggers or policies to it. If a future direct PostgREST-style client is
-- added, enable RLS with policies that join neon_auth."user" through a
-- session/JWT claim rather than auth.uid().
-- ============================================================================
