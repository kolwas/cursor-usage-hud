"""The raven's longer adventures: caught in the rain with an umbrella (and a
rainbow after), a butterfly it cannot catch, a stubborn worm, a treasure
chest, a nap under the moon, a song, a trip on balloons and fireworks.

Each adventure is a timeline: ``frame(name, i)`` gives the raven's pose and
the props (plain numbers, see raven_props.Prop) for frame ``i``. Nothing is
drawn here — raven_art paints the props, raven_glyph the bird — and every
adventure but the balloon trip ends with the raven standing exactly where it
began and no prop left, so the pace carries on seamlessly.
"""

from __future__ import annotations

import math

from usage_hud.ui import raven_glyph as rg
from usage_hud.ui.raven_props import Prop

_STAND = rg.CENTRE_X
_GROUND = rg.GROUND_Y
_GRIP = (27.0, 13.2)  # on the raven grid: just behind the tip of the beak
_CANOPY_DX, _CANOPY_DY = -3.0, -10.5  # the umbrella's hem, relative to the grip
_NO_PROPS: list[Prop] = []


def _pose(**kw) -> rg.RavenPose:
    return rg.RavenPose(x=_STAND, **kw)


# --- rain: an umbrella held in the beak, then a rainbow -----------------------
# per frame: (tilt, hop, umbrella open 0..1, rain 0..1, rainbow 0..1)
_RAIN = (
    (-2.0, 0.0, 0.0, 0.4, 0.0),
    (-3.0, 0.0, 0.0, 0.8, 0.0),
    (-4.0, 0.0, 0.4, 1.0, 0.0),
    (-3.0, 0.0, 0.8, 1.0, 0.0),
    (-4.0, 0.0, 1.0, 1.0, 0.0),
    (-2.0, 0.0, 1.0, 1.0, 0.0),
    (-4.0, 0.0, 1.0, 1.0, 0.0),
    (-2.0, 0.0, 1.0, 1.0, 0.0),
    (-4.0, 0.0, 1.0, 0.9, 0.0),
    (-3.0, 0.0, 1.0, 0.6, 0.0),
    (-4.0, 0.0, 1.0, 0.3, 0.35),
    (-5.0, 0.0, 0.7, 0.0, 0.65),
    (-3.0, -4.0, 0.35, 0.0, 0.85),
    (0.0, -1.0, 0.0, 0.0, 0.85),
    (0.0, 0.0, 0.0, 0.0, 0.5),
    (0.0, 0.0, 0.0, 0.0, 0.0),
)


