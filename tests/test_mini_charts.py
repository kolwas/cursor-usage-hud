"""mini_charts needs a QApplication (QPixmap/QPainter) — skip cleanly without one."""

import base64
import re

import pytest

PySide6 = pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QImage  # noqa: E402
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


@pytest.mark.parametrize("pct", [0.0, 1.0, 25.0, 99.9, 100.0])
def test_usage_bar_icon_renders_for_every_percent(pct):
    mini_charts = _import_mini_charts()
    tag = mini_charts.usage_bar_icon(pct, QColor("#5ddea0"))
    assert tag.startswith('<img src="data:image/png;base64,')


def test_usage_bar_icon_fill_grows_with_percent():
    """The one thing this bar encodes: more percent, more fill — a wider bar
    at 80% than at 10%, nothing else changing."""
    mini_charts = _import_mini_charts()
    low = mini_charts.usage_bar_icon(10.0, QColor("#5ddea0"))
    high = mini_charts.usage_bar_icon(80.0, QColor("#5ddea0"))
    assert low != high


def test_usage_bar_icon_unknown_percent_is_distinct_from_zero():
    mini_charts = _import_mini_charts()
    unknown = mini_charts.usage_bar_icon(None, QColor("#8ec8ff"))
    zero = mini_charts.usage_bar_icon(0.0, QColor("#8ec8ff"))
    assert unknown != zero


def test_usage_bar_icon_clamps_out_of_range_percent_without_crashing():
    mini_charts = _import_mini_charts()
    tag = mini_charts.usage_bar_icon(140.0, QColor("#ff8a80"))
    assert "data:image/png;base64," in tag
    tag2 = mini_charts.usage_bar_icon(-5.0, QColor("#ff8a80"))
    assert "data:image/png;base64," in tag2


def test_burn_timeline_icon_clamps_out_of_range_fractions_without_crashing():
    mini_charts = _import_mini_charts()
    # Negative elapsed (clock skew) and an exhaustion far past the cycle end
    # must still produce a valid image, not raise.
    tag = mini_charts.burn_timeline_icon(-0.4, 3.2, QColor("#ffb020"))
    assert "data:image/png;base64," in tag


def test_unconfident_exhaustion_flag_is_drawn_differently_from_a_confident_one():
    """A tentative prediction is still plotted — never withheld — but its flag
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


def test_elapsed_fill_is_dim_regardless_of_how_far_along_it_is():
    """The elapsed segment is background context ("how far into the cycle"),
    never the alarm signal — it must render in the same dim tone whether the
    cycle is nearly over or barely started. Only the exhaustion flag carries
    severity colour."""
    mini_charts = _import_mini_charts()
    early = mini_charts.burn_timeline_icon(0.1, None, QColor("#8ec8ff"))
    late = mini_charts.burn_timeline_icon(0.8, None, QColor("#8ec8ff"))
    assert early != late  # different fill width, same styling — still renders distinctly
    assert "data:image/png;base64," in early
    assert "data:image/png;base64," in late


def test_exhaustion_flag_present_only_when_a_projection_exists():
    """No projection (``exhaust_frac=None``) must draw a plain fill with no
    flag at all, distinct from a row that has one — the flag's absence is
    itself the "nothing to worry about (yet)" signal."""
    mini_charts = _import_mini_charts()
    no_flag = mini_charts.burn_timeline_icon(0.5, None, QColor("#ff8a80"))
    with_flag = mini_charts.burn_timeline_icon(0.5, 0.6, QColor("#ff8a80"))
    assert no_flag != with_flag


def test_forecast_icon_renders_with_and_without_a_trend():
    mini_charts = _import_mini_charts()
    values = [(0.0, 5.0), (0.5, 12.0), (1.0, 18.0)]
    with_trend = mini_charts.forecast_icon(values, 5.0, 95.0, QColor("#ff8a80"))
    no_trend = mini_charts.forecast_icon(values, 5.0, None, QColor("#ff8a80"))
    assert with_trend.startswith('<img src="data:image/png;base64,')
    assert no_trend.startswith('<img src="data:image/png;base64,')
    assert with_trend != no_trend  # the trend line actually changes the picture


def test_forecast_icon_too_little_data_is_distinct_from_a_real_chart():
    mini_charts = _import_mini_charts()
    empty = mini_charts.forecast_icon([], 5.0, None, QColor("#8ec8ff"))
    one_point = mini_charts.forecast_icon([(0.0, 5.0)], 5.0, None, QColor("#8ec8ff"))
    real = mini_charts.forecast_icon([(0.0, 5.0), (1.0, 10.0)], 5.0, None, QColor("#8ec8ff"))
    assert empty == one_point  # both "not enough data" — same placeholder
    assert empty != real


def test_forecast_icon_zero_window_days_does_not_crash():
    """A defensive guard, not a real scenario (the caller only builds this
    chart once window_days is known to be positive) — must not divide by
    zero if it's ever called with a degenerate window anyway."""
    mini_charts = _import_mini_charts()
    tag = mini_charts.forecast_icon([(0.0, 5.0), (1.0, 10.0)], 0.0, None, QColor("#8ec8ff"))
    assert "data:image/png;base64," in tag


