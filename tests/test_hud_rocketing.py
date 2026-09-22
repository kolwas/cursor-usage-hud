"""Rocketing (short-window spike) gauges get a visibly wider timeline chart."""

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
        renewal_offset_days=10.0,
        confident=True,
        rocketing=False,
    )
    base.update(overrides)
    return BurnProjection(**base)


def test_rocketing_gauge_gets_a_wider_timeline_chart():
    from usage_hud.ui.hud import WeatherPanel

    snap, metric = _snap_and_metric()
    calm = WeatherPanel._timeline_chart(snap, metric, _proj(rocketing=False))
    spiking = WeatherPanel._timeline_chart(snap, metric, _proj(rocketing=True))

    assert 'width="38"' in calm
    assert 'width="70"' in spiking
    assert calm != spiking
