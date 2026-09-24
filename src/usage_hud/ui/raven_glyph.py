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
_LEG_A_LIFTED = ((13.0, 27.2), (13.6, 29.1))
_LEG_B_LIFTED = ((16.0, 27.2), (15.4, 29.1))

# The chip's side watermark is a little scene, not a single static glyph:
# the raven paces a short path back and forth (see walk_pose) and, once in
# a while when it crosses the middle, hops over a bush (see jump_pose,
# paint_bush) instead of just walking past. SCENE_WIDTH/HEIGHT/SCALE are
# the one shared layout the whole scene is built on — hud.py uses them to
# size the QLabel that hosts it.
SCENE_WIDTH = 68
SCENE_HEIGHT = 44
_SCALE = 1.05
_RAVEN_BOX = 32.0 * _SCALE  # the raven_path design grid, at this scale
_TOP_MARGIN = (SCENE_HEIGHT - _RAVEN_BOX) / 2.0
_WALK_X_MIN = 2.0
_WALK_X_MAX = SCENE_WIDTH - _RAVEN_BOX - 2.0
_WALK_BOB = 2.2  # px the whole bird lifts on the "up" step of its stride
_WALK_TILT = 3.5  # degrees leaned into the direction of travel
WALK_CYCLE_STEPS = 16  # one leg of the pace (there and back is double this)

# A short hop arc — (dx, dy, tilt) in pixels/degrees, relative to the bush
# at the path's centre. Always left-to-right: which way the raven was
# actually walking when it triggered the jump is not tracked, and a short
# hop reversing tilt/direction was not worth the extra state for a
# decoration nobody is meant to scrutinise that closely.
_JUMP_ARC: tuple[tuple[float, float, float], ...] = (
    (-15.0, 0.0, 0.0),
    (-9.0, -4.0, -5.0),
    (-3.0, -8.0, -2.0),
    (0.0, -10.0, 2.0),
    (4.0, -7.0, 5.0),
    (9.0, -3.0, 3.0),
    (14.0, 0.0, 0.0),
)
JUMP_FRAME_COUNT = len(_JUMP_ARC)
# How often, of the times the raven crosses the middle of its path, it
# hops over the bush instead of walking straight past — "raz na jakis
# czas", not every single pass.
JUMP_CHANCE = 1.0 / 5.0


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


def at_path_centre(step: int) -> bool:
    """True on the one step per leg of the pace where the raven is
    passing the bush's spot — where hud.py rolls the dice on JUMP_CHANCE
    to switch into a jump instead of continuing to walk."""
    cycle = step % (2 * WALK_CYCLE_STEPS)
    half = WALK_CYCLE_STEPS // 2
    return cycle in (half, WALK_CYCLE_STEPS + half)


def jump_pose(frame: int) -> tuple[float, float, float, tuple, tuple]:
    """(x, y, tilt, leg_a, leg_b) for one frame of the hop-over-the-bush
    arc, relative to the bush's own position at the path's centre. Both
    legs tuck up for the airborne middle frames."""
    dx, y, tilt = _JUMP_ARC[frame % JUMP_FRAME_COUNT]
    x = (_WALK_X_MIN + _WALK_X_MAX) / 2.0 + dx
    airborne = 1 <= frame <= JUMP_FRAME_COUNT - 2
    leg_a, leg_b = (_LEG_A_LIFTED, _LEG_B_LIFTED) if airborne else (_LEG_A, _LEG_B)
    return x, y, tilt, leg_a, leg_b


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


def paint_bush(painter: QPainter, *, color: QColor, cx: float, cy: float) -> None:
    """Three overlapping rounded lobes centred on (``cx``, ``cy``) in
    pixels — just enough to read as a small shrub at this scale, no more
    detail than the raven's own legs get."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    for dx, dy, r in ((-4.0, 1.0, 4.0), (0.0, -1.5, 4.6), (4.0, 1.2, 4.0)):
        painter.drawEllipse(QPointF(cx + dx, cy + dy), r, r)


def raven_scene_html(
    *,
    line_color: QColor,
    eye_color: QColor | None = None,
    bush_color: QColor | None = None,
    mode: str = "walk",
    index: int = 0,
) -> str:
    """A standalone ``<img>`` tag of the raven's little scene — SCENE_WIDTH
    x SCENE_HEIGHT, transparent background (no plate, unlike the tray/badge
    icons — this sits on the chip panel's own painted background, see
    WeatherPanel.paintEvent) — for dropping into a QLabel's rich text as
    the chip's side watermark (ui/hud.py).

    ``mode="walk"``: ``index`` is a step count (see walk_pose) — the raven
    paces back and forth across the scene. ``mode="jump"``: ``index`` is a
    frame in 0..JUMP_FRAME_COUNT-1 (see jump_pose) — the raven hops over a
    bush drawn at the path's centre. WeatherPanel's own timer owns the mode
    switch and the frame/step advance; this function only renders one
    frame of whichever it's told.
    """
    if mode == "jump":
        x, y, tilt, leg_a, leg_b = jump_pose(index)
        facing_left = False
        show_bush = True
    else:
        x, y, tilt, leg_a, leg_b, facing_left = walk_pose(index)
        show_bush = False

    pix = QPixmap(SCENE_WIDTH, SCENE_HEIGHT)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if show_bush and bush_color is not None:
        bush_cx = (_WALK_X_MIN + _WALK_X_MAX) / 2.0 + _RAVEN_BOX / 2.0
        paint_bush(painter, color=bush_color, cx=bush_cx, cy=_TOP_MARGIN + _RAVEN_BOX - 1.0)

    painter.save()
    painter.translate(x, _TOP_MARGIN + y)
    if facing_left:
        # Mirror within the raven's own local box so it paces back the way
        # it came instead of moonwalking.
        painter.translate(_RAVEN_BOX, 0)
        painter.scale(-1, 1)
    pivot = QPointF(_RAVEN_BOX / 2.0, _RAVEN_BOX / 2.0)
    painter.translate(pivot)
    painter.rotate(tilt)
    painter.translate(-pivot)
    paint_raven_outline(
        painter, _SCALE, line_color=line_color, eye_color=eye_color, legs=True, leg_a=leg_a, leg_b=leg_b
    )
    painter.restore()
    painter.end()

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buf, "PNG")
    encoded = base64.b64encode(bytes(buf.data())).decode("ascii")
    return f'<img src="data:image/png;base64,{encoded}" width="{SCENE_WIDTH}" height="{SCENE_HEIGHT}">'
