"""Discord-independent event configuration and legacy schedule phases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class EventPhase(Enum):
    """A phase boundary in the existing single-event schedule."""

    RECRUITING = "recruiting"
    REMINDER = "reminder"
    FORMATION = "formation"
    START = "start"
    FINISH = "finish"

    @classmethod
    def at(cls, now: datetime, starts_at: datetime) -> EventPhase | None:
        """Return the phase matching this minute, preserving current timing."""
        offsets = {
            cls.RECRUITING: timedelta(minutes=-30),
            cls.REMINDER: timedelta(minutes=-15),
            cls.FORMATION: timedelta(minutes=-10),
            cls.START: timedelta(),
            cls.FINISH: timedelta(minutes=60),
        }
        return next(
            (phase for phase, offset in offsets.items() if now == starts_at + offset),
            None,
        )


@dataclass
class EventDefinition:
    """Editable event data; unset values represent a new, empty draft."""

    title: str = ""
    starts_at: datetime | None = None
    description: str = ""
    recruitment_text: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.title.strip()) and self.starts_at is not None

    def update(
        self,
        *,
        title: str | None = None,
        starts_at: datetime | None = None,
        description: str | None = None,
        recruitment_text: str | None = None,
    ) -> None:
        """Update only supplied settings so Discord controls can configure incrementally."""
        if title is not None:
            self.title = title.strip()
        if starts_at is not None:
            self.starts_at = starts_at
        if description is not None:
            self.description = description
        if recruitment_text is not None:
            self.recruitment_text = recruitment_text
