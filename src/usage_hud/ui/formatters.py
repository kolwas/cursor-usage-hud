"""Pure helpers for tray titles / severity (Windows + Linux)."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from usage_hud.cycle import infer_cycle_start
from usage_hud.models import Alert, AlertLevel, BurnProjection, Metric, ProviderSnapshot

# Compact tag for a metric on the chip — the full Metric.label (e.g.
# "Included plan") stays as-is everywhere else (flyout, tray tooltip); only
# the small always-visible chip needs it this short.
_CHIP_METRIC_TAG: dict[str, str] = {
    "included": "Incl",
    "api": "API",
    "auto": "Auto",
    "ondemand": "OnDemand",
    "five_hour": "5h",
    "seven_day": "7d",
    "seven_day_opus": "7d Opus",
    "primary_window": "Primary",
    "secondary_window": "Daily",
    "rolling": "5h",
    "weekly": "Weekly",
    "monthly": "Monthly",
}


def chip_metrics(snap: ProviderSnapshot) -> list[Metric]:
    """Every gauge worth a chip row: all of them, always, not just the first —
    each gets its own line, its own clock and its own prediction."""
    return [m for m in snap.metrics if m.resolved_percent() is not None]


def chip_metric_tag(metric: Metric) -> str:
    return _CHIP_METRIC_TAG.get(metric.key, metric.label)


def format_renewal_offset(days: float | None) -> str | None:
    """Signed offset vs renewal: −1d = exhaust a day before reset; +2d =
    trend lasts two days past it. Below a day this switches to h/m —
    rounding a 5h Claude window's real few-hour margin down to whole days
    always landed on the same uninformative "0d" no matter which way (or
    how far) it actually leaned.
    """
    if days is None:
        return None
    sign = "-" if days < 0 else "+"
    magnitude = abs(days)
    if magnitude >= 99:
        return f"{sign}99d+"
    if magnitude >= 1.0:
        return f"{sign}{int(round(magnitude)):d}d"
    if magnitude < 1.0 / 1440:  # under a minute — call it "at renewal"
        return "0d"
    seconds = magnitude * 86400.0
    hours, minutes = divmod(int(seconds // 60), 60)
    return f"{sign}{hours}h{minutes:02d}m" if hours else f"{sign}{minutes}m"


def format_reset_eta(cycle_end: datetime | None, now: datetime | None = None) -> str:
    """Time until a quota window rolls — "2h10m" for rolling windows, "3d" above a day."""
    if cycle_end is None:
        return ""
    now = now or datetime.now(timezone.utc)
    if cycle_end.tzinfo is None:
        cycle_end = cycle_end.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    seconds = (cycle_end - now).total_seconds()
    if seconds <= 0:
        return "now"
    if seconds >= 86400:
        # Countdown, so floor: "3d" means at least three full days left.
        return f"{int(seconds // 86400)}d"
    hours, minutes = divmod(int(seconds // 60), 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m"


def grouped_reset_etas(
    snap: ProviderSnapshot, metrics: list[Metric], now: datetime | None = None
) -> tuple[str, dict[str, str]]:
    """(shared, per_metric) countdowns for a set of gauges on one provider.

    Gauges on the same billing cycle (e.g. Cursor's Included/API/Auto) all
    reset at once — showing "resets in 25d" next to each one just repeats
    itself. Rolling windows (Claude's 5h/7d) genuinely differ. So: one shared
    countdown when every shown gauge agrees, otherwise one per metric.
    """
    now = now or snap.fetched_at
    per_metric = {m.key: format_reset_eta(m.cycle_end or snap.cycle_end, now) for m in metrics}
    values = list(per_metric.values())
    if values and values[0] and all(v == values[0] for v in values):
        return values[0], {}
    return "", per_metric


def format_days_duration(days: float | None) -> str:
    """Unsigned "6h"/"3d" duration — same h/d granularity as format_reset_eta,
    for a raw "exhausts in…" horizon that has no renewal date to compare to."""
    if days is None or days <= 0:
        return "0h"
    seconds = days * 86400.0
    if seconds >= 86400:
        return f"{int(seconds // 86400)}d"
    hours, minutes = divmod(int(seconds // 60), 60)
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def eta_severity(renewal_offset_days: float) -> str:
    """bad|warn|ok for a signed days-vs-renewal offset — shared by the text
    badge and the timeline chart's exhaustion-marker color, so both agree."""
    if renewal_offset_days < -1:
        return "bad"
    if renewal_offset_days <= 3:
        return "warn"
    return "ok"


def format_chip_eta(proj: BurnProjection | None) -> tuple[str, str] | None:
    """Chip badge: signed days vs renewal at current burn (+ after / − before).

    Returns (label, severity) where severity is bad|warn|ok|tentative. Early
    in a window the rate is noisy but still shown — marked "tentative" (a
    trailing "?", muted color) instead of withheld, so a prediction is always
    visible; only its certainty is communicated differently.

    A gauge whose window-end is unknown entirely (e.g. Claude's 5h before its
    first real reset is seen) has no renewal date to offset against — but if
    a burn rate exists, an unsigned "→6h" exhaustion horizon is shown instead
    of nothing, always tentative since it can't be checked against a reset.
    """
    if proj is None:
        return None
    if proj.renewal_offset_days is not None:
        label = format_renewal_offset(proj.renewal_offset_days)
        if label is None:
            return None
        if not proj.confident:
            return f"{label}?", "tentative"
        return label, eta_severity(proj.renewal_offset_days)
    if proj.days_to_exhaust is not None and proj.avg_daily > 0:
        return f"→{format_days_duration(proj.days_to_exhaust)}", "tentative"
    return None


def reset_fraction_remaining(
    snap: ProviderSnapshot, metric: Metric, now: datetime | None = None
) -> float | None:
    """Fraction of THIS gauge's window still left (1.0 = just opened, 0 = about
    to roll) — drives the pie-clock's wedge. Uses the same cycle_start
    inference as the burn-rate math (cycle.infer_cycle_start), so it works
    from the very first sample, not only once history has accumulated.
    """
    cycle_end = metric.cycle_end or snap.cycle_end
    if cycle_end is None:
        return None
    now = now or snap.fetched_at
    cycle_start = infer_cycle_start(
        cycle_end=cycle_end,
        cycle_start=metric.cycle_start or snap.cycle_start,
        percent_used=metric.resolved_percent(),
        now=now,
    )
    if cycle_start is None:
        return None
    total = (cycle_end - cycle_start).total_seconds()
    if total <= 0:
        return None
    remaining = (cycle_end - now).total_seconds()
    return max(0.0, min(1.0, remaining / total))


def primary_eta_projection(
    snapshots: list[ProviderSnapshot],
    projections: list[BurnProjection],
) -> dict[str, BurnProjection]:
    """Headline +/−d for every provider — first usable gauge (skip on-demand).

    Soft preference only when several gauges exist (Cursor included, Copilot premium).
    New providers automatically get ETA from their first metric with an offset.
    """
    by_key = {(p.provider_id, p.metric_key): p for p in projections}
    soft_prefer = {
        "cursor": ("included",),
        "copilot": ("premium", "chat", "completions"),
        "opencode-go": ("monthly", "weekly", "rolling"),
        "openai": ("primary_window", "secondary_window"),
        "anthropic": ("seven_day", "five_hour", "seven_day_opus"),
    }
    out: dict[str, BurnProjection] = {}
    for snap in snapshots:
        if not snap.ok:
            continue
        order = list(soft_prefer.get(snap.provider_id, ()))
        for metric in snap.metrics:
            if metric.key not in order:
                order.append(metric.key)
        chosen: BurnProjection | None = None
        for key in order:
            if key == "ondemand":
                continue
            proj = by_key.get((snap.provider_id, key))
            if proj and proj.renewal_offset_days is not None and proj.avg_daily > 0:
                chosen = proj
                break
        if chosen is not None:
            out[snap.provider_id] = chosen
    return out


def primary_renewal_offset(
    snapshots: list[ProviderSnapshot],
    projections: list[BurnProjection],
) -> dict[str, float]:
    """provider_id → renewal_offset_days for chip."""
    return {
        pid: proj.renewal_offset_days
        for pid, proj in primary_eta_projection(snapshots, projections).items()
        if proj.renewal_offset_days is not None
    }



def worst_percent(snapshots: list[ProviderSnapshot]) -> float | None:
    pcts: list[float] = []
    for snap in snapshots:
        if not snap.ok:
            continue
        for metric in snap.metrics:
            pct = metric.resolved_percent()
            if pct is not None:
                pcts.append(pct)
    return max(pcts) if pcts else None


def compact_title(snapshots: list[ProviderSnapshot], alerts: list[Alert]) -> str:
    bits: list[str] = []
    for snap in snapshots:
        tag = {
            "cursor": "Cur",
            "copilot": "Cop",
            "opencode-go": "Go",
            "openai": "OAI",
            "anthropic": "Cla",
            "github": "GH",
            "cloud": "Cld",
        }.get(snap.provider_id, snap.provider_id[:3].title())
        if not snap.ok:
            bits.append(f"{tag}:!")
            continue
        pct = snap.primary_percent()
        bits.append(f"{tag}:{pct:.0f}%" if pct is not None else tag)
    text = " · ".join(bits) if bits else "Usage HUD"
    if alerts and alerts[0].level in {AlertLevel.WARN, AlertLevel.CRITICAL}:
        text = f"! {text}"
    return text


def icon_severity(snapshots: list[ProviderSnapshot], alerts: list[Alert]) -> tuple[QColor, bool]:
    """(color, urgent) from real alerts only — not a raw max() over every gauge.

    A blanket "highest % anywhere" badge used to put e.g. Cursor's API-models
    70% on the icon even though nothing had actually crossed an alert
    threshold — alerts.py already applies the right threshold per metric type
    (95%/85%/70% for on-demand…), so the icon should follow its verdict, not
    recompute a cruder one of its own.
    """
    if any(a.level == AlertLevel.CRITICAL for a in alerts):
        return QColor("#ff5c5c"), True
    if any(a.level == AlertLevel.WARN for a in alerts):
        return QColor("#ffb020"), True
    if any(not s.ok for s in snapshots):
        return QColor("#ffb020"), True
    return QColor("#3dd68c"), False


def badge_icon(snapshots: list[ProviderSnapshot], alerts: list[Alert]) -> QIcon:
    """Plain colored icon: green/orange/red for status, a small "!" only when
    something has actually crossed an alert threshold — no raw percent number."""
    color, urgent = icon_severity(snapshots, alerts)

    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(color)
    painter.setPen(QColor(16, 20, 28))
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)
    if urgent:
        painter.setPen(QColor("#101418"))
        font = QFont()
        font.setStyleHint(QFont.StyleHint.SansSerif)
        font.setBold(True)
        font.setPointSize(28)
        painter.setFont(font)
        painter.drawText(pix.rect(), int(Qt.AlignmentFlag.AlignCenter), "!")
    painter.end()
    return QIcon(pix)
