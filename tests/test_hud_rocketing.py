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
        assert rocketing._alert_chart.text() != ""
    finally:
        rocketing.deleteLater()
