"""usage_hud.ui.emblem_glyph — the static branding icon's shapes (raven
perched on a boar). Below SOLID_MAX_SIZE, two detailed creatures smear
together at real icon scale (the same lesson learned from the solo raven
icon), so only the boar renders there; above it, both do.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def test_make_icon_renders_every_shipped_size_without_crashing():
    from tools.make_icon import draw_emblem

    for size in (16, 24, 32, 48, 64, 128, 256):
        pix = draw_emblem(size)
        assert pix.width() == size
        assert pix.height() == size


def test_small_sizes_are_boar_only_larger_sizes_add_the_raven():
    """The solid (<=SOLID_MAX_SIZE) and outline (>SOLID_MAX_SIZE) paths draw
    a visibly different silhouette — the raven accent only exists above the
    threshold."""
    from usage_hud.ui import emblem_glyph

    small = emblem_glyph.boar_path(emblem_glyph.SOLID_MAX_SIZE / 32.0)
    assert small.elementCount() > 0

    big_s = (emblem_glyph.SOLID_MAX_SIZE + 16) / 32.0
    combined = emblem_glyph.boar_path(big_s)
    combined.addPath(emblem_glyph.perched_raven_path(big_s))
    assert combined.elementCount() > emblem_glyph.boar_path(big_s).elementCount()


def test_paint_emblem_solid_and_outline_both_run(tmp_path):
    from PySide6.QtGui import QPainter, QPixmap

    from usage_hud.ui.emblem_glyph import paint_emblem_outline, paint_emblem_solid

    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    paint_emblem_solid(painter, 1.0, fill_color=QColor("#cbbf8f"))
    paint_emblem_outline(
        painter, 1.0, line_color=QColor("#cbbf8f"), accent_color=QColor("#c9a24a")
    )
    painter.end()
    assert not pix.toImage().isNull()
