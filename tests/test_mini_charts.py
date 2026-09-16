"""mini_charts needs a QApplication (QPixmap/QPainter) — skip cleanly without one."""

import pytest

PySide6 = pytest.importorskip("PySide6")

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _import_mini_charts():
    from usage_hud.ui import mini_charts

    return mini_charts


@pytest.mark.parametrize("frac", [0.0, 0.01, 0.25, 0.6, 1.0])
def test_clock_pie_icon_renders_a_png_for_every_fraction(frac):
    mini_charts = _import_mini_charts()
    tag = mini_charts.clock_pie_icon(frac, QColor("#ff6b6b"))
    assert tag.startswith('<img src="data:image/png;base64,')
    assert 'width="12" height="12"' in tag


def test_clock_pie_icon_defaults_to_full_when_fraction_unknown():
    mini_charts = _import_mini_charts()
    tag = mini_charts.clock_pie_icon(None, QColor("#5ddea0"))
    assert "data:image/png;base64," in tag


@pytest.mark.parametrize(
    ("elapsed", "exhaust"),
    [(0.0, 0.0), (0.1, 0.5), (0.9, None), (0.5, 1.4), (1.0, 1.0)],
)
def test_burn_timeline_icon_renders_for_every_input(elapsed, exhaust):
    mini_charts = _import_mini_charts()
    tag = mini_charts.burn_timeline_icon(elapsed, exhaust, QColor("#ff8a80"))
    assert tag.startswith('<img src="data:image/png;base64,')


def test_burn_timeline_icon_clamps_out_of_range_fractions_without_crashing():
    mini_charts = _import_mini_charts()
    # Negative elapsed (clock skew) and an exhaustion far past the cycle end
    # must still produce a valid image, not raise.
    tag = mini_charts.burn_timeline_icon(-0.4, 3.2, QColor("#ffb020"))
    assert "data:image/png;base64," in tag
