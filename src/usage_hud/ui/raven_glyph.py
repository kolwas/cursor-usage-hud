"""The raven contour — the LIVE status icon (tray, taskbar, chip window;
see ui/tray.py, ui/formatters.py), severity-tinted, plus the chip's own
side watermark (ui/hud.py), in a fixed colour.

The static branding icon (tools/make_icon.py) draws a different, richer
raven-perched-on-boar composition from ui/emblem_glyph.py — more room for
detail there than a live, constantly-refreshed 16-24px icon has.
"""

from __future__ import annotations

import base64

from PySide6.QtCore import QBuffer, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

_EYE_POINT = (20.0, 11.6)
_LEG_A = ((12.5, 27.3), (11.3, 30.2))
_LEG_B = ((16.5, 27.3), (17.7, 30.2))

# A small idle-animation cycle for the watermark (see raven_watermark_html):
# a gentle rock of the whole glyph (reads as a head bob, since the head is
# what's furthest from the pivot) plus an alternating raised foot, like a
# bird shifting its weight — never a real walk cycle, just enough fidget to
# not look like a frozen sticker. One leg is shortened + pulled slightly
# in per "lifted" frame; the planted leg is untouched.
_LEG_A_LIFTED = ((13.0, 27.2), (13.6, 29.1))
_LEG_B_LIFTED = ((16.0, 27.2), (15.4, 29.1))
_ANIM_FRAMES: tuple[tuple[float, tuple, tuple], ...] = (
    (0.0, _LEG_A, _LEG_B),
    (2.2, _LEG_A_LIFTED, _LEG_B),
    (0.0, _LEG_A, _LEG_B),
    (-2.2, _LEG_A, _LEG_B_LIFTED),
)
ANIM_FRAME_COUNT = len(_ANIM_FRAMES)


def raven_path(s: float, *, detailed: bool = True) -> QPainterPath:
    """One closed contour, side profile, facing right: rounded back, a
    strongly hooked beak (the "under-curl" right past the tip is what
    reads as raptor/corvid rather than a generic songbird bill), a soft
    throat hackle, and a single tail feather flick — drawn on a 32x32
    design grid and scaled by ``s``.

    ``detailed=False`` drops the throat notch and tail feather in favour
    of smooth curves: at small pixel sizes those fine details are thinner
    than a pixel and just turn into noise, not detail.
    """
    path = QPainterPath()
    path.moveTo(3.5 * s, 19.0 * s)  # tail base
    # back, up and over the crown — one smooth arch
    path.quadTo(5.5 * s, 9.5 * s, 14.5 * s, 7.2 * s)
    # crown down to the base of the upper beak
    path.quadTo(19.5 * s, 7.4 * s, 23.5 * s, 9.7 * s)
    # upper beak out to the tip
    path.quadTo(27.5 * s, 10.8 * s, 30.5 * s, 13.2 * s)
    # the hook: curls back up under the tip before dropping to the chin —
    # this single notch is what makes the bill read as hooked, not straight
    path.quadTo(27.0 * s, 13.8 * s, 25.2 * s, 12.6 * s)
    path.lineTo(23.5 * s, 15.2 * s)  # chin
    if detailed:
        # one soft hackle — a hint of a shaggy throat, not a jagged zigzag
        path.quadTo(25.6 * s, 17.6 * s, 22.5 * s, 20.0 * s)
    else:
        path.quadTo(24.6 * s, 17.8 * s, 21.5 * s, 20.2 * s)
    # chest and belly, one continuous curve back toward the tail
    path.quadTo(18.0 * s, 27.3 * s, 12.0 * s, 27.7 * s)
    path.quadTo(6.8 * s, 26.9 * s, 4.6 * s, 20.2 * s)
    if detailed:
        # a single tail feather flick, not a self-crossing zigzag — the
        # earlier two-notch fan doubled back across its own base and read
        # as a stray mark rather than a feather.
        path.lineTo(1.2 * s, 18.6 * s)
    path.closeSubpath()
    return path


