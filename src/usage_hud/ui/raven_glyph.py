"""The raven contour — the LIVE status icon (tray, taskbar, chip window;
see ui/tray.py, ui/formatters.py), severity-tinted, plus the chip's own
side watermark (ui/hud.py), in a fixed colour.

The static branding icon (tools/make_icon.py) draws a different, richer
raven-perched-on-boar composition from ui/emblem_glyph.py — more room for
detail there than a live, constantly-refreshed 16-24px icon has.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from PySide6.QtCore import QBuffer, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QTransform

_EYE_POINT = (20.0, 11.6)
_LEG_A = ((12.5, 27.3), (11.3, 30.2))
_LEG_B = ((16.5, 27.3), (17.7, 30.2))
_LEG_A_LIFTED = ((13.0, 27.2), (13.6, 29.1))
_LEG_B_LIFTED = ((16.0, 27.2), (15.4, 29.1))

# The chip's side watermark is a little scene, not a single static glyph:
# the raven paces a short path back and forth (see walk_pose) and, once in
# a while when it crosses the middle, hops over a bush (see jump_pose,
# paint_bush) instead of just walking past. SCENE_WIDTH/HEIGHT/SCALE are
# the one shared layout the whole scene is built on — hud.py uses them to
# size the QLabel that hosts it.
SCENE_WIDTH = 68
SCENE_HEIGHT = 54  # headroom above the raven for hops, wings and dropped props
_SCALE = 1.05
# The scene is drawn on the 68x44 grid above and shrunk as a whole to this
# many on-screen pixels, so the walk path, hop arc and bush keep their
# proportions while the chip takes less room.
SCENE_ZOOM = 0.72
SCENE_DISPLAY_WIDTH = round(SCENE_WIDTH * SCENE_ZOOM)
SCENE_DISPLAY_HEIGHT = round(SCENE_HEIGHT * SCENE_ZOOM)
_RAVEN_BOX = 32.0 * _SCALE  # the raven_path design grid, at this scale
_TOP_MARGIN = (SCENE_HEIGHT - _RAVEN_BOX) / 2.0
_WALK_X_MIN = 2.0
_WALK_X_MAX = SCENE_WIDTH - _RAVEN_BOX - 2.0
_WALK_BOB = 2.2  # px the whole bird lifts on the "up" step of its stride
_WALK_TILT = 3.5  # degrees leaned into the direction of travel
WALK_CYCLE_STEPS = 16  # one leg of the pace (there and back is double this)
# Public layout the gags (raven_gags) build on.
RAVEN_BOX = _RAVEN_BOX
PATH_X_MIN = _WALK_X_MIN
PATH_X_MAX = _WALK_X_MAX
CENTRE_X = (_WALK_X_MIN + _WALK_X_MAX) / 2.0  # raven's left edge at mid-path
FLOOR_Y = _TOP_MARGIN + _RAVEN_BOX  # bottom of the standing raven
FEET_PIVOT = (14.5 * _SCALE, 29.2 * _SCALE)  # where a peck rocks the body from
LEG_A, LEG_B = _LEG_A, _LEG_B
LEG_A_LIFTED, LEG_B_LIFTED = _LEG_A_LIFTED, _LEG_B_LIFTED

# The hop over the bush starts from wherever the raven is walking, in the
# direction it is walking: a crouch, a push-off, an arc over the bush with
# the wings half open, a landing squash and a recovery. Per frame:
# (dx along the hop, y, tilt, squash, wing, legs tucked). Mirrored for a
# raven walking left.
JUMP_LENGTH = 24.0
_JUMP_FRAMES: tuple[tuple[float, float, float, float, str | None, bool], ...] = (
    (0.0, 0.0, 0.0, 0.86, None, False),
    (3.0, -4.0, -14.0, 1.08, "up", True),
    (8.0, -10.0, -8.0, 1.0, "mid", True),
    (13.0, -14.0, 0.0, 1.0, "mid", True),
    (17.0, -12.0, 8.0, 1.0, "down", True),
    (20.5, -7.0, 12.0, 1.0, "mid", True),
    (23.0, -2.0, 6.0, 1.0, "up", False),
    (24.0, 0.0, 0.0, 0.85, None, False),
    (24.0, 0.0, 0.0, 1.0, None, False),
)
JUMP_FRAME_COUNT = len(_JUMP_FRAMES)
_BUSH_SCALE = (0.55, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.6)
# How often, at the point on its pace where a hop can start, the raven
# hops over the bush instead of walking straight past — "raz na jakis
# czas", not every single pass.
JUMP_CHANCE = 1.0 / 5.0


@dataclass(frozen=True)
class RavenPose:
    """Everything the renderer needs to draw the raven for one frame."""

    x: float
    y: float = 0.0
    tilt: float = 0.0
    squash: float = 1.0  # <1 flattened, >1 stretched (about the feet)
    visible: bool = True
    wing: str | None = None
    leg_a: tuple[tuple[float, float], tuple[float, float]] = _LEG_A
    leg_b: tuple[tuple[float, float], tuple[float, float]] = _LEG_B
    facing_left: bool = False
    pivot: tuple[float, float] | None = None  # tilt about this point


# Flight: now and then, on reaching the right end of its path, the raven
# flaps up out of the scene, is gone for a few beats, then glides back in
# from the left and lands where the pace starts (see fly_pose).
FLY_CLIMB_FRAMES = 6
FLY_GONE_FRAMES = 6
FLY_RETURN_FRAMES = 7
FLY_FRAME_COUNT = FLY_CLIMB_FRAMES + FLY_GONE_FRAMES + FLY_RETURN_FRAMES
FLY_CHANCE = 1.0 / 12.0
_WING_FILL = QColor(24, 28, 19)  # the chip panel's own dark olive
_FLAP = ("down", "up", "mid")  # one wingbeat; three poses read as flapping
_WING_ROOT = (13.0, 14.0)
_WING_LEN = 19.0
# pose -> (angle of the wing's long axis in degrees, which side the
# trailing edge is on: +1 / -1)
_WING_POSES: dict[str, tuple[float, int]] = {
    "up": (-104.0, -1),
    "mid": (196.0, -1),
    "down": (98.0, 1),
}


def wing_path(s: float, pose: str) -> QPainterPath:
    """A feathered wing as one outline — smooth leading edge, scalloped
    trailing edge with four finger tips — rooted at the shoulder of the
    32x32 raven grid and swung to "up", "mid" (swept back) or "down"."""
    length = _WING_LEN
    blade = QPainterPath()
    blade.moveTo(0.0, -2.2)
    blade.quadTo(length * 0.5, -6.0, length, -0.8)
    for x, y in (
        (length * 0.80, 1.6),
        (length * 0.82, 4.2),
        (length * 0.58, 3.0),
        (length * 0.58, 5.8),
        (length * 0.34, 4.4),
        (length * 0.30, 6.4),
        (0.0, 4.2),
    ):
        blade.lineTo(x, y)
    blade.closeSubpath()
    angle, side = _WING_POSES[pose]
    transform = QTransform()
    transform.translate(_WING_ROOT[0] * s, _WING_ROOT[1] * s)
    transform.rotate(angle)
    transform.scale(s, s * side)
    return transform.map(blade)


def at_path_right_end(step: int) -> bool:
    """True on the step the raven reaches the right end of its pace, facing
    right — the one spot it can take off from without turning round."""
    return step % (2 * WALK_CYCLE_STEPS) == WALK_CYCLE_STEPS


def fly_pose(frame: int) -> tuple[bool, float, float, float, str | None, bool]:
    """(visible, x, y, tilt, wing, legs_down) for one frame of the flight:
    climb out to the upper right, a few frames out of sight, then a glide
    in from the left that ends standing at the start of the path. Always
    facing right. x/y are pixels in scene coordinates (y relative to the
    standing line), tilt in degrees (negative = nose up)."""
    frame = max(0, min(frame, FLY_FRAME_COUNT - 1))
    if frame < FLY_CLIMB_FRAMES:
        t = frame + 1
        x = _WALK_X_MAX + 3.5 * t
        y = -(3.2 * t + 0.6 * t * t)
        return True, x, y, -22.0, _FLAP[frame % len(_FLAP)], False
    frame -= FLY_CLIMB_FRAMES
    if frame < FLY_GONE_FRAMES:
        return False, 0.0, 0.0, 0.0, None, False
    r = frame - FLY_GONE_FRAMES
    u = (r + 1) / FLY_RETURN_FRAMES
    x = -34.0 + (_WALK_X_MIN + 34.0) * u
    y = -30.0 * (1.0 - u) ** 1.6
    if r == FLY_RETURN_FRAMES - 1:
        return True, x, 0.0, 0.0, None, True  # landed
    if r == FLY_RETURN_FRAMES - 2:
        return True, x, y, 4.0, "up", True  # flare: wings up, feet reaching down
    return True, x, y, 9.0 * (1.0 - u), _FLAP[r % len(_FLAP)], False


def walk_pose(
    step: int,
) -> tuple[float, float, float, tuple, tuple, bool]:
    """(x, y, tilt, leg_a, leg_b, facing_left) for one step of a back-and-
    forth pace across ``_WALK_X_MIN.._WALK_X_MAX`` — x/y in pixels, tilt in
    degrees. The leg lifted and the direction leaned into both flip every
    step, and the whole glyph lifts slightly on the "up" step, so it reads
    as a walking gait rather than sliding across the path."""
    cycle = step % (2 * WALK_CYCLE_STEPS)
    if cycle <= WALK_CYCLE_STEPS:
        frac = cycle / WALK_CYCLE_STEPS
        facing_left = False
    else:
        frac = 1.0 - (cycle - WALK_CYCLE_STEPS) / WALK_CYCLE_STEPS
        facing_left = True
    x = _WALK_X_MIN + (_WALK_X_MAX - _WALK_X_MIN) * frac
    leg_toggle = step % 2 == 0
    leg_a, leg_b = (_LEG_A_LIFTED, _LEG_B) if leg_toggle else (_LEG_A, _LEG_B_LIFTED)
    y = -_WALK_BOB if leg_toggle else 0.0
    at_a_turn = frac <= 0.0 or frac >= 1.0
    tilt = 0.0 if at_a_turn else (-_WALK_TILT if facing_left else _WALK_TILT)
    return x, y, tilt, leg_a, leg_b, facing_left


def at_gag_spot(step: int) -> bool:
    """True on the one step per lap where the raven stands at the middle of
    its path facing right — where the stationary gags (raven_gags) start."""
    return step % (2 * WALK_CYCLE_STEPS) == WALK_CYCLE_STEPS // 2


def jump_start_step(step: int) -> bool:
    """True on the step per leg where a hop can start: early on each leg,
    so there is room to land before the end of the path."""
    return step % WALK_CYCLE_STEPS == 2


def step_for_x(x: float, facing_left: bool) -> int:
    """The walk step that puts the raven at ``x`` heading the given way — so
    the pace resumes exactly where a hop or a gag left it."""
    frac = (min(max(x, _WALK_X_MIN), _WALK_X_MAX) - _WALK_X_MIN) / (_WALK_X_MAX - _WALK_X_MIN)
    steps = round(frac * WALK_CYCLE_STEPS)
    return 2 * WALK_CYCLE_STEPS - steps if facing_left else steps


def jump_end_x(x0: float, facing_left: bool) -> float:
    return x0 - JUMP_LENGTH if facing_left else x0 + JUMP_LENGTH


def jump_pose(frame: int, x0: float, facing_left: bool = False) -> RavenPose:
    """One frame of the hop, starting from ``x0`` (where the raven was
    walking) and heading right, or left when ``facing_left``."""
    dx, y, tilt, squash, wing, tucked = _JUMP_FRAMES[frame % JUMP_FRAME_COUNT]
    legs = (_LEG_A_LIFTED, _LEG_B_LIFTED) if tucked else (_LEG_A, _LEG_B)
    return RavenPose(
        x=x0 - dx if facing_left else x0 + dx,
        y=y,
        tilt=tilt,
        squash=squash,
        wing=wing,
        leg_a=legs[0],
        leg_b=legs[1],
        facing_left=facing_left,
    )


def jump_bush(frame: int, x0: float, facing_left: bool) -> tuple[float, float]:
    """(centre x, scale) of the bush for one frame: it sits ahead of the
    raven, pops up as the raven crouches and sinks back after it lands."""
    ahead = -12.0 if facing_left else 12.0
    return x0 + _RAVEN_BOX / 2.0 + ahead, _BUSH_SCALE[frame % JUMP_FRAME_COUNT]


def fly_raven_pose(frame: int) -> RavenPose:
    visible, x, y, tilt, wing, legs_down = fly_pose(frame)
    legs = (_LEG_A, _LEG_B) if legs_down else (_LEG_A_LIFTED, _LEG_B_LIFTED)
    return RavenPose(x=x, y=y, tilt=tilt, visible=visible, wing=wing, leg_a=legs[0], leg_b=legs[1])


def walk_raven_pose(step: int) -> RavenPose:
    x, y, tilt, leg_a, leg_b, facing_left = walk_pose(step)
    return RavenPose(x=x, y=y, tilt=tilt, leg_a=leg_a, leg_b=leg_b, facing_left=facing_left)


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
    wing: str | None = None,
    wing_fill: QColor | None = None,
) -> None:
    """Strokes the detailed contour (no fill) — the "zarys" (outline)
    treatment, for anything above ``SOLID_MAX_SIZE``. Caller owns the
    plate/background and draws it first. ``leg_a``/``leg_b`` default to the
    static resting pose; raven_scene_html swaps in walk/jump variants to
    animate the gait."""
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

    if wing is not None:
        painter.setPen(pen)
        # Filled with the panel's own colour so the wing hides the body
        # outline behind it instead of crossing it in a tangle of lines.
        painter.setBrush(wing_fill if wing_fill is not None else Qt.BrushStyle.NoBrush)
        painter.drawPath(wing_path(s, wing))

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


def paint_bush(
    painter: QPainter,
    *,
    color: QColor,
    cx: float,
    cy: float,
    scale: float = 1.0,
    berry_color: QColor | None = None,
) -> None:
    """A small shrub standing on (``cx``, ``cy``) — four overlapping lobes
    and, when ``berry_color`` is given, a few berries. ``scale`` grows it
    from the ground up."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    for dx, dy, r in ((-5.5, -3.0, 4.4), (-1.6, -6.5, 5.4), (3.2, -5.4, 5.0), (6.0, -2.4, 3.8)):
        painter.drawEllipse(QPointF(cx + dx * scale, cy + dy * scale), r * scale, r * scale)
    if berry_color is not None and scale > 0.8:
        painter.setBrush(berry_color)
        for dx, dy in ((-3.5, -5.5), (1.5, -9.0), (5.5, -5.0)):
            painter.drawEllipse(QPointF(cx + dx * scale, cy + dy * scale), 0.9, 0.9)


