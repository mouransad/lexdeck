"""Small SQLite adapter with versioned, forward-only schema migrations."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 2

MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    deck_id TEXT NOT NULL REFERENCES decks(id) ON DELETE RESTRICT,
    prompt TEXT NOT NULL CHECK (length(trim(prompt)) > 0),
    meaning TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]',
    fsrs_json TEXT NOT NULL,
    due_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 4),
    reviewed_at TEXT NOT NULL,
    duration_ms INTEGER,
    scheduler_log_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due_at) WHERE archived_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards(deck_id) WHERE archived_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_reviews_card ON reviews(card_id, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(reviewed_at DESC);
"""

MIGRATION_2 = """
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS recall_reviews (
    id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    remembered INTEGER NOT NULL CHECK (remembered IN (0, 1)),
    reviewed_at TEXT NOT NULL,
    duration_ms INTEGER
);

INSERT OR IGNORE INTO recall_reviews(id, card_id, remembered, reviewed_at, duration_ms)
SELECT id, card_id, CASE WHEN rating >= 3 THEN 1 ELSE 0 END, reviewed_at, duration_ms
FROM reviews;

DROP TABLE reviews;

CREATE INDEX IF NOT EXISTS idx_recall_reviews_card
    ON recall_reviews(card_id, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_recall_reviews_date
    ON recall_reviews(reviewed_at DESC);

INSERT INTO schema_migrations(version, applied_at)
VALUES (2, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));

COMMIT;
"""


class Database:
    """Owns connections and schema creation for one local database file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            current_version = int(
                connection.execute(
                    "SELECT coalesce(max(version), 0) FROM schema_migrations"
                ).fetchone()[0]
            )
            if current_version < 1:
                connection.executescript(MIGRATION_1)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) "
                    "VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"
                )
            if current_version < SCHEMA_VERSION:
                connection.executescript(MIGRATION_2)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()
