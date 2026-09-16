"""Claude usage — strictly local, from files Claude already writes on this PC.

Claude subscriptions have no monthly meter and no daily meter: every limit is a
*rolling window*.

* 5h — session window, all models, refills 5 h after the window opened
* 7d — weekly window, all models

This provider deliberately reads **no credentials and makes no network call**.
It uses two files only:

* ``plan-usage-history.json`` (Claude Desktop) — percent per window, written
  while the desktop app runs. It carries no reset timestamps, so window ends are
  estimated from the sample series and marked as estimates.
* ``~/.claude.json`` → ``oauthAccount`` — plan metadata (account, rate-limit
  tier, extra-usage flag). Secrets are never touched.

A Claude account token would give exact reset times from the account API, but
reading that token and sending it anywhere is out of scope for this HUD.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from usage_hud.models import Metric, ProviderSnapshot, utc_now
from usage_hud.providers.base import Provider

# Claude Desktop log key, chip label, window length.
# The Opus-only weekly window exists on Max plans but is not in the local log.
WINDOWS: tuple[tuple[str, str, str, timedelta], ...] = (
    ("five_hour", "fh", "5h", timedelta(hours=5)),
    ("seven_day", "sd", "7d", timedelta(days=7)),
)

# A log older than this is reported as stale rather than as the current truth.
STALE_AFTER = timedelta(minutes=20)

_TIER_RE = re.compile(r"^(max|pro|free|team)(?:_(\d+)x)?$")


# --------------------------------------------------------------------------- #
# Local file discovery
# --------------------------------------------------------------------------- #


def claude_desktop_roots() -> list[Path]:
    """Candidate Claude Desktop user-data dirs (Windows Store + native + Linux)."""
    roots: list[Path] = []
    override = os.environ.get("CLAUDE_DESKTOP_DIR", "").strip()
    if override:
        roots.append(Path(override).expanduser())

    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA") or "")
        roaming = Path(os.environ.get("APPDATA") or "")
        # MSIX / Store package virtualizes Roaming\Claude under LocalCache.
        packages = local / "Packages"
        if packages.is_dir():
            for pkg in packages.glob("Claude_*"):
                roots.append(pkg / "LocalCache" / "Roaming" / "Claude")
        roots.append(roaming / "Claude")
        roots.append(local / "Claude")
    else:
        # Electron / Flatpak-ish layouts on Linux/KDE.
        roots.append(Path.home() / ".config" / "Claude")
        roots.append(Path.home() / ".var" / "app" / "com.anthropic.Claude" / "config" / "Claude")

    # De-dupe while preserving order.
    seen: set[Path] = set()
    out: list[Path] = []
    for root in roots:
        key = root.resolve() if root.exists() else root
        if key in seen:
            continue
        seen.add(key)
        out.append(root)
    return out


def find_plan_usage_history() -> Path | None:
    for root in claude_desktop_roots():
        path = root / "plan-usage-history.json"
        if path.is_file():
            return path
    return None


def claude_json_path() -> Path:
    override = os.environ.get("CLAUDE_JSON", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- #
# Plan metadata (~/.claude.json — account profile, no secrets)
# --------------------------------------------------------------------------- #


def claude_account_meta() -> dict[str, Any]:
    account = _read_json(claude_json_path()).get("oauthAccount")
    return account if isinstance(account, dict) else {}


def claude_account_label(account: dict[str, Any] | None = None) -> str:
    account = claude_account_meta() if account is None else account
    return str(account.get("emailAddress") or account.get("displayName") or "")


def plan_from_tier(tier: str) -> str:
    """"default_claude_max_5x" -> "Max 5x". Internal codenames map to "" ."""
    key = tier.strip().lower()
    while key.startswith(("default_", "claude_")):
        key = key.split("_", 1)[1] if "_" in key else ""
    match = _TIER_RE.match(key)
    if not match:
        return ""
    name, multiplier = match.group(1).title(), match.group(2)
    return f"{name} {multiplier}x" if multiplier else name


def plan_title(account: dict[str, Any]) -> str:
    """Chip / panel heading: plan tier and account, whatever is known."""
    tier = str(account.get("userRateLimitTier") or account.get("organizationRateLimitTier") or "")
    plan = plan_from_tier(tier)
    title = f"Claude {plan}" if plan else "Claude"
    label = claude_account_label(account)
    return f"{title} · {label}" if label else title


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #


def _epoch_ms(value: Any) -> datetime | None:
    try:
        ms = float(value)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    # Some writers store seconds, some milliseconds.
    if ms > 1e11:
        ms /= 1000.0
    try:
        return datetime.fromtimestamp(ms, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _pct_metric(
    key: str,
    label: str,
    pct: float,
    *,
    cycle_end: datetime | None = None,
    detail: str = "",
) -> Metric:
    value = max(0.0, min(100.0, float(pct)))
    return Metric(
        key=key,
        label=label,
        used=value,
        limit=100.0,
        unit="%",
        remaining=max(0.0, 100.0 - value),
        percent_used=value,
        detail=detail,
        cycle_end=cycle_end,
    )


def _samples(data: dict[str, Any]) -> list[tuple[datetime, dict[str, Any]]]:
    out: list[tuple[datetime, dict[str, Any]]] = []
    for sample in data.get("samples") or []:
        if not isinstance(sample, dict):
            continue
        ts = _epoch_ms(sample.get("t"))
        usage = sample.get("u")
        if ts is None or not isinstance(usage, dict):
            continue
        out.append((ts, usage))
    out.sort(key=lambda item: item[0])
    return out


def infer_window_end(
    samples: list[tuple[datetime, dict[str, Any]]],
    log_key: str,
    span: timedelta,
    now: datetime,
) -> datetime | None:
    """Estimate when a rolling window opened, from the local percent series.

    The window start is the last reset visible in the log: either a drop in
    utilization, or the last zero sample before usage appeared. An all-zero
    series means no window is running, and a window that should already have
    rolled is reported as unknown instead of being guessed forward.
    """
    points: list[tuple[datetime, float]] = []
    for ts, usage in samples:
        value = usage.get(log_key)
        if value is None:
            continue
        try:
            points.append((ts, float(value)))
        except (TypeError, ValueError):
            continue
    if not points or points[-1][1] <= 0:
        return None

    start_idx: int | None = None
    for i in range(1, len(points)):
        if points[i][1] < points[i - 1][1]:
            start_idx = i
    if start_idx is None:
        for i in range(len(points)):
            if points[i][1] == 0 and any(v > 0 for _, v in points[i + 1 :]):
                start_idx = i
    if start_idx is None:
        return None

    end = points[start_idx][0] + span
    return end if end > now else None


def snapshot_from_desktop_history(
    now: datetime,
    *,
    title: str,
    extra_usage: bool = False,
) -> ProviderSnapshot | None:
    """Percent-only log written by the Claude Desktop app while it runs."""
    path = find_plan_usage_history()
    if path is None:
        return None
    samples = _samples(_read_json(path))
    if not samples:
        return None

    last_ts, last_usage = samples[-1]
    age = now - last_ts
    stale = age > STALE_AFTER
    detail = "Claude Desktop log"
    if stale:
        hours = age.total_seconds() / 3600.0
        detail += f" · stale {hours:.0f}h" if hours >= 1 else f" · stale {age.seconds // 60}m"

    metrics: list[Metric] = []
    for key, log_key, label, span in WINDOWS:
        if last_usage.get(log_key) is None:
            continue
        try:
            pct = float(last_usage[log_key])
        except (TypeError, ValueError):
            continue
        cycle_end = None if stale else infer_window_end(samples, log_key, span, now)
        metrics.append(
            _pct_metric(
                key,
                label,
                pct,
                cycle_end=cycle_end,
                detail=detail + (" · reset est." if cycle_end else ""),
            )
        )
    if not metrics:
        return None

    message = "Claude Desktop log · resets estimated locally"
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
        raw={
            "source": "plan-usage-history",
            "path": str(path),
            "sampled_at": last_ts.isoformat(),
        },
    )


def claude_present_locally() -> bool:
    """True when this PC shows any Claude subscription signal at all."""
    return find_plan_usage_history() is not None or bool(claude_account_meta())


# --------------------------------------------------------------------------- #
# Provider
# --------------------------------------------------------------------------- #


class AnthropicProvider(Provider):
    id = "anthropic"
    title = "Claude"

    def fetch(self) -> ProviderSnapshot:
        now = utc_now()
        account = claude_account_meta()
        title = plan_title(account)

        snapshot = snapshot_from_desktop_history(
            now,
            title=title,
            extra_usage=bool(account.get("hasExtraUsageEnabled")),
        )
        if snapshot is not None:
            return snapshot

        return ProviderSnapshot(
            provider_id=self.id,
            title=title,
            ok=False,
            fetched_at=now,
            error=(
                "no Claude Desktop usage log on this PC "
                "(it is written while the Claude Desktop app runs)"
            ),
        )
