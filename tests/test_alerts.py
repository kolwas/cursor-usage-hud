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
        hot=True,
    )
    alerts = evaluate_alerts([snap], [proj], Settings())
    assert any(a.code == "included_hot_day" for a in alerts)


def test_rocketing_alert():
    """A short-window spike must fire its own CRITICAL alert, not just widen
    the chart — this is the actual notification the user relies on."""
    snap = ProviderSnapshot(
        provider_id="anthropic",
        title="Claude Max 5x",
        ok=True,
        fetched_at=utc_now(),
        metrics=[
            Metric(key="five_hour", label="5h", used=24, limit=100, unit="%", percent_used=24)
        ],
    )
    proj = BurnProjection(
        provider_id="anthropic",
        metric_key="five_hour",
        used_today=19,
        avg_daily=469,
        projected_cycle_end=None,
        days_left=None,
        will_exhaust=False,
        note="spiking right now (~45m)",
        rocketing=True,
    )
    alerts = evaluate_alerts([snap], [proj], Settings())
    match = next((a for a in alerts if a.code == "five_hour_rocketing"), None)
    assert match is not None
    assert match.level == AlertLevel.CRITICAL
    assert "24%" in match.body


def test_hot_takes_priority_over_rocketing_for_the_same_gauge():
    """Both flags can be true at once — one alert per gauge, not two."""
    snap = ProviderSnapshot(
        provider_id="anthropic",
        title="Claude",
        ok=True,
        fetched_at=utc_now(),
        metrics=[Metric(key="five_hour", label="5h", used=24, limit=100, unit="%", percent_used=24)],
    )
    proj = BurnProjection(
        provider_id="anthropic",
        metric_key="five_hour",
        used_today=40,
        avg_daily=5,
        projected_cycle_end=None,
        days_left=None,
        will_exhaust=False,
        hot=True,
        rocketing=True,
    )
    alerts = evaluate_alerts([snap], [proj], Settings())
    codes = [a.code for a in alerts if a.provider_id == "anthropic"]
    assert "five_hour_hot_day" in codes
    assert "five_hour_rocketing" not in codes
