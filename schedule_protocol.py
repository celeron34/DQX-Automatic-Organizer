"""JSON message format sent from the schedule bot to the formation bot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from dqx_ise import DefenseScheduleEntry


def serialize_entries(entries: list[DefenseScheduleEntry]) -> dict[str, list[dict[str, Any]]]:
    return {
        "entries": [
            {
                "datetime": entry.datetime.isoformat(timespec="seconds"),
                "force_id": entry.force_id,
                "is_all_forces": entry.is_all_forces,
            }
            for entry in entries
        ]
    }


def deserialize_entries(payload: Any) -> list[DefenseScheduleEntry]:
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise ValueError("payload must contain an entries array")

    entries = []
    for index, item in enumerate(payload["entries"]):
        if not isinstance(item, dict):
            raise ValueError(f"entries[{index}] must be an object")
        try:
            starts_at = datetime.fromisoformat(item["datetime"])
            force_id = item["force_id"]
            is_all_forces = item["is_all_forces"]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"entries[{index}] has invalid fields") from error
        if isinstance(force_id, bool) or not isinstance(force_id, int):
            raise ValueError(f"entries[{index}].force_id must be an integer")
        if not isinstance(is_all_forces, bool):
            raise ValueError(f"entries[{index}].is_all_forces must be a boolean")
        entries.append(DefenseScheduleEntry(starts_at, force_id, is_all_forces))
    return entries
