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


def test_clock_pie_icon_draws_a_distinct_unknown_state_instead_of_guessing():
    """frac=None must not silently become 'full' or 'empty' — every row needs
    the same icon present, but an unknown one must look different from a
    genuine 0%/100% so it isn't mistaken for real data."""
    mini_charts = _import_mini_charts()
    unknown = mini_charts.clock_pie_icon(None, QColor("#5ddea0"))
    full = mini_charts.clock_pie_icon(1.0, QColor("#5ddea0"))
    empty = mini_charts.clock_pie_icon(0.0, QColor("#5ddea0"))
    assert "data:image/png;base64," in unknown
    assert unknown != full
    assert unknown != empty


@pytest.mark.parametrize(
    ("elapsed", "exhaust"),
    [(0.0, 0.0), (0.1, 0.5), (0.9, None), (0.5, 1.4), (1.0, 1.0), (None, None)],
)
def test_burn_timeline_icon_renders_for_every_input(elapsed, exhaust):
    mini_charts = _import_mini_charts()
    tag = mini_charts.burn_timeline_icon(elapsed, exhaust, QColor("#ff8a80"))
    assert tag.startswith('<img src="data:image/png;base64,')


def test_burn_timeline_icon_unknown_elapsed_is_distinct_from_zero():
    mini_charts = _import_mini_charts()
    unknown = mini_charts.burn_timeline_icon(None, None, QColor("#8ec8ff"))
    zero = mini_charts.burn_timeline_icon(0.0, None, QColor("#8ec8ff"))
    assert unknown != zero


def test_burn_timeline_icon_clamps_out_of_range_fractions_without_crashing():
    mini_charts = _import_mini_charts()
    # Negative elapsed (clock skew) and an exhaustion far past the cycle end
    # must still produce a valid image, not raise.
    tag = mini_charts.burn_timeline_icon(-0.4, 3.2, QColor("#ffb020"))
    assert "data:image/png;base64," in tag


def test_unconfident_exhaustion_dot_is_drawn_differently_from_a_confident_one():
    """A tentative prediction is still plotted — never withheld — but its dot
    must not look identical to a confident one, or it would read as a verdict."""
    mini_charts = _import_mini_charts()
    confident = mini_charts.burn_timeline_icon(0.3, 0.6, QColor("#ff8a80"), confident=True)
    tentative = mini_charts.burn_timeline_icon(0.3, 0.6, QColor("#ff8a80"), confident=False)
    assert confident != tentative


def test_sparkline_with_too_few_points_draws_a_placeholder():
    mini_charts = _import_mini_charts()
    for values in ([], [42.0]):
        tag = mini_charts.sparkline_icon(values, QColor("#5ddea0"))
        assert tag.startswith('<img src="data:image/png;base64,')


def test_sparkline_renders_a_real_trend():
    mini_charts = _import_mini_charts()
    tag = mini_charts.sparkline_icon([2.0, 5.0, 4.0, 11.0, 30.0], QColor("#ffb020"))
    assert tag.startswith('<img src="data:image/png;base64,')


def test_sparkline_flat_line_still_renders():
    """A flat trend (min == max) must not divide by zero when scaling."""
    mini_charts = _import_mini_charts()
    tag = mini_charts.sparkline_icon([10.0, 10.0, 10.0], QColor("#5ddea0"))
    assert "data:image/png;base64," in tag


def test_hot_spike_badge_is_visually_distinct():
    """The spike badge must actually change the rendered image, not just be
    accepted as a no-op parameter."""
    mini_charts = _import_mini_charts()
    calm = mini_charts.sparkline_icon([5.0, 6.0, 7.0], QColor("#5ddea0"), hot=False)
    spiking = mini_charts.sparkline_icon([5.0, 6.0, 7.0], QColor("#5ddea0"), hot=True)
    assert calm != spiking


def test_low_usage_dims_the_elapsed_fill():
    """A gauge at 0-19% needs zero attention — its elapsed bar (which only
    encodes cycle position, not usage) must not be just as bright as a
    heavily-used gauge's, or a fine 0% reads as visually loud."""
    mini_charts = _import_mini_charts()
    bright = mini_charts.burn_timeline_icon(0.8, None, QColor("#8ec8ff"), usage_pct=70.0)
    dim = mini_charts.burn_timeline_icon(0.8, None, QColor("#8ec8ff"), usage_pct=0.0)
    assert bright != dim


def test_no_usage_pct_keeps_the_default_bright_fill():
    """Backward-compatible default: omitting usage_pct must not silently dim."""
    mini_charts = _import_mini_charts()
    default = mini_charts.burn_timeline_icon(0.8, None, QColor("#8ec8ff"))
    bright = mini_charts.burn_timeline_icon(0.8, None, QColor("#8ec8ff"), usage_pct=70.0)
    assert default == bright
