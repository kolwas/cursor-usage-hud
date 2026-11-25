"""The raven's long set pieces: the cage (and the mouse who frees it), the
giant foot (its shadow, the stomp, a flattened raven stuck to the sole), a
snowfall and a scarf, a kite, fishing, a wizard's hat and flowers, soap
bubbles, an egg that hatches, a birthday and a disco.

Like raven_adventures, each is a timeline — ``frame(name, i)`` gives the
pose and the props (plain numbers, see raven_props.Prop) for frame ``i``,
painted by raven_story_art — and each ends with the raven standing exactly
where it began and no prop left.
"""

from __future__ import annotations

import math

from usage_hud.ui import raven_glyph as rg
from usage_hud.ui.raven_props import Prop

_STAND = rg.CENTRE_X
_GROUND = rg.GROUND_Y
_MID = _STAND + rg.RAVEN_BOX / 2.0
_NONE: list[Prop] = []
LANDS_AT_START: frozenset[str] = frozenset()


def _pose(x: float = _STAND, **kw) -> rg.RavenPose:
    return rg.RavenPose(x=x, pivot=kw.pop("pivot", rg.FEET_PIVOT), **kw)


# --- cage: it drops, the raven rattles the bars, paces, droops; a mouse brings a key
_CAGE_X = _MID + 20.0  # the right-hand bars
# per frame: (tilt, dx, hop, squash, faces left, eyes shut)
_CAGE_RAVEN = (
    (-6.0, 0.0, 0.0, 1.0, False, False),
    (-8.0, 0.0, 0.0, 1.05, False, False),
    (0.0, 0.0, 0.0, 0.95, False, False),
    (-5.0, 0.0, -2.0, 1.04, False, False),
    (0.0, 0.0, 0.0, 1.0, False, False),
    (18.0, 0.0, 0.0, 1.0, False, False),  # pecks the bars
    (0.0, 0.0, 0.0, 1.0, False, False),
    (18.0, 0.0, 0.0, 1.0, False, False),
    (5.0, 0.0, 0.0, 1.0, False, False),
    (3.0, -1.0, -1.0, 1.0, True, False),  # paces: left ...
    (3.0, -2.5, 0.0, 1.0, True, False),
    (3.0, -1.0, -1.0, 1.0, True, False),
    (-3.0, 0.5, 0.0, 1.0, False, False),  # ... and right
    (-3.0, 2.0, -1.0, 1.0, False, False),
    (0.0, 1.0, 0.0, 1.0, False, False),
    (4.0, 0.0, 0.0, 0.95, False, True),  # droops
    (6.0, 0.0, 0.0, 0.92, False, True),
    (7.0, 0.0, 0.0, 0.92, False, True),  # wishes for a key
    (6.0, 0.0, 0.0, 0.92, False, True),
    (-8.0, 0.0, 0.0, 1.0, False, False),  # perks up: the mouse!
    (-4.0, 0.0, -2.0, 1.05, False, False),
    (-2.0, 0.0, 0.0, 1.0, False, False),
    (4.0, 0.0, 0.0, 1.0, False, False),
    (10.0, 0.0, 0.0, 1.0, False, False),  # presses to the bars
    (10.0, 0.0, 0.0, 1.0, False, False),
    (8.0, 0.0, 0.0, 1.0, False, False),
    (0.0, 0.0, 0.0, 1.0, False, False),  # the cage lifts
    (-4.0, 0.0, -3.0, 1.06, False, False),
    (-4.0, 0.0, -4.0, 1.08, False, False),
    (0.0, 0.0, -1.0, 1.04, False, False),  # free: hops, lands
    (0.0, 0.0, 0.0, 0.9, False, False),
    (0.0, 0.0, 0.0, 1.0, False, False),
    (0.0, 0.0, 0.0, 1.0, False, False),
    (0.0, 0.0, 0.0, 1.0, False, False),
)
_CAGE_DY = {0: -46.0, 1: -24.0, 2: 0.0, 3: -3.0, 26: -6.0, 27: -22.0, 28: -40.0}
# the mouse, per frame: (x, step, faces (-1 left / +1 right), key 0/1 mouth/2 lock, upright)
_CAGE_MOUSE = {
    19: (70.0, 0.0, -1, 1, 0),
    20: (64.5, 1.0, -1, 1, 0),
    21: (60.0, 0.0, -1, 1, 0),
    22: (57.0, 1.0, -1, 1, 0),
    23: (57.0, 0.0, -1, 1, 1),
    24: (57.0, 0.0, -1, 2, 1),
    25: (57.0, 1.0, -1, 2, 1),
    26: (57.0, 0.0, -1, 0, 1),
    27: (57.0, 1.0, -1, 0, 1),
    28: (57.0, 0.0, -1, 0, 1),
    29: (58.5, 1.0, 1, 0, 0),
    30: (62.0, 0.0, 1, 0, 0),
    31: (66.0, 1.0, 1, 0, 0),
    32: (70.0, 0.0, 1, 0, 0),
}


