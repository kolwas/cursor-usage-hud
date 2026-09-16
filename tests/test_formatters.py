from datetime import datetime, timedelta, timezone

from usage_hud.models import Alert, AlertLevel, BurnProjection, Metric, ProviderSnapshot, utc_now
from usage_hud.ui.formatters import (
    chip_metric_tag,
    chip_metrics,
    eta_severity,
    format_chip_eta,
    format_days_duration,
    format_reset_eta,
    grouped_reset_etas,
    icon_severity,
    reset_fraction_remaining,
)

NOW = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)


def test_rolling_window_shows_hours_and_minutes():
    assert format_reset_eta(NOW + timedelta(hours=2, minutes=10), NOW) == "2h10m"


def test_short_window_shows_minutes():
    assert format_reset_eta(NOW + timedelta(minutes=8), NOW) == "8m"


def test_long_window_shows_days():
    assert format_reset_eta(NOW + timedelta(days=3, hours=2), NOW) == "3d"


def test_days_are_floored_not_rounded_up():
    """A countdown must not claim 4d when 3 d 20 h remain."""
    assert format_reset_eta(NOW + timedelta(days=3, hours=20), NOW) == "3d"
    assert format_reset_eta(NOW + timedelta(hours=23, minutes=59), NOW) == "23h59m"


def test_unknown_or_past_window():
    assert format_reset_eta(None, NOW) == ""
    assert format_reset_eta(NOW - timedelta(minutes=1), NOW) == "now"


def _snap(provider_id: str, *metrics: Metric) -> ProviderSnapshot:
    return ProviderSnapshot(
        provider_id=provider_id, title=provider_id, ok=True, fetched_at=utc_now(), metrics=list(metrics)
    )


def test_claude_chip_shows_both_short_and_long_term():
    """The small chip must carry 5h and 7d together, not just one of them."""
    snap = _snap(
        "anthropic",
        Metric(key="five_hour", label="5h", used=8, limit=100, unit="%", percent_used=8),
        Metric(key="seven_day", label="7d", used=2, limit=100, unit="%", percent_used=2),
    )
    metrics = chip_metrics(snap)
    assert [m.key for m in metrics] == ["five_hour", "seven_day"]


def test_claude_chip_falls_back_when_a_window_is_missing():
    snap = _snap(
        "anthropic",
        Metric(key="seven_day", label="7d", used=2, limit=100, unit="%", percent_used=2),
    )
    assert [m.key for m in chip_metrics(snap)] == ["seven_day"]


def test_chip_shows_every_gauge_with_a_resolvable_percent():
    """Every gauge, always — Included alone used to hide API, the one that
    actually risks an overrun; On-demand with no percent yet is skipped."""
    snap = _snap(
        "cursor",
        Metric(key="included", label="Included plan", used=11, limit=100, unit="%", percent_used=11),
        Metric(key="api", label="API models", used=70, limit=100, unit="%", percent_used=70),
        Metric(key="auto", label="Auto models", used=5, limit=100, unit="%", percent_used=5),
        Metric(key="ondemand", label="On-demand spend", used=0, limit=None, unit="$", percent_used=None),
    )
    assert [m.key for m in chip_metrics(snap)] == ["included", "api", "auto"]


def test_other_providers_keep_a_single_chip_gauge():
    snap = _snap(
        "copilot",
        Metric(key="premium", label="Premium requests", used=1, limit=100, unit="%", percent_used=1),
    )
    assert [m.key for m in chip_metrics(snap)] == ["premium"]


def test_chip_metric_tag_is_short_for_known_keys_and_falls_back_to_the_label():
    assert chip_metric_tag(Metric(key="included", label="Included plan", used=0, limit=100, unit="%")) == "Incl"
    assert chip_metric_tag(Metric(key="api", label="API models", used=0, limit=100, unit="%")) == "API"
    assert chip_metric_tag(Metric(key="seven_day", label="7d", used=0, limit=100, unit="%")) == "7d"
    assert chip_metric_tag(Metric(key="premium", label="Premium requests", used=0, limit=100, unit="%")) == "Premium requests"


def test_icon_is_only_urgent_when_a_real_alert_fired():
    """A raw 70% on one metric with no crossed threshold must stay the plain/ok icon —
    this is exactly the Cursor 'API models 70%' case that used to force the badge red/orange."""
    snap = _snap(
        "cursor",
        Metric(key="api", label="API models", used=70, limit=100, unit="%", percent_used=70),
    )
    color, urgent = icon_severity([snap], alerts=[])
    assert urgent is False
    assert color.name() == "#3dd68c"


def test_icon_turns_urgent_on_a_warn_alert():
    alert = Alert(level=AlertLevel.WARN, provider_id="cursor", code="api_high", title="t", body="b")
    color, urgent = icon_severity([], alerts=[alert])
    assert urgent is True
    assert color.name() == "#ffb020"


def test_icon_turns_urgent_on_a_critical_alert():
    alert = Alert(level=AlertLevel.CRITICAL, provider_id="cursor", code="api_critical", title="t", body="b")
    color, urgent = icon_severity([], alerts=[alert])
    assert urgent is True
    assert color.name() == "#ff5c5c"


def test_icon_turns_urgent_when_a_provider_errors_even_without_an_alert_object():
    snap = ProviderSnapshot(provider_id="cursor", title="Cursor", ok=False, fetched_at=utc_now(), error="boom")
    color, urgent = icon_severity([snap], alerts=[])
    assert urgent is True
    assert color.name() == "#ffb020"


