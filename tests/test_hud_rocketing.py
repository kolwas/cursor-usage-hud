"""Alarm states (rocketing spike, confirmed exhaustion risk) are colour
signals on the timeline chart — never a different size. Widening just the
alarming row used to put different-length bars inside one shared table
column (Qt sizes a column to its widest cell), which read as stray/uneven
fragments rather than something that stood out — reverted to a uniform
width, alarm communicated by colour alone.
"""

import pytest

pytest.importorskip("PySide6")

from datetime import timedelta  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

from usage_hud.models import BurnProjection, Metric, ProviderSnapshot, utc_now  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _snap_and_metric():
    now = utc_now()
    snap = ProviderSnapshot(
        provider_id="cursor",
        title="Cursor",
        ok=True,
        fetched_at=now,
        cycle_start=now - timedelta(days=5),
        cycle_end=now + timedelta(days=25),
    )
    metric = Metric(
        key="included", label="Included", used=25, limit=100, unit="%", percent_used=25,
    )
    return snap, metric


def _proj(**overrides) -> BurnProjection:
    base = dict(
        provider_id="cursor",
        metric_key="included",
        used_today=0.0,
        avg_daily=2.0,
        projected_cycle_end=None,
        days_left=25.0,
        will_exhaust=False,
        days_elapsed=5.0,
        days_to_exhaust=35.0,
        renewal_offset_days=10.0,
        confident=True,
        rocketing=False,
    )
    base.update(overrides)
    return BurnProjection(**base)


def _width(tag: str) -> str | None:
    import re

    m = re.search(r'width="(\d+)"', tag)
    return m.group(1) if m else None


def test_every_state_renders_the_same_width():
    from usage_hud.ui.hud import WeatherPanel

    snap, metric = _snap_and_metric()
    calm = WeatherPanel._timeline_chart(snap, metric, _proj())
    spiking = WeatherPanel._timeline_chart(snap, metric, _proj(rocketing=True))
    at_risk = WeatherPanel._timeline_chart(
        snap, metric, _proj(will_exhaust=True, confident=True)
    )

    widths = {_width(calm), _width(spiking), _width(at_risk)}
    assert len(widths) == 1
    assert None not in widths


def test_rocketing_is_a_distinct_colour_not_a_size_change():
    from usage_hud.ui.hud import WeatherPanel

    snap, metric = _snap_and_metric()
    calm = WeatherPanel._timeline_chart(snap, metric, _proj(rocketing=False))
    spiking = WeatherPanel._timeline_chart(snap, metric, _proj(rocketing=True))

    assert _width(calm) == _width(spiking)
    assert calm != spiking  # still visually distinct — via colour


def test_alarming_row_gets_a_whole_row_background_tint():
    """Colour on the tiny chart/ETA cells alone was too easy to miss at a
    glance (the original complaint about the Cursor 'api' gauge not standing
    out) — a confirmed at-risk or rocketing row must tint its whole <tr>,
    while a calm or merely-tentative one must not."""
    from usage_hud.ui.hud import WeatherPanel

    snap, metric = _snap_and_metric()
    snap.metrics.append(metric)

    def _chip_html_for(proj: BurnProjection) -> str:
        panel = WeatherPanel()
        panel._snapshots = [snap]
        panel._projections = [proj]
        try:
            return panel._chip_html()
        finally:
            panel.deleteLater()

    calm_html = _chip_html_for(_proj())
    rocketing_html = _chip_html_for(_proj(rocketing=True))
    at_risk_html = _chip_html_for(_proj(will_exhaust=True, confident=True))
    tentative_at_risk_html = _chip_html_for(_proj(will_exhaust=True, confident=False))

    assert WeatherPanel._CHIP_ALARM_BG not in calm_html
    assert WeatherPanel._CHIP_ALARM_BG in rocketing_html
    assert WeatherPanel._CHIP_ALARM_BG in at_risk_html
    # Not confirmed yet — must not tint the whole row before it earns it.
    assert WeatherPanel._CHIP_ALARM_BG not in tentative_at_risk_html


