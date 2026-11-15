"""Repository layer with parameterised SQL for PostgreSQL and SQLite.

Every user-owned query includes ``user_id`` in the predicate to enforce
authorization even though the backend database role bypasses RLS.
"""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from app.database.connection import Database, SqliteTransaction, PostgresTransaction
from app.utils.serialization import loads_json, normalise_row, normalise_rows
from app.utils.time import utc_now_iso

JSON_ITINERARY_FIELDS = {
    "interests",
    "preferences_snapshot",
    "budget_estimate",
    "weather_summary",
    "recommendations",
    "warnings",
    "generation_metadata",
}

PROFILE_FIELDS = (
    "full_name",
    "phone",
    "avatar_url",
    "date_of_birth",
    "preferred_currency",
)

ITINERARY_COLUMNS = (
    "id",
    "user_id",
    "title",
    "summary",
    "destination_name",
    "destination_place_id",
    "destination_address",
    "destination_latitude",
    "destination_longitude",
    "start_date",
    "end_date",
    "travellers",
    "total_budget",
    "currency",
    "status",
    "accommodation_preference",
    "transportation_preference",
    "pace",
    "interests",
    "preferences_snapshot",
    "budget_estimate",
    "weather_summary",
    "recommendations",
    "warnings",
    "generation_metadata",
    "created_at",
    "updated_at",
)

ACTIVITY_COLUMNS = (
    "id",
    "itinerary_day_id",
    "place_id",
    "name",
    "category",
    "description",
    "address",
    "latitude",
    "longitude",
    "rating",
    "price_level",
    "opening_hours",
    "website_uri",
    "google_maps_uri",
    "start_time",
    "end_time",
    "estimated_cost",
    "cost_type",
    "route_to_next",
    "notes",
    "sort_order",
    "created_at",
    "updated_at",
)

DAY_COLUMNS = (
    "id",
    "itinerary_id",
    "day_number",
    "date",
    "title",
    "summary",
    "estimated_day_cost",
    "created_at",
    "updated_at",
)

ITINERARY_UPDATABLE_COLUMNS = {
    "title",
    "summary",
    "status",
    "total_budget",
    "currency",
    "budget_estimate",
    "weather_summary",
    "recommendations",
    "warnings",
    "preferences_snapshot",
    "generation_metadata",
    "start_date",
    "end_date",
}


Transaction = SqliteTransaction | PostgresTransaction


