"""raven_glyph.raven_watermark_html: the chip's side-watermark raven has a
small idle-fidget animation (a tilt plus an alternating raised foot) driven
by WeatherPanel's own timer — this covers the frame cycle renders distinct
poses and wraps cleanly, without needing a live Qt event loop tick.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def test_animation_frames_are_visually_distinct():
    from usage_hud.ui.raven_glyph import ANIM_FRAME_COUNT, raven_watermark_html

    frames = [
        raven_watermark_html(40, line_color=QColor("#cbbf8f"), eye_color=QColor("#c9a24a"), frame=f)
        for f in range(ANIM_FRAME_COUNT)
    ]
    assert len(set(frames)) > 1


def test_frame_index_wraps_around():
    from usage_hud.ui.raven_glyph import ANIM_FRAME_COUNT, raven_watermark_html

    first = raven_watermark_html(40, line_color=QColor("#cbbf8f"), frame=0)
    wrapped = raven_watermark_html(40, line_color=QColor("#cbbf8f"), frame=ANIM_FRAME_COUNT)
    assert first == wrapped


def test_default_frame_matches_frame_zero():
    from usage_hud.ui.raven_glyph import raven_watermark_html

    default = raven_watermark_html(40, line_color=QColor("#cbbf8f"))
    explicit = raven_watermark_html(40, line_color=QColor("#cbbf8f"), frame=0)
    assert default == explicit


def test_weather_panel_advances_the_watermark_on_each_tick():
    from usage_hud.ui.hud import WeatherPanel

    panel = WeatherPanel(opacity=0.9)
    before = panel._raven_mark.text()
    before_frame = panel._raven_frame
    panel._tick_raven_mark()
    assert panel._raven_frame != before_frame
    assert panel._raven_mark.text() != before
    panel.deleteLater()
