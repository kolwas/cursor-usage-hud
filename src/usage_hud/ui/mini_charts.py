"""Tiny inline charts for the chip/panel — a pie "clock" and a burn timeline.

QLabel's RichText engine has no CSS gradients/canvas, so these are rasterized
with QPainter and handed back as ``data:image/png;base64,...`` strings to drop
straight into an ``<img>`` tag. Sizes are chip-scale (a few px), not dashboard
widgets.
"""

from __future__ import annotations

import base64

from PySide6.QtCore import QBuffer, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

_TRACK = QColor(255, 255, 255, 36)
_ELAPSED = QColor(255, 255, 255, 100)


def _data_uri(pix: QPixmap) -> str:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buf, "PNG")
    encoded = base64.b64encode(bytes(buf.data())).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _img_tag(data_uri: str, width: int, height: int, *, valign: str = "middle") -> str:
    return f'<img src="{data_uri}" width="{width}" height="{height}" style="vertical-align:{valign};">'


def clock_pie_icon(
    frac_remaining: float | None, color: QColor, *, size: int = 12
) -> str:
    """A tiny pie wedge that shrinks as the window's time runs out.

    The wedge's ANGLE tracks time (how much of the window is left); its
    COLOR tracks usage severity — the two are independent, as asked: a clock
    running down safely stays green, one running down while nearly full
    turns red, regardless of how much time remains.
    """
    if frac_remaining is None:
        frac_remaining = 1.0
    frac_remaining = max(0.0, min(1.0, frac_remaining))

    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
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
    elapsed_frac: float,
    exhaust_frac: float | None,
    marker_color: QColor,
    *,
    width: int = 30,
    height: int = 8,
) -> str:
    """A tiny horizontal timeline: cycle_start..cycle_end as the full bar,
    filled up to "now", with a dot marking the projected exhaustion date —
    the prediction as a picture instead of a signed day count.
    """
    elapsed_frac = max(0.0, min(1.0, elapsed_frac))

    pix = QPixmap(width, height)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    track_y = height / 2 - 1
    painter.setBrush(_TRACK)
    painter.drawRoundedRect(0, int(track_y), width, 2, 1, 1)

    if elapsed_frac > 0:
        painter.setBrush(_ELAPSED)
        painter.drawRoundedRect(0, int(track_y), max(2, round(width * elapsed_frac)), 2, 1, 1)

    if exhaust_frac is not None:
        x = max(0.0, min(1.0, exhaust_frac)) * (width - 3) + 1.5
        painter.setBrush(marker_color)
        painter.drawEllipse(QPointF(x, height / 2), 2.4, 2.4)

    painter.end()
    return _img_tag(_data_uri(pix), width, height)
