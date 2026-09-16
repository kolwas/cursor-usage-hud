"""Tiny inline charts for the chip/panel — a pie "clock" and a burn timeline.

QLabel's RichText engine has no CSS gradients/canvas, so these are rasterized
with QPainter and handed back as ``data:image/png;base64,...`` strings to drop
straight into an ``<img>`` tag. Sizes are chip-scale (a few px), not dashboard
widgets.

Both charts are drawn for EVERY gauge, always, in the same size and position —
even when there isn't enough data yet. A dashed/hollow "unknown" rendering
(``frac=None``) keeps every row the same shape instead of some rows having an
icon and others not, which used to make the chip jump around.
"""

from __future__ import annotations

import base64

from PySide6.QtCore import QBuffer, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

_TRACK = QColor(255, 255, 255, 60)
_ELAPSED = QColor(255, 255, 255, 165)
_UNKNOWN = QColor(255, 255, 255, 90)
_DOT_HALO = QColor(12, 14, 20, 210)


def _data_uri(pix: QPixmap) -> str:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buf, "PNG")
    encoded = base64.b64encode(bytes(buf.data())).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _img_tag(data_uri: str, width: int, height: int, *, valign: str = "middle") -> str:
    return f'<img src="{data_uri}" width="{width}" height="{height}" style="vertical-align:{valign};">'


def _unknown_pen() -> QPen:
    pen = QPen(_UNKNOWN)
    pen.setStyle(Qt.PenStyle.DashLine)
    pen.setWidthF(1.1)
    return pen


def clock_pie_icon(
    frac_remaining: float | None, color: QColor, *, size: int = 12
) -> str:
    """A tiny pie wedge that shrinks as the window's time runs out.

    The wedge's ANGLE tracks time (how much of the window is left); its
    COLOR tracks usage severity — the two are independent, as asked: a clock
    running down safely stays green, one running down while nearly full
    turns red, regardless of how much time remains.

    ``frac_remaining=None`` (we don't know when this window resets) draws a
    dashed hollow ring instead of guessing — visually distinct from a
    genuine 0% (solid, empty) or 100% (solid, full) wedge.
    """
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if frac_remaining is None:
        painter.setPen(_unknown_pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(1, 1, size - 2, size - 2)
        painter.end()
        return _img_tag(_data_uri(pix), size, size)

    frac_remaining = max(0.0, min(1.0, frac_remaining))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_TRACK)
    painter.drawEllipse(0, 0, size, size)

    if frac_remaining > 1e-4:
        painter.setBrush(color)
        # Qt pie angles are 1/16th of a degree, counter-clockwise; start at
        # 12 o'clock and sweep clockwise as the remaining slice.
        span = round(360 * 16 * frac_remaining)
        painter.drawPie(0, 0, size, size, 90 * 16, -span)

    painter.end()
    return _img_tag(_data_uri(pix), size, size)


def burn_timeline_icon(
    elapsed_frac: float | None,
    exhaust_frac: float | None,
    marker_color: QColor,
    *,
    confident: bool = True,
    width: int = 38,
    height: int = 10,
) -> str:
    """A tiny horizontal timeline: cycle_start..cycle_end as the full bar,
    filled up to "now", with a dot marking the projected exhaustion date —
    the prediction as a picture instead of a signed day count.

    Sized and contrasted to still read at chip scale: a 3px track, a 4px dot
    with a dark halo so it stays visible over light or dark fills alike.

    ``elapsed_frac=None`` (no cycle_end to place "now" on) draws a dashed
    empty track — same size and position as every other row's timeline, just
    with nothing plotted on it yet. ``confident=False`` still plots the dot
    (predictions are never withheld) but as a hollow ring instead of a solid
    fill, so an early/noisy estimate reads as tentative rather than final.
    """
    bar_h = 3
    pix = QPixmap(width, height)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    track_y = (height - bar_h) / 2

    if elapsed_frac is None:
        painter.setPen(_unknown_pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(0, int(track_y), width - 1, bar_h, 1, 1)
        painter.end()
        return _img_tag(_data_uri(pix), width, height)

    painter.setPen(Qt.PenStyle.NoPen)
    elapsed_frac = max(0.0, min(1.0, elapsed_frac))

    painter.setBrush(_TRACK)
    painter.drawRoundedRect(0, int(track_y), width, bar_h, 1, 1)

    if elapsed_frac > 0:
        painter.setBrush(_ELAPSED)
        painter.drawRoundedRect(0, int(track_y), max(3, round(width * elapsed_frac)), bar_h, 1, 1)

    if exhaust_frac is not None:
        x = max(0.0, min(1.0, exhaust_frac)) * (width - 4) + 2.0
        center = QPointF(x, height / 2)
        # Dark halo first so the dot reads on any background, then the dot.
        painter.setBrush(_DOT_HALO)
        painter.drawEllipse(center, 4.0, 4.0)
        if confident:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(marker_color)
        else:
            pen = QPen(marker_color)
            pen.setWidthF(1.3)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, 3.0, 3.0)

    painter.end()
    return _img_tag(_data_uri(pix), width, height)
