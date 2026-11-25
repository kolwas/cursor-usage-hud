"""The palette and the few drawing helpers shared by the artwork of the
raven's scenes (raven_art, raven_story_art): a small, soft set of colours
that sits well on the chip's dark olive panel."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

CORAL = QColor("#e8705b")
CORAL_DARK = QColor("#b4503f")
GOLD = QColor("#efbf4f")
GOLD_DARK = QColor("#b98a2a")
TEAL = QColor("#5cc2b0")
SKY = QColor("#8fbfe6")
PINK = QColor("#ec97aa")
PINK_DARK = QColor("#c46f85")
LILAC = QColor("#ab9de6")
PLUM = QColor("#7566b8")
CREAM = QColor("#f4edcb")
SNOW = QColor("#e9f1f6")
WOOD = QColor("#8f6440")
WOOD_DARK = QColor("#684529")
DIRT = QColor("#6f5538")
ORANGE = QColor("#f2a444")
MOUSE = QColor("#aeb0b8")
WATER = QColor("#3b7a94")
LEAF = QColor("#6fae67")
PALETTE = (CORAL, GOLD, TEAL, LILAC)


def alpha(color: QColor, value: float) -> QColor:
    out = QColor(color)
    out.setAlpha(max(0, min(255, int(value))))
    return out


def fill(painter: QPainter, color: QColor) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)


def stroke(painter: QPainter, color: QColor, width: float) -> None:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)


def star(painter: QPainter, x: float, y: float, size: float, color: QColor) -> None:
    """A four-pointed twinkle."""
    path = QPainterPath()
    for k in range(8):
        radius = size if k % 2 == 0 else size * 0.3
        angle = math.radians(k * 45.0 - 90.0)
        point = QPointF(x + radius * math.cos(angle), y + radius * math.sin(angle))
        if k == 0:
            path.moveTo(point)
        else:
            path.lineTo(point)
    path.closeSubpath()
    fill(painter, color)
    painter.drawPath(path)


def heart(painter: QPainter, x: float, y: float, size: float, color: QColor) -> None:
    path = QPainterPath(QPointF(x, y + size * 0.9))
    path.cubicTo(QPointF(x - size * 1.6, y - size * 0.2), QPointF(x - size * 0.6, y - size * 1.3), QPointF(x, y - size * 0.35))
    path.cubicTo(QPointF(x + size * 0.6, y - size * 1.3), QPointF(x + size * 1.6, y - size * 0.2), QPointF(x, y + size * 0.9))
    fill(painter, color)
    painter.drawPath(path)