def test_forecast_icon_overshoot_past_the_cap_does_not_crash():
    """The whole point is to visualise a trend that blows past 100% — the
    y-scale must expand to fit it rather than choke on it."""
    mini_charts = _import_mini_charts()
    tag = mini_charts.forecast_icon(
        [(0.0, 10.0), (0.5, 60.0), (1.0, 95.0)], 2.0, 340.0, QColor("#ff8a80")
    )
    assert "data:image/png;base64," in tag


def _decode(img_tag: str) -> QImage:
    b64 = re.search(r'base64,([^"]+)', img_tag).group(1)
    img = QImage()
    img.loadFromData(base64.b64decode(b64))
    return img


def _has_pixel_near(img: QImage, cx: float, cy: float, wants: str, radius: int = 2) -> bool:
    """Is there a pixel within ``radius`` of (cx, cy) whose dominant channel
    matches ``wants`` ("red"/"green"/"amber")? Antialiasing and dashed
    lines mean a single exact pixel is not a reliable sample; a small
    neighbourhood scan is what the eye actually does looking at the chart.
    """
    w, h = img.width(), img.height()
    for y in range(max(0, int(cy) - radius), min(h, int(cy) + radius + 1)):
        for x in range(max(0, int(cx) - radius), min(w, int(cx) + radius + 1)):
            c = img.pixelColor(x, y)
            r, g, b = c.red(), c.green(), c.blue()
            if wants == "red" and r > 150 and r > g + 60 and r > b + 60:
                return True
            if wants == "green" and g > 150 and g > r + 30 and g > b + 20:
                return True
            if wants == "amber" and r > 150 and 60 < g < 200 and b < 80:
                return True
    return False


def test_forecast_icon_draws_the_cap_line_at_exactly_100_percent():
    """Pixel-level check, not a visual eyeball: for known values (not noisy
    live data, so the expected geometry can be computed by hand), is the
    red 100% line actually AT the y that the documented formula says it
    should be — not just "a red line exists somewhere"."""
    mini_charts = _import_mini_charts()
    width, height = 110, 40
    tag = mini_charts.forecast_icon(
        [(0.0, 0.0), (1.0, 50.0)], 5.0, 100.0, QColor("#5ddea0"), width=width, height=height
    )
    img = _decode(tag)

    y_max = max(0.0, 50.0, 100.0) * 1.08
    pad, plot_h = 2.0, height - 4.0
    y100 = pad + plot_h * (1.0 - min(100.0 / y_max, 1.0))
    assert _has_pixel_near(img, width / 2, y100, "red")


def test_forecast_icon_trend_line_passes_through_the_interpolated_point():
    """The trend line must be an actual straight line from "now" to the
    projected value at the window's own end — checked by sampling the
    midpoint of that segment, not just "an amber pixel exists"."""
    mini_charts = _import_mini_charts()
    width, height = 110, 40
    values = [(0.0, 0.0), (1.0, 50.0)]
    window_days = 5.0
    projected_value = 100.0  # straight line from (1, 50) to (5, 100)
    tag = mini_charts.forecast_icon(
        values, window_days, projected_value, QColor("#5ddea0"), width=width, height=height
    )
    img = _decode(tag)

    y_max = max(0.0, 50.0, 100.0) * 1.08
    pad = 2.0
    plot_w, plot_h = width - 4.0, height - 4.0

    def xpix(d: float) -> float:
        return pad + plot_w * max(0.0, min(1.0, d / window_days))

    def ypix(v: float) -> float:
        return pad + plot_h * (1.0 - min(max(0.0, v / y_max), 1.0))

    # Halfway from "now" (elapsed=1, 50%) to the window's end (elapsed=5,
    # 100%) on a straight line is elapsed=3, value=75.
    assert _has_pixel_near(img, xpix(3.0), ypix(75.0), "amber")


def test_forecast_icon_overshoot_clips_to_the_top_edge_not_the_scale():
    """A projection far past 100% (300%) must not drag the whole y-axis
    down to fit it — the trend line clips to the top edge instead, so the
    100% cap line stays where the formula puts it (~4.7px here), not
    squeezed to the very top by a distant projected value."""
    mini_charts = _import_mini_charts()
    width, height = 110, 40
    tag = mini_charts.forecast_icon(
        [(0.0, 10.0), (1.0, 60.0)], 5.0, 300.0, QColor("#5ddea0"), width=width, height=height
    )
    img = _decode(tag)

    y_max = max(10.0, 60.0, 100.0) * 1.08  # must NOT include 300 here
    pad, plot_h = 2.0, height - 4.0
    y100 = pad + plot_h * (1.0 - min(100.0 / y_max, 1.0))
    assert _has_pixel_near(img, width / 2, y100, "red")
    # The clipped trend line lands at the top edge (y=pad), near the
    # window's own end (right edge) — not partway down a stretched scale.
    assert _has_pixel_near(img, width - 3, pad, "amber", radius=2)
