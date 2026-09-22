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
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF

_TRACK = QColor(255, 255, 255, 70)
# Dim on purpose — "time elapsed so far" is background context, not the
# thing to look at, so it must never out-compete the exhaustion flag below.
_ELAPSED = QColor(150, 156, 170, 210)
_UNKNOWN = QColor(255, 255, 255, 120)
_DOT_HALO = QColor(12, 14, 20, 210)
_HOT = QColor(255, 61, 61, 255)
# The chip window is translucent (WA_TranslucentBackground) — whatever is on
# the real desktop shows through it. A semi-transparent bar blends into
# THAT, not into a predictable dark panel, so on a light or busy background
# it all but disappears. An opaque backing plate under the timeline fixes
# the contrast regardless of what's behind the chip.
_PLATE = QColor(18, 21, 28, 235)


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

    # Opaque plate first — see burn_timeline_icon for why (translucent chip
    # window, so a semi-transparent fill would blend into the real desktop
    # behind it rather than a predictable dark panel).
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_PLATE)
    painter.drawEllipse(0, 0, size, size)

    if frac_remaining is None:
        painter.setPen(_unknown_pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(1, 1, size - 2, size - 2)
        painter.end()
        return _img_tag(_data_uri(pix), size, size)

    frac_remaining = max(0.0, min(1.0, frac_remaining))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_TRACK)
    painter.drawEllipse(1, 1, size - 2, size - 2)

    if frac_remaining > 1e-4:
        painter.setBrush(color)
        # Qt pie angles are 1/16th of a degree, counter-clockwise; start at
        # 12 o'clock and sweep clockwise as the remaining slice.
        span = round(360 * 16 * frac_remaining)
        painter.drawPie(1, 1, size - 2, size - 2, 90 * 16, -span)

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
    """A tiny horizontal timeline: cycle_start..cycle_end as the full bar.

    One thing to read, not two: a dim grey fill for "time elapsed so far"
    (background context — nobody needs to act on this) and, only when a
    projection exists, a single coloured FLAG — a tick spanning the bar's
    full height — marking where the current burn rate would exhaust the
    quota. No flag drawn = nothing projected. The flag's colour is the same
    severity colour used in the text ETA columns next to it, so there is
    one colour convention for the whole chip, not a separate one to learn
    for this picture.

    A plain 3px dot used to carry the exhaustion marker; at chip scale it
    read as texture rather than a deliberate mark, and it was easy to
    mistake for "this row is fine" when it was actually the row saying
    "you're about to run out." A full-height flag is harder to miss and
    impossible to mistake for the track underneath it.

    Sized and contrasted to still read at chip scale: an opaque dark plate
    behind the whole bar (the chip window is translucent, so a merely
    semi-transparent fill would blend into whatever is on the real desktop
    behind it, not into a predictable dark panel), plus a dark halo behind
    the flag so it stays visible over light or dark fills alike.

    ``elapsed_frac=None`` (no cycle_end to place "now" on) draws a dashed
    empty track — same size and position as every other row's timeline, just
    with nothing plotted on it yet. ``confident=False`` still draws the flag
    (predictions are never withheld) but dashed instead of solid — the same
    "tentative" convention as the "~" marker in the text columns.
    """
    bar_h = 4
    pix = QPixmap(width, height)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    track_y = (height - bar_h) / 2

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_PLATE)
    painter.drawRoundedRect(0, 0, width, height, 3, 3)

    if elapsed_frac is None:
        painter.setPen(_unknown_pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, int(track_y), width - 2, bar_h, 1, 1)
        painter.end()
        return _img_tag(_data_uri(pix), width, height)

    painter.setPen(Qt.PenStyle.NoPen)
    elapsed_frac = max(0.0, min(1.0, elapsed_frac))

    painter.setBrush(_TRACK)
    painter.drawRoundedRect(1, int(track_y), width - 2, bar_h, 1, 1)

    if elapsed_frac > 0:
        painter.setBrush(_ELAPSED)
        painter.drawRoundedRect(1, int(track_y), max(3, round((width - 2) * elapsed_frac)), bar_h, 1, 1)

    if exhaust_frac is not None:
        x = max(0.0, min(1.0, exhaust_frac)) * (width - 4) + 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_DOT_HALO)
        painter.drawRoundedRect(x - 1.6, 0.5, 3.2, height - 1.0, 1, 1)
        if confident:
            painter.setBrush(marker_color)
            painter.drawRoundedRect(x - 0.8, 0.5, 1.6, height - 1.0, 0.8, 0.8)
        else:
            pen = QPen(marker_color)
            pen.setWidthF(1.4)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(x, 1.0), QPointF(x, height - 1.0))

    painter.end()
    return _img_tag(_data_uri(pix), width, height)


def sparkline_icon(
    values: list[float],
    color: QColor,
    *,
    hot: bool = False,
    width: int = 54,
    height: int = 16,
) -> str:
    """The real observed history, not the synthetic cycle-position math the
    clock/timeline use: a small 0-100% line of actual percent-used samples
    over whatever window the caller queried from HistoryStore.series().

    Fewer than 2 points (nothing recorded yet) draws an empty dashed plate —
    same shape as the other two "no data yet" states, never a blank gap.

    ``hot=True`` (today's usage is spiking well past the average pace, the
    same condition that fires the CRITICAL "burning hot" tray alert) adds a
    solid red spike-triangle badge in the corner — a small procedural shape
    rather than an emoji, since a skull glyph would just blur into a colored
    dot at this pixel scale.
    """
    pix = QPixmap(width, height)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_PLATE)
    painter.drawRoundedRect(0, 0, width, height, 3, 3)

    pad = 2.0
    if len(values) < 2:
        pen = _unknown_pen()
        painter.setPen(pen)
        painter.drawLine(QPointF(pad, height - pad), QPointF(width - pad, height - pad))
        painter.end()
        return _img_tag(_data_uri(pix), width, height)

    lo, hi = min(values), max(values)
    span = max(hi - lo, 1e-6)
    plot_w = width - 2 * pad
    plot_h = height - 2 * pad
    n = len(values)

    def point(i: int, v: float) -> QPointF:
        x = pad + (plot_w * i / (n - 1) if n > 1 else 0.0)
        y = pad + plot_h * (1.0 - (v - lo) / span)
        return QPointF(x, y)

    pts = [point(i, v) for i, v in enumerate(values)]

    pen = QPen(color)
    pen.setWidthF(1.4)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    for a, b in zip(pts, pts[1:]):
        painter.drawLine(a, b)

    # Mark "now" (the last sample) so the current level is unambiguous even
    # when the line is nearly flat.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_DOT_HALO)
    painter.drawEllipse(pts[-1], 2.6, 2.6)
    painter.setBrush(color)
    painter.drawEllipse(pts[-1], 1.7, 1.7)

    if hot:
        bs = 6.0
        bx, by = width - bs - 1.0, 1.0
        triangle = QPolygonF(
            [QPointF(bx + bs / 2, by), QPointF(bx, by + bs), QPointF(bx + bs, by + bs)]
        )
        painter.setBrush(_DOT_HALO)
        painter.drawEllipse(QPointF(bx + bs / 2, by + bs / 2), bs * 0.75, bs * 0.75)
        painter.setBrush(_HOT)
        painter.drawPolygon(triangle)

    painter.end()
    return _img_tag(_data_uri(pix), width, height)