def _draw_raven(painter: QPainter, pose: RavenPose, line_color: QColor, eye_color: QColor | None) -> None:
    if not pose.visible:
        return
    painter.save()
    painter.translate(pose.x, _TOP_MARGIN + pose.y)
    if pose.facing_left:
        # Mirror within the raven's own local box so it paces back the way
        # it came instead of moonwalking.
        painter.translate(_RAVEN_BOX, 0)
        painter.scale(-1, 1)
    if pose.squash != 1.0:
        # Squash / stretch about the bottom centre: a flattened bird spreads
        # sideways, a stretched one gets slimmer.
        sx = 1.0 + (1.0 - pose.squash) * 0.55
        painter.translate(_RAVEN_BOX / 2.0, _RAVEN_BOX)
        painter.scale(sx, pose.squash)
        painter.translate(-_RAVEN_BOX / 2.0, -_RAVEN_BOX)
    pivot = QPointF(*(pose.pivot or (_RAVEN_BOX / 2.0, _RAVEN_BOX / 2.0)))
    painter.translate(pivot)
    painter.rotate(pose.tilt)
    painter.translate(-pivot)
    paint_raven_outline(
        painter,
        _SCALE,
        line_color=line_color,
        eye_color=eye_color,
        legs=True,
        leg_a=pose.leg_a,
        leg_b=pose.leg_b,
        wing=pose.wing,
        wing_fill=_WING_FILL,
    )
    painter.restore()


