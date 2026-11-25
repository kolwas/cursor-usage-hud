"""The artwork of the raven's adventures (see raven_adventures): umbrella,
rain and rainbow, butterfly, worm, treasure chest, moon and stars, notes,
balloons, fireworks.

The raven itself is sand-coloured line art; these props add a small, soft
palette on top of the chip's dark olive panel. Every painter is a pure
function of its Prop (see raven_props), so a frame is fully described by
data; ``paint`` picks the painter for a prop's kind.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QRadialGradient

from usage_hud.ui import raven_glyph as rg
from usage_hud.ui import raven_story_art
from usage_hud.ui.raven_draw import (
    CORAL,
    CORAL_DARK,
    CREAM,
    DIRT,
    GOLD,
    GOLD_DARK,
    LILAC,
    ORANGE,
    PALETTE,
    PINK,
    PINK_DARK,
    SKY,
    TEAL,
    WOOD,
    WOOD_DARK,
)
from usage_hud.ui.raven_draw import alpha as _alpha
from usage_hud.ui.raven_draw import fill as _fill
from usage_hud.ui.raven_draw import star as _star
from usage_hud.ui.raven_draw import stroke as _stroke
from usage_hud.ui.raven_props import Prop

_GROUND = rg.GROUND_Y
_PALETTE = PALETTE

# Drawn before the raven (sky, weather) — everything else in front of it.
BACK_KINDS = frozenset({"rainbow", "rain", "moon", "stars", "burst"})


# --- rain, umbrella, rainbow ---------------------------------------------------
_RAIN_COLUMNS = (3.0, 9.0, 15.0, 21.0, 27.0, 33.0, 39.0, 45.0, 51.0, 57.0, 63.0)
_RAIN_ORDER = (5, 0, 8, 3, 10, 1, 6, 9, 2, 7, 4)  # which columns fall first
_UMBRELLA_R = 15.5


def _dome_y(cx: float, base: float, radius: float, x: float) -> float:
    inside = max(0.0, 1.0 - ((x - cx) / radius) ** 2)
    return base - radius * 0.74 * math.sqrt(inside)


def _paint_rain(painter: QPainter, prop: Prop, _line: QColor) -> None:
    frame, intensity = int(prop.a), prop.b
    opened, cx, base = prop.extra
    sheltered = opened > 0.5
    _stroke(painter, _alpha(SKY, 215), 0.9)
    count = round(len(_RAIN_COLUMNS) * intensity)
    for n, col in enumerate(_RAIN_ORDER[:count]):
        x = _RAIN_COLUMNS[col]
        y = (n * 17 + frame * 11) % 50 - 6.0
        if 20.0 < x < 50.0 and 17.0 < y < 40.0:
            continue  # the raven stands in the way
        if sheltered and abs(x - cx) < _UMBRELLA_R and y + 4.0 > _dome_y(cx, base, _UMBRELLA_R, x):
            continue  # the umbrella keeps it off
        if y + 4.0 > _GROUND:
            _stroke(painter, _alpha(SKY, 150), 0.6)
            painter.drawEllipse(QPointF(x, _GROUND + 0.6), 1.7, 0.6)  # a ripple
            _stroke(painter, _alpha(SKY, 215), 0.9)
            continue
        painter.drawLine(QPointF(x, y), QPointF(x - 1.3, y + 4.0))


def _paint_umbrella(painter: QPainter, prop: Prop, line_color: QColor) -> None:
    cx, base = prop.a, prop.b
    opened, hx, hy = prop.extra
    w, h = 0.16 + 0.84 * opened, 0.5 + 0.5 * opened
    left, right = cx - _UMBRELLA_R * w, cx + _UMBRELLA_R * w
    top = base - _UMBRELLA_R * 0.74 * h
    _stroke(painter, line_color, 1.1)
    painter.drawLine(QPointF(cx, base), QPointF(hx, hy))
    dome = QPainterPath()
    dome.moveTo(left, base)
    dome.cubicTo(
        QPointF(left, top + (base - top) * 0.18), QPointF(cx - (cx - left) * 0.55, top), QPointF(cx, top)
    )
    dome.cubicTo(
        QPointF(cx + (right - cx) * 0.55, top), QPointF(right, top + (base - top) * 0.18), QPointF(right, base)
    )
    scallops = 4
    step = (right - left) / scallops
    for k in range(scallops):  # the wavy hem
        dome.quadTo(QPointF(right - (k + 0.5) * step, base + 2.6 * h), QPointF(right - (k + 1) * step, base))
    dome.closeSubpath()
    _fill(painter, CORAL)
    painter.drawPath(dome)
    if opened > 0.45:
        _stroke(painter, _alpha(CORAL_DARK, 230), 0.8)
        for side in (-1.0, 1.0):
            rib = QPainterPath(QPointF(cx, top))
            rib.quadTo(QPointF(cx + side * (right - cx) * 0.42, top + (base - top) * 0.2), QPointF(cx + side * (right - cx) * 0.5, base))
            painter.drawPath(rib)
    _fill(painter, GOLD)
    painter.drawEllipse(QPointF(cx, top - 0.5), 0.9, 0.9)


def _paint_rainbow(painter: QPainter, prop: Prop, _line: QColor) -> None:
    centre_x, centre_y = 34.0, 41.0
    for k, color in enumerate((CORAL, GOLD, TEAL)):
        radius = 31.0 - 3.0 * k
        _stroke(painter, _alpha(color, 215 * prop.a), 2.6)
        painter.drawArc(QRectF(centre_x - radius, centre_y - radius, 2 * radius, 2 * radius), 0, 180 * 16)


# --- butterfly -----------------------------------------------------------------
def _paint_butterfly(painter: QPainter, prop: Prop, line_color: QColor) -> None:
    x, y = prop.a, prop.b
    spread = prop.extra[0]
    _fill(painter, ORANGE)
    for side in (-1.0, 1.0):
        painter.save()
        painter.translate(x + side * 2.3 * spread, y - 1.2)
        painter.rotate(side * 22.0)
        painter.drawEllipse(QPointF(0.0, 0.0), 2.7 * spread + 0.2, 2.5)
        painter.restore()
        painter.drawEllipse(QPointF(x + side * 1.7 * spread, y + 1.7), 1.9 * spread + 0.2, 1.8)
    _fill(painter, _alpha(CREAM, 230))
    for side in (-1.0, 1.0):
        painter.drawEllipse(QPointF(x + side * 3.3 * spread, y - 1.9), 0.55, 0.55)
    _stroke(painter, line_color, 1.2)
    painter.drawLine(QPointF(x, y - 2.2), QPointF(x, y + 2.4))
    _stroke(painter, _alpha(line_color, 200), 0.6)
    painter.drawLine(QPointF(x, y - 2.2), QPointF(x - 1.3, y - 4.0))
    painter.drawLine(QPointF(x, y - 2.2), QPointF(x + 1.3, y - 4.0))


# --- worm ----------------------------------------------------------------------
def _paint_mound(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, size = prop.a, prop.b
    _fill(painter, DIRT)
    painter.drawChord(QRectF(x - 5.0 * size, _GROUND + 0.6 - 2.6 * size, 10.0 * size, 5.2 * size), 0, 180 * 16)
    if size > 0.6:
        _fill(painter, _alpha(WOOD, 200))
        for dx, dy in ((-2.6, -0.6), (1.4, -1.5), (3.0, -0.4)):
            painter.drawEllipse(QPointF(x + dx * size, _GROUND + 0.4 + dy * size), 0.5, 0.4)


def _paint_worm(painter: QPainter, prop: Prop, _line: QColor) -> None:
    tip_x, tip_y = prop.a, prop.b
    base_x, base_y, amp, phase = prop.extra
    dx, dy = tip_x - base_x, tip_y - base_y
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    points = []
    for k in range(15):
        u = k / 14.0
        wave = amp * math.sin(u * math.pi * 2.6 + phase) * math.sin(u * math.pi) * 2.0
        points.append(QPointF(base_x + dx * u + nx * wave, base_y + dy * u + ny * wave))
    for width, color in ((2.7, PINK), (1.0, _alpha(CREAM, 120))):
        _stroke(painter, color, width)
        path = QPainterPath(points[0])
        for p in points[1:]:
            path.lineTo(p)
        painter.drawPath(path)
    ring = points[len(points) // 3]
    _stroke(painter, PINK_DARK, 0.7)
    painter.drawLine(QPointF(ring.x() - nx * 1.4, ring.y() - ny * 1.4), QPointF(ring.x() + nx * 1.4, ring.y() + ny * 1.4))


# --- treasure ------------------------------------------------------------------
def _paint_chest(painter: QPainter, prop: Prop, _line: QColor) -> None:
    cx, lid_open = prop.a, prop.b
    size, glow = prop.extra
    width, height, lid_h = 13.0 * size, 6.6 * size, 3.4 * size
    gy = _GROUND + 0.8
    left, right, top = cx - width / 2.0, cx + width / 2.0, gy - height
    if glow > 0.0:
        halo = QRadialGradient(QPointF(cx, top - 1.0), 13.0)
        halo.setColorAt(0.0, _alpha(GOLD, 190 * glow))
        halo.setColorAt(1.0, _alpha(GOLD, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(QPointF(cx, top - 1.0), 13.0, 13.0)
        _stroke(painter, _alpha(GOLD, 170 * glow), 0.9)
        for deg in (-150.0, -120.0, -90.0, -60.0, -30.0):
            a = math.radians(deg)
            painter.drawLine(
                QPointF(cx + 6.0 * math.cos(a), top - 1.0 + 6.0 * math.sin(a)),
                QPointF(cx + 11.0 * math.cos(a), top - 1.0 + 11.0 * math.sin(a)),
            )
    _fill(painter, WOOD)
    painter.drawRoundedRect(QRectF(left, top, width, height), 0.9, 0.9)
    _stroke(painter, WOOD_DARK, 0.6)
    painter.drawLine(QPointF(left + 0.5, top + height * 0.55), QPointF(right - 0.5, top + height * 0.55))
    _fill(painter, GOLD)
    for bx in (left + 1.3 * size, right - 2.7 * size):
        painter.drawRect(QRectF(bx, top, 1.4 * size, height))
    if lid_open > 0.3:  # a heap of gold shows once the lid is up
        _fill(painter, GOLD)
        painter.drawEllipse(QPointF(cx, top + 0.1), width * 0.4, 1.7 * size)
        _fill(painter, _alpha(CREAM, 190))
        painter.drawEllipse(QPointF(cx - width * 0.12, top - 0.4), 0.7, 0.5)
    painter.save()
    painter.translate(right, top)
    painter.rotate(lid_open * 92.0)
    lid = QPainterPath()
    lid.moveTo(-width, 0.0)
    lid.lineTo(-width, -lid_h * 0.5)
    lid.quadTo(-width / 2.0, -lid_h * 1.5, 0.0, -lid_h * 0.5)
    lid.lineTo(0.0, 0.0)
    lid.closeSubpath()
    _fill(painter, WOOD)
    painter.drawPath(lid)
    _stroke(painter, GOLD, 1.3 * size)
    painter.drawLine(QPointF(-width * 0.5, 0.0), QPointF(-width * 0.5, -lid_h * 1.0))
    painter.restore()
    if lid_open < 0.2:  # the lock
        _fill(painter, GOLD)
        painter.drawRect(QRectF(cx - 0.9 * size, top - 0.3, 1.8 * size, 2.3 * size))
        _fill(painter, WOOD_DARK)
        painter.drawEllipse(QPointF(cx, top + 0.8 * size), 0.35, 0.35)


def _paint_coin(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    rx = max(0.6, 2.7 * abs(math.cos(prop.extra[0])))
    pen = QPen(GOLD_DARK)
    pen.setWidthF(0.7)
    painter.setPen(pen)
    painter.setBrush(GOLD)
    painter.drawEllipse(QPointF(x, y), rx, 2.7)
    if rx > 1.5:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen.setWidthF(0.45)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(x, y), rx * 0.6, 1.6)
        _fill(painter, _alpha(CREAM, 220))
        painter.drawEllipse(QPointF(x - rx * 0.35, y - 1.0), 0.5, 0.5)


def _paint_sparkle(painter: QPainter, prop: Prop, _line: QColor) -> None:
    _star(painter, prop.a, prop.b, prop.extra[0], CREAM)


# --- night ---------------------------------------------------------------------
_STARS = ((24.0, 4.5, 1.6), (57.0, 5.0, 1.4), (64.0, 15.0, 1.2), (4.0, 29.0, 1.3), (31.0, 2.5, 1.0))


def _paint_moon(painter: QPainter, prop: Prop, _line: QColor) -> None:
    disc = QPainterPath()
    disc.addEllipse(QPointF(9.5, 11.0), 6.2, 6.2)
    bite = QPainterPath()
    bite.addEllipse(QPointF(12.5, 9.2), 5.5, 5.5)
    _fill(painter, _alpha(CREAM, 235 * prop.a))
    painter.drawPath(disc.subtracted(bite))


def _paint_stars(painter: QPainter, prop: Prop, _line: QColor) -> None:
    frame, strength = int(prop.a), prop.b
    for k, (x, y, size) in enumerate(_STARS):
        twinkle = (1.0, 0.65, 1.25)[(frame + k) % 3]
        _star(painter, x, y, size * twinkle, _alpha(CREAM, 230 * strength))


def _paint_zzz(painter: QPainter, prop: Prop, _line: QColor) -> None:
    frame = prop.a
    for k in range(3):
        age = (frame * 0.9 + k * 3.0) % 9.0
        x, y, size = 45.0 + age * 1.5, 16.0 - age * 1.35, 1.9 + age * 0.28
        strength = min(1.0, age / 1.5) * (1.0 - age / 9.0)
        _stroke(painter, _alpha(LILAC, 255 * strength), 0.9 + age * 0.04)
        z = QPainterPath(QPointF(x, y))
        z.lineTo(x + size, y)
        z.lineTo(x, y + size)
        z.lineTo(x + size, y + size)
        painter.drawPath(z)


def _paint_alert(painter: QPainter, prop: Prop, _line: QColor) -> None:
    s = prop.a
    x, y = 40.0, 6.5
    _stroke(painter, CORAL, 2.1 * s)
    painter.drawLine(QPointF(x, y - 5.5 * s), QPointF(x, y + 1.6 * s))
    _fill(painter, CORAL)
    painter.drawEllipse(QPointF(x, y + 4.6 * s), 1.2 * s, 1.2 * s)
    _stroke(painter, _alpha(GOLD, 230), 0.9)
    for sx in (-1.0, 1.0):
        painter.drawLine(QPointF(x + sx * 4.2, y - 4.0), QPointF(x + sx * 6.2, y - 5.5))
        painter.drawLine(QPointF(x + sx * 4.6, y + 0.5), QPointF(x + sx * 6.8, y + 0.7))


# --- music ---------------------------------------------------------------------
def _paint_note(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    variant, strength, colour = prop.extra
    color = _alpha(_PALETTE[int(colour) % 3], 255 * strength)

    def head(cx: float, cy: float) -> None:
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-20.0)
        _fill(painter, color)
        painter.drawEllipse(QPointF(0.0, 0.0), 1.9, 1.35)
        painter.restore()

    _stroke(painter, color, 0.9)
    if variant < 0.5:
        head(x, y)
        painter.drawLine(QPointF(x + 1.7, y - 0.4), QPointF(x + 1.7, y - 6.4))
        flag = QPainterPath(QPointF(x + 1.7, y - 6.4))
        flag.quadTo(QPointF(x + 4.6, y - 5.4), QPointF(x + 3.6, y - 2.6))
        painter.drawPath(flag)
    else:
        head(x - 2.4, y + 0.8)
        head(x + 2.4, y)
        painter.drawLine(QPointF(x - 0.7, y + 0.4), QPointF(x - 0.7, y - 5.4))
        painter.drawLine(QPointF(x + 4.1, y - 0.4), QPointF(x + 4.1, y - 6.4))
        _stroke(painter, color, 1.5)
        painter.drawLine(QPointF(x - 0.7, y - 5.4), QPointF(x + 4.1, y - 6.4))


# --- balloons and fireworks ----------------------------------------------------
_BALLOONS = ((-6.0, -10.0, CORAL), (0.0, -13.0, GOLD), (6.0, -9.5, TEAL))


def _paint_balloons(painter: QPainter, prop: Prop, line_color: QColor) -> None:
    knot_x, knot_y = prop.a, prop.b
    sway = 0.6 * math.sin(prop.extra[0] * 1.3)
    for k, (ox, oy, color) in enumerate(_BALLOONS):
        bx, by = knot_x + ox + sway * (k + 1) * 0.4, knot_y + oy
        _stroke(painter, _alpha(line_color, 150), 0.7)
        painter.drawLine(QPointF(knot_x, knot_y), QPointF(bx, by + 4.4))
        _fill(painter, color)
        painter.drawEllipse(QPointF(bx, by), 3.6, 4.4)
        tie = QPainterPath(QPointF(bx - 0.9, by + 5.3))
        tie.lineTo(QPointF(bx, by + 4.1))
        tie.lineTo(QPointF(bx + 0.9, by + 5.3))
        tie.closeSubpath()
        painter.drawPath(tie)
        _fill(painter, _alpha(CREAM, 150))
        painter.drawEllipse(QPointF(bx - 1.3, by - 1.7), 0.9, 1.4)


def _paint_burst(painter: QPainter, prop: Prop, _line: QColor) -> None:
    x, y = prop.a, prop.b
    age, colour = prop.extra
    color = _PALETTE[int(colour) % 3]
    fade = max(0.0, 1.0 - max(0.0, age - 3.0) / 4.0)
    radius = 1.5 + 2.8 * age
    sag = 0.32 * max(0.0, age - 3.0) ** 2
    if age < 2:
        _fill(painter, _alpha(CREAM, 220))
        painter.drawEllipse(QPointF(x, y), 2.6 - age, 2.6 - age)
    for k in range(10):
        a = 2.0 * math.pi * k / 10.0 + 0.3 * colour
        ux, uy = math.cos(a), math.sin(a)
        inner = max(0.0, radius - 3.2)
        _stroke(painter, _alpha(color, 235 * fade), 1.1)
        painter.drawLine(QPointF(x + ux * inner, y + uy * inner + sag), QPointF(x + ux * radius, y + uy * radius + sag))
        if age >= 2:
            _fill(painter, _alpha(CREAM, 230 * fade))
            painter.drawEllipse(QPointF(x + ux * radius, y + uy * radius + sag), 0.7, 0.7)


_PAINTERS: dict[str, Callable[[QPainter, Prop, QColor], None]] = {
    "rain": _paint_rain,
    "umbrella": _paint_umbrella,
    "rainbow": _paint_rainbow,
    "butterfly": _paint_butterfly,
    "mound": _paint_mound,
    "worm": _paint_worm,
    "chest": _paint_chest,
    "coin": _paint_coin,
    "sparkle": _paint_sparkle,
    "moon": _paint_moon,
    "stars": _paint_stars,
    "zzz": _paint_zzz,
    "alert": _paint_alert,
    "note": _paint_note,
    "balloons": _paint_balloons,
    "burst": _paint_burst,
}
_PAINTERS.update(raven_story_art.PAINTERS)
BACK_KINDS = BACK_KINDS | raven_story_art.BACK_KINDS
KINDS = frozenset(_PAINTERS)


def paint(painter: QPainter, prop: Prop, line_color: QColor) -> None:
    painter.save()
    _PAINTERS[prop.kind](painter, prop, line_color)
    painter.restore()
