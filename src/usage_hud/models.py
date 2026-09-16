"""Shared models for usage-hud providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AlertLevel(str, Enum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Metric:
    """One usage gauge."""

    key: str
    label: str
    used: float
    limit: float | None
    unit: str = ""  # "$", "%", "min", "req", ...
    remaining: float | None = None
    percent_used: float | None = None
    detail: str = ""
    # Optional per-metric quota window (rolling 5h / weekly / …).
    cycle_start: datetime | None = None
    cycle_end: datetime | None = None

    def resolved_percent(self) -> float | None:
        if self.percent_used is not None:
            return self.percent_used
        if self.limit is None or self.limit <= 0:
            return None
        return min(100.0, max(0.0, 100.0 * self.used / self.limit))

    def resolved_remaining(self) -> float | None:
        if self.remaining is not None:
            return self.remaining
        if self.limit is None:
            return None
        return max(0.0, self.limit - self.used)


@dataclass
class ProviderSnapshot:
    provider_id: str
    title: str
    ok: bool
    fetched_at: datetime
    metrics: list[Metric] = field(default_factory=list)
    cycle_start: datetime | None = None
    cycle_end: datetime | None = None
    message: str = ""
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def primary_percent(self) -> float | None:
        for metric in self.metrics:
            pct = metric.resolved_percent()
            if pct is not None:
                return pct
        return None


@dataclass(frozen=True)
class Alert:
    level: AlertLevel
    provider_id: str
    code: str
    title: str
    body: str


@dataclass
class BurnProjection:
    provider_id: str
    metric_key: str
    used_today: float
    avg_daily: float
    projected_cycle_end: float | None
    days_left: float | None
    will_exhaust: bool
    note: str = ""
    # Days until limit at current avg burn (None = unknown / idle).
    days_to_exhaust: float | None = None
    # days_to_exhaust − days until renewal: −1 = one day before reset.
    renewal_offset_days: float | None = None
    # Days since this window/cycle opened — with days_left, gives the mini
    # timeline chart its "now" position on the cycle_start..cycle_end axis.
    days_elapsed: float | None = None