def _cage(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, dx, hop, squash, left, shut = _CAGE_RAVEN[i]
    pose = _pose(x=_STAND + dx, tilt=tilt, y=hop, squash=squash, facing_left=left, eye_closed=shut)
    props: list[Prop] = []
    dy = 0.0 if 4 <= i <= 25 else _CAGE_DY.get(i)
    if dy is not None:
        props.append(Prop("cage", dy))
        props.append(Prop("padlock", _CAGE_X, 36.0 + dy, (1.0 if i >= 25 else 0.0,)))
    if i in (17, 18):
        props.append(Prop("thought", 60.0, 11.0, (0.5 if i == 17 else 1.0,)))
    if i == 19:
        props.append(Prop("sparkle", 60.0, 10.0, (3.0,)))
    if i in _CAGE_MOUSE:
        x, step, face, key, upright = _CAGE_MOUSE[i]
        props.append(Prop("mouse", x, _GROUND + 0.4, (step, float(face), float(key), float(upright))))
    if i == 25:
        props.append(Prop("sparkle", _CAGE_X + 1.5, 34.0, (2.4,)))
    return pose, props


# --- foot: the shadow grows, the foot stomps, lifts the flat raven, drops it, it pops back
# per frame: (tilt, hop, squash)
_FOOT_RAVEN = (
    (20.0, 0.0, 1.0),
    (2.0, 0.0, 1.0),
    (22.0, 0.0, 1.0),
    (0.0, 0.0, 1.0),
    (-12.0, 0.0, 1.0),  # looks up
    (-4.0, 0.0, 0.93),
    (-4.0, 0.0, 0.9),
    (-2.0, 0.0, 0.9),
    (0.0, 0.0, 0.12),  # STOMP
    (0.0, 0.0, 0.12),
    (0.0, 0.0, 0.12),
    (0.0, 0.0, 0.12),
    (0.0, -6.0, 0.12),  # stuck to the sole as it rises
    (3.0, -20.0, 0.12),
    (-3.0, -34.0, 0.12),
    (10.0, -46.0, 0.12),
    (28.0, -30.0, 0.25),  # peels off and falls
    (10.0, -8.0, 0.3),
    (0.0, 0.0, 0.12),
    (0.0, 0.0, 0.5),  # pumps back up
    (0.0, 0.0, 1.22),
    (0.0, 0.0, 0.92),
    (0.0, 0.0, 1.04),
    (6.0, 0.0, 1.0),  # dizzy
    (-6.0, 0.0, 1.0),
    (4.0, 0.0, 1.0),
    (-2.0, 0.0, 1.0),
    (0.0, 0.0, 1.0),
)
_FOOT_DY = {6: -75.0, 7: -36.0, 8: 0.0, 9: 0.0, 10: 0.0, 11: 0.0, 12: -6.0, 13: -20.0, 14: -34.0, 15: -48.0, 16: -64.0}
_FOOT_SHADOW = (0.25, 0.4, 0.6, 0.8, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.8, 0.6, 0.4, 0.25, 0.1)


def _foot(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, hop, squash = _FOOT_RAVEN[i]
    pose = _pose(tilt=tilt, y=hop, squash=squash)
    props: list[Prop] = []
    if i < len(_FOOT_SHADOW):
        props.append(Prop("shadow", _FOOT_SHADOW[i]))
    if i in _FOOT_DY:
        props.append(Prop("foot", _FOOT_DY[i]))
    if 4 <= i <= 5:
        props.append(Prop("alert", 1.0))
    if 5 <= i <= 6:
        props.append(Prop("sweat", 47.5, 14.0 + 2.5 * (i - 5)))
    if 8 <= i <= 12:
        props.append(Prop("dust", float(i - 8)))
    if 19 <= i <= 26:
        t = i - 19
        props.append(Prop("feather", 44.0 + 5.0 * math.sin(t * 1.2), 16.0 + 3.1 * t, (30.0 * math.sin(t * 1.2 + 1.0),)))
    if 21 <= i <= 25:
        props.append(Prop("dizzy", float(i)))
    return pose, props


# --- snow: it snows, a scarf, shivering, snow piles on its back, it shakes it off
# per frame: (tilt, hop, squash, snowfall, scarf, cap, breath age, shake age, drift); -1 = none
_SNOW = (
    (0.0, 0.0, 1.0, 0.25, 0.0, 0.0, -1, -1, 0.0),
    (-6.0, 0.0, 1.0, 0.6, 0.0, 0.0, -1, -1, 0.0),
    (-4.0, 0.0, 1.0, 1.0, 0.0, 0.0, -1, -1, 0.2),
    (0.0, 0.0, 1.0, 1.0, 0.0, 0.0, -1, -1, 0.3),
    (0.0, 0.0, 1.0, 1.0, 0.5, 0.0, -1, -1, 0.4),
    (3.0, 0.0, 0.97, 1.0, 1.0, 0.2, 0, -1, 0.5),
    (-3.0, 0.0, 0.97, 1.0, 1.0, 0.35, 1, -1, 0.55),
    (3.0, 0.0, 0.96, 1.0, 1.0, 0.5, 0, -1, 0.6),
    (-3.0, 0.0, 0.96, 1.0, 1.0, 0.65, 1, -1, 0.65),
    (3.0, 0.0, 0.95, 1.0, 1.0, 0.8, 0, -1, 0.7),
    (-3.0, 0.0, 0.95, 1.0, 1.0, 1.0, 1, -1, 0.75),
    (14.0, 0.0, 1.0, 1.0, 1.0, 0.8, -1, 0, 0.8),
    (-14.0, 0.0, 1.0, 0.9, 1.0, 0.4, -1, 1, 0.8),
    (12.0, 0.0, 1.0, 0.8, 1.0, 0.0, -1, 2, 0.8),
    (-8.0, 0.0, 1.0, 0.8, 1.0, 0.0, -1, 3, 0.7),
    (0.0, -3.0, 1.06, 0.5, 1.0, 0.0, -1, -1, 0.6),
    (0.0, 0.0, 0.94, 0.25, 1.0, 0.0, -1, -1, 0.45),
    (0.0, 0.0, 1.0, 0.0, 1.0, 0.0, -1, -1, 0.3),
    (0.0, 0.0, 1.0, 0.0, 0.6, 0.0, -1, -1, 0.2),
    (0.0, 0.0, 1.0, 0.0, 0.3, 0.0, -1, -1, 0.1),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1, -1, 0.0),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1, -1, 0.0),
)
_NECK_BACK, _NECK_FRONT, _BACK = (16.0, 7.9), (21.3, 19.6), (9.5, 9.5)  # on the raven grid