# Below this size a stroked outline smears into a grey smudge — Windows uses
# 16/24px for the tray and taskbar, where individual hairline strokes are
# thinner than a pixel. paint_raven_solid is what those sizes should use.
SOLID_MAX_SIZE = 24


def paint_raven_outline(
    painter: QPainter,
    s: float,
    *,
    line_color: QColor,
    eye_color: QColor | None = None,
    legs: bool = True,
    leg_a: tuple[tuple[float, float], tuple[float, float]] = _LEG_A,
    leg_b: tuple[tuple[float, float], tuple[float, float]] = _LEG_B,
    line_width: float | None = None,
) -> None:
    """Strokes the detailed contour (no fill) — the "zarys" (outline)
    treatment, for anything above ``SOLID_MAX_SIZE``. Caller owns the
    plate/background and draws it first. ``leg_a``/``leg_b`` default to the
    static resting pose; raven_watermark_html swaps in a lifted variant to
    animate a weight-shift."""
    pen = QPen(line_color)
    pen.setWidthF(line_width if line_width is not None else max(1.1, 1.7 * s))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(raven_path(s, detailed=True))

    if eye_color is not None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(eye_color)
        ex, ey = _EYE_POINT
        painter.drawEllipse(QPointF(ex * s, ey * s), 0.8 * s, 0.8 * s)

    if legs:
        painter.setPen(pen)
        (ax0, ay0), (ax1, ay1) = leg_a
        (bx0, by0), (bx1, by1) = leg_b
        painter.drawLine(QPointF(ax0 * s, ay0 * s), QPointF(ax1 * s, ay1 * s))
        painter.drawLine(QPointF(bx0 * s, by0 * s), QPointF(bx1 * s, by1 * s))


def paint_raven_solid(
    painter: QPainter,
    s: float,
    *,
    fill_color: QColor,
    eye_punch_color: QColor,
) -> None:
    """Fills the simplified silhouette and punches the eye out in
    ``eye_punch_color`` (normally whatever sits behind the glyph) — the
    tray-scale treatment, legible where a stroke would not be."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(fill_color)
    painter.drawPath(raven_path(s, detailed=False))
    painter.setBrush(eye_punch_color)
    ex, ey = _EYE_POINT
    painter.drawEllipse(QPointF(ex * s, ey * s), max(1.0, 1.1 * s), max(1.0, 1.1 * s))


def raven_watermark_html(
    size: int, *, line_color: QColor, eye_color: QColor | None = None, frame: int = 0
) -> str:
    """A standalone ``<img>`` tag of the outline raven on a transparent
    background — no plate, unlike the tray/badge icons — for dropping into
    a QLabel's rich text as a decorative mark, e.g. the chip's own side
    watermark (ui/hud.py), which already sits on the panel's own painted
    background (see WeatherPanel.paintEvent) and needs no plate of its own.

    ``frame`` (0..``ANIM_FRAME_COUNT``-1, wrapping) selects a pose from the
    idle-fidget cycle — a small rock of the whole glyph plus an alternating
    raised foot. The caller (WeatherPanel's own small QTimer) advances the
    frame and re-sets this HTML periodically; this function itself is a
    single static render, not the timer.
    """
    tilt, leg_a, leg_b = _ANIM_FRAMES[frame % ANIM_FRAME_COUNT]

    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 32.0

    # Rock around the glyph's own centre rather than the canvas corner, so
    # the tilt reads as the bird leaning, not the whole image sliding.
    pivot = QPointF(size / 2.0, size / 2.0)
    painter.translate(pivot)
    painter.rotate(tilt)
    painter.translate(-pivot)

    paint_raven_outline(
        painter, s, line_color=line_color, eye_color=eye_color, legs=True, leg_a=leg_a, leg_b=leg_b
    )
    painter.end()

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buf, "PNG")
    encoded = base64.b64encode(bytes(buf.data())).decode("ascii")
    return f'<img src="data:image/png;base64,{encoded}" width="{size}" height="{size}">'