def test_alert_chart_appears_next_to_the_raven_only_when_something_is_hot(tmp_path):
    """Requested: a small chart next to the raven when a gauge's pace is
    genuinely alarming — visible (and widening the window for it, not
    covering anything) only then, hidden the rest of the time."""
    from usage_hud.history import HistoryStore
    from usage_hud.ui.hud import WeatherPanel

    snap, metric = _snap_and_metric()
    snap.metrics.append(metric)
    history = HistoryStore(tmp_path / "history.json")
    now = utc_now()
    history.record([snap])
    snap2 = ProviderSnapshot(
        provider_id="cursor", title="Cursor", ok=True, fetched_at=now + timedelta(minutes=5),
        metrics=[Metric(key="included", label="Included", used=30, limit=100, unit="%", percent_used=30)],
    )
    history.record([snap2])

    def _panel_for(proj: BurnProjection) -> WeatherPanel:
        panel = WeatherPanel(history=history)
        panel._snapshots = [snap]
        panel._projections = [proj]
        panel._render()
        return panel

    # isHidden() reflects the widget's own explicit show()/hide() call, not
    # whether the (never-shown-in-this-test) top-level panel itself is on
    # screen — isVisible() would be False either way here.
    calm = _panel_for(_proj())
    try:
        assert calm._alert_chart.isHidden() is True
    finally:
        calm.deleteLater()

    rocketing = _panel_for(_proj(rocketing=True))
    try:
        assert rocketing._alert_chart.isHidden() is False
        text = rocketing._alert_chart.text()
        # Requested: a caption saying which gauge this is and how far back
        # it goes — a lone picture with no label wasn't worth much.
        assert "Cur" in text
        assert "m</div>" in text or "h</div>" in text or "d</div>" in text
    finally:
        rocketing.deleteLater()


def test_span_caption_formats_by_magnitude():
    from usage_hud.ui.hud import WeatherPanel

    def _points(minutes_span: float) -> list:
        t0 = utc_now()
        t1 = t0 + timedelta(minutes=minutes_span)
        return [(t0, 1.0), (t1, 2.0)]

    assert WeatherPanel._span_caption(_points(38)) == "38m"
    assert WeatherPanel._span_caption(_points(135)) == "2h15m"
    assert WeatherPanel._span_caption(_points(120)) == "2h"
    assert WeatherPanel._span_caption(_points(60 * 50)) == "2d2h"
    assert WeatherPanel._span_caption([]) == ""


def test_hot_gauge_prefers_the_soonest_real_exhaustion_not_iteration_order():
    """Regression, live report: "Nie ma wykresu do cla 5h czemu?". Two
    alarming, non-rocketing gauges — Cursor API confirmed over budget in
    relative terms ("-12d" against a ~30-day cycle) and Claude 5h about to
    actually hit its cap within the hour ("-2h21m" against a 5h cycle).
    The 5h gauge is far more urgent in absolute time (days_to_exhaust ~0.03
    vs ~4.4) but was losing every time purely because Cursor was iterated
    first and neither counted as "rocketing" — the tie-break never
    reconsidered after the first pick. days_to_exhaust must decide it.
    """
    from usage_hud.ui.hud import WeatherPanel

    now = utc_now()
    cursor_snap = ProviderSnapshot(
        provider_id="cursor", title="Cursor", ok=True, fetched_at=now,
        cycle_start=now - timedelta(days=15), cycle_end=now + timedelta(days=16),
        metrics=[Metric(key="api", label="API", used=90, limit=100, unit="%", percent_used=90)],
    )
    claude_snap = ProviderSnapshot(
        provider_id="anthropic", title="Claude", ok=True, fetched_at=now,
        cycle_start=now - timedelta(hours=4), cycle_end=now + timedelta(minutes=8),
        metrics=[Metric(key="five_hour", label="5h", used=95, limit=100, unit="%", percent_used=95)],
    )
    cursor_proj = _proj(
        provider_id="cursor", metric_key="api", will_exhaust=True,
        days_to_exhaust=4.45, renewal_offset_days=-11.53,
    )
    claude_proj = _proj(
        provider_id="anthropic", metric_key="five_hour", will_exhaust=True,
        days_to_exhaust=0.035, renewal_offset_days=-0.098,
    )

    panel = WeatherPanel()
    # Cursor listed FIRST — the exact ordering that triggered the bug.
    panel._snapshots = [cursor_snap, claude_snap]
    panel._projections = [cursor_proj, claude_proj]
    try:
        gauges = panel._hot_gauges()
        assert gauges
        assert (gauges[0][0].provider_id, gauges[0][1].key) == ("anthropic", "five_hour")
        # Both are alarming — both belong in the cycle, not just the winner.
        assert len(gauges) == 2
    finally:
        panel.deleteLater()


