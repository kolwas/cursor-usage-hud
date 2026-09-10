from usage_hud.alerts import evaluate_alerts
from usage_hud.config import Settings
from usage_hud.models import AlertLevel, BurnProjection, Metric, ProviderSnapshot, utc_now


def test_ondemand_critical_alert():
    snap = ProviderSnapshot(
        provider_id="cursor",
        title="Cursor",
        ok=True,
        fetched_at=utc_now(),
        metrics=[
            Metric(
                key="ondemand",
                label="On-demand",
                used=28.0,
                limit=30.0,
                unit="$",
                percent_used=93.3,
            )
        ],
    )
    alerts = evaluate_alerts([snap], [], Settings())
    assert any(a.level == AlertLevel.WARN for a in alerts)


def test_hot_day_projection_alert():
    snap = ProviderSnapshot(
        provider_id="cursor",
        title="Cursor",
        ok=True,
        fetched_at=utc_now(),
        metrics=[Metric(key="included", label="Included", used=10, limit=100, unit="")],
    )
    proj = BurnProjection(
        provider_id="cursor",
        metric_key="included",
        used_today=40,
        avg_daily=5,
        projected_cycle_end=None,
        days_left=10,
        will_exhaust=False,
        note="today burning hot",
    )
    alerts = evaluate_alerts([snap], [proj], Settings())
    assert any(a.code == "included_hot_day" for a in alerts)