def _snow(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, hop, squash, fall, scarf, cap, breath, shake, drift = _SNOW[i]
    pose = _pose(tilt=tilt, y=hop, squash=squash)
    props: list[Prop] = []
    if fall:
        props.append(Prop("snow", float(i), fall))
    if drift:
        props.append(Prop("drift", 56.0, drift))
    if scarf:
        root, front = rg.pose_point(pose, _NECK_BACK), rg.pose_point(pose, _NECK_FRONT)
        props.append(Prop("scarf", root[0], root[1], (front[0], front[1], i * 0.9, scarf)))
    back = rg.pose_point(pose, _BACK)
    if cap:
        props.append(Prop("snowcap", back[0], back[1] - 0.4, (cap,)))
    if breath >= 0:
        bx, by = rg.pose_point(pose, rg.BEAK_TIP)
        props.append(Prop("puff", bx + 1.5, by - 1.0, (float(breath), 0.0)))
    if shake >= 0:
        props.append(Prop("puff", back[0], back[1] - 2.0, (float(shake), 1.0)))
    return pose, props


# --- kite: it flies a kite, a gust nearly lifts it off, the string snaps
# per frame: (tilt, dx, hop, kite (x, y, rot, slack, scale) or None, wind)
_KITE = (
    (-4.0, 0.0, 0.0, (58.0, 11.0, 0.0, 0.6, 0.6), 0.6),
    (-6.0, 0.0, 0.0, (58.0, 11.0, 10.0, 0.6, 1.0), 0.8),
    (-8.0, 0.0, 0.0, (61.0, 8.0, -10.0, 0.5, 1.0), 0.8),
    (-8.0, 0.0, 0.0, (55.0, 6.0, 20.0, 0.4, 1.0), 0.8),
    (-8.0, 0.0, 0.0, (50.0, 9.0, 5.0, 0.6, 1.0), 0.8),
    (-8.0, 0.0, 0.0, (56.0, 12.0, -15.0, 0.4, 1.0), 0.8),
    (-8.0, 0.0, 0.0, (62.0, 9.0, 25.0, 0.5, 1.0), 0.8),
    (-8.0, 0.0, 0.0, (58.0, 5.0, -20.0, 0.4, 1.0), 0.8),
    (-8.0, 0.0, 0.0, (52.0, 7.0, 15.0, 0.5, 1.0), 0.8),
    (-8.0, 0.0, 0.0, (58.0, 11.0, 0.0, 0.5, 1.0), 0.8),
    (-14.0, 0.0, -2.0, (64.0, 4.0, 30.0, 0.2, 1.0), 1.0),  # a gust
    (-14.0, 0.0, -3.0, (62.0, 3.0, 10.0, 0.1, 1.0), 1.0),
    (-10.0, 0.0, -1.0, (63.0, 5.0, -10.0, 0.1, 1.0), 1.0),
    (16.0, 1.5, 0.0, (68.0, 1.0, 20.0, -1.0, 1.0), 0.8),  # the string snaps
    (10.0, 0.0, 0.0, (74.0, -4.0, 0.0, -1.0, 1.0), 0.4),
    (-8.0, 0.0, 0.0, None, 0.0),
    (-10.0, 0.0, 0.0, None, 0.0),
    (0.0, 0.0, 0.0, None, 0.0),
    (0.0, 0.0, 0.0, None, 0.0),
    (0.0, 0.0, 0.0, None, 0.0),
)


def _kite(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, dx, hop, kite, wind = _KITE[i]
    pose = _pose(x=_STAND + dx, tilt=tilt, y=hop, squash=0.95 if i == 17 else 1.0)
    props: list[Prop] = []
    if wind:
        props.append(Prop("wind", float(i), wind))
    if kite:
        x, y, rot, slack, scale = kite
        bx, by = rg.pose_point(pose, rg.BEAK_TIP)
        props.append(Prop("kite", x, y, (rot, bx, by, slack, scale)))
    return pose, props


# --- fishing: a rod in the beak, a bite, a fish leaps and is swallowed
_POND_X = 57.0
_FLOAT = (59.5, _GROUND - 1.2)
# per frame: (tilt, hop, squash, eyes shut, pond, rod, bend, line, float bob, ripple)
_FISH = (
    (0.0, 0.0, 1.0, False, 0.5, 0, 0.0, 0, 0.0, 0.0),
    (4.0, 0.0, 1.0, False, 1.0, 1, 0.0, 0, 0.0, 0.0),
    (6.0, 0.0, 1.0, False, 1.0, 1, 0.0, 2, 0.0, 0.0),  # the cast: float in the air
    (3.0, 0.0, 1.0, False, 1.0, 1, 0.0, 1, 0.0, 0.2),
    (3.0, 0.0, 0.97, False, 1.0, 1, 0.0, 1, 0.5, 0.4),
    (3.0, 0.0, 0.97, False, 1.0, 1, 0.0, 1, -0.5, 0.6),
    (3.0, 0.0, 0.97, True, 1.0, 1, 0.0, 1, 0.5, 0.8),
    (2.0, 0.0, 0.97, True, 1.0, 1, 0.0, 1, -0.5, 0.0),
    (-5.0, 0.0, 1.04, False, 1.0, 1, 0.0, 1, 0.5, 0.0),
    (3.0, 0.0, 1.0, False, 1.0, 1, 0.0, 1, 0.0, 0.0),
    (3.0, 0.0, 1.0, False, 1.0, 1, 0.0, 1, 0.0, 0.0),
    (-2.0, 0.0, 1.0, False, 1.0, 1, 0.0, 1, 1.0, 0.3),
    (3.0, 0.0, 1.0, False, 1.0, 1, 0.0, 1, 2.0, 0.0),  # a bite
    (-16.0, 0.0, 1.0, False, 1.0, 1, 1.0, 0, 0.0, 0.0),  # yank!
    (-14.0, 0.0, 1.0, False, 1.0, 1, 0.7, 0, 0.0, 0.0),
    (-10.0, 0.0, 1.0, False, 1.0, 1, 0.5, 0, 0.0, 0.0),
    (-6.0, 0.0, 1.0, False, 1.0, 1, 0.3, 0, 0.0, 0.0),
    (-4.0, 0.0, 1.0, False, 1.0, 1, 0.0, 0, 0.0, 0.0),
    (-3.0, 0.0, 1.08, False, 1.0, 1, 0.0, 0, 0.0, 0.0),  # gulp
    (0.0, -3.0, 1.0, False, 1.0, 1, 0.0, 0, 0.0, 0.0),
    (0.0, 0.0, 0.93, False, 1.0, 1, 0.0, 0, 0.0, 0.0),
    (0.0, 0.0, 1.0, False, 0.6, 0, 0.0, 0, 0.0, 0.0),
    (0.0, 0.0, 1.0, False, 0.3, 0, 0.0, 0, 0.0, 0.0),
    (0.0, 0.0, 1.0, False, 0.0, 0, 0.0, 0, 0.0, 0.0),
)
# the fish, per frame: (x, y, angle, size); frame 17+ it is at the beak
_FISH_AIR = {13: (60.0, 34.0, -70.0, 1.0), 14: (58.0, 23.0, -30.0, 1.0), 15: (53.0, 11.0, 15.0, 1.0), 16: (48.5, 14.0, 60.0, 1.0)}
_FISH_SHADOW = {9: (51.0, 0.6), 10: (55.0, 0.8), 11: (58.5, 1.0)}


def _fishing(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, hop, squash, shut, pond, rod, bend, line, bob, ripple = _FISH[i]
    pose = _pose(tilt=tilt, y=hop, squash=squash, eye_closed=shut)
    props: list[Prop] = []
    if pond:
        props.append(Prop("pond", _POND_X, pond, (ripple,)))
    bx, by = rg.pose_point(pose, rg.BEAK_TIP)
    if rod:
        tip = (bx + 12.0 - 9.0 * bend, by - 16.0 + 4.0 * bend)
        fx, fy = (56.0, 22.0) if line == 2 else (_FLOAT[0], _FLOAT[1] + bob)
        props.append(Prop("rod", tip[0], tip[1], (bx, by, fx, fy, 1.0 if line else 0.0)))
    if i == 3:
        props.append(Prop("splash", _FLOAT[0], _FLOAT[1] + 0.5, (0.0,)))
    if i in _FISH_SHADOW:
        sx, size = _FISH_SHADOW[i]
        props.append(Prop("fishshadow", sx, _GROUND + 0.9, (size,)))
    if i in (13, 14, 15):
        props.append(Prop("splash", _FLOAT[0], _FLOAT[1] + 0.5, (float(i - 13),)))
    if i in _FISH_AIR:
        x, y, angle, size = _FISH_AIR[i]
        props.append(Prop("fish", x, y, (angle, size)))
    elif 17 <= i <= 19:
        size = (1.0, 0.6, 0.25)[i - 17]
        props.append(Prop("fish", bx + 0.5, by + 3.0, (90.0, size)))
    return pose, props


# --- wizard: a hat drops on its head, magic, flowers sprout, the hat flies off
_BLOOMS = ((54.5, 0), (59.5, 1), (64.5, 2))  # (x, colour)
# per frame: (tilt, hop, squash, wing, hat mode, flower sizes)
_WIZARD = (
    (-8.0, 0.0, 1.0, None, "fall0", (0.0, 0.0, 0.0)),
    (-8.0, 0.0, 1.0, None, "fall1", (0.0, 0.0, 0.0)),
    (0.0, 0.0, 0.94, None, "on", (0.0, 0.0, 0.0)),
    (-4.0, 0.0, 1.0, None, "on", (0.0, 0.0, 0.0)),
    (-4.0, 0.0, 1.0, "up", "on", (0.0, 0.0, 0.0)),
    (-4.0, 0.0, 1.0, "mid", "on", (0.0, 0.0, 0.0)),
    (-4.0, 0.0, 1.0, "up", "on", (0.4, 0.0, 0.0)),
    (-4.0, 0.0, 1.0, "down", "on", (0.8, 0.0, 0.0)),
    (-4.0, 0.0, 1.0, "up", "on", (1.0, 0.5, 0.0)),
    (-4.0, 0.0, 1.0, "mid", "on", (1.0, 1.0, 0.6)),
    (-4.0, 0.0, 1.0, "up", "on", (1.0, 1.0, 1.0)),
    (-4.0, 0.0, 1.0, "down", "on", (1.0, 1.0, 1.0)),
    (22.0, 0.0, 1.0, None, "slip", (1.0, 1.0, 1.0)),
    (-6.0, 0.0, 1.0, None, "fly0", (1.0, 1.0, 1.0)),
    (-6.0, 0.0, 1.0, None, "fly1", (0.7, 0.7, 0.7)),
    (0.0, 0.0, 1.0, None, None, (0.4, 0.4, 0.4)),
    (0.0, 0.0, 1.0, None, None, (0.15, 0.15, 0.15)),
    (0.0, 0.0, 1.0, None, None, (0.0, 0.0, 0.0)),
    (0.0, 0.0, 1.0, None, None, (0.0, 0.0, 0.0)),
)
_MAGIC = {  # wing tip sparkles by frame: ((x, y, size), ...)
    4: ((26.0, 6.0, 2.4), (31.0, 3.0, 1.4)),
    5: ((12.0, 19.0, 2.2), (17.0, 14.0, 1.4)),
    6: ((26.0, 6.0, 2.2), (22.0, 10.0, 1.5)),
    7: ((29.0, 40.0, 1.8), (22.0, 36.0, 1.3)),
    8: ((26.0, 6.0, 2.4), (20.0, 12.0, 1.4)),
    9: ((12.0, 19.0, 2.2), (47.0, 12.0, 1.4)),
    10: ((26.0, 6.0, 2.4), (54.0, 28.0, 2.0), (63.0, 24.0, 1.6)),
    11: ((29.0, 40.0, 1.8), (58.0, 30.0, 1.8)),
    15: ((55.0, 33.0, 2.0), (60.0, 36.0, 1.5)),
}


def _wizard(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, hop, squash, wing, hat, sizes = _WIZARD[i]
    pose = _pose(tilt=tilt, y=hop, squash=squash, wing=wing)
    props: list[Prop] = []
    crown = rg.pose_point(pose, rg.CROWN)
    if hat == "fall0":
        props.append(Prop("hat", 37.0, -6.0, (15.0, 1.0, 0.0)))
    elif hat == "fall1":
        props.append(Prop("hat", 37.5, 9.0, (8.0, 1.0, 0.0)))
    elif hat in ("on", "slip"):
        props.append(Prop("hat", crown[0], crown[1] + 0.4, (tilt + (12.0 if hat == "slip" else 0.0), 1.0, 0.0)))
    elif hat == "fly0":
        props.append(Prop("hat", 47.0, 8.0, (90.0, 1.0, 0.0)))
    elif hat == "fly1":
        props.append(Prop("hat", 57.0, -2.0, (140.0, 1.0, 0.0)))
    if i == 2:
        props.append(Prop("sparkle", 37.0, 11.0, (2.6,)))
    for x, y, size in _MAGIC.get(i, ()):
        props.append(Prop("sparkle", x, y, (size,)))
    for (x, colour), size in zip(_BLOOMS, sizes):
        if size:
            props.append(Prop("bloom", x, size, (float(colour),)))
    return pose, props


# --- bubbles: it blows two, jumps to pop one, the other drifts up and bursts
_BUBBLE_A = {4: (52.0, 19.5), 5: (53.5, 17.5), 6: (54.5, 16.0), 7: (54.0, 15.0), 8: (52.5, 14.5)}
_BUBBLE_B = {8: (51.5, 20.5), 9: (54.0, 18.0), 10: (57.0, 14.5), 11: (60.0, 11.0), 12: (62.0, 7.5)}
# per frame: (tilt, hop, squash)
_BUBBLES = (
    (0.0, 0.0, 1.0),
    (-6.0, 0.0, 1.0),
    (-8.0, 0.0, 1.0),
    (-8.0, 0.0, 1.0),
    (-2.0, 0.0, 1.0),
    (-6.0, 0.0, 1.0),
    (-8.0, 0.0, 1.0),
    (-8.0, 0.0, 1.0),
    (-16.0, -6.0, 1.05),  # jumps for it
    (-10.0, -5.0, 1.0),
    (0.0, 0.0, 0.92),
    (-10.0, 0.0, 1.0),
    (-10.0, 0.0, 1.0),
    (-8.0, 0.0, 1.0),
    (-4.0, 0.0, 1.0),
    (0.0, 0.0, 1.0),
    (0.0, 0.0, 1.0),
    (0.0, 0.0, 1.0),
)


def _bubbles(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, hop, squash = _BUBBLES[i]
    pose = _pose(tilt=tilt, y=hop, squash=squash)
    bx, by = rg.pose_point(pose, rg.BEAK_TIP)
    props: list[Prop] = []
    if i in (1, 2, 3):  # blowing the first
        r = (0.9, 2.3, 3.8)[i - 1]
        props.append(Prop("bubble", bx + 0.8 + r * 0.5, by - 1.0 - r * 0.4, (r,)))
    if i in _BUBBLE_A:
        props.append(Prop("bubble", *_BUBBLE_A[i], (4.6,)))
    if i in (5, 6, 7):  # blowing the second
        r = (0.9, 2.3, 3.6)[i - 5]
        props.append(Prop("bubble", bx + 0.8 + r * 0.5, by - 1.0 - r * 0.4, (r,)))
    if i in _BUBBLE_B:
        props.append(Prop("bubble", *_BUBBLE_B[i], (4.2,)))
    if i in (9, 10):
        props.append(Prop("pop", 52.5, 14.0, (float(i - 9),)))
    if i in (13, 14, 15):
        props.append(Prop("pop", 62.5, 5.0, (float(i - 13),)))
    return pose, props


# --- egg: it taps an egg, it cracks, a chick hatches, hearts, the chick hops off
_EGG_X = 56.0
# per frame: (tilt, hop, squash, egg size, wobble, crack)
_EGG = (
    (0.0, 0.0, 1.0, 0.5, 0.0, 0.0),
    (0.0, 0.0, 1.0, 1.1, 0.0, 0.0),
    (10.0, 0.0, 1.0, 1.0, 0.0, 0.0),
    (20.0, 0.0, 1.0, 1.0, 8.0, 0.0),
    (4.0, 0.0, 1.0, 1.0, -8.0, 0.0),
    (20.0, 0.0, 1.0, 1.0, 10.0, 0.3),
    (4.0, 0.0, 1.0, 1.0, -10.0, 0.6),
    (6.0, 0.0, 1.0, 1.0, 6.0, 1.0),
    (-8.0, -2.0, 1.06, 0.0, 0.0, 0.0),  # pop!
    (-6.0, -1.0, 1.0, 0.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (2.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (6.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (14.0, 0.0, 1.0, 0.0, 0.0, 0.0),  # leans down to the chick
    (12.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (12.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (8.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (2.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (-4.0, 0.0, 1.0, 0.0, 0.0, 0.0),  # waves it off
    (-4.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
)
# chick, per frame: (x, hop, facing, squash)
_CHICK_AT = {
    8: (56.0, 0.0, 1, 0.5),
    9: (56.0, 0.0, 1, 1.0),
    10: (56.0, 0.0, 1, 1.0),
    11: (53.5, -3.0, -1, 1.0),
    12: (51.5, 0.0, -1, 0.85),
    13: (50.0, 0.0, -1, 1.0),
    14: (50.0, 0.0, -1, 1.0),
    15: (50.0, 0.0, -1, 1.0),
    16: (50.0, -1.5, -1, 1.0),
    17: (52.0, -3.0, 1, 1.0),
    18: (56.0, 0.0, 1, 0.85),
    19: (60.0, -3.0, 1, 1.0),
    20: (64.0, 0.0, 1, 0.85),
    21: (68.0, -3.0, 1, 1.0),
}


def _egg(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, hop, squash, size, wobble, crack = _EGG[i]
    pose = _pose(tilt=tilt, y=hop, squash=squash)
    props: list[Prop] = []
    if size:
        props.append(Prop("egg", _EGG_X, size, (wobble, crack)))
    if 8 <= i <= 20:
        if i <= 10:  # the two halves fly up and fall back
            h = (33.0, 24.0, 31.0)[i - 8]
            props.append(Prop("shell", 53.0 - (i - 8) * 1.5, h, (-35.0 - 12.0 * (i - 8), -1.0, 1.0)))
            props.append(Prop("shell", 59.0 + (i - 8) * 1.5, h - 2.0, (35.0 + 12.0 * (i - 8), 1.0, 1.0)))
        else:
            fade = 1.0 if i < 18 else (21 - i) / 3.0
            props.append(Prop("shell", 51.5, _GROUND - 0.6, (-62.0, -1.0, fade)))
            props.append(Prop("shell", 62.0, _GROUND - 0.6, (62.0, 1.0, fade)))
    if i in _CHICK_AT:
        x, hop_c, face, sq = _CHICK_AT[i]
        props.append(Prop("chick", x, _GROUND + 0.4 + hop_c, (float(face), sq)))
    if i == 8:
        props.append(Prop("sparkle", 56.0, 27.0, (3.0,)))
    if 14 <= i <= 17:
        t = i - 14
        props.append(Prop("heart", 46.0 - t * 1.2, 14.0 - 2.4 * t, (2.1, 1.0 - t / 5.0)))
        if t >= 1:
            props.append(Prop("heart", 52.5 + t * 0.8, 16.0 - 2.2 * (t - 1), (1.6, 1.0 - (t - 1) / 4.0)))
    return pose, props


# --- birthday: a cake, a party hat, a wish, the candle goes out, confetti
_CAKE_X = 56.0
# per frame: (tilt, hop, squash, cake size, flame, flame bend, hat mode)
_BIRTHDAY = (
    (6.0, 0.0, 1.0, 0.5, 0.0, 0.0, None),
    (8.0, 0.0, 1.0, 1.0, 1.0, 0.0, None),
    (-4.0, 0.0, 1.0, 1.0, 1.0, 0.0, "fall0"),
    (0.0, 0.0, 0.96, 1.0, 1.0, 0.0, "fall1"),
    (-4.0, 0.0, 1.0, 1.0, 1.0, 0.0, "on"),
    (12.0, 0.0, 1.0, 1.0, 1.0, 0.0, "on"),
    (-8.0, 0.0, 1.07, 1.0, 1.0, 0.0, "on"),  # takes a deep breath
    (-10.0, 0.0, 1.1, 1.0, 1.0, 0.0, "on"),
    (22.0, 0.0, 1.0, 1.0, 0.7, 1.0, "on"),  # blows
    (10.0, 0.0, 1.0, 1.0, 0.0, 0.0, "on"),
    (4.0, -4.0, 1.04, 1.0, 0.0, 0.0, "on"),
    (0.0, 0.0, 0.92, 1.0, 0.0, 0.0, "on"),
    (4.0, 0.0, 1.0, 1.0, 0.0, 0.0, "on"),
    (-6.0, 0.0, 1.0, 1.0, 0.0, 0.0, "on"),
    (6.0, 0.0, 1.0, 1.0, 0.0, 0.0, "on"),
    (-4.0, 0.0, 1.0, 1.0, 0.0, 0.0, "on"),
    (0.0, 0.0, 1.0, 0.7, 0.0, 0.0, "on"),
    (0.0, 0.0, 1.0, 0.4, 0.0, 0.0, "off"),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, None),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, None),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, None),
)


def _birthday(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, hop, squash, cake, flame, bend, hat = _BIRTHDAY[i]
    pose = _pose(tilt=tilt, y=hop, squash=squash)
    props: list[Prop] = []
    if cake:
        props.append(Prop("cake", _CAKE_X, cake, (flame, bend)))
    crown = rg.pose_point(pose, rg.CROWN)
    if hat == "fall0":
        props.append(Prop("hat", 37.0, -4.0, (10.0, 1.0, 1.0)))
    elif hat == "fall1":
        props.append(Prop("hat", 37.5, 10.0, (6.0, 1.0, 1.0)))
    elif hat == "on":
        props.append(Prop("hat", crown[0], crown[1] + 0.4, (tilt, 1.0, 1.0)))
    elif hat == "off":
        props.append(Prop("hat", crown[0] + 5.0, crown[1] - 6.0, (40.0, 1.0, 1.0)))
        props.append(Prop("sparkle", crown[0] + 5.0, crown[1] - 8.0, (2.4,)))
    if i == 0 or i == 1:
        props.append(Prop("sparkle", _CAKE_X + 5.0, 30.0, (2.4 if i else 1.6,)))
    if i == 8:  # the breath
        bx, by = rg.pose_point(pose, rg.BEAK_TIP)
        props.append(Prop("puff", bx + 1.5, by + 1.0, (0.0, 0.0)))
    if 9 <= i <= 14:
        props.append(Prop("smoke", _CAKE_X + 1.2, _GROUND - 14.8, (float(i - 9),)))
    if 9 <= i <= 18:
        props.append(Prop("confetti", float(i - 9)))
    return pose, props


# --- disco: a mirror ball comes down, lights, the raven dances
_DISCO_BALL = {1: -2.0, 2: 4.0, 20: 0.0, 21: -8.0}
_DISCO_LIGHT = (0.0, 0.4, 0.8) + (1.0,) * 17 + (0.7, 0.4, 0.15, 0.0)


def _disco(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    dancing = 3 <= i <= 19
    if dancing:
        up = i % 2 == 0
        pose = _pose(
            x=_STAND + 2.5 * math.sin(i * 1.2),
            tilt=-10.0 if up else 10.0,
            y=-3.0 if up else 0.0,
            wing="up" if up else "down",
            facing_left=(i // 4) % 2 == 1,
            leg_a=rg.LEG_A_LIFTED if up else rg.LEG_A,
            leg_b=rg.LEG_B_LIFTED if up else rg.LEG_B,
        )
    else:
        pose = _pose()
    props: list[Prop] = []
    ball = _DISCO_BALL.get(i, 5.0 if 3 <= i <= 19 else None)
    light = _DISCO_LIGHT[i]
    if ball is not None:
        props.append(Prop("discoball", ball, float(i)))
    if light:
        props.append(Prop("beams", float(i), light, (5.0,)))
        props.append(Prop("floor", float(i), light))
    return pose, props


_SCENES = {
    "cage": (len(_CAGE_RAVEN), _cage),
    "foot": (len(_FOOT_RAVEN), _foot),
    "snow": (len(_SNOW), _snow),
    "kite": (len(_KITE), _kite),
    "fishing": (len(_FISH), _fishing),
    "wizard": (len(_WIZARD), _wizard),
    "bubbles": (len(_BUBBLES), _bubbles),
    "egg": (len(_EGG), _egg),
    "birthday": (len(_BIRTHDAY), _birthday),
    "disco": (len(_DISCO_LIGHT), _disco),
}
NAMES = tuple(_SCENES)


def frame_count(name: str) -> int:
    return _SCENES[name][0]


def frame(name: str, index: int) -> tuple[rg.RavenPose, list[Prop]]:
    count, build = _SCENES[name]
    return build(max(0, min(index, count - 1)))
