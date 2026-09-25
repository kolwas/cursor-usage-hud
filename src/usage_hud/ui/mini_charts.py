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


def usage_bar_icon(
    pct: float | None,
    color: QColor,
    *,
    width: int = 38,
    height: int = 10,
) -> str:
    """The chip's own usage bar: fill width = percent used, full stop — no
    second axis, no marker to decode. It exists because the richer burn
    timeline (track = cycle, dim fill = elapsed time, flag = projected
    exhaustion) kept reading as unclear at chip scale even after several
    passes — two encodings sharing one 38x10px picture is one too many for
    a glance. This is what the CHIP shows; the flyout/expanded view still
    draws the full burn timeline next to the words that explain it, where
    there is room to.

    Deliberately the same size and position as the old chart column so the
    table layout does not shift, and the same "dashed track, nothing
    plotted" convention for ``pct=None`` as every other icon here.
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

    if pct is None:
        painter.setPen(_unknown_pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, int(track_y), width - 2, bar_h, 1, 1)
        painter.end()
        return _img_tag(_data_uri(pix), width, height)

    frac = max(0.0, min(1.0, pct / 100.0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_TRACK)
    painter.drawRoundedRect(1, int(track_y), width - 2, bar_h, 1, 1)

    if frac > 0:
        painter.setBrush(color)
        painter.drawRoundedRect(1, int(track_y), max(3, round((width - 2) * frac)), bar_h, 1, 1)

    painter.end()
    return _img_tag(_data_uri(pix), width, height)


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


_LIMIT_LINE = QColor(255, 68, 68, 230)  # the red 100% cap line
_TREND_LINE = QColor(255, 176, 32, 220)  # amber — a projection, not observed fact


def forecast_icon(
    values: list[tuple[float, float]],
    window_days: float,
    projected_value: float | None,
    color: QColor,
    *,
    width: int = 76,
    height: int = 26,
) -> str:
    """The alert chart's own picture, scaled to the WHOLE window, not just
    however many samples happen to exist: the x-axis runs from the window's
    own start to its own end (``window_days``, in days — the real observed
    line only ever occupies the elapsed slice of that, the rest stays open
    canvas), a dashed red line marks the 100% cap, and a straight amber
    trend line continues from the last observed point out to where the
    current pace would land BY the time the window ends (``projected_
    value``) — so a burn rocketing towards the cap reads directly as "the
    trend line crosses red before it reaches the right edge", not a number
    to do the arithmetic on yourself.

    ``values`` is (elapsed_days_since_window_start, percent_used), oldest
    first — not the raw 0..100-normalised list ``sparkline_icon`` takes,
    since this chart's y-axis is a fixed 0..headroom scale (so the cap line
    and the trend line both mean something), not autoscaled to whatever the
    data happens to span.
    """
    pix = QPixmap(width, height)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_PLATE)
    painter.drawRoundedRect(0, 0, width, height, 3, 3)

    if len(values) < 2 or window_days <= 0:
        painter.setPen(_unknown_pen())
        painter.drawLine(QPointF(2.0, height - 2.0), QPointF(width - 2.0, height - 2.0))
        painter.end()
        return _img_tag(_data_uri(pix), width, height)

    # The y-axis stops at 100% plus a hair of headroom — NOT stretched to
    # fit however far a projection overshoots. Whether the trend clears the
    # cap by a little or a lot is the same answer ("yes, it's exceeded"),
    # and scaling the whole chart to fit a distant projected value used to
    # squeeze the actual 0-100% range — the part with real data in it —
    # into a thin band at the bottom. A trend that overshoots now just
    # runs off the top of the chart instead of dragging everything else
    # down to make room for it.
    y_max = max([v for _, v in values] + [100.0]) * 1.08

    pad = 2.0
    plot_w = width - 2 * pad
    plot_h = height - 2 * pad

    def xpix(elapsed_days: float) -> float:
        frac = max(0.0, min(1.0, elapsed_days / window_days))
        return pad + plot_w * frac

    def ypix(pct: float) -> float:
        frac = max(0.0, pct / y_max)
        return pad + plot_h * (1.0 - min(frac, 1.0))

    # The 100% cap, dashed red, spanning the whole window width — not just
    # the observed slice — so it reads as a fixed ceiling the chart is
    # measured against, not something tied to how much data exists yet.
    cap_pen = QPen(_LIMIT_LINE)
    cap_pen.setWidthF(1.0)
    cap_pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(cap_pen)
    y100 = ypix(100.0)
    painter.drawLine(QPointF(pad, y100), QPointF(width - pad, y100))

    pts = [QPointF(xpix(d), ypix(v)) for d, v in values]
    pen = QPen(color)
    pen.setWidthF(1.4)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    for a, b in zip(pts, pts[1:]):
        painter.drawLine(a, b)

    # "Now" — the last observed sample, not the end of the canvas (which is
    # the window's own end, usually still empty space to the right of it).
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_DOT_HALO)
    painter.drawEllipse(pts[-1], 2.2, 2.2)
    painter.setBrush(color)
    painter.drawEllipse(pts[-1], 1.4, 1.4)

    if projected_value is not None:
        trend_pen = QPen(_TREND_LINE)
        trend_pen.setWidthF(1.1)
        trend_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(trend_pen)
        end_pt = QPointF(xpix(window_days), ypix(projected_value))
        painter.drawLine(pts[-1], end_pt)

    painter.end()
    return _img_tag(_data_uri(pix), width, height)
