from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest
from lexdeck_core import LexdeckService, StudyOrder
from lexdeck_core.database import MIGRATION_1
from lexdeck_core.repository import CardNotFoundError
from lexdeck_core.service import ValidationError


@pytest.fixture
def service(tmp_path):
    return LexdeckService(tmp_path / "lexdeck.db")


def test_adds_unicode_card_with_nullable_meaning(service: LexdeckService) -> None:
    incomplete = service.add_card("in light of")
    complete = service.add_card("meticulous", "دقیق و موشکاف")

    assert incomplete.meaning is None
    assert complete.meaning == "دقیق و موشکاف"
    assert service.stats().total_cards == 2
    assert service.stats().complete_cards == 1


def test_rejects_empty_content(service: LexdeckService) -> None:
    with pytest.raises(ValidationError, match="cannot be empty"):
        service.add_card("  ")


def test_search_edit_and_archive(service: LexdeckService) -> None:
    card = service.add_card("run into", "meet unexpectedly")

    assert service.list_cards(query="unexpected")[0].id == card.id
    updated = service.edit_card(
        card.id[:8],
        prompt="run into someone",
        meaning="meet someone unexpectedly",
    )
    assert updated.prompt == "run into someone"
    assert updated.meaning == "meet someone unexpectedly"

    service.remove_card(card.id[:8])
    assert service.list_cards() == []
    with pytest.raises(CardNotFoundError):
        service.get_card(card.id)


def test_bulk_archive_is_atomic_and_preserves_order(service: LexdeckService) -> None:
    first = service.add_card("first")
    second = service.add_card("second")
    remaining = service.add_card("remaining")

    archived = service.remove_cards([second.id, first.id, second.id])

    assert [card.id for card in archived] == [second.id, first.id]
    assert [card.id for card in service.list_cards()] == [remaining.id]


def test_bulk_archive_does_not_change_cards_when_resolution_fails(
    service: LexdeckService,
) -> None:
    first = service.add_card("first")
    second = service.add_card("second")

    with pytest.raises(CardNotFoundError):
        service.remove_cards([first.id, "missing-card"])

    assert {card.id for card in service.list_cards()} == {first.id, second.id}


def test_binary_recall_updates_stats(service: LexdeckService) -> None:
    card = service.add_card("ubiquitous", "present everywhere")
    reviewed_at = datetime.now().astimezone()

    result = service.record_recall(card.id, True, reviewed_at=reviewed_at)

    assert result.remembered is True
    assert result.reviewed_at == reviewed_at
    assert service.stats().reviewed_today == 1
    assert service.stats().remembered_today == 1


def test_every_session_contains_every_card(service: LexdeckService) -> None:
    incomplete = service.add_card("unfinished")
    complete = service.add_card("finished", "done")

    sorted_cards = service.study_cards(StudyOrder.SORTED)
    random_cards = service.study_cards(StudyOrder.RANDOM)

    assert [card.id for card in sorted_cards] == [complete.id, incomplete.id]
    assert {card.id for card in random_cards} == {complete.id, incomplete.id}


def test_migrates_legacy_ratings_to_binary_recall(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(path) as connection:
        connection.executescript(MIGRATION_1)
        connection.execute("INSERT INTO schema_migrations VALUES (1, ?)", (now,))
        connection.execute("INSERT INTO decks VALUES ('deck', 'Legacy', NULL, ?)", (now,))
        connection.execute(
            "INSERT INTO cards VALUES "
            "('card', 'deck', 'legacy', 'old meaning', '[]', '{}', ?, ?, ?, NULL)",
            (now, now, now),
        )
        connection.execute(
            "INSERT INTO reviews VALUES ('review', 'card', 3, ?, NULL, '{}')",
            (now,),
        )

    service = LexdeckService(path)

    assert service.stats().reviewed_today == 1
    assert service.stats().remembered_today == 1
    with service.database.connect() as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'reviews'"
            ).fetchone()
            is None
        )
