"""Explicit hide / snooze state for the chip (persisted)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# minutes; None in API means forever
SNOOZE_CHOICES: tuple[tuple[str, int | None], ...] = (
    ("60 minutes", 60),
    ("180 minutes", 180),
    ("1 day", 24 * 60),
    ("Forever", None),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SnoozeState:
    forever: bool = False
    until: datetime | None = None

    @property
    def active(self) -> bool:
        if self.forever:
            return True
        if self.until is None:
            return False
        return self.until > _utc_now()

    def remaining_label(self) -> str:
        if self.forever:
            return "forever"
        if self.until is None:
            return ""
        secs = max(0, int((self.until - _utc_now()).total_seconds()))
        if secs >= 86400:
            return f"{secs // 86400}d { (secs % 86400) // 3600}h"
        if secs >= 3600:
            return f"{secs // 3600}h {(secs % 3600) // 60}m"
        return f"{secs // 60}m"


class SnoozeStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> SnoozeState:
        if not self.path.is_file():
            return SnoozeState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return SnoozeState()
        forever = bool(data.get("forever"))
        until = None
        raw = data.get("until")
        if raw:
            try:
                until = datetime.fromisoformat(str(raw))
                if until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
            except ValueError:
                until = None
        state = SnoozeState(forever=forever, until=until)
        if not state.active and (forever or until):
            # Expired timed snooze — clear file.
            self.clear()
            return SnoozeState()
        return state

    def save(self, state: SnoozeState) -> None:
        payload = {
            "forever": state.forever,
            "until": state.until.isoformat() if state.until else None,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def clear(self) -> None:
        if self.path.is_file():
            try:
                self.path.unlink()
            except OSError:
                pass

    def snooze(self, minutes: int | None) -> SnoozeState:
        if minutes is None:
            state = SnoozeState(forever=True, until=None)
        else:
            state = SnoozeState(
                forever=False,
                until=_utc_now() + timedelta(minutes=minutes),
            )
        self.save(state)
        return state
