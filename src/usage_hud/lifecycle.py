"""A tiny run record: when the app started, a pulse while it runs, and how it ended.

A process that is killed from outside leaves no traceback, so the only way to
learn how it died is what it did NOT write. On the next start the previous run's
pulse file still says "running" if that run never exited cleanly, and the last
pulse time bounds when it died.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

_PULSE = "pulse.txt"
_LOG = "lifecycle.log"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _append(state_dir: Path, line: str) -> None:
    try:
        with open(state_dir / _LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{_now()} {line}\n")
    except OSError:
        pass


def _write_pulse(state_dir: Path, status: str) -> None:
    try:
        (state_dir / _PULSE).write_text(f"{status} {_now()} pid={os.getpid()}\n", encoding="utf-8")
    except OSError:
        pass


def start(state_dir: Path) -> None:
    """Record a start; note a previous run that never exited cleanly."""
    try:
        previous = (state_dir / _PULSE).read_text(encoding="utf-8").strip()
    except OSError:
        previous = ""
    if previous.startswith("running"):
        _append(state_dir, f"previous run vanished without a clean exit; last pulse: {previous}")
    _append(state_dir, f"start pid={os.getpid()}")
    _write_pulse(state_dir, "running")


def pulse(state_dir: Path) -> None:
    _write_pulse(state_dir, "running")


def note(state_dir: Path, text: str) -> None:
    _append(state_dir, text)


_LONG_TOKENISH = re.compile(r"[A-Za-z0-9_\-.+/=]{40,}")
_MAX_ERROR_CHARS = 160


def _plain_error(text: str) -> str:
    """One short line: runs that could be a token are masked, the rest capped."""
    text = _LONG_TOKENISH.sub("…", " ".join(text.split()))
    return text if len(text) <= _MAX_ERROR_CHARS else text[:_MAX_ERROR_CHARS] + "…"


def note_provider_failures(state_dir: Path, snapshots: list, seen: dict[str, str]) -> None:
    """Log why a provider failed (the chip only shows "!") — once per change.

    ``seen`` remembers each provider's last failure so a steady error is not
    repeated every refresh; a later success is noted once as "ok again".
    """
    for snap in snapshots:
        if snap.ok:
            if seen.pop(snap.provider_id, ""):
                _append(state_dir, f"{snap.provider_id}: ok again")
            continue
        reason = _plain_error(snap.error or "failed without a message")
        if seen.get(snap.provider_id) != reason:
            seen[snap.provider_id] = reason
            _append(state_dir, f"{snap.provider_id}: {reason}")


def session_ending(state_dir: Path) -> None:
    _append(state_dir, "Windows session is ending (logoff/shutdown/restart)")


def clean_exit(state_dir: Path) -> None:
    _append(state_dir, "clean exit")
    _write_pulse(state_dir, "exited")


def no_tray(state_dir: Path) -> None:
    _append(state_dir, "no system tray available; exiting")
    _write_pulse(state_dir, "exited")