def _two_hot_snapshots():
    """Two distinct, simultaneously-alarming gauges — the fixture the
    cycling tests below share."""
    now = utc_now()
    cursor_snap = ProviderSnapshot(
        provider_id="cursor", title="Cursor", ok=True, fetched_at=now,
        cycle_start=now - timedelta(days=15), cycle_end=now + timedelta(days=16),
        metrics=[Metric(key="api", label="API", used=90, limit=100, unit="%", percent_used=90)],
    )
    claude_snap = ProviderSnapshot(
        provider_id="anthropic", title="Claude", ok=True, fetched_at=now,
        cycle_start=now - timedelta(hours=4), cycle_end=now + timedelta(minutes=8),
        metrics=[Metric(key="five_hour", label="5h", used=95, limit=100, unit="%", percent_used=95)],
    )
    cursor_proj = _proj(
        provider_id="cursor", metric_key="api", will_exhaust=True,
        days_to_exhaust=4.45, renewal_offset_days=-11.53,
    )
    claude_proj = _proj(
        provider_id="anthropic", metric_key="five_hour", will_exhaust=True,
        days_to_exhaust=0.035, renewal_offset_days=-0.098,
    )
    return [cursor_snap, claude_snap], [cursor_proj, claude_proj]


def test_alert_cycle_rotates_through_every_alarming_gauge_and_wraps(tmp_path):
    """Requested: "Zagrozone powinny pokazywac" — more than one alarming
    gauge must actually get shown, not just the single worst one. Ticking
    the cycle must advance through all of them and wrap back to the start,
    and must nudge the raven (see _tick_raven_mark's jump mode) as the
    swap happens rather than silently changing the picture underneath it.

    Needs a real HistoryStore with actual samples: _render()'s "nothing to
    show" branch resets the cycle index back to 0, which is correct
    behaviour on its own but would mask the index ever advancing in a test
    with no history to chart (_alert_chart_html always returns "" then).
    """
    import dataclasses

    from usage_hud.history import HistoryStore
    from usage_hud.ui.hud import WeatherPanel

    snapshots, projections = _two_hot_snapshots()
    history = HistoryStore(tmp_path / "history.json")
    for snap in snapshots:
        # Two samples each, a few minutes apart — _alert_chart_html needs
        # at least 2 points of real history to draw anything at all.
        history.record([dataclasses.replace(snap, fetched_at=snap.fetched_at - timedelta(minutes=5))])
        history.record([snap])

    panel = WeatherPanel(history=history)
    panel._snapshots = snapshots
    panel._projections = projections
    try:
        assert panel._alert_cycle_index == 0
        panel._tick_alert_cycle()
        assert panel._alert_cycle_index == 1
        assert panel._raven_mode == "jump"  # the swap-flourish fired
        panel._tick_alert_cycle()
        assert panel._alert_cycle_index == 0  # wrapped back around
    finally:
        panel.deleteLater()


def test_alert_cycle_is_a_no_op_with_at_most_one_alarming_gauge():
    from usage_hud.ui.hud import WeatherPanel

    panel = WeatherPanel()
    panel._snapshots = []
    panel._projections = []
    try:
        panel._raven_mode = "walk"
        panel._tick_alert_cycle()
        assert panel._alert_cycle_index == 0
        assert panel._raven_mode == "walk"  # no swap happened, no flourish
    finally:
        panel.deleteLater()


def test_rocketing_gauge_gets_a_longer_turn_and_a_visible_ring():
    """Requested: "te problematyczne z rocket powiny byc mocniej
    eksponowane" — a rocketing gauge must both get more time on screen
    per turn than a steady confirmed risk, and render visibly differently
    (a red ring around the chart), not just equal billing."""
    from PySide6.QtGui import QColor

    from usage_hud.ui import mini_charts
    from usage_hud.ui.hud import WeatherPanel, _ALERT_CYCLE_HOT_MS, _ALERT_CYCLE_MS

    snap, metric = _snap_and_metric()
    snap.metrics.append(metric)

    steady = WeatherPanel()
    try:
        steady._snapshots = [snap]
        steady._projections = [_proj(will_exhaust=True, confident=True, rocketing=False)]
        steady._render()
        assert steady._alert_cycle_timer.interval() == _ALERT_CYCLE_MS
    finally:
        steady.deleteLater()

    spiking = WeatherPanel()
    try:
        spiking._snapshots = [snap]
        spiking._projections = [_proj(rocketing=True)]
        spiking._render()
        assert spiking._alert_cycle_timer.interval() == _ALERT_CYCLE_HOT_MS
    finally:
        spiking.deleteLater()

    calm_chart = mini_charts.forecast_icon([(0.0, 5.0), (1.0, 10.0)], 5.0, 20.0, QColor("#5ddea0"))
    hot_chart = mini_charts.forecast_icon(
        [(0.0, 5.0), (1.0, 10.0)], 5.0, 20.0, QColor("#5ddea0"), rocketing=True
    )
    assert calm_chart != hot_chart
