"""Opt-in live Claude usage — exact percent and exact reset time per window.

The default Claude provider reads only files Claude Desktop already writes
(see anthropic.py): no token, no network. This module is the OPTIONAL
alternative, off unless the user turns on "claude_live_usage" in Settings.

Everything here is split on purpose:

* ``fetch_live_usage`` is the ONE function that touches a credential and the
  network.
* ``snapshot_from_live`` and ``AnthropicProvider.fetch`` only consume the plain
  ``LiveWindow`` values it returns, so they are testable with synthetic data.

Rules for the implementation of ``fetch_live_usage``:

* Read the sign-in token only inside the call, keep it in a local variable,
  never store it (settings, history, state dir, git) and never log or print it
  — including in exception messages.
* Send it only to Anthropic's own host, over HTTPS, with a short timeout.
* Never refresh or rotate the token: refreshing could sign Claude Code out.
  An expired token means ``LiveUsageUnavailable``; the HUD then falls back to
  the Desktop log by itself.
* Return percentages on a 0-100 scale and reset times as aware datetimes (or
  ``None`` when the source gives none).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from usage_hud.models import Metric, ProviderSnapshot

# (metric key, label) — same keys the Desktop-log path uses, so charts,
# history and the chip treat both sources identically.
LIVE_WINDOWS: tuple[tuple[str, str], ...] = (
    ("five_hour", "5h"),
    ("seven_day", "7d"),
)


class LiveUsageUnavailable(Exception):
    """Live usage could not be fetched (no sign-in, expired, offline, unexpected
    reply). The message is shown to the user, so it must never contain secrets."""


@dataclass(frozen=True)
class LiveWindow:
    percent: float
    resets_at: datetime | None = None


_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
_TIMEOUT_SECONDS = 10
# The HUD refreshes every few minutes; the usage numbers move far slower than
# that, and a polite client keeps the request rate low.
_CACHE_SECONDS = 300
_cache: tuple[float, dict[str, LiveWindow]] | None = None


def _credentials_path() -> Path:
    return Path.home() / ".claude" / ".credentials.json"


def _read_token(path: Path) -> str:
    """The access token, held only in the caller's local variable. Raises
    LiveUsageUnavailable (never including any file content) when there is no
    usable sign-in. Never refreshes: that could sign Claude Code out."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        block = data["claudeAiOauth"]
        token = block["accessToken"]
        expires_ms = block.get("expiresAt")
    except (OSError, ValueError, KeyError, TypeError):
        raise LiveUsageUnavailable("no Claude Code sign-in found") from None
    if not isinstance(token, str) or not token:
        raise LiveUsageUnavailable("no Claude Code sign-in found")
    if isinstance(expires_ms, (int, float)) and expires_ms / 1000.0 <= time.time():
        raise LiveUsageUnavailable(
            "Claude Code sign-in expired - use Claude Code once to renew it"
        )
    return token


def _parse_window(block: object) -> LiveWindow | None:
    if not isinstance(block, dict):
        return None
    percent = block.get("utilization")
    if isinstance(percent, bool) or not isinstance(percent, (int, float)):
        return None
    resets_at = None
    raw_end = block.get("resets_at")
    if isinstance(raw_end, str):
        try:
            resets_at = datetime.fromisoformat(raw_end.replace("Z", "+00:00"))
        except ValueError:
            resets_at = None
        if resets_at is not None and resets_at.tzinfo is None:
            resets_at = resets_at.replace(tzinfo=timezone.utc)
    return LiveWindow(percent=float(percent), resets_at=resets_at)


def fetch_live_usage(
    *,
    credentials_path: Path | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, LiveWindow]:
    """Return ``{"five_hour": LiveWindow, "seven_day": LiveWindow}`` (either may
    be missing). See the module docstring for the rules.

    The only place in the app that reads a sign-in token and the only request
    to Anthropic. Every failure becomes ``LiveUsageUnavailable`` with a fixed,
    secret-free message; the HUD then falls back to the Desktop log.
    """
    global _cache
    if _cache is not None and time.monotonic() - _cache[0] < _CACHE_SECONDS:
        return _cache[1]

    token = _read_token(credentials_path or _credentials_path())
    request = urllib.request.Request(
        _USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "Accept": "application/json",
            "User-Agent": "usage-hud",
        },
    )
    del token
    try:
        with opener(request, timeout=_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LiveUsageUnavailable(f"Anthropic answered HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise LiveUsageUnavailable("Anthropic not reachable") from None
    except ValueError:
        raise LiveUsageUnavailable("unexpected reply from Anthropic") from None

    usage: dict[str, LiveWindow] = {}
    if isinstance(payload, dict):
        for key, _label in LIVE_WINDOWS:
            window = _parse_window(payload.get(key))
            if window is not None:
                usage[key] = window
    if not usage:
        raise LiveUsageUnavailable("unexpected reply from Anthropic")
    _cache = (time.monotonic(), usage)
    return usage


def snapshot_from_live(
    now: datetime,
    usage: dict[str, LiveWindow],
    *,
    title: str,
    extra_usage: bool = False,
) -> ProviderSnapshot | None:
    metrics: list[Metric] = []
    for key, label in LIVE_WINDOWS:
        window = usage.get(key)
        if window is None:
            continue
        value = max(0.0, min(100.0, float(window.percent)))
        end = window.resets_at.astimezone(timezone.utc) if window.resets_at else None
        metrics.append(
            Metric(
                key=key,
                label=label,
                used=value,
                limit=100.0,
                unit="%",
                remaining=100.0 - value,
                percent_used=value,
                detail="Claude live usage",
                cycle_end=end,
            )
        )
    if not metrics:
        return None
    message = "Claude live usage · exact resets"
    if extra_usage:
        message += " · extra usage on (weekly cap is not a hard stop)"
    return ProviderSnapshot(
        provider_id="anthropic",
        title=title,
        ok=True,
        fetched_at=now,
        metrics=metrics,
        cycle_end=metrics[0].cycle_end,
        message=message,
        raw={"source": "live"},
    )
