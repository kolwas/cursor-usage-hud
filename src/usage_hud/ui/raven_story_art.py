"""The artwork of the raven's long set pieces (see raven_stories): the mouse
with the key, the giant foot's shadow and dust, snow and a scarf, a kite, a
pond with a fish, a wizard's hat and flowers, soap bubbles, an egg and its
chick, a birthday cake with confetti, a disco ball.

Every painter is a pure function of its Prop (see raven_props); raven_art
adds them to its table so ``raven_art.paint`` finds them by kind.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QRadialGradient, QBrush

from usage_hud.ui import raven_glyph as rg
from usage_hud.ui.raven_draw import (
    CORAL,
    CREAM,
    GOLD,
    GOLD_DARK,
    LEAF,
    LILAC,
    MOUSE,
    ORANGE,
    PALETTE,
    PINK,
    PLUM,
    SKY,
    SNOW,
    TEAL,
    WATER,
    WOOD,
    WOOD_DARK,
    alpha,
    fill,
    heart,
    star,
    stroke,
)
from usage_hud.ui.raven_props import Prop

_GROUND = rg.GROUND_Y
_MID = rg.CENTRE_X + rg.RAVEN_BOX / 2.0  # scene x of the standing raven's middle
_CAKE_PINK = QColor("#f0a3b3")
_SPONGE = QColor("#f2e3b5")
_CHICK = QColor("#f6d35c")

BACK_KINDS = frozenset({"shadow", "snow", "wind", "pond", "beams", "floor"})


# --- the cage: a mouse with a key, a padlock, a wish -----------------------------
def _paint_mouse(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    phase, facing, key, upright = prop.extra
    painter.translate(x, y)
    if facing > 0:
        painter.scale(-1.0, 1.0)  # drawn facing left; mirrored to run right
    fill(painter, MOUSE)
    if upright:
        painter.drawEllipse(QPointF(0.0, -4.6), 2.6, 4.1)  # standing on its hind legs
        painter.drawEllipse(QPointF(-1.2, -9.5), 2.2, 1.9)
        fill(painter, PINK)
        painter.drawEllipse(QPointF(-3.2, -9.3), 0.55, 0.55)
        painter.drawEllipse(QPointF(0.2, -11.0), 0.8, 0.8)
        fill(painter, MOUSE)
        painter.drawEllipse(QPointF(0.0, -11.2), 1.4, 1.4)  # ear
        fill(painter, QColor(40, 36, 36))
        painter.drawEllipse(QPointF(-2.1, -10.0), 0.4, 0.4)
        stroke(painter, MOUSE, 0.9)
        painter.drawLine(QPointF(1.2, -2.0), QPointF(1.6, 0.0))
        painter.drawLine(QPointF(-1.0, -1.8), QPointF(-1.4, 0.0))
        if key:
            painter.drawLine(QPointF(-1.5, -6.0), QPointF(-3.0, -6.4))  # reaching out with the key
        else:
            wave = math.sin(phase * math.pi * 1.5) * 1.6
            painter.drawLine(QPointF(1.6, -6.2), QPointF(3.6, -9.0 + wave))  # waving goodbye
        stroke(painter, alpha(MOUSE, 200), 0.7)
        tail = QPainterPath(QPointF(2.4, -2.2))
        tail.quadTo(QPointF(6.0, -2.0), QPointF(6.4, -5.0))
        painter.drawPath(tail)
    else:
        painter.drawEllipse(QPointF(0.0, -2.9), 4.2, 2.7)
        painter.drawEllipse(QPointF(-4.2, -3.4), 2.3, 1.9)
        fill(painter, PINK)
        painter.drawEllipse(QPointF(-6.3, -3.4), 0.6, 0.6)
        painter.drawEllipse(QPointF(-3.3, -5.6), 0.9, 0.9)
        fill(painter, MOUSE)
        painter.drawEllipse(QPointF(-3.3, -5.7), 1.5, 1.5)
        fill(painter, PINK)
        painter.drawEllipse(QPointF(-3.3, -5.6), 0.8, 0.8)
        fill(painter, QColor(40, 36, 36))
        painter.drawEllipse(QPointF(-4.7, -3.9), 0.45, 0.45)
        stroke(painter, MOUSE, 0.9)
        step = 1.4 * math.sin(phase * math.pi)
        painter.drawLine(QPointF(-2.0, -0.6), QPointF(-2.0 + step, 0.2))
        painter.drawLine(QPointF(2.0, -0.6), QPointF(2.0 - step, 0.2))
        stroke(painter, alpha(MOUSE, 200), 0.7)
        tail = QPainterPath(QPointF(4.0, -3.0))
        tail.quadTo(QPointF(7.4, -3.4), QPointF(8.6, -6.2))
        painter.drawPath(tail)
    if key == 1:  # the key held in its teeth
        stroke(painter, GOLD, 0.8)
        painter.drawLine(QPointF(-6.2, -3.3), QPointF(-10.2, -3.3))
        painter.drawLine(QPointF(-9.4, -3.3), QPointF(-9.4, -2.0))
        painter.drawLine(QPointF(-8.4, -3.3), QPointF(-8.4, -2.3))
        painter.drawEllipse(QPointF(-11.1, -3.3), 1.0, 1.0)
    elif key == 2:  # turning in the lock
        stroke(painter, GOLD, 0.8)
        painter.drawLine(QPointF(-3.0, -6.4), QPointF(-4.6, -6.4))
        painter.drawEllipse(QPointF(-2.4, -6.4), 0.9, 0.9)


def _paint_padlock(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    opened = prop.extra[0]
    stroke(painter, GOLD_DARK, 0.9)
    shackle = QPainterPath(QPointF(x - 1.1, y - 1.0))
    lift = 1.3 * opened
    shackle.lineTo(x - 1.1, y - 2.4 - lift)
    shackle.quadTo(QPointF(x, y - 4.2 - lift), QPointF(x + 1.1, y - 2.4 - lift))
    shackle.lineTo(x + 1.1, y - 1.0 - (0.0 if not opened else 0.9))
    painter.drawPath(shackle)
    fill(painter, GOLD)
    painter.drawRoundedRect(QRectF(x - 1.9, y - 1.0, 3.8, 3.1), 0.7, 0.7)
    fill(painter, alpha(WOOD_DARK, 230))
    painter.drawEllipse(QPointF(x, y + 0.4), 0.4, 0.4)


def _paint_thought(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    s = prop.extra[0]
    stroke(painter, alpha(CREAM, 200), 0.7)
    painter.setBrush(alpha(CREAM, 30))
    painter.drawEllipse(QPointF(x - 5.6 * s, y + 7.4 * s), 1.0 * s, 1.0 * s)
    painter.drawEllipse(QPointF(x - 3.4 * s, y + 4.7 * s), 1.6 * s, 1.6 * s)
    painter.drawEllipse(QPointF(x, y), 5.8 * s, 5.0 * s)
    stroke(painter, GOLD, 0.9 * s)  # the key it wishes for
    painter.drawEllipse(QPointF(x - 2.3 * s, y - 0.4 * s), 1.4 * s, 1.4 * s)
    painter.drawLine(QPointF(x - 0.9 * s, y - 0.4 * s), QPointF(x + 3.2 * s, y - 0.4 * s))
    painter.drawLine(QPointF(x + 2.4 * s, y - 0.4 * s), QPointF(x + 2.4 * s, y + 1.4 * s))
    painter.drawLine(QPointF(x + 3.2 * s, y - 0.4 * s), QPointF(x + 3.2 * s, y + 1.0 * s))


# --- the foot: its shadow, the dust, dizzy stars, a falling feather --------------
def _paint_shadow(painter: QPainter, prop: Prop, _line: QColor) -> None:
    size = prop.a
    fill(painter, QColor(0, 0, 0, int(190 * size)))
    painter.drawEllipse(QPointF(_MID, _GROUND + 1.4), 25.0 * size, 3.6 * size)


def _paint_dust(painter: QPainter, prop: Prop, _line: QColor) -> None:
    age = prop.a
    fade = max(0.0, 1.0 - age / 5.5)
    for side in (-1.0, 1.0):
        for k in range(3):
            cx = _MID + side * (13.0 + 3.8 * age + k * 3.6)
            cy = _GROUND - 1.2 - 1.1 * age * (1.0 - k * 0.2) - k * 0.6
            r = 2.0 + 0.8 * age + (2 - k) * 0.5
            fill(painter, alpha(CREAM, 190 * fade))
            painter.drawEllipse(QPointF(cx, cy), r, r * 0.85)
    if age < 1.0:  # the jolt of the impact
        stroke(painter, alpha(CREAM, 230), 0.9)
        for k in range(11):
            a = math.pi * (0.06 + 0.88 * k / 10.0)
            painter.drawLine(
                QPointF(_MID + 17.0 * math.cos(a), _GROUND - 1.0 - 8.0 * math.sin(a)),
                QPointF(_MID + 24.0 * math.cos(a), _GROUND - 1.0 - 13.0 * math.sin(a)),
            )


def _paint_dizzy(painter: QPainter, prop: Prop, _line: QColor) -> None:
    frame = prop.a
    for k in range(3):
        a = frame * 0.95 + k * 2.094
        size = 1.5 + 0.35 * math.sin(a)
        star(painter, 40.0 + 8.5 * math.cos(a), 14.0 + 2.4 * math.sin(a), size, GOLD if k % 2 == 0 else CREAM)


def _paint_sweat(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    drop = QPainterPath(QPointF(x, y - 2.6))
    drop.cubicTo(QPointF(x + 0.6, y - 1.2), QPointF(x + 1.6, y - 0.2), QPointF(x, y + 1.1))
    drop.cubicTo(QPointF(x - 1.6, y - 0.2), QPointF(x - 0.6, y - 1.2), QPointF(x, y - 2.6))
    fill(painter, SKY)
    painter.drawPath(drop)
    fill(painter, alpha(CREAM, 200))
    painter.drawEllipse(QPointF(x - 0.4, y - 0.2), 0.35, 0.5)


def _paint_feather(painter: QPainter, prop: Prop, line_color: QColor) -> None:
    painter.translate(prop.a, prop.b)
    painter.rotate(prop.extra[0])
    fill(painter, alpha(line_color, 215))
    painter.drawEllipse(QPointF(0.0, 0.0), 3.4, 1.1)
    stroke(painter, alpha(WOOD_DARK, 220), 0.5)
    painter.drawLine(QPointF(-4.2, 0.0), QPointF(3.2, 0.0))


# --- snow ------------------------------------------------------------------------
def _paint_snow(painter: QPainter, prop: Prop, _line: QColor) -> None:
    frame, intensity = int(prop.a), prop.b
    for n in range(round(16 * intensity)):
        x = 2.5 + (n * 4.3) % 64.0 + 1.6 * math.sin(frame * 0.7 + n)
        y = (n * 11 + frame * 3.6) % 52.0 - 4.0
        if (20.0 < x < 50.0 and 17.0 < y < 40.0) or y > _GROUND:
            continue
        fill(painter, alpha(SNOW, 235))
        r = 0.7 + (n % 3) * 0.25
        painter.drawEllipse(QPointF(x, y), r, r)


def _paint_drift(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, size = prop.a, prop.b
    fill(painter, alpha(SNOW, 235))
    painter.drawChord(QRectF(x - 8.0 * size, _GROUND + 0.8 - 4.4 * size, 16.0 * size, 8.8 * size), 0, 180 * 16)
    painter.drawChord(QRectF(x - 13.0 * size, _GROUND + 0.8 - 2.4 * size, 9.0 * size, 4.8 * size), 0, 180 * 16)


def _paint_scarf(painter: QPainter, prop: Prop, _line: QColor) -> None:
    rx, ry = prop.a, prop.b
    ex, ey, phase, scale = prop.extra
    mx, my = (rx + ex) / 2.0 - 0.8, (ry + ey) / 2.0 + 1.4
    band = QPainterPath(QPointF(rx, ry))
    band.quadTo(QPointF(mx, my), QPointF(ex, ey))
    stroke(painter, CORAL, 2.9 * scale)
    painter.drawPath(band)
    stroke(painter, alpha(CREAM, 230), 0.7 * scale)
    painter.drawPath(band)
    for k, (length, dy) in enumerate(((9.5, 1.4), (7.0, 3.6))):
        tail = QPainterPath(QPointF(rx, ry + dy))
        for step in range(1, 9):
            t = step / 8.0
            tail.lineTo(rx - length * scale * t, ry + dy + 2.3 * math.sin(phase + t * 4.2 + k) * t)
        stroke(painter, CORAL, 2.2 * scale)
        painter.drawPath(tail)
        fill(painter, CREAM)
        painter.drawEllipse(
            QPointF(rx - length * scale, ry + dy + 2.3 * math.sin(phase + 4.2 + k)), 0.8 * scale, 0.8 * scale
        )


def _paint_snowcap(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    size = prop.extra[0]
    fill(painter, alpha(SNOW, 245))
    painter.drawEllipse(QPointF(x, y), 5.2 * size, 1.8 * size)
    painter.drawEllipse(QPointF(x - 2.6 * size, y - 1.2 * size), 2.0 * size, 1.2 * size)
    painter.drawEllipse(QPointF(x + 1.8 * size, y - 1.5 * size), 1.6 * size, 1.1 * size)


def _paint_puff(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    age, kind = prop.extra
    if kind < 0.5:  # a breath cloud in the cold
        fade = max(0.0, 1.0 - age / 3.0)
        for k in range(3):
            fill(painter, alpha(SNOW, 215 * fade))
            painter.drawEllipse(QPointF(x + 1.8 * age + k * 1.6, y - 1.0 * age - k * 0.7), 1.8 + 0.6 * age, 1.4 + 0.5 * age)
    else:  # snow shaken off
        fade = max(0.0, 1.0 - age / 4.5)
        for k in range(9):
            a = 2.0 * math.pi * k / 9.0
            fill(painter, alpha(SNOW, 240 * fade))
            painter.drawEllipse(
                QPointF(x + (2.0 + 3.4 * age) * math.cos(a), y + (2.0 + 3.0 * age) * math.sin(a) + 0.3 * age * age), 0.9, 0.9
            )


# --- the kite ---------------------------------------------------------------------
def _paint_wind(painter: QPainter, prop: Prop, _line: QColor) -> None:
    frame, strength = prop.a, prop.b
    stroke(painter, alpha(CREAM, 95 * strength), 0.7)
    for k in range(4):
        y = 5.0 + k * 8.2
        x = 66.0 - ((frame * 7.0 + k * 19.0) % 72.0)
        length = 8.0 + (k % 2) * 4.0
        painter.drawLine(QPointF(x, y), QPointF(x + length, y))
        painter.drawArc(QRectF(x + length - 2.0, y - 2.0, 3.0, 2.0), 0, 180 * 16)


def _paint_kite(painter: QPainter, prop: Prop, line_color: QColor) -> None:
    x, y = prop.a, prop.b
    rot, fx, fy, slack, scale = prop.extra
    rad = math.radians(rot)
    bottom = QPointF(x - 5.8 * scale * math.sin(rad), y + 5.8 * scale * math.cos(rad))
    if slack >= 0.0:
        string = QPainterPath(QPointF(fx, fy))
        string.quadTo(QPointF((fx + bottom.x()) / 2.0, (fy + bottom.y()) / 2.0 + slack * 5.0), bottom)
        stroke(painter, alpha(line_color, 180), 0.6)
        painter.drawPath(string)
    painter.translate(x, y)
    painter.rotate(rot)
    painter.scale(scale, scale)
    tail = QPainterPath(QPointF(0.0, 5.8))
    for step in range(1, 11):
        t = step / 10.0
        tail.lineTo(2.0 * math.sin(t * 6.0 + rad * 3.0), 5.8 + 13.0 * t)
    stroke(painter, alpha(CREAM, 190), 0.5)
    painter.drawPath(tail)
    for k, color in enumerate((TEAL, GOLD, CORAL)):
        t = (k + 1) * 0.28
        fill(painter, color)
        bx, by = 2.0 * math.sin(t * 6.0 + rad * 3.0), 5.8 + 13.0 * t
        painter.drawEllipse(QPointF(bx - 1.1, by), 1.2, 0.8)
        painter.drawEllipse(QPointF(bx + 1.1, by), 1.2, 0.8)
    left = QPainterPath(QPointF(0.0, -5.2))
    left.lineTo(-3.8, 0.0)
    left.lineTo(0.0, 5.8)
    left.closeSubpath()
    right = QPainterPath(QPointF(0.0, -5.2))
    right.lineTo(3.8, 0.0)
    right.lineTo(0.0, 5.8)
    right.closeSubpath()
    fill(painter, GOLD)
    painter.drawPath(left)
    fill(painter, CORAL)
    painter.drawPath(right)
    stroke(painter, alpha(CREAM, 210), 0.5)
    painter.drawLine(QPointF(0.0, -5.2), QPointF(0.0, 5.8))
    painter.drawLine(QPointF(-3.8, 0.0), QPointF(3.8, 0.0))


# --- the pond, the rod, the fish ---------------------------------------------------
def _paint_pond(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, size = prop.a, prop.b
    ripple = prop.extra[0]
    cy = _GROUND + 0.9
    fill(painter, alpha(WATER, 230))
    painter.drawEllipse(QPointF(x, cy), 9.8 * size, 2.9 * size)
    stroke(painter, alpha(SKY, 130), 0.5)
    painter.drawEllipse(QPointF(x, cy), 6.6 * size, 1.7 * size)
    if ripple > 0.0:
        stroke(painter, alpha(CREAM, 170 * (1.0 - ripple)), 0.5)
        painter.drawEllipse(QPointF(x + 1.8, cy), 1.5 + 6.0 * ripple, 0.5 + 1.7 * ripple)
    if size > 0.7:  # reeds at the edge
        stroke(painter, LEAF, 0.8)
        painter.drawLine(QPointF(x + 9.0, cy), QPointF(x + 8.2, cy - 6.5 * size))
        painter.drawLine(QPointF(x + 9.8, cy), QPointF(x + 10.4, cy - 4.5 * size))
        fill(painter, WOOD)
        painter.drawEllipse(QPointF(x + 8.3, cy - 6.0 * size), 0.6, 1.2)


def _paint_rod(painter: QPainter, prop: Prop, line_color: QColor) -> None:
    tip_x, tip_y = prop.a, prop.b
    hold_x, hold_y, float_x, float_y, line = prop.extra
    rod = QPainterPath(QPointF(hold_x, hold_y))
    rod.quadTo(QPointF((hold_x + tip_x) / 2.0 + 0.5, (hold_y + tip_y) / 2.0 - 0.8), QPointF(tip_x, tip_y))
    stroke(painter, WOOD, 1.1)
    painter.drawPath(rod)
    if line:
        stroke(painter, alpha(CREAM, 210), 0.5)
        thread = QPainterPath(QPointF(tip_x, tip_y))
        thread.quadTo(QPointF(tip_x + 1.2, (tip_y + float_y) / 2.0), QPointF(float_x, float_y))
        painter.drawPath(thread)
        fill(painter, CREAM)
        painter.drawEllipse(QPointF(float_x, float_y + 0.5), 0.9, 0.8)
        fill(painter, CORAL)
        painter.drawEllipse(QPointF(float_x, float_y - 0.4), 1.0, 0.9)


def _paint_fish(painter: QPainter, prop: Prop, _line: QColor) -> None:
    painter.translate(prop.a, prop.b)
    painter.rotate(prop.extra[0])
    painter.scale(prop.extra[1], prop.extra[1])
    tail = QPainterPath(QPointF(-3.6, 0.0))
    tail.lineTo(-6.9, -2.5)
    tail.lineTo(-6.9, 2.5)
    tail.closeSubpath()
    fill(painter, GOLD)
    painter.drawPath(tail)
    fin = QPainterPath(QPointF(-1.2, -1.9))
    fin.lineTo(0.4, -3.9)
    fin.lineTo(1.6, -1.9)
    fin.closeSubpath()
    painter.drawPath(fin)
    fill(painter, ORANGE)
    painter.drawEllipse(QPointF(0.0, 0.0), 4.2, 2.2)
    fill(painter, alpha(CREAM, 190))
    painter.drawEllipse(QPointF(0.0, 0.9), 3.0, 0.9)
    fill(painter, QColor(40, 36, 36))
    painter.drawEllipse(QPointF(2.3, -0.5), 0.5, 0.5)


def _paint_fishshadow(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    size = prop.extra[0]
    fill(painter, QColor(8, 36, 50, 160))
    painter.drawEllipse(QPointF(x, y), 3.6 * size, 1.0 * size)
    tail = QPainterPath(QPointF(x - 3.0 * size, y))
    tail.lineTo(x - 5.2 * size, y - 0.9 * size)
    tail.lineTo(x - 5.2 * size, y + 0.9 * size)
    tail.closeSubpath()
    painter.drawPath(tail)


def _paint_splash(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    age = prop.extra[0]
    fade = max(0.0, 1.0 - age / 4.5)
    for k in range(7):
        a = math.radians(-170.0 + k * 22.0)
        dist = 1.5 + 2.4 * age
        fill(painter, alpha(SKY, 235 * fade))
        painter.drawEllipse(QPointF(x + dist * math.cos(a), y + dist * math.sin(a) + 0.35 * age * age), 0.65, 0.65)
    stroke(painter, alpha(CREAM, 150 * fade), 0.5)
    painter.drawEllipse(QPointF(x, y + 0.6), 1.5 + 2.2 * age, 0.5 + 0.5 * age)


# --- the wizard ---------------------------------------------------------------------
def _paint_hat(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    angle, scale, kind = prop.extra
    painter.translate(x, y)
    painter.rotate(angle)
    painter.scale(scale, scale)
    if kind < 0.5:  # a wizard's hat with a bent tip and a golden star
        brim = QColor(PLUM).darker(125)
        fill(painter, brim)
        painter.drawEllipse(QPointF(0.0, 0.2), 8.2, 1.9)
        cone = QPainterPath(QPointF(-5.3, 0.0))
        cone.cubicTo(QPointF(-4.6, -5.2), QPointF(-1.6, -9.5), QPointF(3.8, -12.8))
        cone.cubicTo(QPointF(3.2, -8.5), QPointF(4.6, -4.0), QPointF(5.3, 0.0))
        cone.closeSubpath()
        fill(painter, PLUM)
        painter.drawPath(cone)
        stroke(painter, GOLD, 0.9)
        painter.drawLine(QPointF(-5.1, -1.4), QPointF(5.1, -1.4))
        star(painter, -0.8, -6.0, 1.7, GOLD)
        star(painter, 1.9, -3.2, 0.9, CREAM)
    else:  # a party hat: stripes and a pompom
        cone = QPainterPath(QPointF(-4.0, 0.0))
        cone.lineTo(0.0, -11.0)
        cone.lineTo(4.0, 0.0)
        cone.closeSubpath()
        fill(painter, CORAL)
        painter.drawPath(cone)
        stroke(painter, alpha(CREAM, 235), 1.0)
        painter.drawLine(QPointF(-3.0, -2.4), QPointF(2.0, -7.2))
        painter.drawLine(QPointF(-1.2, -1.0), QPointF(3.4, -4.4))
        fill(painter, TEAL)
        painter.drawEllipse(QPointF(0.0, 0.1), 4.3, 0.9)
        fill(painter, GOLD)
        painter.drawEllipse(QPointF(0.0, -11.2), 1.5, 1.5)


def _paint_bloom(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, size = prop.a, prop.b
    colour = (CORAL, GOLD, LILAC, PINK)[int(prop.extra[0]) % 4]
    base = _GROUND + 0.6
    top = base - 9.5 * size
    stroke(painter, LEAF, 0.9)
    stem = QPainterPath(QPointF(x, base))
    stem.quadTo(QPointF(x + 0.9, (base + top) / 2.0), QPointF(x, top))
    painter.drawPath(stem)
    fill(painter, LEAF)
    painter.drawEllipse(QPointF(x + 1.7 * size, base - 3.6 * size), 1.7 * size, 0.8 * size)
    for k in range(5):
        a = 2.0 * math.pi * k / 5.0 - math.pi / 2.0
        fill(painter, colour)
        painter.drawEllipse(QPointF(x + 1.9 * size * math.cos(a), top + 1.9 * size * math.sin(a)), 1.7 * size, 1.7 * size)
    fill(painter, CREAM)
    painter.drawEllipse(QPointF(x, top), 1.1 * size, 1.1 * size)


# --- soap bubbles ---------------------------------------------------------------------
def _paint_bubble(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    r = prop.extra[0]
    stroke(painter, alpha(SKY, 175), 0.7)
    painter.setBrush(alpha(SKY, 36))
    painter.drawEllipse(QPointF(x, y), r, r)
    stroke(painter, alpha(CREAM, 230), 0.8)
    painter.drawArc(QRectF(x - r * 0.64, y - r * 0.64, r * 1.28, r * 1.28), 105 * 16, 55 * 16)
    stroke(painter, alpha(LILAC, 160), 0.6)
    painter.drawArc(QRectF(x - r * 0.64, y - r * 0.64, r * 1.28, r * 1.28), 285 * 16, 40 * 16)


def _paint_pop(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    age = prop.extra[0]
    fade = max(0.0, 1.0 - age / 3.5)
    for k in range(8):
        a = 2.0 * math.pi * k / 8.0
        r1, r2 = 2.2 + 1.6 * age, 4.8 + 1.6 * age
        stroke(painter, alpha(SKY, 230 * fade), 0.8)
        painter.drawLine(QPointF(x + r1 * math.cos(a), y + r1 * math.sin(a)), QPointF(x + r2 * math.cos(a), y + r2 * math.sin(a)))
        fill(painter, alpha(CREAM, 230 * fade))
        painter.drawEllipse(QPointF(x + (r2 + 0.9) * math.cos(a), y + (r2 + 0.9) * math.sin(a)), 0.5, 0.5)


# --- the egg and the chick ---------------------------------------------------------------
def _egg_path() -> QPainterPath:
    egg = QPainterPath(QPointF(0.0, 0.0))
    egg.cubicTo(QPointF(-4.6, 0.0), QPointF(-4.9, -5.0), QPointF(-3.0, -7.6))
    egg.cubicTo(QPointF(-1.8, -9.4), QPointF(1.8, -9.4), QPointF(3.0, -7.6))
    egg.cubicTo(QPointF(4.9, -5.0), QPointF(4.6, 0.0), QPointF(0.0, 0.0))
    return egg


def _paint_egg(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, size = prop.a, prop.b
    wobble, crack = prop.extra
    painter.translate(x, _GROUND + 0.6)
    painter.rotate(wobble)
    painter.scale(size, size)
    fill(painter, CREAM)
    painter.drawPath(_egg_path())
    fill(painter, alpha(CORAL, 235))
    for sx, sy, r in ((-1.6, -3.2, 0.9), (1.9, -5.4, 0.8), (0.5, -1.5, 0.6), (-1.9, -6.2, 0.55)):
        painter.drawEllipse(QPointF(sx, sy), r, r)
    if crack > 0.0:
        stroke(painter, WOOD_DARK, 0.6)
        zig = [(-3.8, -4.6), (-2.0, -5.9), (-0.4, -4.3), (1.4, -5.9), (3.5, -4.5)]
        keep = max(2, round(len(zig) * crack))
        path = QPainterPath(QPointF(*zig[0]))
        for px, py in zig[1:keep]:
            path.lineTo(px, py)
        painter.drawPath(path)


def _paint_shell(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    angle, side, strength = prop.extra
    painter.translate(x, y)
    painter.rotate(angle)
    painter.scale(side, 1.0)
    half = QPainterPath(QPointF(-3.6, 0.0))
    half.lineTo(-2.2, -1.7)
    half.lineTo(-0.8, 0.0)
    half.lineTo(0.8, -1.7)
    half.lineTo(2.2, 0.0)
    half.lineTo(3.6, -1.4)
    half.cubicTo(QPointF(4.0, -5.0), QPointF(1.8, -6.6), QPointF(0.0, -6.6))
    half.cubicTo(QPointF(-1.8, -6.6), QPointF(-4.0, -5.0), QPointF(-3.6, 0.0))
    fill(painter, alpha(CREAM, 255 * strength))
    painter.drawPath(half)


def _paint_chick(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    facing, squash = prop.extra
    painter.translate(x, y)
    if facing < 0:
        painter.scale(-1.0, 1.0)
    painter.scale(1.0, squash)
    stroke(painter, ORANGE, 0.7)
    painter.drawLine(QPointF(-1.0, -0.6), QPointF(-1.2, 0.2))
    painter.drawLine(QPointF(1.0, -0.6), QPointF(1.2, 0.2))
    fill(painter, _CHICK)
    painter.drawEllipse(QPointF(0.0, -3.5), 3.9, 3.5)
    fill(painter, alpha(GOLD, 255))
    painter.drawEllipse(QPointF(-1.0, -3.0), 1.7, 1.2)  # a wing
    tuft = QPainterPath(QPointF(-0.6, -6.9))
    tuft.quadTo(QPointF(-0.2, -8.6), QPointF(0.9, -7.5))
    stroke(painter, _CHICK, 0.8)
    painter.drawPath(tuft)
    beak = QPainterPath(QPointF(3.4, -4.9))
    beak.lineTo(5.7, -4.1)
    beak.lineTo(3.4, -3.4)
    beak.closeSubpath()
    fill(painter, ORANGE)
    painter.drawPath(beak)
    fill(painter, QColor(40, 36, 36))
    painter.drawEllipse(QPointF(1.9, -5.0), 0.55, 0.55)


def _paint_heart(painter: QPainter, prop: Prop, _line: QColor) -> None:
    size, strength = prop.extra
    heart(painter, prop.a, prop.b, size, alpha(PINK, 255 * strength))


# --- the birthday ------------------------------------------------------------------------------
def _paint_cake(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, size = prop.a, prop.b
    flame, bend = prop.extra
    painter.translate(x, _GROUND + 0.9)
    painter.scale(size, size)
    fill(painter, _SPONGE)
    painter.drawRoundedRect(QRectF(-6.2, -5.4, 12.4, 5.4), 1.0, 1.0)
    fill(painter, CORAL)
    painter.drawRoundedRect(QRectF(-6.2, -5.4, 12.4, 1.5), 0.7, 0.7)
    for dx in (-4.5, -1.5, 2.0, 5.0):
        painter.drawEllipse(QPointF(dx, -3.9), 0.8, 1.0)
    fill(painter, _CAKE_PINK)
    painter.drawRoundedRect(QRectF(-4.0, -8.8, 8.0, 3.4), 0.9, 0.9)
    fill(painter, alpha(CREAM, 240))
    painter.drawRoundedRect(QRectF(-0.7, -12.6, 1.4, 3.8), 0.4, 0.4)
    stroke(painter, GOLD, 0.5)
    painter.drawLine(QPointF(-0.7, -11.6), QPointF(0.7, -11.0))
    painter.drawLine(QPointF(-0.7, -10.2), QPointF(0.7, -9.6))
    if flame > 0.0:
        glow = QRadialGradient(QPointF(bend * 1.2, -14.2), 5.0)
        glow.setColorAt(0.0, alpha(GOLD, 120 * flame))
        glow.setColorAt(1.0, alpha(GOLD, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(bend * 1.2, -14.2), 5.0, 5.0)
        tip = QPointF(bend * 2.2, -13.9 - 3.0 * flame)
        drop = QPainterPath(tip)
        drop.cubicTo(QPointF(1.4 * flame, -14.2), QPointF(1.1 * flame, -12.8), QPointF(0.0, -12.7))
        drop.cubicTo(QPointF(-1.1 * flame, -12.8), QPointF(-1.4 * flame, -14.2), tip)
        fill(painter, ORANGE)
        painter.drawPath(drop)
        fill(painter, GOLD)
        painter.drawEllipse(QPointF(0.0, -13.2), 0.5 * flame, 0.8 * flame)


def _paint_confetti(painter: QPainter, prop: Prop, _line: QColor) -> None:
    age = prop.a
    strength = 1.0 if age < 6.5 else max(0.0, 1.0 - (age - 6.5) / 3.5)
    colors = (CORAL, GOLD, TEAL, LILAC, PINK)
    for k in range(20):
        x = 3.5 + (k * 47) % 62 + 2.4 * math.sin(age * 0.9 + k * 1.7)
        y = -6.0 + (k * 13) % 9 + age * 3.9 + (k % 4) * 0.6
        if y > _GROUND or y < -2.0:
            continue
        painter.save()
        painter.translate(x, y)
        painter.rotate(k * 37 + age * (40 + (k % 5) * 12))
        fill(painter, alpha(colors[k % 5], 255 * strength))
        painter.drawRect(QRectF(-1.1, -0.6, 2.2, 1.2))
        painter.restore()


def _paint_smoke(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    age = prop.extra[0]
    stroke(painter, alpha(QColor("#c7cbd1"), 170 * max(0.0, 1.0 - age / 5.0)), 0.9)
    path = QPainterPath(QPointF(x, y))
    for step in range(1, 10):
        t = step / 9.0
        path.lineTo(x + 1.7 * math.sin(t * 5.0 + age) * t, y - t * (4.0 + 3.0 * age))
    painter.drawPath(path)


# --- the disco ---------------------------------------------------------------------------------
def _paint_discoball(painter: QPainter, prop: Prop, _line: QColor) -> None:
    ball_y, frame = prop.a, prop.b
    stroke(painter, alpha(CREAM, 160), 0.5)
    painter.drawLine(QPointF(_MID, -2.0), QPointF(_MID, ball_y - 4.2))
    fill(painter, QColor("#b9c1ca"))
    painter.drawEllipse(QPointF(_MID, ball_y), 4.3, 4.3)
    stroke(painter, alpha(QColor("#6b7480"), 210), 0.4)
    for k in (-0.55, 0.0, 0.55):
        painter.drawEllipse(QPointF(_MID, ball_y), 4.3 * abs(k) + 0.01, 4.3)
    for dy in (-2.2, 0.0, 2.2):
        painter.drawLine(QPointF(_MID - 4.2, ball_y + dy), QPointF(_MID + 4.2, ball_y + dy))
    for k in range(3):
        a = frame * 0.8 + k * 2.1
        star(painter, _MID + 2.2 * math.cos(a), ball_y - 0.6 + 2.0 * math.sin(a), 1.1, CREAM)


def _paint_beams(painter: QPainter, prop: Prop, _line: QColor) -> None:
    frame, strength, ball_y = prop.a, prop.b, prop.extra[0]
    for k, color in enumerate((CORAL, TEAL, GOLD)):
        foot = _MID + 26.0 * math.sin(frame * 0.55 + k * 2.1)
        beam = QPainterPath(QPointF(_MID, ball_y))
        beam.lineTo(foot - 3.4, _GROUND + 1.0)
        beam.lineTo(foot + 3.4, _GROUND + 1.0)
        beam.closeSubpath()
        fill(painter, alpha(color, 105 * strength))
        painter.drawPath(beam)


def _paint_floor(painter: QPainter, prop: Prop, _line: QColor) -> None:
    frame, strength = int(prop.a), prop.b
    for k in range(9):
        fill(painter, alpha(PALETTE[(k + frame) % 4], 205 * strength))
        painter.drawRoundedRect(QRectF(8.0 + k * 5.9, _GROUND + 0.8, 5.3, 2.4), 0.5, 0.5)


PAINTERS: dict[str, Callable[[QPainter, Prop, QColor], None]] = {
    "mouse": _paint_mouse,
    "padlock": _paint_padlock,
    "thought": _paint_thought,
    "shadow": _paint_shadow,
    "dust": _paint_dust,
    "dizzy": _paint_dizzy,
    "sweat": _paint_sweat,
    "feather": _paint_feather,
    "snow": _paint_snow,
    "drift": _paint_drift,
    "scarf": _paint_scarf,
    "snowcap": _paint_snowcap,
    "puff": _paint_puff,
    "wind": _paint_wind,
    "kite": _paint_kite,
    "pond": _paint_pond,
    "rod": _paint_rod,
    "fish": _paint_fish,
    "fishshadow": _paint_fishshadow,
    "splash": _paint_splash,
    "hat": _paint_hat,
    "bloom": _paint_bloom,
    "bubble": _paint_bubble,
    "pop": _paint_pop,
    "egg": _paint_egg,
    "shell": _paint_shell,
    "chick": _paint_chick,
    "heart": _paint_heart,
    "cake": _paint_cake,
    "confetti": _paint_confetti,
    "smoke": _paint_smoke,
    "discoball": _paint_discoball,
    "beams": _paint_beams,
    "floor": _paint_floor,
}
