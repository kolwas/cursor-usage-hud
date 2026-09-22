"""Local snapshot history for burn-rate projections (all providers)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from usage_hud.cycle import infer_cycle_start
from usage_hud.models import BurnProjection, Metric, ProviderSnapshot

# Ignore noisy first/last-sample rates shorter than this.
_MIN_ELAPSED_DAYS = 0.25  # 6 hours
_SKIP_KEYS = frozenset({"ondemand"})
# ~8 days of history at the default 180s refresh — enough to cover a whole
# Claude 7d weekly window on the sparkline, not just the burn-rate math.
_MAX_SAMPLES = 8000

# A window near its own reset gives an unstable rate: 2% used in the first
# hour of a 7-day window extrapolates to "14%/day", which looks like an
# overrun even though it is just noise from a tiny denominator. Require a
# slice of the window's OWN length to have elapsed — scaled to the window,
# so a 5h window and a 30-day one each get a sane, proportional warm-up —
# before trusting the rate enough to project an exhaustion date from it.
_WARMUP_FRACTION = 0.10
_WARMUP_FLOOR_DAYS = 1.0 / 24.0  # 1 hour

# "Rocketing": a short-window burst, independent of `hot`'s whole-day
# comparison — catches a burst happening right now even a few minutes after
# midnight, when there is barely any "today" for `hot` to compare against.
_ROCKET_WINDOW_MINUTES = 45
_ROCKET_MIN_COVERAGE = 0.4  # need to have actually observed this much of the window
_ROCKET_MIN_DELTA = 8.0  # percentage points — ignore noise on a near-flat gauge
# Used only when there's no older history to compare the recent pace to —
# an absolute "this alone is fast" floor, in points/hour.
_ROCKET_ABSOLUTE_FLOOR = 15.0


def _recent_spike(
    series: list[dict[str, Any]],
    metric_key: str,
    now: datetime,
    multiplier: float,
    *,
    window_minutes: int = _ROCKET_WINDOW_MINUTES,
) -> bool:
    """Is this metric's pace over the last ~window_minutes far above its OWN
    recent-past pace — a burst happening right now?

    Deliberately does NOT compare against avg_daily: for a short rolling
    window (Claude's 5h) avg_daily is itself computed from a tiny elapsed
    slice, so it is already inflated by the very burst this is supposed to
    catch — comparing a spike to a baseline the spike has already poisoned
    can never trip. Instead this compares the last window_minutes against
    the pace over the OLDER history in the same series (before that
    window), a baseline the recent burst hasn't touched.
    """
    cutoff = now - timedelta(minutes=window_minutes)
    points = sorted(
        (_parse_ts(s["ts"]), lvl)
        for s in series
        if (lvl := _metric_level(s, metric_key)) is not None
    )
    recent = [(t, v) for t, v in points if t >= cutoff]
    older = [(t, v) for t, v in points if t < cutoff]
    if len(recent) < 2:
        return False

    t0, v0 = recent[0]
    t1, v1 = recent[-1]
    elapsed_hours = (t1 - t0).total_seconds() / 3600.0
    if elapsed_hours < (window_minutes / 60.0) * _ROCKET_MIN_COVERAGE:
        return False  # two samples seconds apart inside the window isn't a trend

    delta = max(0.0, v1 - v0)
    if delta < _ROCKET_MIN_DELTA:
        return False
    recent_rate_per_hour = delta / max(elapsed_hours, 1e-6)

    if len(older) >= 2:
        ot0, ov0 = older[0]
        ot1, ov1 = older[-1]
        older_hours = max((ot1 - ot0).total_seconds() / 3600.0, 1e-6)
        baseline_per_hour = max(0.0, ov1 - ov0) / older_hours
        if baseline_per_hour > 0.5:
            return recent_rate_per_hour >= multiplier * baseline_per_hour

    # No usable older pace (flat, absent, or negligible) — fall back to an
    # absolute "this alone is fast" floor instead of comparing to nothing.
    return recent_rate_per_hour >= _ROCKET_ABSOLUTE_FLOOR


def _fmt_offset(days: float) -> str:
    """Signed day offset vs renewal: −1d = one day before reset."""
    rounded = int(round(days))
    if rounded == 0:
        return "0d"
    if rounded > 99:
        return "+99d+"
    if rounded < -99:
        return "-99d+"
    return f"{rounded:+d}d"


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _cycle_end_key(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    try:
        return _parse_ts(str(value)).astimezone(timezone.utc).isoformat()
    except ValueError:
        return str(value)


def _metric_level(sample: dict[str, Any], key: str) -> float | None:
    """Prefer percent_used (plan %) over raw used (pool counters)."""
    for m in sample.get("metrics") or []:
        if m.get("key") != key:
            continue
        if m.get("percent_used") is not None:
            return float(m["percent_used"])
        if m.get("used") is not None:
            return float(m["used"])
    return None


def _metric_window(
    snap: ProviderSnapshot,
    metric: Metric,
    now: datetime,
) -> tuple[datetime | None, datetime | None, float | None, bool]:
    """Resolve cycle_start/end/days_left for one gauge (metric overrides snap).

    The 4th value says whether cycle_start is REAL (Cursor's actual
    billingCycleStart) or had to be back-inferred from percent-used + time-
    to-reset (every provider that, like Claude, never reports a start at
    all). That distinction matters upstream: a "cycle pace" built on an
    inferred start reconstructs the very constant-rate assumption that
    produced it, which is not an independent signal.
    """
    cycle_end = metric.cycle_end or snap.cycle_end
    explicit_start = metric.cycle_start or snap.cycle_start
    pct = metric.resolved_percent()
    cycle_start = infer_cycle_start(
        cycle_end=cycle_end,
        cycle_start=explicit_start,
        percent_used=pct,
        now=now,
    )
    days_left = None
    if cycle_end is not None:
        days_left = max(
            0.0,
            (cycle_end.astimezone(timezone.utc) - now).total_seconds() / 86400.0,
        )
    return cycle_start, cycle_end, days_left, explicit_start is not None


class HistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self._write({"samples": []})

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"samples": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def record(self, snapshots: list[ProviderSnapshot]) -> None:
        data = self._read()
        samples: list[dict[str, Any]] = data.setdefault("samples", [])
        for snap in snapshots:
            if not snap.ok:
                continue
            entry = {
                "ts": snap.fetched_at.astimezone(timezone.utc).isoformat(),
                "provider_id": snap.provider_id,
                "cycle_start": snap.cycle_start.isoformat() if snap.cycle_start else None,
                "cycle_end": snap.cycle_end.isoformat() if snap.cycle_end else None,
                "metrics": [
                    {
                        "key": m.key,
                        "used": m.used,
                        "limit": m.limit,
                        "percent_used": m.resolved_percent(),
                        "unit": m.unit,
                        "cycle_end": m.cycle_end.isoformat() if m.cycle_end else None,
                    }
                    for m in snap.metrics
                ],
            }
            samples.append(entry)
        if len(samples) > _MAX_SAMPLES:
            data["samples"] = samples[-_MAX_SAMPLES:]
        self._write(data)

    def series(
        self,
        provider_id: str,
        metric_key: str,
        *,
        since: datetime | None = None,
        max_points: int | None = None,
    ) -> list[tuple[datetime, float]]:
        """(timestamp, percent_used) history for one gauge, oldest first —
        the real, observed trend a sparkline draws, as opposed to the
        synthetic cycle-position math the pie/timeline charts use.

        ``max_points`` evenly subsamples a long run down to a chart-sized
        count (raw 180s-interval samples over days would otherwise vastly
        outnumber the pixels available to draw them) while always keeping
        the first and last point, so the plotted range never shrinks.
        """
        out: list[tuple[datetime, float]] = []
        for s in self._read().get("samples") or []:
            if s.get("provider_id") != provider_id:
                continue
            pct = _metric_level(s, metric_key)
            if pct is None:
                continue
            ts = _parse_ts(s["ts"])
            if since is not None and ts < since:
                continue
            out.append((ts, pct))
        if max_points is not None and len(out) > max_points > 1:
            step = (len(out) - 1) / (max_points - 1)
            idxs = sorted({round(i * step) for i in range(max_points)})
            out = [out[i] for i in idxs]
        return out

    def projections(
        self,
        snapshots: list[ProviderSnapshot],
        burn_multiplier: float,
    ) -> list[BurnProjection]:
        data = self._read()
        samples = data.get("samples") or []
        out: list[BurnProjection] = []
        now = datetime.now(timezone.utc)

        for snap in snapshots:
            if not snap.ok or not snap.metrics:
                continue
            for metric in snap.metrics:
                if metric.key in _SKIP_KEYS:
                    continue
                if metric.limit is None and metric.resolved_percent() is None:
                    continue

                pct = metric.resolved_percent()
                if pct is not None:
                    level_now = pct
                    remaining = max(0.0, 100.0 - pct)
                    unit_is_pct = True
                else:
                    level_now = metric.used
                    rem = metric.resolved_remaining()
                    remaining = rem if rem is not None else 0.0
                    unit_is_pct = False

                cycle_start, cycle_end, days_left, cycle_start_is_real = _metric_window(
                    snap, metric, now
                )

                elapsed_since_start: float | None = None
                if cycle_start is not None:
                    elapsed_since_start = max(
                        (now - cycle_start.astimezone(timezone.utc)).total_seconds()
                        / 86400.0,
                        0.0,
                    )

                avg_daily = 0.0
                note_source = ""
                if elapsed_since_start is not None and level_now > 0:
                    days_in = max(elapsed_since_start, _WARMUP_FLOOR_DAYS)
                    avg_daily = level_now / days_in
                    note_source = "cycle pace"

                # Confident enough to forecast an exhaustion date only once a
                # meaningful slice of THIS window has actually been observed.
                confident = True
                if elapsed_since_start is not None and days_left is not None:
                    window_days = elapsed_since_start + days_left
                    warmup = max(_WARMUP_FLOOR_DAYS, window_days * _WARMUP_FRACTION)
                    confident = elapsed_since_start >= warmup

                cycle_key = _cycle_end_key(cycle_end or snap.cycle_end)
                series = [
                    s
                    for s in samples
                    if s.get("provider_id") == snap.provider_id
                    and _metric_level(s, metric.key) is not None
                ]
                if cycle_key is not None:
                    same_cycle = [
                        s
                        for s in series
                        if _cycle_end_key(s.get("cycle_end")) == cycle_key
                    ]
                    if len(same_cycle) >= 2:
                        series = same_cycle

                used_today = 0.0
                if len(series) >= 2:
                    first, last = series[0], series[-1]
                    t0, t1 = _parse_ts(first["ts"]), _parse_ts(last["ts"])
                    elapsed_days = max((t1 - t0).total_seconds() / 86400.0, 1e-6)
                    v0 = _metric_level(first, metric.key) or 0.0
                    v1 = _metric_level(last, metric.key) or 0.0
                    delta = max(0.0, v1 - v0)
                    if elapsed_days >= _MIN_ELAPSED_DAYS:
                        hist_avg = delta / elapsed_days
                        # A cycle-pace built on a back-inferred start (no
                        # provider gives Claude a real one) algebraically
                        # reconstructs the constant-rate assumption that
                        # produced that start — it can never disagree with
                        # "exactly on pace", which is why the badge always
                        # read "0d". Real observed history always overrides
                        # it once available; a REAL cycle_start (Cursor's
                        # actual billing date) is an independent number, so
                        # there only the larger (more cautious) of the two wins.
                        if not cycle_start_is_real or hist_avg > avg_daily:
                            avg_daily = hist_avg
                            note_source = "history"

                    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    today_samples = [s for s in series if _parse_ts(s["ts"]) >= day_start]
                    if today_samples:
                        a = _metric_level(today_samples[0], metric.key) or 0.0
                        b = _metric_level(today_samples[-1], metric.key) or 0.0
                        used_today = max(0.0, b - a)

                if avg_daily <= 0 and days_left is None:
                    out.append(
                        BurnProjection(
                            provider_id=snap.provider_id,
                            metric_key=metric.key,
                            used_today=used_today,
                            avg_daily=0.0,
                            projected_cycle_end=None,
                            days_left=None,
                            will_exhaust=False,
                            note="collecting history…",
                        )
                    )
                    continue

                # Predictions are ALWAYS computed and returned now — early on
                # they are noisier, which is exactly what `confident` is for:
                # callers render an unconfident one as a tentative/muted
                # estimate instead of a verdict, rather than showing nothing.
                days_to_exhaust: float | None = None
                renewal_offset: float | None = None
                projected = None
                will_exhaust = False

                if remaining <= 0:
                    days_to_exhaust = 0.0
                elif avg_daily > 1e-9:
                    days_to_exhaust = remaining / avg_daily

                if days_left is not None and avg_daily > 0:
                    if unit_is_pct:
                        projected = level_now + avg_daily * days_left
                        will_exhaust = projected >= 100.0 - 1e-6
                    elif metric.limit is not None:
                        projected = metric.used + avg_daily * days_left
                        will_exhaust = projected >= metric.limit

                if days_to_exhaust is not None and days_left is not None:
                    renewal_offset = days_to_exhaust - days_left

                hot = avg_daily > 0 and used_today >= burn_multiplier * max(avg_daily, 1e-9)
                rocketing = _recent_spike(series, metric.key, now, burn_multiplier)
                rate_label = f"~{avg_daily:.2f}%/day" if unit_is_pct else f"~{avg_daily:.1f}/day"
                confidence_note = "" if confident else " (early estimate)"

                note = ""
                if hot:
                    note = "today burning hot"
                elif rocketing:
                    note = f"spiking right now (~{_ROCKET_WINDOW_MINUTES}m)"
                elif will_exhaust and renewal_offset is not None:
                    note = f"exhaust {_fmt_offset(renewal_offset)} vs renewal{confidence_note}"
                elif will_exhaust:
                    note = f"on track to exhaust before reset{confidence_note}"
                elif renewal_offset is not None and avg_daily > 0:
                    note = f"ETA {_fmt_offset(renewal_offset)} vs renewal{confidence_note} · {rate_label}"
                    if note_source:
                        note += f" ({note_source})"
                elif avg_daily > 0:
                    note = rate_label

                out.append(
                    BurnProjection(
                        provider_id=snap.provider_id,
                        metric_key=metric.key,
                        used_today=used_today,
                        avg_daily=avg_daily,
                        projected_cycle_end=projected,
                        days_left=days_left,
                        will_exhaust=will_exhaust,
                        note=note,
                        days_to_exhaust=days_to_exhaust,
                        renewal_offset_days=renewal_offset,
                        days_elapsed=elapsed_since_start,
                        confident=confident,
                        hot=hot,
                        rocketing=rocketing,
                    )
                )
        return out
