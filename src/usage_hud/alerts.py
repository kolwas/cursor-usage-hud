"""Alert rules for usage thresholds and burn rate."""

from __future__ import annotations

from usage_hud.config import Settings
from usage_hud.models import Alert, AlertLevel, BurnProjection, ProviderSnapshot


def evaluate_alerts(
    snapshots: list[ProviderSnapshot],
    projections: list[BurnProjection],
    settings: Settings,
) -> list[Alert]:
    alerts: list[Alert] = []

    for snap in snapshots:
        if not snap.ok:
            alerts.append(
                Alert(
                    level=AlertLevel.WARN,
                    provider_id=snap.provider_id,
                    code="provider_error",
                    title=f"{snap.title} offline",
                    body=snap.error or "fetch failed",
                )
            )
            continue

        for metric in snap.metrics:
            pct = metric.resolved_percent()
            if pct is None:
                continue
            threshold = settings.alert_included_pct
            if metric.key == "ondemand":
                threshold = settings.alert_ondemand_pct
            if pct >= 95:
                alerts.append(
                    Alert(
                        level=AlertLevel.CRITICAL,
                        provider_id=snap.provider_id,
                        code=f"{metric.key}_critical",
                        title=f"{snap.title}: {metric.label} {pct:.0f}%",
                        body=f"Used {metric.used:g}{metric.unit} of {metric.limit:g}{metric.unit}",
                    )
                )
            elif pct >= threshold:
                alerts.append(
                    Alert(
                        level=AlertLevel.WARN,
                        provider_id=snap.provider_id,
                        code=f"{metric.key}_high",
                        title=f"{snap.title}: {metric.label} {pct:.0f}%",
                        body="Approaching limit — ease off premium models / CI.",
                    )
                )

    by_key = {(p.provider_id, p.metric_key): p for p in projections}
    for snap in snapshots:
        for metric in snap.metrics:
            proj = by_key.get((snap.provider_id, metric.key))
            if not proj:
                continue
            if "burning hot" in proj.note:
                alerts.append(
                    Alert(
                        level=AlertLevel.CRITICAL,
                        provider_id=snap.provider_id,
                        code=f"{metric.key}_hot_day",
                        title=f"{snap.title}: heavy burn today",
                        body=(
                            f"{metric.label}: +{proj.used_today:.2f}{metric.unit} today "
                            f"vs avg {proj.avg_daily:.2f}{metric.unit}/day"
                        ),
                    )
                )
            elif proj.will_exhaust:
                days = f"{proj.days_left:.1f}d" if proj.days_left is not None else "?"
                alerts.append(
                    Alert(
                        level=AlertLevel.WARN,
                        provider_id=snap.provider_id,
                        code=f"{metric.key}_projected",
                        title=f"{snap.title}: projected overrun",
                        body=(
                            f"{metric.label} may hit limit before reset ({days} left)"
                        ),
                    )
                )

    # De-dupe by code+provider, keep highest severity.
    rank = {AlertLevel.INFO: 0, AlertLevel.WARN: 1, AlertLevel.CRITICAL: 2}
    best: dict[tuple[str, str], Alert] = {}
    for alert in alerts:
        key = (alert.provider_id, alert.code)
        prev = best.get(key)
        if prev is None or rank[alert.level] > rank[prev.level]:
            best[key] = alert
    return sorted(best.values(), key=lambda a: (-rank[a.level], a.provider_id, a.code))
