"""The raven's rarer scenes on the chip: pecking at the ground, a cage
dropping over it, a 100-ton weight, Monty Python's giant foot, and being
chased off with a broom (it flies away and comes back — see raven_glyph's
flight). Each scene is a timeline of ``(RavenPose, props)`` frames; the
renderer in raven_glyph draws them and WeatherPanel's timer steps through
them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from usage_hud.ui import raven_glyph as rg

# Per time the raven stands at the middle of its path facing right: the
# chance of each scene. Rarer ones (the props) well under the hop's 1 in 5.
GAG_CHANCES: tuple[tuple[str, float], ...] = (
    ("peck", 0.07),
    ("cage", 0.02),
    ("weight", 0.02),
    ("foot", 0.02),
    ("shoo", 0.025),
)
GAG_NAMES = tuple(name for name, _ in GAG_CHANCES)


@dataclass(frozen=True)
class Prop:
    """A thing in the scene. ``a`` is the main offset: how far above its
    resting place a dropped prop is (negative = higher), or the broom's x."""

    kind: str
    a: float = 0.0
    b: float = 0.0


_CX = rg.CENTRE_X + rg.RAVEN_BOX / 2.0  # scene x of the standing raven's middle

_PECK_TILT = (0.0, 20.0, 0.0, 20.0, 2.0, 22.0, 0.0, 0.0)

_CAGE_DY = (-46.0, -24.0, 0.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -6.0, -22.0, -40.0, -64.0)
_CAGE_TILT = (0.0, 0.0, 0.0, 0.0, -5.0, 18.0, 0.0, 18.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0)

_WEIGHT_DY = (-60.0, -30.0, 0.0, -1.0, 0.0, -1.0, -6.0, -20.0, -44.0, -72.0, -72.0, -72.0)
_WEIGHT_SQUASH = (1.0, 1.0, 0.2, 0.2, 0.2, 0.2, 0.2, 0.3, 1.2, 0.92, 1.04, 1.0)

_FOOT_DY = (-75.0, -40.0, 0.0, 0.0, 0.0, 0.0, -6.0, -20.0, -44.0, -80.0, -80.0, -80.0, -80.0)
_FOOT_SQUASH = (1.0, 1.0, 0.12, 0.12, 0.12, 0.12, 0.15, 0.3, 1.2, 0.95, 1.04, 1.0, 1.0)

_SHOO_CHASE = 5  # frames of running from the broom before it takes off


def gag_frame_count(name: str) -> int:
    return {
        "peck": len(_PECK_TILT),
        "cage": len(_CAGE_DY),
        "weight": len(_WEIGHT_DY),
        "foot": len(_FOOT_DY),
        "shoo": _SHOO_CHASE + rg.FLY_FRAME_COUNT,
    }[name]


def pick_gag(roll: float) -> str | None:
    """The scene a roll in [0, 1) selects, or None for most rolls."""
    for name, chance in GAG_CHANCES:
        if roll < chance:
            return name
        roll -= chance
    return None


# A dropped prop this far above its resting place is long out of the scene.
_GONE_DY = {"cage": -60.0, "weight": -65.0, "foot": -70.0}


def gag_frame(name: str, frame: int) -> tuple[rg.RavenPose, list[Prop]]:
    pose, props = _gag_frame(name, frame)
    return pose, [p for p in props if p.a > _GONE_DY.get(p.kind, float("-inf"))]


def _gag_frame(name: str, frame: int) -> tuple[rg.RavenPose, list[Prop]]:
    frame = max(0, min(frame, gag_frame_count(name) - 1))
    stand = rg.CENTRE_X
    if name == "peck":
        return rg.RavenPose(x=stand, tilt=_PECK_TILT[frame], pivot=rg.FEET_PIVOT), []
    if name == "cage":
        pose = rg.RavenPose(x=stand, tilt=_CAGE_TILT[frame], pivot=rg.FEET_PIVOT)
        return pose, [Prop("cage", _CAGE_DY[frame])]
    if name == "weight":
        pose = rg.RavenPose(x=stand, squash=_WEIGHT_SQUASH[frame])
        return pose, [Prop("weight", _WEIGHT_DY[frame])]
    if name == "foot":
        pose = rg.RavenPose(x=stand, squash=_FOOT_SQUASH[frame])
        return pose, [Prop("foot", _FOOT_DY[frame])]
    # shoo: run from the broom to the end of the path, then fly off.
    if frame < _SHOO_CHASE:
        u = (frame + 1) / _SHOO_CHASE
        x = stand + (rg.PATH_X_MAX - stand) * u
        step_up = frame % 2 == 0
        legs = (rg.LEG_A_LIFTED, rg.LEG_B) if step_up else (rg.LEG_A, rg.LEG_B_LIFTED)
        pose = rg.RavenPose(x=x, y=-1.5 if step_up else 0.0, tilt=7.0, leg_a=legs[0], leg_b=legs[1])
        return pose, [Prop("broom", x - 4.0, 6.0 if frame % 2 else -6.0)]
    k = frame - _SHOO_CHASE
    props = [Prop("broom", rg.PATH_X_MAX - 4.0 - 14.0 * (k + 1), 0.0)] if k < 3 else []
    return rg.fly_raven_pose(k), props


