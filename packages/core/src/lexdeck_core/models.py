"""Domain models shared by every Lexdeck interface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class StudyOrder(StrEnum):
    """Available ordering strategies for a review session."""

    RANDOM = "random"
    SORTED = "sorted"


@dataclass(frozen=True, slots=True)
class Card:
    id: str
    prompt: str
    meaning: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def is_complete(self) -> bool:
        """A card can be tested once it has an answer."""
        return bool(self.meaning and self.meaning.strip())


@dataclass(frozen=True, slots=True)
class RecallResult:
    card: Card
    remembered: bool
    reviewed_at: datetime


@dataclass(frozen=True, slots=True)
class Stats:
    total_cards: int
    complete_cards: int
    reviewed_today: int
    remembered_today: int
    streak_days: int
