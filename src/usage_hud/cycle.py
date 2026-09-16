"""Billing / quota window helpers shared by all providers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def prev_month_same_day(dt: datetime) -> datetime:
    """Monthly quota: start ≈ previous reset (same calendar day last month)."""
    dt = ensure_utc(dt)
    year, month = dt.year, dt.month - 1
    if month < 1:
        year, month = year - 1, 12
    for day in range(dt.day, 0, -1):
        try:
            return dt.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    return dt.replace(year=year, month=month, day=1)


def infer_cycle_start(
    *,
    cycle_end: datetime | None,
    cycle_start: datetime | None = None,
    percent_used: float | None = None,
    now: datetime | None = None,
) -> datetime | None:
    """Fill missing cycle_start for any provider.

    Order:
    1. explicit cycle_start
    2. from % used + time-to-reset (rolling windows)
    3. previous month before cycle_end (monthly plans)
    """
    if cycle_start is not None:
        return ensure_utc(cycle_start)
    if cycle_end is None:
        return None
    end = ensure_utc(cycle_end)
    now = ensure_utc(now or datetime.now(timezone.utc))
    days_left = max(0.0, (end - now).total_seconds() / 86400.0)
    pct = percent_used
    if pct is not None and 0.0 < pct < 100.0 and days_left > 1e-6:
        # time_used / time_left ≈ pct / (100-pct)
        days_in = days_left * pct / (100.0 - pct)
        if days_in > 0:
            return now - timedelta(days=days_in)
    # Monthly-style fallback.
    return prev_month_same_day(end)


def window_end_from_seconds(now: datetime, reset_after_seconds: float | int | None) -> datetime | None:
    if reset_after_seconds is None:
        return None
    try:
        secs = float(reset_after_seconds)
    except (TypeError, ValueError):
        return None
    if secs < 0:
        return None
    return ensure_utc(now) + timedelta(seconds=secs)