def paint_props(painter: QPainter, props: list[Prop], line_color: QColor, fill_color: QColor) -> None:
    pen = QPen(line_color)
    pen.setWidthF(1.4)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    for prop in props:
        painter.save()
        painter.setPen(pen)
        if prop.kind == "cage":
            _paint_cage(painter, prop.a)
        elif prop.kind == "weight":
            _paint_weight(painter, prop.a, line_color, fill_color)
        elif prop.kind == "foot":
            _paint_foot(painter, prop.a, fill_color)
        elif prop.kind == "broom":
            _paint_broom(painter, prop.a, prop.b, fill_color)
        painter.restore()


def _paint_cage(painter: QPainter, dy: float) -> None:
    half = 20.0
    bottom = rg.FLOOR_Y + 1.0 + dy
    top = bottom - 35.0
    painter.setBrush(Qt.BrushStyle.NoBrush)
    outline = QPainterPath()
    outline.moveTo(_CX - half, bottom)
    outline.lineTo(_CX - half, top + 11.0)
    outline.quadTo(_CX - half, top, _CX, top)
    outline.quadTo(_CX + half, top, _CX + half, top + 11.0)
    outline.lineTo(_CX + half, bottom)
    painter.drawPath(outline)
    painter.drawLine(QPointF(_CX - half - 1.5, bottom), QPointF(_CX + half + 1.5, bottom))
    for k in range(1, 5):
        x = _CX - half + k * (2.0 * half / 5.0)
        frac = abs(x - _CX) / half
        painter.drawLine(QPointF(x, bottom), QPointF(x, top + 11.0 * (1.0 - math.sqrt(1.0 - frac)) ** 2))
    painter.drawEllipse(QPointF(_CX, top - 2.4), 2.2, 2.2)


def _paint_weight(painter: QPainter, dy: float, line_color: QColor, fill_color: QColor) -> None:
    bottom = rg.FLOOR_Y - 5.5 + dy
    top = bottom - 21.0
    body = QPainterPath()
    body.moveTo(_CX - 10.0, top)
    body.lineTo(_CX + 10.0, top)
    body.lineTo(_CX + 17.0, bottom)
    body.lineTo(_CX - 17.0, bottom)
    body.closeSubpath()
    painter.setBrush(fill_color)
    painter.drawPath(body)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(_CX, top - 3.4), 4.6, 3.6)  # the lifting ring
    font = QFont("Arial")
    font.setBold(True)
    font.setPixelSize(9)
    painter.setFont(font)
    painter.setPen(line_color)
    painter.drawText(QRectF(_CX - 16.0, top + 3.0, 32.0, 15.0), Qt.AlignmentFlag.AlignCenter, "100t")


def _paint_foot(painter: QPainter, dy: float, fill_color: QColor) -> None:
    sole = rg.FLOOR_Y - 3.0 + dy

    def point(x: float, y: float) -> QPointF:
        return QPointF(_CX + x, sole + y)

    leg = QPainterPath()
    leg.moveTo(point(-19.0, 0.0))
    leg.lineTo(point(21.0, 0.0))
    leg.quadTo(point(26.0, -0.5), point(26.0, -4.0))  # big toe, front
    leg.quadTo(point(26.0, -8.0), point(21.0, -9.0))  # big toe, top
    leg.quadTo(point(12.0, -13.0), point(3.0, -19.0))  # instep up to the ankle
    leg.lineTo(point(3.0, -110.0))  # the leg, up out of the scene
    leg.lineTo(point(-12.0, -110.0))
    leg.lineTo(point(-12.0, -21.0))
    leg.quadTo(point(-21.0, -15.0), point(-19.0, -5.0))  # heel
    leg.closeSubpath()
    painter.setBrush(fill_color)
    painter.drawPath(leg)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for toe_x, toe_y in ((21.0, -12.0), (16.5, -14.5), (11.5, -16.2)):  # the other toes
        painter.drawEllipse(point(toe_x, toe_y), 2.3, 2.0)


def _paint_broom(painter: QPainter, x: float, swing: float, fill_color: QColor) -> None:
    floor = rg.FLOOR_Y
    head_top = floor - 10.0
    head = QPainterPath()
    head.moveTo(x - 4.0, head_top)
    head.lineTo(x + 4.0, head_top)
    head.lineTo(x + 9.0, floor)
    head.lineTo(x - 9.0, floor)
    head.closeSubpath()
    painter.setBrush(fill_color)
    painter.drawPath(head)
    for dx in (-5.0, -1.7, 1.7, 5.0):
        painter.drawLine(QPointF(x + dx * 0.6, head_top + 3.0), QPointF(x + dx, floor - 1.0))
    painter.drawLine(QPointF(x, head_top), QPointF(x - 17.0 + swing, head_top - 30.0))
