-- ============================================================================
-- Smart Travel Planner - Supabase PostgreSQL production schema
-- Run this file once in the Supabase SQL Editor (or via `supabase db push`).
-- Supabase Auth owns credentials. This schema stores application data only.
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
create table if not exists public.profiles (
    id                 uuid primary key references auth.users(id) on delete cascade,
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

-- ------------------------------------------ provision profile for new users
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, email, full_name, avatar_url)
    values (
        new.id,
        coalesce(new.email, new.id::text || '@no-email.invalid'),
        coalesce(
            new.raw_user_meta_data ->> 'full_name',
            new.raw_user_meta_data ->> 'name'
        ),
        coalesce(
            new.raw_user_meta_data ->> 'avatar_url',
            new.raw_user_meta_data ->> 'picture'
        )
    )
    on conflict (id) do update
        set email = excluded.email,
            updated_at = now();
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ============================================================================
-- Row Level Security
-- The backend connects as the database owner, but these policies protect any
-- direct Supabase client access (for example the future React app).
-- ============================================================================
alter table public.profiles enable row level security;
alter table public.travel_preferences enable row level security;
alter table public.itineraries enable row level security;
alter table public.itinerary_days enable row level security;
alter table public.itinerary_activities enable row level security;
alter table public.saved_destinations enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
    for select to authenticated using (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
    for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "preferences_all_own" on public.travel_preferences;
create policy "preferences_all_own" on public.travel_preferences
    for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "itineraries_all_own" on public.itineraries;
create policy "itineraries_all_own" on public.itineraries
    for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "itinerary_days_all_own" on public.itinerary_days;
create policy "itinerary_days_all_own" on public.itinerary_days
    for all to authenticated
    using (
        exists (
            select 1 from public.itineraries i
            where i.id = itinerary_days.itinerary_id and i.user_id = auth.uid()
        )
    )
    with check (
        exists (
            select 1 from public.itineraries i
            where i.id = itinerary_days.itinerary_id and i.user_id = auth.uid()
        )
    );

drop policy if exists "itinerary_activities_all_own" on public.itinerary_activities;
create policy "itinerary_activities_all_own" on public.itinerary_activities
    for all to authenticated
    using (
        exists (
            select 1
            from public.itinerary_days d
            join public.itineraries i on i.id = d.itinerary_id
            where d.id = itinerary_activities.itinerary_day_id and i.user_id = auth.uid()
        )
    )
    with check (
        exists (
            select 1
            from public.itinerary_days d
            join public.itineraries i on i.id = d.itinerary_id
            where d.id = itinerary_activities.itinerary_day_id and i.user_id = auth.uid()
        )
    );

drop policy if exists "saved_destinations_all_own" on public.saved_destinations;
create policy "saved_destinations_all_own" on public.saved_destinations
    for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

grant usage on schema public to authenticated;
grant select, update on public.profiles to authenticated;
grant select, insert, update, delete on public.travel_preferences to authenticated;
grant select, insert, update, delete on public.itineraries to authenticated;
grant select, insert, update, delete on public.itinerary_days to authenticated;
grant select, insert, update, delete on public.itinerary_activities to authenticated;
grant select, insert, update, delete on public.saved_destinations to authenticated;

-- ------------------------------------------------------ review updated_at
drop trigger if exists reviews_set_updated_at on public.reviews;
create trigger reviews_set_updated_at
    before update on public.reviews
    for each row execute function public.set_updated_at();

-- ============================================================================
-- Row Level Security for reviews, notifications, and share links
-- ============================================================================
alter table public.reviews enable row level security;
alter table public.notifications enable row level security;
alter table public.itinerary_shares enable row level security;

drop policy if exists "reviews_select_authenticated" on public.reviews;
create policy "reviews_select_authenticated" on public.reviews
    for select to authenticated using (true);

drop policy if exists "reviews_insert_own" on public.reviews;
create policy "reviews_insert_own" on public.reviews
    for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "reviews_update_own" on public.reviews;
create policy "reviews_update_own" on public.reviews
    for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "reviews_delete_own" on public.reviews;
create policy "reviews_delete_own" on public.reviews
    for delete to authenticated using (auth.uid() = user_id);

drop policy if exists "notifications_all_own" on public.notifications;
create policy "notifications_all_own" on public.notifications
    for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "itinerary_shares_all_own" on public.itinerary_shares;
create policy "itinerary_shares_all_own" on public.itinerary_shares
    for all to authenticated
    using (
        auth.uid() = user_id
        and exists (
            select 1 from public.itineraries i
            where i.id = itinerary_shares.itinerary_id and i.user_id = auth.uid()
        )
    )
    with check (
        auth.uid() = user_id
        and exists (
            select 1 from public.itineraries i
            where i.id = itinerary_shares.itinerary_id and i.user_id = auth.uid()
        )
    );

grant select, insert, update, delete on public.reviews to authenticated;
grant select, insert, update, delete on public.notifications to authenticated;
grant select, insert, update, delete on public.itinerary_shares to authenticated;

-- Notification inserts are also performed by the backend service role.
-- The backend uses the database owner connection, so no service-role JWT is stored here.

-- Enable Supabase Realtime for in-app notifications when the publication exists.
-- RLS still restricts every subscriber to its own rows.
do $$
begin
    alter publication supabase_realtime add table public.notifications;
exception
    when duplicate_object then null;
    when undefined_object then null;
end $$;