async def _insert(tx: Transaction, table: str, data: dict[str, Any]) -> None:
    columns = list(data.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    await tx.execute(sql, [data[column] for column in columns])


def _decode_itinerary_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    row = dict(row)
    for field in JSON_ITINERARY_FIELDS:
        default = [] if field in {"interests", "warnings"} else {}
        row[field] = loads_json(row.get(field), default)
    if row.get("weather_summary") == {}:
        row["weather_summary"] = None
    if row.get("recommendations") == {}:
        row["recommendations"] = None
    if row.get("budget_estimate") == {}:
        row["budget_estimate"] = None
    return normalise_row(row)


def _decode_activity_row(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    row["opening_hours"] = loads_json(row.get("opening_hours"), [])
    row["route_to_next"] = loads_json(row.get("route_to_next"), None)
    return normalise_row(row)  # type: ignore[return-value]


def _decode_day_row(row: dict[str, Any]) -> dict[str, Any]:
    row = normalise_row(row)
    assert row is not None
    row["activities"] = []
    return row


class ProfileRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def get_by_id(self, user_id: uuid.UUID | str) -> dict[str, Any] | None:
        row = await self._db.fetch_one("SELECT * FROM profiles WHERE id = %s", [str(user_id)])
        return normalise_row(row)

    async def ensure_from_auth(
        self,
        *,
        user_id: uuid.UUID | str,
        email: str,
        full_name: str | None = None,
        avatar_url: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        user_id_str = str(user_id)
        async with self._db.transaction() as tx:
            await tx.execute(
                """
                INSERT INTO profiles
                    (id, email, full_name, avatar_url, preferred_currency, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'USD', %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                [user_id_str, email, full_name, avatar_url, now, now],
            )
            await tx.execute(
                """
                UPDATE profiles
                SET email = %s,
                    full_name = COALESCE(full_name, %s),
                    avatar_url = COALESCE(avatar_url, %s),
                    updated_at = %s
                WHERE id = %s
                """,
                [email, full_name, avatar_url, now, user_id_str],
            )
            row = await tx.fetch_one("SELECT * FROM profiles WHERE id = %s", [user_id_str])
        assert row is not None
        return normalise_row(row)  # type: ignore[return-value]

    async def update(
        self, user_id: uuid.UUID | str, fields: dict[str, Any]
    ) -> dict[str, Any] | None:
        updates = {key: value for key, value in fields.items() if key in PROFILE_FIELDS}
        if not updates:
            return await self.get_by_id(user_id)
        updates["updated_at"] = utc_now_iso()
        set_clause = ", ".join(f"{column} = %s" for column in updates)
        params = [*updates.values(), str(user_id)]
        async with self._db.transaction() as tx:
            await tx.execute(
                f"UPDATE profiles SET {set_clause} WHERE id = %s",
                params,
            )
            row = await tx.fetch_one("SELECT * FROM profiles WHERE id = %s", [str(user_id)])
        return normalise_row(row)

    async def get_preferences(self, user_id: uuid.UUID | str) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            "SELECT * FROM travel_preferences WHERE user_id = %s", [str(user_id)]
        )
        if row is None:
            return None
        for field in ("interests", "activity_preferences", "dietary_preferences"):
            row[field] = loads_json(row.get(field), [])
        return normalise_row(row)

    async def upsert_preferences(
        self, user_id: uuid.UUID | str, preferences: dict[str, Any]
    ) -> dict[str, Any]:
        now = utc_now_iso()
        user_id_str = str(user_id)
        async with self._db.transaction() as tx:
            await tx.execute(
                """
                INSERT INTO travel_preferences
                    (user_id, home_city, interests, activity_preferences,
                     accommodation_preference, transportation_preference, budget_level,
                     dietary_preferences, accessibility_needs, currency, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    home_city = excluded.home_city,
                    interests = excluded.interests,
                    activity_preferences = excluded.activity_preferences,
                    accommodation_preference = excluded.accommodation_preference,
                    transportation_preference = excluded.transportation_preference,
                    budget_level = excluded.budget_level,
                    dietary_preferences = excluded.dietary_preferences,
                    accessibility_needs = excluded.accessibility_needs,
                    currency = excluded.currency,
                    updated_at = excluded.updated_at
                """,
                [
                    user_id_str,
                    preferences.get("home_city"),
                    preferences.get("interests", []),
                    preferences.get("activity_preferences", []),
                    preferences.get("accommodation_preference", "midrange_hotel"),
                    preferences.get("transportation_preference", "mixed"),
                    preferences.get("budget_level"),
                    preferences.get("dietary_preferences", []),
                    preferences.get("accessibility_needs"),
                    preferences.get("currency", "USD"),
                    now,
                    now,
                ],
            )
            row = await tx.fetch_one(
                "SELECT * FROM travel_preferences WHERE user_id = %s", [user_id_str]
            )
        assert row is not None
        for field in ("interests", "activity_preferences", "dietary_preferences"):
            row[field] = loads_json(row.get(field), [])
        return normalise_row(row)  # type: ignore[return-value]

    async def add_saved_destination(
        self, user_id: uuid.UUID | str, destination: dict[str, Any]
    ) -> dict[str, Any]:
        now = utc_now_iso()
        user_id_str = str(user_id)
        async with self._db.transaction() as tx:
            await tx.execute(
                """
                INSERT INTO saved_destinations
                    (id, user_id, place_id, name, address, latitude, longitude,
                     category, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, place_id) DO UPDATE SET
                    name = excluded.name,
                    address = excluded.address,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    category = excluded.category,
                    notes = excluded.notes
                """,
                [
                    str(uuid.uuid4()),
                    user_id_str,
                    destination["place_id"],
                    destination["name"],
                    destination.get("address"),
                    destination.get("latitude"),
                    destination.get("longitude"),
                    destination.get("category"),
                    destination.get("notes"),
                    now,
                ],
            )
            row = await tx.fetch_one(
                "SELECT * FROM saved_destinations WHERE user_id = %s AND place_id = %s",
                [user_id_str, destination["place_id"]],
            )
        assert row is not None
        return normalise_row(row)  # type: ignore[return-value]

    async def list_saved_destinations(self, user_id: uuid.UUID | str) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT * FROM saved_destinations
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            [str(user_id)],
        )
        return normalise_rows(rows)

    async def delete_saved_destination(self, user_id: uuid.UUID | str, place_id: str) -> bool:
        rowcount = await self._db.execute(
            "DELETE FROM saved_destinations WHERE user_id = %s AND place_id = %s",
            [str(user_id), place_id],
        )
        return rowcount > 0


class ItineraryRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def create(
        self,
        itinerary: dict[str, Any],
        days: list[dict[str, Any]],
    ) -> None:
        async with self._db.transaction() as tx:
            await _insert(tx, "itineraries", itinerary)
            for day in days:
                day_row = {column: day[column] for column in DAY_COLUMNS}
                await _insert(tx, "itinerary_days", day_row)
                for activity in day["activities"]:
                    activity_row = {column: activity[column] for column in ACTIVITY_COLUMNS}
                    await _insert(tx, "itinerary_activities", activity_row)

    async def list_for_user(
        self,
        user_id: uuid.UUID | str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        async with self._db.transaction() as tx:
            rows = await tx.fetch_all(
                """
                SELECT * FROM itineraries
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                [str(user_id), limit, offset],
            )
            count_row = await tx.fetch_one(
                "SELECT COUNT(*) AS total FROM itineraries WHERE user_id = %s",
                [str(user_id)],
            )
        total = int(count_row["total"]) if count_row else 0
        return [_decode_itinerary_row(row) for row in rows], total  # type: ignore[misc]

    async def get_for_user(
        self,
        user_id: uuid.UUID | str,
        itinerary_id: uuid.UUID | str,
        *,
        include_days: bool = True,
    ) -> dict[str, Any] | None:
        async with self._db.transaction() as tx:
            row = await tx.fetch_one(
                "SELECT * FROM itineraries WHERE id = %s AND user_id = %s",
                [str(itinerary_id), str(user_id)],
            )
            if row is None:
                return None
            itinerary = _decode_itinerary_row(row)
            assert itinerary is not None
            if not include_days:
                return itinerary

            day_rows = await tx.fetch_all(
                """
                SELECT * FROM itinerary_days
                WHERE itinerary_id = %s
                ORDER BY day_number ASC
                """,
                [str(itinerary_id)],
            )
            activity_rows = await tx.fetch_all(
                """
                SELECT a.*
                FROM itinerary_activities a
                JOIN itinerary_days d ON d.id = a.itinerary_day_id
                WHERE d.itinerary_id = %s
                ORDER BY d.day_number ASC, a.sort_order ASC
                """,
                [str(itinerary_id)],
            )

        activities_by_day: dict[str, list[dict[str, Any]]] = {}
        for activity in activity_rows:
            activities_by_day.setdefault(activity["itinerary_day_id"], []).append(
                _decode_activity_row(activity)
            )
        days = []
        for day_row in day_rows:
            day = _decode_day_row(day_row)
            day["activities"] = activities_by_day.get(day_row["id"], [])
            days.append(day)
        itinerary["days"] = days
        return itinerary

    async def update_fields_and_days(
        self,
        user_id: uuid.UUID | str,
        itinerary_id: uuid.UUID | str,
        fields: dict[str, Any],
        days: list[dict[str, Any]] | None,
    ) -> bool:
        """Atomically update itinerary metadata and optionally replace its days."""
        updates = {
            key: value
            for key, value in fields.items()
            if key in ITINERARY_UPDATABLE_COLUMNS
        }
        async with self._db.transaction() as tx:
            owned = await tx.fetch_one(
                "SELECT id FROM itineraries WHERE id = %s AND user_id = %s",
                [str(itinerary_id), str(user_id)],
            )
            if owned is None:
                return False

            if days is not None:
                await tx.execute(
                    "DELETE FROM itinerary_days WHERE itinerary_id = %s",
                    [str(itinerary_id)],
                )
                for day in days:
                    await _insert(
                        tx,
                        "itinerary_days",
                        {column: day[column] for column in DAY_COLUMNS},
                    )
                    for activity in day.get("activities", []):
                        await _insert(
                            tx,
                            "itinerary_activities",
                            {
                                column: activity[column]
                                for column in ACTIVITY_COLUMNS
                            },
                        )

            updates["updated_at"] = utc_now_iso()
            set_clause = ", ".join(f"{column} = %s" for column in updates)
            await tx.execute(
                f"UPDATE itineraries SET {set_clause} "
                "WHERE id = %s AND user_id = %s",
                [*updates.values(), str(itinerary_id), str(user_id)],
            )
        return True

    async def delete(
        self, user_id: uuid.UUID | str, itinerary_id: uuid.UUID | str
    ) -> bool:
        rowcount = await self._db.execute(
            "DELETE FROM itineraries WHERE id = %s AND user_id = %s",
            [str(itinerary_id), str(user_id)],
        )
        return rowcount > 0

    async def count_for_user(self, user_id: uuid.UUID | str) -> int:
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM itineraries WHERE user_id = %s",
            [str(user_id)],
        )
        return int(row["total"]) if row else 0


REVIEW_UPDATABLE_COLUMNS = {
    "rating",
    "title",
    "comment",
    "visited_on",
}


class ReviewRepository:
    """User reviews for Google Places locations.

    A review is never presented as a verified visit or as Google's own rating.
    """

    def __init__(self, database: Database) -> None:
        self._db = database

    async def create(
        self,
        *,
        user_id: uuid.UUID | str,
        place_id: str,
        place_name: str,
        rating: int,
        title: str | None,
        comment: str | None,
        visited_on: str | None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        review_id = str(uuid.uuid4())
        async with self._db.transaction() as tx:
            await tx.execute(
                """
                INSERT INTO reviews
                    (id, user_id, place_id, place_name, rating, title, comment,
                     visited_on, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    review_id,
                    str(user_id),
                    place_id,
                    place_name,
                    rating,
                    title,
                    comment,
                    visited_on,
                    now,
                    now,
                ],
            )
            row = await self._fetch_with_reviewer(tx, review_id)
        assert row is not None
        return normalise_row(row)  # type: ignore[return-value]

    @staticmethod
    async def _fetch_with_reviewer(
        tx: Any, review_id: str
    ) -> dict[str, Any] | None:
        return await tx.fetch_one(
            """
            SELECT r.*, p.full_name AS reviewer_name
            FROM reviews r
            JOIN profiles p ON p.id = r.user_id
            WHERE r.id = %s
            """,
            [review_id],
        )

    async def get_for_user(
        self, user_id: uuid.UUID | str, review_id: uuid.UUID | str
    ) -> dict[str, Any] | None:
        async with self._db.transaction() as tx:
            row = await tx.fetch_one(
                """
                SELECT r.*, p.full_name AS reviewer_name
                FROM reviews r
                JOIN profiles p ON p.id = r.user_id
                WHERE r.id = %s AND r.user_id = %s
                """,
                [str(review_id), str(user_id)],
            )
        return normalise_row(row)

    async def get_by_user_and_place(
        self, user_id: uuid.UUID | str, place_id: str
    ) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            """
            SELECT r.*, p.full_name AS reviewer_name
            FROM reviews r
            JOIN profiles p ON p.id = r.user_id
            WHERE r.user_id = %s AND r.place_id = %s
            """,
            [str(user_id), place_id],
        )
        return normalise_row(row)

    async def list_for_place(
        self, place_id: str, *, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int, float | None]:
        async with self._db.transaction() as tx:
            rows = await tx.fetch_all(
                """
                SELECT r.*, p.full_name AS reviewer_name
                FROM reviews r
                JOIN profiles p ON p.id = r.user_id
                WHERE r.place_id = %s
                ORDER BY r.created_at DESC
                LIMIT %s OFFSET %s
                """,
                [place_id, limit, offset],
            )
            count_row = await tx.fetch_one(
                "SELECT COUNT(*) AS total FROM reviews WHERE place_id = %s",
                [place_id],
            )
            stats_row = await tx.fetch_one(
                """
                SELECT COUNT(*) AS total, AVG(rating) AS average
                FROM reviews WHERE place_id = %s
                """,
                [place_id],
            )
        total = int(count_row["total"]) if count_row else 0
        average = (
            round(float(stats_row["average"]), 2)
            if stats_row and stats_row.get("average") is not None
            else None
        )
        return normalise_rows(rows), total, average  # type: ignore[return-value]

    async def list_for_user(
        self, user_id: uuid.UUID | str, *, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        async with self._db.transaction() as tx:
            rows = await tx.fetch_all(
                """
                SELECT r.*, p.full_name AS reviewer_name
                FROM reviews r
                JOIN profiles p ON p.id = r.user_id
                WHERE r.user_id = %s
                ORDER BY r.created_at DESC
                LIMIT %s OFFSET %s
                """,
                [str(user_id), limit, offset],
            )
            count_row = await tx.fetch_one(
                "SELECT COUNT(*) AS total FROM reviews WHERE user_id = %s",
                [str(user_id)],
            )
        total = int(count_row["total"]) if count_row else 0
        return normalise_rows(rows), total  # type: ignore[return-value]

    async def update(
        self,
        user_id: uuid.UUID | str,
        review_id: uuid.UUID | str,
        fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        updates = {
            key: value
            for key, value in fields.items()
            if key in REVIEW_UPDATABLE_COLUMNS
        }
        if not updates:
            return await self.get_for_user(user_id, review_id)
        updates["updated_at"] = utc_now_iso()
        set_clause = ", ".join(f"{column} = %s" for column in updates)
        params = [*updates.values(), str(review_id), str(user_id)]
        async with self._db.transaction() as tx:
            await tx.execute(
                f"UPDATE reviews SET {set_clause} WHERE id = %s AND user_id = %s",
                params,
            )
            row = await tx.fetch_one(
                """
                SELECT r.*, p.full_name AS reviewer_name
                FROM reviews r
                JOIN profiles p ON p.id = r.user_id
                WHERE r.id = %s AND r.user_id = %s
                """,
                [str(review_id), str(user_id)],
            )
        return normalise_row(row)

    async def delete(
        self, user_id: uuid.UUID | str, review_id: uuid.UUID | str
    ) -> bool:
        rowcount = await self._db.execute(
            "DELETE FROM reviews WHERE id = %s AND user_id = %s",
            [str(review_id), str(user_id)],
        )
        return rowcount > 0

    async def count_for_user(self, user_id: uuid.UUID | str) -> int:
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM reviews WHERE user_id = %s",
            [str(user_id)],
        )
        return int(row["total"]) if row else 0


class NotificationRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    @staticmethod
    def _decode(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        row = dict(row)
        row["metadata"] = loads_json(row.get("metadata"), {})
        return normalise_row(row)

    async def create(
        self,
        *,
        user_id: uuid.UUID | str,
        notification_type: str,
        title: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        notification_id = str(uuid.uuid4())
        now = utc_now_iso()
        async with self._db.transaction() as tx:
            await tx.execute(
                """
                INSERT INTO notifications
                    (id, user_id, type, title, message, metadata, read_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NULL, %s)
                """,
                [
                    notification_id,
                    str(user_id),
                    notification_type,
                    title,
                    message,
                    metadata or {},
                    now,
                ],
            )
            row = await tx.fetch_one(
                "SELECT * FROM notifications WHERE id = %s", [notification_id]
            )
        assert row is not None
        return self._decode(row)  # type: ignore[return-value]

    async def list_for_user(
        self,
        user_id: uuid.UUID | str,
        *,
        unread_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int, int]:
        where = "user_id = %s"
        params: list[Any] = [str(user_id)]
        if unread_only:
            where += " AND read_at IS NULL"
        async with self._db.transaction() as tx:
            rows = await tx.fetch_all(
                f"""
                SELECT * FROM notifications
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                [*params, limit, offset],
            )
            count_row = await tx.fetch_one(
                f"SELECT COUNT(*) AS total FROM notifications WHERE {where}",
                params,
            )
            unread_row = await tx.fetch_one(
                """
                SELECT COUNT(*) AS total FROM notifications
                WHERE user_id = %s AND read_at IS NULL
                """,
                [str(user_id)],
            )
        total = int(count_row["total"]) if count_row else 0
        unread = int(unread_row["total"]) if unread_row else 0
        return [self._decode(row) for row in rows], total, unread  # type: ignore[misc]

    async def mark_read(
        self, user_id: uuid.UUID | str, notification_id: uuid.UUID | str
    ) -> dict[str, Any] | None:
        now = utc_now_iso()
        async with self._db.transaction() as tx:
            await tx.execute(
                """
                UPDATE notifications SET read_at = COALESCE(read_at, %s)
                WHERE id = %s AND user_id = %s
                """,
                [now, str(notification_id), str(user_id)],
            )
            row = await tx.fetch_one(
                "SELECT * FROM notifications WHERE id = %s AND user_id = %s",
                [str(notification_id), str(user_id)],
            )
        return self._decode(row)

    async def mark_all_read(self, user_id: uuid.UUID | str) -> int:
        rowcount = await self._db.execute(
            """
            UPDATE notifications SET read_at = %s
            WHERE user_id = %s AND read_at IS NULL
            """,
            [utc_now_iso(), str(user_id)],
        )
        return int(rowcount)

    async def delete(
        self, user_id: uuid.UUID | str, notification_id: uuid.UUID | str
    ) -> bool:
        rowcount = await self._db.execute(
            "DELETE FROM notifications WHERE id = %s AND user_id = %s",
            [str(notification_id), str(user_id)],
        )
        return rowcount > 0


class ItineraryShareRepository:
    """Hashed, expiring share links. Raw tokens never touch the database."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def create(
        self,
        *,
        itinerary_id: uuid.UUID | str,
        user_id: uuid.UUID | str,
        token_hash: str,
        expires_at: str | None,
    ) -> dict[str, Any]:
        share_id = str(uuid.uuid4())
        now = utc_now_iso()
        async with self._db.transaction() as tx:
            await tx.execute(
                """
                INSERT INTO itinerary_shares
                    (id, itinerary_id, user_id, token_hash, expires_at, revoked_at, created_at)
                VALUES (%s, %s, %s, %s, %s, NULL, %s)
                """,
                [
                    share_id,
                    str(itinerary_id),
                    str(user_id),
                    token_hash,
                    expires_at,
                    now,
                ],
            )
            row = await tx.fetch_one(
                "SELECT * FROM itinerary_shares WHERE id = %s", [share_id]
            )
        assert row is not None
        return normalise_row(row)  # type: ignore[return-value]

    async def get_active_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            """
            SELECT * FROM itinerary_shares
            WHERE token_hash = %s AND revoked_at IS NULL
            """,
            [token_hash],
        )
        return normalise_row(row)

    async def list_for_itinerary(
        self, user_id: uuid.UUID | str, itinerary_id: uuid.UUID | str
    ) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT * FROM itinerary_shares
            WHERE user_id = %s AND itinerary_id = %s AND revoked_at IS NULL
            ORDER BY created_at DESC
            """,
            [str(user_id), str(itinerary_id)],
        )
        return normalise_rows(rows)

    async def revoke_all(
        self, user_id: uuid.UUID | str, itinerary_id: uuid.UUID | str
    ) -> int:
        rowcount = await self._db.execute(
            """
            UPDATE itinerary_shares SET revoked_at = %s
            WHERE user_id = %s AND itinerary_id = %s AND revoked_at IS NULL
            """,
            [utc_now_iso(), str(user_id), str(itinerary_id)],
        )
        return int(rowcount)


class AnalyticsRepository:
    """Raw rows used to build currency-safe user analytics in Python.

    Different currencies are never summed together.
    """

    def __init__(self, database: Database) -> None:
        self._db = database

    async def itinerary_rows(self, user_id: uuid.UUID | str) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT id, destination_name, destination_place_id, start_date, end_date,
                   travellers, total_budget, currency, status, budget_estimate,
                   created_at
            FROM itineraries
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            [str(user_id)],
        )
        decoded: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["budget_estimate"] = loads_json(item.get("budget_estimate"), None)
            decoded.append(normalise_row(item))  # type: ignore[arg-type]
        return decoded

    async def activity_rows(self, user_id: uuid.UUID | str) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT i.currency AS currency,
                   i.travellers AS travellers,
                   a.category AS category,
                   a.estimated_cost AS estimated_cost,
                   a.cost_type AS cost_type
            FROM itinerary_activities a
            JOIN itinerary_days d ON d.id = a.itinerary_day_id
            JOIN itineraries i ON i.id = d.itinerary_id
            WHERE i.user_id = %s
            """,
            [str(user_id)],
        )
        return normalise_rows(rows)  # type: ignore[return-value]
