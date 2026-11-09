"""Keeps Claude Code's sign-in fresh so live Claude usage does not drop out.

The HUD reads Claude Code's access token (see providers/anthropic_live.py) but
never refreshes it: a refresh from outside could sign Claude Code out. The token
lives only a few hours, and Claude Code renews it only when it is used. So the
HUD *uses* it — one tiny request through the official `claude` CLI, which
refreshes its own token as a side effect. This module never reads, writes or
logs any credential; it only runs the CLI and records whether it succeeded.

Runs only when live Claude usage is switched on, at most every few hours, and
sooner when the HUD sees the sign-in has expired.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

SCHEDULED_INTERVAL = timedelta(hours=3)  # how often it runs while the sign-in is fine
RETRY_AFTER_EXPIRY = timedelta(minutes=20)  # between attempts once it has expired
_TIMEOUT_SECONDS = 90
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console flash on Windows
_STATE_FILE = "keepalive.json"
_WORK_DIR = "keepalive"  # the CLI's working dir: keeps it out of real projects


@dataclass(frozen=True)
class KeepaliveResult:
    ran: bool
    ok: bool
    text: str  # fixed wording, never any output of the CLI


def find_claude_cli() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        shim = Path(os.environ["APPDATA"]) / "npm" / "claude.cmd"
        if shim.is_file():
            return str(shim)
    return None


def _load(state_dir: Path) -> dict:
    try:
        data = json.loads((state_dir / _STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(state_dir: Path, data: dict) -> None:
    try:
        (state_dir / _STATE_FILE).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def needs_refresh_now(snapshots: list) -> bool:
    """True when a Claude snapshot says live usage failed because the sign-in
    expired — the moment to renew it rather than wait for the schedule."""
    return any("sign-in expired" in snap.raw.get("live_error", "") for snap in snapshots)


def run_keepalive(
    state_dir: Path,
    *,
    expired: bool = False,
    now: datetime | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    find_cli: Callable[[], str | None] = find_claude_cli,
) -> KeepaliveResult:
    now = now or datetime.now(timezone.utc)
    state = _load(state_dir)
    gap = RETRY_AFTER_EXPIRY if expired else SCHEDULED_INTERVAL
    last = state.get("last_attempt")
    if last:
        try:
            if now - datetime.fromisoformat(last) < gap:
                return KeepaliveResult(False, False, "skipped (ran recently)")
        except ValueError:
            pass
    cli = find_cli()
    if cli is None:
        return KeepaliveResult(False, False, "skipped (claude CLI not found)")

    work = state_dir / _WORK_DIR
    work.mkdir(parents=True, exist_ok=True)
    state["last_attempt"] = now.isoformat()
    _save(state_dir, state)
    try:
        proc = runner(
            [cli, "-p", "ok", "--model", "haiku", "--no-session-persistence"],
            cwd=str(work),
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=_TIMEOUT_SECONDS,
            creationflags=_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return KeepaliveResult(True, False, "failed (timed out)")
    except OSError as exc:
        return KeepaliveResult(True, False, f"failed ({type(exc).__name__})")
    if proc.returncode != 0:
        return KeepaliveResult(True, False, f"failed (exit {proc.returncode})")
    state["last_ok"] = now.isoformat()
    _save(state_dir, state)
    return KeepaliveResult(True, True, "refreshed")


class KeepaliveRunner(QObject):
    """Runs run_keepalive off the UI thread; ``on_result(reason, result)`` is
    called later on the UI thread."""

    _done = Signal(str, object)

    def __init__(self, on_result: Callable[[str, KeepaliveResult], None]) -> None:
        super().__init__()
        self._on_result = on_result
        self._busy = False
        self._done.connect(self._finish)

    @property
    def busy(self) -> bool:
        return self._busy

    def start(self, state_dir: Path, *, reason: str) -> None:
        if self._busy:
            return
        self._busy = True
        threading.Thread(target=self._work, args=(state_dir, reason), daemon=True).start()

    def _work(self, state_dir: Path, reason: str) -> None:
        try:
            result = run_keepalive(state_dir, expired=reason == "expired")
        except Exception:  # noqa: BLE001 - must never take the app down
            result = KeepaliveResult(True, False, "failed (unexpected error)")
        self._done.emit(reason, result)

    @Slot(str, object)
    def _finish(self, reason: str, result: KeepaliveResult) -> None:
        self._busy = False
        self._on_result(reason, result)
