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
    # The reading is the last one a source logged, old enough that the real
    # value has probably moved on — shown as "last known", never fed to
    # alerts, predictions or history.
    stale: bool = False

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
    # False = too little of the window has elapsed to trust avg_daily yet;
    # the projection fields below are still populated (never hidden), just
    # to be rendered as a tentative/muted estimate rather than a verdict.
    confident: bool = True
    # True = today's usage is spiking well past the average pace — drives
    # both the CRITICAL "burning hot" alert and a skull marker on the
    # sparkline, so a sudden spike is flagged in both places at once.
    hot: bool = False
    # True = a short-window (~45 min) spike far above the metric's own usual
    # pace — distinct from `hot` (a whole-day comparison): this catches a
    # burst happening right now even early in the day, when `hot`'s
    # used_today-vs-avg_daily comparison wouldn't yet have enough of the day
    # behind it to trip. Widens the timeline chart so it stands out.
    rocketing: bool = False

    # A spike only matters if, at its pace, the gauge would use up (nearly)
    # all it has left before it resets: days_to_exhaust within this multiple
    # of the time left. 1.25 = the burst alone would eat about 80% of what
    # remains. Unit-agnostic (works for %, $, requests alike).
    SPIKE_THREAT_RATIO = 1.25

    @property
    def is_alarming(self) -> bool:
        """Worth the chip's alarm treatment (alert chart, tinted row): a
        confirmed risk of running out before the reset, or a pace spike that
        is actually heading for the cap — not a spike on a gauge that still
        has hours to spare."""
        if self.will_exhaust and self.confident:
            return True
        if not self.rocketing:
            return False
        if self.days_to_exhaust is None or not self.days_left:
            return True  # cannot judge the margin — keep the warning
        return self.days_to_exhaust <= self.days_left * self.SPIKE_THREAT_RATIO
