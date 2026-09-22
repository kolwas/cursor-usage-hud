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
