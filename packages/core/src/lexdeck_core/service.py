"""Application workflows used identically by the CLI, TUI, and future web UI."""

from __future__ import annotations

import random
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from lexdeck_core.database import Database
from lexdeck_core.models import Card, RecallResult, Stats, StudyOrder
from lexdeck_core.paths import database_path
from lexdeck_core.repository import Repository


class ValidationError(ValueError):
    pass


class LexdeckService:
    def __init__(self, path: Path | None = None) -> None:
        self.database = Database(path or database_path())
        self.database.initialize()
        self.repository = Repository(self.database)
        self._default_deck_id = self.repository.ensure_default_deck()

    @property
    def data_path(self) -> Path:
        return self.database.path

    def add_card(
        self,
        prompt: str,
        meaning: str | None = None,
    ) -> Card:
        prompt = _required(prompt, "The card content cannot be empty")
        meaning = _optional(meaning)
        return self.repository.create_card(
            deck_id=self._default_deck_id,
            prompt=prompt,
            meaning=meaning,
        )

    def edit_card(
        self,
        card_id: str,
        *,
        prompt: str,
        meaning: str | None,
    ) -> Card:
        existing = self.get_card(card_id)
        return self.repository.update_card(
            existing.id,
            prompt=_required(prompt, "The card content cannot be empty"),
            meaning=_optional(meaning),
        )

    def get_card(self, card_id: str) -> Card:
        return self.repository.get_card(card_id)

    def list_cards(self, *, query: str | None = None, limit: int | None = None) -> list[Card]:
        return self.repository.list_cards(query=query, limit=limit)

    def study_cards(self, order: StudyOrder) -> list[Card]:
        """Return every active card in the order selected for this session."""
        cards = self.repository.list_cards()
        if order is StudyOrder.RANDOM:
            random.shuffle(cards)
        else:
            cards.sort(key=lambda card: (card.prompt.casefold(), card.created_at, card.id))
        return cards

    def remove_card(self, card_id: str) -> Card:
        card = self.get_card(card_id)
        self.repository.archive_card(card.id)
        return card

    def remove_cards(self, card_ids: Iterable[str]) -> list[Card]:
        """Archive a resolved set of active cards in one transaction."""
        cards_by_id: dict[str, Card] = {}
        for card_id in card_ids:
            card = self.get_card(card_id)
            cards_by_id[card.id] = card
        cards = list(cards_by_id.values())
        self.repository.archive_cards([card.id for card in cards])
        return cards

    def record_recall(
        self,
        card_id: str,
        remembered: bool,
        *,
        reviewed_at: datetime | None = None,
        duration_ms: int | None = None,
    ) -> RecallResult:
        card = self.get_card(card_id)
        actual_reviewed_at = reviewed_at or datetime.now(UTC)
        if actual_reviewed_at.tzinfo is None:
            actual_reviewed_at = actual_reviewed_at.replace(tzinfo=UTC)
        else:
            actual_reviewed_at = actual_reviewed_at.astimezone(UTC)
        self.repository.save_recall(
            card_id=card.id,
            remembered=remembered,
            reviewed_at=actual_reviewed_at,
            duration_ms=duration_ms,
        )
        return RecallResult(card, remembered, actual_reviewed_at)

    def stats(self) -> Stats:
        return self.repository.stats()


def _required(value: str, message: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(message)
    return cleaned


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
