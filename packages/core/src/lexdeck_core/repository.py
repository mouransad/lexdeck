"""SQLite repository. SQL stays here; user workflows stay in the service layer."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from lexdeck_core.database import Database
from lexdeck_core.models import Card, Stats


class CardNotFoundError(LookupError):
    pass


class Repository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_default_deck(self) -> str:
        """Return the internal compatibility deck used by the legacy schema."""
        with self.database.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM decks WHERE name = 'Default' COLLATE NOCASE"
            ).fetchone()
            if existing:
                return str(existing["id"])
        deck_id = str(uuid4())
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO decks(id, name, description, created_at) "
                "VALUES (?, 'Default', NULL, ?)",
                (deck_id, _dump_time(_now())),
            )
        return deck_id

    def create_card(
        self,
        *,
        deck_id: str,
        prompt: str,
        meaning: str | None,
    ) -> Card:
        card_id = str(uuid4())
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO cards(
                    id, deck_id, prompt, meaning, tags_json, fsrs_json,
                    due_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card_id,
                    deck_id,
                    prompt,
                    meaning,
                    "[]",
                    "{}",
                    _dump_time(now),
                    _dump_time(now),
                    _dump_time(now),
                ),
            )
        return self.get_card(card_id)

    def get_card(self, card_id_or_prefix: str) -> Card:
        with self.database.connect() as connection:
            rows = connection.execute(
                _CARD_SELECT + " WHERE c.archived_at IS NULL AND (c.id = ? OR c.id LIKE ?) LIMIT 2",
                (card_id_or_prefix, f"{card_id_or_prefix}%"),
            ).fetchall()
        if not rows:
            raise CardNotFoundError(f"No card matches {card_id_or_prefix!r}")
        if len(rows) > 1:
            raise CardNotFoundError(f"Card ID prefix {card_id_or_prefix!r} is ambiguous")
        return _card_from_row(rows[0])

    def list_cards(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
    ) -> list[Card]:
        clauses = ["c.archived_at IS NULL"]
        parameters: list[object] = []
        if query:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append(
                "(c.prompt LIKE ? ESCAPE '\\' COLLATE NOCASE "
                "OR coalesce(c.meaning, '') LIKE ? ESCAPE '\\' COLLATE NOCASE)"
            )
            needle = f"%{escaped}%"
            parameters.extend([needle, needle])
        sql = _CARD_SELECT + " WHERE " + " AND ".join(clauses) + " ORDER BY c.updated_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            parameters.append(limit)
        with self.database.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [_card_from_row(row) for row in rows]

    def update_card(
        self,
        card_id: str,
        *,
        prompt: str,
        meaning: str | None,
    ) -> Card:
        with self.database.connect() as connection:
            result = connection.execute(
                """
                UPDATE cards
                SET prompt = ?, meaning = ?, updated_at = ?
                WHERE id = ? AND archived_at IS NULL
                """,
                (
                    prompt,
                    meaning,
                    _dump_time(_now()),
                    card_id,
                ),
            )
        if result.rowcount == 0:
            raise CardNotFoundError(card_id)
        return self.get_card(card_id)

    def archive_card(self, card_id: str) -> None:
        now = _dump_time(_now())
        with self.database.connect() as connection:
            result = connection.execute(
                "UPDATE cards SET archived_at = ?, updated_at = ? "
                "WHERE id = ? AND archived_at IS NULL",
                (now, now, card_id),
            )
        if result.rowcount == 0:
            raise CardNotFoundError(card_id)

    def archive_cards(self, card_ids: list[str]) -> None:
        if not card_ids:
            return
        now = _dump_time(_now())
        placeholders = ", ".join("?" for _ in card_ids)
        with self.database.connect() as connection:
            result = connection.execute(
                f"UPDATE cards SET archived_at = ?, updated_at = ? "
                f"WHERE archived_at IS NULL AND id IN ({placeholders})",
                [now, now, *card_ids],
            )
            if result.rowcount != len(card_ids):
                raise CardNotFoundError("One or more selected cards are no longer active")

    def save_recall(
        self,
        *,
        card_id: str,
        remembered: bool,
        reviewed_at: datetime,
        duration_ms: int | None,
    ) -> None:
        with self.database.connect() as connection:
            result = connection.execute(
                """
                INSERT INTO recall_reviews(id, card_id, remembered, reviewed_at, duration_ms)
                SELECT ?, id, ?, ?, ? FROM cards
                WHERE id = ? AND archived_at IS NULL
                """,
                (
                    str(uuid4()),
                    int(remembered),
                    _dump_time(reviewed_at),
                    duration_ms,
                    card_id,
                ),
            )
        if result.rowcount == 0:
            raise CardNotFoundError(card_id)

    def stats(self) -> Stats:
        today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    count(*) AS total,
                    count(CASE WHEN meaning IS NOT NULL AND length(trim(meaning)) > 0 THEN 1 END)
                        AS complete
                FROM cards WHERE archived_at IS NULL
                """
            ).fetchone()
            recall_row = connection.execute(
                """
                SELECT count(*) AS total, coalesce(sum(remembered), 0) AS remembered
                FROM recall_reviews WHERE reviewed_at >= ?
                """,
                (_dump_time(today),),
            ).fetchone()
            dates = [
                datetime.fromisoformat(str(item[0])).date()
                for item in connection.execute(
                    "SELECT DISTINCT substr(reviewed_at, 1, 10) FROM recall_reviews ORDER BY 1 DESC"
                ).fetchall()
            ]
        reviewed_today = int(recall_row["total"])
        remembered_today = int(recall_row["remembered"])
        return Stats(
            total_cards=int(row["total"]),
            complete_cards=int(row["complete"]),
            reviewed_today=reviewed_today,
            remembered_today=remembered_today,
            streak_days=_streak(dates, today.date()),
        )


_CARD_SELECT = """
SELECT c.id, c.prompt, c.meaning, c.created_at, c.updated_at
FROM cards c
"""


def _card_from_row(row: sqlite3.Row) -> Card:
    return Card(
        id=str(row["id"]),
        prompt=str(row["prompt"]),
        meaning=str(row["meaning"]) if row["meaning"] is not None else None,
        created_at=_load_time(str(row["created_at"])),
        updated_at=_load_time(str(row["updated_at"])),
    )


def _now() -> datetime:
    return datetime.now(UTC)


def _dump_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _load_time(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _streak(review_dates: list[date], today: date) -> int:
    if not review_dates:
        return 0
    current = today
    if review_dates[0] != today:
        current = today - timedelta(days=1)
    streak = 0
    date_set = set(review_dates)
    while current in date_set:
        streak += 1
        current -= timedelta(days=1)
    return streak
