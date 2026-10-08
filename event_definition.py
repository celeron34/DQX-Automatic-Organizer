"""Discord-independent event configuration and legacy schedule phases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class EventPhase(Enum):
    """A phase boundary shared by every event instance."""

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


@dataclass
class EventInstance:
    """Mutable, independent runtime state for one scheduled event."""

    definition: EventDefinition
    recruiting_members: list[Any] = field(default_factory=list)
    parties: list[Any] | None = None
    recruiting_message: Any = None
    processed_phases: set[EventPhase] = field(default_factory=set)

    @property
    def starts_at(self) -> datetime:
        if self.definition.starts_at is None:
            raise ValueError("An event instance needs a start time")
        return self.definition.starts_at

    def claim_phase(self, phase: EventPhase) -> bool:
        """Ensure a phase is processed at most once by the minute loop."""
        if phase in self.processed_phases:
            return False
        self.processed_phases.add(phase)
        return True
