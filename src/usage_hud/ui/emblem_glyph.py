"""The static branding emblem: a raven perched on a boar, in a military
color palette — the app's own mascot (the raven, used live elsewhere —
see raven_glyph.py) plus the user's personal animal, "woven in" together
per an explicit request, rather than either replacing the other.

This is deliberately separate from raven_glyph.py: that module draws the
LIVE status icon (tray, taskbar, chip window, chip watermark), which must
stay a plain raven — tinted by real-time severity color where it's a
status indicator, or a fixed accent color where it's just the chip's own
watermark — never a two-animal composition, since a live icon renders at
real 16-24px tray/taskbar scale where two detailed shapes do not survive.
This module is only for the STATIC app icon (tools/make_icon.py's output,
przepiorka.ico/.png) — the identity mark, not a live indicator, with more
room for detail.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

# Two creatures at 16-24px silhouette scale (the raven alone already needs
# a solid-silhouette fallback below raven_glyph.SOLID_MAX_SIZE) reliably
# turns into a single grey smudge, not two animals — so this module's own
# solid fallback goes further up: only the boar (the larger, simpler
# shape) below this size, both above it.
SOLID_MAX_SIZE = 32


def boar_path(s: float) -> QPainterPath:
    """Side profile, facing right: a bristled mane ridge along the spine
    (the boar's signature, the same role the raven's hooked beak plays),
    a small ear, a flat snout with a tusk, four legs."""
    p = QPainterPath()
    p.moveTo(4.0 * s, 24.0 * s)  # tail base, low back
    p.quadTo(2.5 * s, 19.0 * s, 5.0 * s, 14.5 * s)  # rear haunch up
    # bristled mane along the spine
    p.lineTo(7.5 * s, 10.0 * s)
    p.lineTo(9.5 * s, 13.0 * s)
    p.lineTo(12.0 * s, 8.5 * s)
    p.lineTo(14.0 * s, 12.0 * s)
    p.lineTo(16.5 * s, 8.0 * s)
    p.lineTo(18.5 * s, 11.5 * s)
    p.lineTo(20.5 * s, 9.5 * s)
    # ear
    p.lineTo(22.0 * s, 7.5 * s)
    p.lineTo(23.5 * s, 11.0 * s)
    # forehead down to snout
    p.quadTo(26.0 * s, 12.0 * s, 29.0 * s, 14.5 * s)
    p.lineTo(30.5 * s, 16.0 * s)  # snout tip (flat pig nose)
    p.lineTo(29.5 * s, 17.5 * s)
    p.lineTo(26.5 * s, 17.0 * s)  # underside of snout back to jaw
    # small tusk jutting from the lower jaw
    p.lineTo(27.5 * s, 20.0 * s)
    p.lineTo(24.5 * s, 18.5 * s)
    # jaw down to chest / belly
    p.quadTo(22.0 * s, 23.5 * s, 17.0 * s, 26.5 * s)
    p.quadTo(11.0 * s, 28.5 * s, 6.5 * s, 26.0 * s)
    p.quadTo(4.5 * s, 25.0 * s, 4.0 * s, 24.0 * s)
    p.closeSubpath()
    return p


_BOAR_LEGS: tuple[tuple[tuple[float, float], tuple[float, float]], ...] = (
    ((9.0, 26.5), (8.0, 30.0)),
    ((13.0, 27.0), (12.5, 30.2)),
    ((19.0, 26.0), (19.5, 29.8)),
    ((23.0, 24.0), (24.0, 28.0)),
)
_BOAR_EYE_POINT = (21.0, 9.6)
_RAVEN_ANCHOR = (13.5, 4.2)  # where the perched bird sits, relative to the 32x32 grid


def perched_raven_path(s: float, ox: float = _RAVEN_ANCHOR[0], oy: float = _RAVEN_ANCHOR[1]) -> QPainterPath:
    """A small perched-bird silhouette: a compact rounded body with a
    forward beak and a short tail nub. Deliberately simpler than the solo
    raven glyph's hooked-beak contour — at this small an accent scale that
    fancier path reads as a closed loop, not a bird."""
    p = QPainterPath()
    p.addEllipse(QPointF(ox * s, oy * s), 3.4 * s, 2.6 * s)
    beak = QPainterPath()
    beak.moveTo((ox + 2.6) * s, (oy - 0.6) * s)
    beak.lineTo((ox + 6.0) * s, (oy + 0.1) * s)
    beak.lineTo((ox + 2.6) * s, (oy + 1.2) * s)
    beak.closeSubpath()
    p.addPath(beak)
    tail = QPainterPath()
    tail.moveTo((ox - 3.2) * s, (oy - 0.6) * s)
    tail.lineTo((ox - 5.6) * s, (oy - 1.8) * s)
    tail.lineTo((ox - 2.6) * s, (oy + 0.6) * s)
    tail.closeSubpath()
    p.addPath(tail)
    return p


def paint_emblem_solid(painter: QPainter, s: float, *, fill_color: QColor) -> None:
    """Boar only, filled — the tray/taskbar-adjacent scale fallback."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(fill_color)
    painter.drawPath(boar_path(s))


def paint_emblem_outline(
    painter: QPainter,
    s: float,
    *,
    line_color: QColor,
    accent_color: QColor,
    line_width: float | None = None,
) -> None:
    """Boar + perched raven, stroked outline — both animals "woven in"."""
    pen = QPen(line_color)
    pen.setWidthF(line_width if line_width is not None else max(1.1, 1.6 * s))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(boar_path(s))
    painter.drawPath(perched_raven_path(s))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(accent_color)
    ex, ey = _BOAR_EYE_POINT
    painter.drawEllipse(QPointF(ex * s, ey * s), 0.8 * s, 0.8 * s)

    painter.setPen(pen)
    for (x0, y0), (x1, y1) in _BOAR_LEGS:
        painter.drawLine(QPointF(x0 * s, y0 * s), QPointF(x1 * s, y1 * s))