def raven_scene_html(
    *,
    line_color: QColor,
    eye_color: QColor | None = None,
    bush_color: QColor | None = None,
    mode: str = "walk",
    index: int = 0,
    gag: str | None = None,
    x0: float | None = None,
    facing_left: bool = False,
) -> str:
    """A standalone ``<img>`` tag of the raven's little scene — SCENE_WIDTH
    x SCENE_HEIGHT, transparent background (no plate, unlike the tray/badge
    icons — this sits on the chip panel's own painted background, see
    WeatherPanel.paintEvent) — for dropping into a QLabel's rich text as
    the chip's side watermark (ui/hud.py).

    ``mode="walk"``: ``index`` is a step count (see walk_pose). ``"jump"``:
    ``index`` is a frame of the hop (see jump_pose) that starts at ``x0``
    heading left or right. ``"fly"``: a frame of the flight (see fly_pose).
    ``"gag"``: a frame of the named scene in raven_gags. WeatherPanel's own
    timer owns the mode switch and the frame/step advance; this function
    only renders one frame of whichever it's told.
    """
    bush: tuple[float, float] | None = None
    props: list = []
    if mode == "fly":
        pose = fly_raven_pose(index)
    elif mode == "jump":
        start = CENTRE_X if x0 is None else x0
        pose = jump_pose(index, start, facing_left)
        bush = jump_bush(index, start, facing_left)
    elif mode == "gag":
        from usage_hud.ui import raven_gags

        pose, props = raven_gags.gag_frame(gag or "peck", index)
    else:
        pose = walk_raven_pose(index)

    pix = QPixmap(SCENE_DISPLAY_WIDTH, SCENE_DISPLAY_HEIGHT)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(SCENE_ZOOM, SCENE_ZOOM)

    if bush is not None and bush_color is not None:
        paint_bush(
            painter,
            color=bush_color,
            cx=bush[0],
            cy=FLOOR_Y - 1.0,
            scale=bush[1],
            berry_color=eye_color,
        )
    _draw_raven(painter, pose, line_color, eye_color)
    if props:
        from usage_hud.ui import raven_gags

        raven_gags.paint_props(painter, props, line_color, _WING_FILL)
    painter.end()
    return _pixmap_to_img_tag(pix)


def _pixmap_to_img_tag(pix: QPixmap) -> str:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buf, "PNG")
    encoded = base64.b64encode(bytes(buf.data())).decode("ascii")
    return (
        f'<img src="data:image/png;base64,{encoded}" '
        f'width="{SCENE_DISPLAY_WIDTH}" height="{SCENE_DISPLAY_HEIGHT}">'
    )