def _rain(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, hop, umbrella, rain, rainbow = _RAIN[i]
    pose = _pose(tilt=tilt, y=hop)
    props: list[Prop] = []
    if rainbow:
        props.append(Prop("rainbow", rainbow))
    grip = rg.pose_point(pose, _GRIP)
    canopy = (grip[0] + _CANOPY_DX, grip[1] + _CANOPY_DY)
    if rain:
        props.append(Prop("rain", i, rain, (umbrella, canopy[0], canopy[1])))
    if umbrella:
        props.append(Prop("umbrella", canopy[0], canopy[1], (umbrella, grip[0], grip[1])))
    return pose, props


# --- butterfly: it hovers at the beak, dodges the snap, flutters off ----------
# per frame: (butterfly x, y, raven tilt)
_BUTTERFLY = (
    (62.0, 8.0, 0.0),
    (60.0, 12.0, -3.0),
    (58.0, 10.0, -4.0),
    (55.0, 15.0, -2.0),
    (53.0, 19.0, 2.0),
    (55.0, 20.0, 5.0),
    (52.0, 17.0, 15.0),  # the snap
    (47.0, 9.0, -14.0),
    (40.0, 5.0, -10.0),
    (30.0, 7.0, -8.0),
    (20.0, 4.0, -5.0),
    (10.0, 8.0, -3.0),
    (-2.0, 5.0, 0.0),
    (-12.0, 5.0, 0.0),
)


def _butterfly(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    x, y, tilt = _BUTTERFLY[i]
    pose = _pose(tilt=tilt, squash=0.97 if i == 6 else 1.0, pivot=rg.FEET_PIVOT)
    if x < -6.0:
        return pose, _NO_PROPS
    spread = 1.0 if i % 2 == 0 else 0.35  # one flap per frame
    return pose, [Prop("butterfly", x, y, (spread,))]


# --- worm: it pops up, dodges two pecks, is pulled out and swallowed ----------
_WORM_X = 56.0
# per frame: (tilt, hop, squash, mound size, worm height, wiggle) — the worm
# stands on its mound; from frame 6 it hangs from the beak instead.
_WORM_STAND = (
    (0.0, 0.0, 1.0, 0.5, 0.0, 0.0),
    (-3.0, 0.0, 1.04, 1.0, 4.0, 0.0),
    (4.0, 0.0, 1.0, 1.0, 8.0, 1.0),
    (22.0, 0.0, 1.0, 1.0, 9.0, 2.0),
    (4.0, 0.0, 1.0, 1.0, 9.5, 3.0),
    (24.0, 0.0, 1.0, 1.0, 9.0, 4.0),
)
# frames 6..: (tilt, hop, squash, mound size, dangle length, taut)
_WORM_PULL = (
    (-6.0, -1.0, 1.0, 1.0, 0.0, 1.0),  # pulling: stretched between mound and beak
    (-12.0, -1.5, 1.0, 0.9, 0.0, 1.0),
    (-14.0, 0.0, 0.92, 0.7, 11.0, 0.0),  # pop: free, hanging from the beak
    (-8.0, 0.0, 1.06, 0.5, 6.0, 0.0),
    (-6.0, 0.0, 1.0, 0.4, 3.0, 0.0),
    (-3.0, -3.0, 1.08, 0.3, 0.0, 0.0),  # gulp, a happy hop
    (0.0, 0.0, 0.92, 0.2, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.1, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
)


def _worm(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    if i < len(_WORM_STAND):
        tilt, hop, squash, mound, height, wiggle = _WORM_STAND[i]
        pose = _pose(tilt=tilt, y=hop, squash=squash, pivot=rg.FEET_PIVOT)
        props = [Prop("mound", _WORM_X, mound)]
        if height:
            props.append(Prop("worm", _WORM_X, _GROUND - height, (_WORM_X, _GROUND, 1.3, wiggle)))
        return pose, props
    tilt, hop, squash, mound, dangle, taut = _WORM_PULL[i - len(_WORM_STAND)]
    pose = _pose(tilt=tilt, y=hop, squash=squash, pivot=rg.FEET_PIVOT)
    props = [Prop("mound", _WORM_X, mound)] if mound else []
    beak = rg.pose_point(pose, rg.BEAK_TIP)
    if taut:
        props.append(Prop("worm", beak[0], beak[1] + 1.0, (_WORM_X, _GROUND, 0.5, float(i))))
    elif dangle:
        props.append(Prop("worm", beak[0], beak[1] + 1.0, (beak[0] + 0.5, beak[1] + 1.0 + dangle, 1.1, float(i))))
    return pose, props


# --- treasure: a chest pops up, opens, a coin leaps out and is caught ---------
_CHEST_X = 55.5
# per frame: (tilt, hop, lid open, chest size, glow, coin x, coin y) — a coin
# y of None means no coin in the air
_TREASURE = (
    (0.0, 0.0, 0.0, 0.5, 0.0, None, None),
    (4.0, 0.0, 0.0, 1.1, 0.0, None, None),
    (8.0, 0.0, 0.35, 1.0, 0.0, None, None),
    (12.0, 0.0, 0.75, 1.0, 0.5, None, None),
    (12.0, 0.0, 1.0, 1.0, 1.0, None, None),
    (6.0, 0.0, 1.0, 1.0, 1.0, 57.0, 28.0),
    (-4.0, 0.0, 1.0, 1.0, 0.8, 55.0, 16.0),
    (-12.0, 0.0, 1.0, 1.0, 0.6, 52.0, 8.0),
    (-12.0, 0.0, 1.0, 1.0, 0.4, 49.5, 10.0),
    (-4.0, 0.0, 1.0, 1.0, 0.3, 48.0, 17.0),
    (2.0, 0.0, 0.8, 1.0, 0.2, 49.0, 23.0),  # caught
    (-6.0, 0.0, 0.5, 1.0, 0.0, "beak", None),
    (-3.0, -3.0, 0.25, 1.0, 0.0, None, None),
    (0.0, -1.0, 0.0, 0.8, 0.0, None, None),
    (0.0, 0.0, 0.0, 0.4, 0.0, None, None),
    (0.0, 0.0, 0.0, 0.0, 0.0, None, None),
)


def _treasure(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, hop, lid, size, glow, coin_x, coin_y = _TREASURE[i]
    pose = _pose(tilt=tilt, y=hop, pivot=rg.FEET_PIVOT, squash=1.04 if i == 10 else 1.0)
    props: list[Prop] = []
    if size:
        props.append(Prop("chest", _CHEST_X, lid, (size, glow)))
    if coin_x == "beak":
        bx, by = rg.pose_point(pose, rg.BEAK_TIP)
        props.append(Prop("coin", bx - 0.5, by + 0.5, (0.0,)))
        props.append(Prop("sparkle", bx + 3.0, by - 3.5, (3.0,)))
        props.append(Prop("sparkle", bx - 3.0, by - 5.5, (2.0,)))
    elif coin_x is not None:
        props.append(Prop("coin", coin_x, coin_y, (i * 1.1,)))
        if i in (7, 8):
            props.append(Prop("sparkle", coin_x + 4.0, coin_y - 2.0, (3.0 if i == 7 else 2.0,)))
    if i == 12:
        props.append(Prop("sparkle", 52.0, 20.0, (2.4,)))
    return pose, props


# --- sleep: a yawn, a nap under the moon, a start ----------------------------
# per frame: (tilt, hop, squash, eyes shut, moon 0..1, zzz, alert)
_SLEEP = (
    (-8.0, 0.0, 1.06, False, 0.3, False, 0.0),
    (-4.0, 0.0, 1.0, False, 0.6, False, 0.0),
    (3.0, 0.0, 0.95, True, 1.0, False, 0.0),
    (6.0, 0.0, 0.92, True, 1.0, True, 0.0),
    (7.0, 0.0, 0.94, True, 1.0, True, 0.0),
    (6.0, 0.0, 0.92, True, 1.0, True, 0.0),
    (7.0, 0.0, 0.94, True, 1.0, True, 0.0),
    (6.0, 0.0, 0.92, True, 1.0, True, 0.0),
    (7.0, 0.0, 0.94, True, 1.0, True, 0.0),
    (6.0, 0.0, 0.92, True, 1.0, True, 0.0),
    (7.0, 0.0, 0.94, True, 1.0, True, 0.0),
    (-6.0, -6.0, 1.08, False, 0.8, False, 1.0),  # startled awake
    (0.0, 0.0, 0.88, False, 0.5, False, 1.0),
    (0.0, 0.0, 1.0, False, 0.25, False, 0.0),
    (0.0, 0.0, 1.0, False, 0.0, False, 0.0),
)


def _sleep(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    tilt, hop, squash, shut, moon, zzz, alert = _SLEEP[i]
    pose = _pose(tilt=tilt, y=hop, squash=squash, eye_closed=shut, pivot=rg.FEET_PIVOT)
    props: list[Prop] = []
    if moon:
        props.append(Prop("moon", moon))
        props.append(Prop("stars", i, moon))
    if zzz:
        props.append(Prop("zzz", i))
    if alert:
        props.append(Prop("alert", alert))
    return pose, props


# --- music: it sings, notes float away ---------------------------------------
_NOTE_BORN = (1, 4, 7)
_NOTE_LIFE = 7
_SONG_FRAMES = 15


def _music(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    sings = 0 < i < _SONG_FRAMES - 2
    tilt = (-11.0 if i % 2 else -6.0) if sings else 0.0
    pose = _pose(tilt=tilt, y=-1.0 if sings and i % 2 else 0.0, pivot=rg.FEET_PIVOT)
    props: list[Prop] = []
    bx, by = rg.pose_point(pose, rg.BEAK_TIP)
    for n, born in enumerate(_NOTE_BORN):
        age = i - born
        if 0 <= age < _NOTE_LIFE:
            x = bx + 1.0 + 1.8 * age + 2.0 * math.sin(age * 1.1 + n)
            y = by - 1.0 - 2.3 * age
            props.append(Prop("note", x, y, (float(n % 2), 1.0 - age / _NOTE_LIFE, float(n))))
    return pose, props


# --- balloons: a bunch lifts it away; it glides back in ----------------------
_BACK = (9.0, 10.0)  # on the raven grid: the arch of the back, where the strings are tied
_BALLOON_APPROACH = (  # (knot x, knot y, tilt, hop) while the bunch drifts in
    (62.0, 12.0, -4.0, 0.0),
    (52.0, 15.0, -8.0, 0.0),
    (40.0, 18.0, -8.0, -3.0),
)
# where the bunch carries the raven, frame by frame: (x, y) of its box
_BALLOON_RISE = ((20.0, -2.0), (26.0, -4.0), (34.0, -5.0), (44.0, -6.0), (56.0, -6.0), (72.0, -5.0))
_BALLOON_GONE = 2


def _balloons_frame_count() -> int:
    return len(_BALLOON_APPROACH) + len(_BALLOON_RISE) + _BALLOON_GONE + rg.FLY_RETURN_FRAMES


def _balloons(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    approach = len(_BALLOON_APPROACH)
    if i < approach:
        kx, ky, tilt, hop = _BALLOON_APPROACH[i]
        return _pose(tilt=tilt, y=hop, pivot=rg.FEET_PIVOT), [Prop("balloons", kx, ky, (float(i),))]
    i -= approach
    if i < len(_BALLOON_RISE):
        x, y = _BALLOON_RISE[i]
        pose = rg.RavenPose(
            x=x, y=y, tilt=-5.0, leg_a=rg.LEG_A_LIFTED, leg_b=rg.LEG_B_LIFTED, pivot=rg.FEET_PIVOT
        )
        knot_x, knot_y = rg.pose_point(pose, _BACK)
        return pose, [Prop("balloons", knot_x, knot_y, (float(i + approach),))]
    i -= len(_BALLOON_RISE)
    if i < _BALLOON_GONE:
        return rg.RavenPose(x=_STAND, visible=False), _NO_PROPS
    return rg.fly_raven_pose(rg.FLY_CLIMB_FRAMES + rg.FLY_GONE_FRAMES + i - _BALLOON_GONE), _NO_PROPS


# --- fireworks: three bursts in the sky, the raven watching -------------------
_FIREWORKS_FRAMES = 15
_BURST_AGES = 7  # a burst lives for this many frames
_BURSTS = ((56.0, 9.0, 1), (26.0, 7.0, 4), (44.0, 5.0, 7))  # (x, y, first frame)


def _fireworks(i: int) -> tuple[rg.RavenPose, list[Prop]]:
    watching = 0 < i < _FIREWORKS_FRAMES - 2
    tilt = -12.0 if watching else 0.0
    startle = i == 1
    pose = _pose(tilt=tilt, squash=1.04 if startle else 1.0, y=-2.0 if i == 12 else 0.0, pivot=rg.FEET_PIVOT)
    props: list[Prop] = []
    for n, (x, y, born) in enumerate(_BURSTS):
        age = i - born
        if 0 <= age < _BURST_AGES:
            props.append(Prop("burst", x, y, (float(age), float(n))))
    return pose, props


_SCENES = {
    "rain": (len(_RAIN), _rain),
    "butterfly": (len(_BUTTERFLY), _butterfly),
    "worm": (len(_WORM_STAND) + len(_WORM_PULL), _worm),
    "treasure": (len(_TREASURE), _treasure),
    "sleep": (len(_SLEEP), _sleep),
    "music": (_SONG_FRAMES, _music),
    "balloons": (_balloons_frame_count(), _balloons),
    "fireworks": (_FIREWORKS_FRAMES, _fireworks),
}
NAMES = tuple(_SCENES)
# The balloon trip ends with a landing at the start of the pace, like being
# chased off by the broom; every other adventure ends where it began.
LANDS_AT_START = frozenset({"balloons"})


def frame_count(name: str) -> int:
    return _SCENES[name][0]


def frame(name: str, index: int) -> tuple[rg.RavenPose, list[Prop]]:
    count, build = _SCENES[name]
    return build(max(0, min(index, count - 1)))