def test_shared_cycle_gets_one_reset_countdown_not_one_per_gauge():
    """Cursor's Included/API/Auto reset together — repeating '25d' three times
    is noise, not clarity."""
    cycle_end = NOW + timedelta(days=25)
    snap = ProviderSnapshot(
        provider_id="cursor",
        title="Cursor",
        ok=True,
        fetched_at=NOW,
        cycle_end=cycle_end,
        metrics=[
            Metric(key="included", label="Included plan", used=11, limit=100, unit="%", percent_used=11),
            Metric(key="api", label="API models", used=70, limit=100, unit="%", percent_used=70),
        ],
    )
    shared, per_metric = grouped_reset_etas(snap, snap.metrics, NOW)
    assert shared == "25d"
    assert per_metric == {}


def test_rolling_windows_each_keep_their_own_countdown():
    """Claude's 5h and 7d genuinely reset at different times — must not collapse."""
    snap = ProviderSnapshot(
        provider_id="anthropic",
        title="Claude",
        ok=True,
        fetched_at=NOW,
        metrics=[
            Metric(
                key="five_hour", label="5h", used=8, limit=100, unit="%", percent_used=8,
                cycle_end=NOW + timedelta(hours=3, minutes=14),
            ),
            Metric(
                key="seven_day", label="7d", used=2, limit=100, unit="%", percent_used=2,
                cycle_end=NOW + timedelta(days=6),
            ),
        ],
    )
    shared, per_metric = grouped_reset_etas(snap, snap.metrics, NOW)
    assert shared == ""
    assert per_metric == {"five_hour": "3h14m", "seven_day": "6d"}


def test_eta_severity_thresholds():
    assert eta_severity(-5) == "bad"
    assert eta_severity(-1.01) == "bad"
    assert eta_severity(-1) == "warn"
    assert eta_severity(0) == "warn"
    assert eta_severity(3) == "warn"
    assert eta_severity(3.01) == "ok"
    assert eta_severity(40) == "ok"


def test_reset_fraction_remaining_for_a_window_with_a_known_start():
    """3h14m left of a 5h window is roughly 0.65 remaining."""
    cycle_end = NOW + timedelta(hours=3, minutes=14)
    cycle_start = cycle_end - timedelta(hours=5)
    snap = ProviderSnapshot(
        provider_id="anthropic", title="Claude", ok=True, fetched_at=NOW,
        cycle_start=cycle_start,
    )
    metric = Metric(
        key="five_hour", label="5h", used=35, limit=100, unit="%", percent_used=35,
        cycle_end=cycle_end,
    )
    frac = reset_fraction_remaining(snap, metric, NOW)
    assert frac is not None
    assert 0.6 < frac < 0.7


def test_reset_fraction_remaining_is_none_without_a_cycle_end():
    snap = ProviderSnapshot(provider_id="cursor", title="Cursor", ok=True, fetched_at=NOW)
    metric = Metric(key="included", label="Included", used=10, limit=100, unit="%", percent_used=10)
    assert reset_fraction_remaining(snap, metric, NOW) is None


def test_reset_fraction_remaining_is_clamped_to_0_1():
    # A window that should already have rolled (now past cycle_end) must not
    # report a negative or >1 fraction.
    cycle_end = NOW - timedelta(hours=1)
    snap = ProviderSnapshot(
        provider_id="anthropic", title="Claude", ok=True, fetched_at=NOW,
        cycle_start=cycle_end - timedelta(hours=5),
    )
    metric = Metric(
        key="five_hour", label="5h", used=99, limit=100, unit="%", percent_used=99,
        cycle_end=cycle_end,
    )
    frac = reset_fraction_remaining(snap, metric, NOW)
    assert frac is None or 0.0 <= frac <= 1.0


def _proj(**overrides) -> BurnProjection:
    base = dict(
        provider_id="anthropic",
        metric_key="seven_day",
        used_today=0.0,
        avg_daily=5.0,
        projected_cycle_end=None,
        days_left=6.0,
        will_exhaust=False,
        renewal_offset_days=-2.0,
        confident=True,
    )
    base.update(overrides)
    return BurnProjection(**base)


def test_confident_prediction_keeps_its_real_severity():
    label, sev = format_chip_eta(_proj(confident=True))
    assert label == "-2d"
    assert sev == "bad"


def test_unconfident_prediction_is_still_shown_but_marked_tentative():
    """A prediction is never withheld for being early — it is shown with a
    '?' and a neutral severity instead of the real (possibly alarming) one."""
    label, sev = format_chip_eta(_proj(confident=False))
    assert label == "-2d?"
    assert sev == "tentative"


def test_no_renewal_offset_still_means_no_badge():
    assert format_chip_eta(_proj(renewal_offset_days=None)) is None
    assert format_chip_eta(None) is None


def test_unknown_reset_time_still_shows_a_raw_exhaustion_horizon():
    """Claude's 5h before its first real reset is seen: no cycle_end, so no
    renewal_offset_days — but a burn rate exists, so an unsigned '→Nd' is
    shown instead of nothing, always as a tentative estimate."""
    label, sev = format_chip_eta(
        _proj(renewal_offset_days=None, days_to_exhaust=2.5, avg_daily=6.9)
    )
    assert label == "→2d"
    assert sev == "tentative"


def test_no_burn_rate_at_all_still_means_no_badge():
    assert format_chip_eta(_proj(renewal_offset_days=None, days_to_exhaust=None)) is None
    assert format_chip_eta(_proj(renewal_offset_days=None, days_to_exhaust=2.0, avg_daily=0.0)) is None


def test_format_days_duration_matches_reset_eta_granularity():
    assert format_days_duration(0) == "0h"
    assert format_days_duration(None) == "0h"
    assert format_days_duration(0.5) == "12h00m"
    assert format_days_duration(3.2) == "3d"
