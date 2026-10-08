"""Opt-in live Claude usage — exact percent and exact reset time per window.

The default Claude provider reads only files Claude Desktop already writes
(see anthropic.py): no token, no network. This module is the OPTIONAL
alternative, off unless the user turns on "claude_live_usage" in Settings.

Everything here is split on purpose:

* ``fetch_live_usage`` is the ONE function that touches a credential and the
  network. It is deliberately left unimplemented in this file — it is written
  and reviewed by the user (or a tool the user chose), not generated here.
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

from dataclasses import dataclass
from datetime import datetime, timezone

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


def fetch_live_usage() -> dict[str, LiveWindow]:
    """Return ``{"five_hour": LiveWindow, "seven_day": LiveWindow}`` (either may
    be missing). See the module docstring for the rules.

    NOT IMPLEMENTED HERE — to be filled in by the user. Until then the option
    is harmless: it raises, and the HUD keeps using the Desktop log.
    """
    raise LiveUsageUnavailable("live usage is enabled but fetch_live_usage() is not implemented")


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
