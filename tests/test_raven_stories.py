"""The raven's long set pieces (raven_stories / raven_story_art): the cage
and the mouse, the foot, snow, a kite, fishing, a wizard's hat, bubbles, an
egg, a birthday, a disco. Each is a timeline that tells its story in order
and leaves the pace as it found it.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from usage_hud.ui import raven_art, raven_gags  # noqa: E402
from usage_hud.ui import raven_glyph as rg  # noqa: E402
from usage_hud.ui import raven_stories as st  # noqa: E402

LINE, EYE = QColor("#cbbf8f"), QColor("#c9a24a")
LEGACY_KINDS = {"cage", "foot"}  # painted by raven_gags


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _frames(name):
    return [st.frame(name, i) for i in range(st.frame_count(name))]


def _props(name, kind):
    """(frame index, prop) for every prop of ``kind`` in the scene."""
    return [(i, p) for i, (_pose, props) in enumerate(_frames(name)) for p in props if p.kind == kind]


def test_the_ten_set_pieces_are_registered_and_long():
    assert set(st.NAMES) == {"cage", "foot", "snow", "kite", "fishing", "wizard", "bubbles", "egg", "birthday", "disco"}
    assert set(st.NAMES) <= set(raven_gags.GAG_NAMES)
    for name in st.NAMES:
        assert raven_gags.gag_frame_count(name) == st.frame_count(name) >= 18
    assert st.frame_count("cage") >= 30 and st.frame_count("foot") >= 25  # the two that were short


def test_every_prop_has_a_painter_and_every_frame_renders():
    for name in st.NAMES:
        for i, (_pose, props) in enumerate(_frames(name)):
            assert {p.kind for p in props} <= raven_art.KINDS | LEGACY_KINDS, (name, i)
            html = rg.raven_scene_html(line_color=LINE, eye_color=EYE, mode="gag", gag=name, index=i)
            assert html.startswith('<img src="data:image/png;base64,')


def test_each_set_piece_is_animated_and_ends_standing_with_nothing_left():
    for name in st.NAMES:
        images = {
            rg.raven_scene_html(line_color=LINE, eye_color=EYE, mode="gag", gag=name, index=i)
            for i in range(st.frame_count(name))
        }
        assert len(images) >= st.frame_count(name) - 5, name
        pose, props = st.frame(name, st.frame_count(name) - 1)
        assert (pose.x, pose.squash, pose.tilt, pose.visible) == (rg.CENTRE_X, 1.0, 0.0, True), name
        assert props == [], name
        assert not pose.eye_closed and pose.y == 0.0, name


def test_the_panel_plays_every_set_piece_to_the_end_and_resumes_the_pace():
    from usage_hud.ui.hud import WeatherPanel

    panel = WeatherPanel(opacity=0.9)
    for name in st.NAMES:
        panel._raven_mode = "walk"
        panel._raven_step = rg.WALK_CYCLE_STEPS // 2
        panel._start_gag(name)
        for _ in range(st.frame_count(name)):
            panel._tick_raven_mark()
        assert panel._raven_mode == "walk" and panel._raven_step == rg.WALK_CYCLE_STEPS // 2, name
    panel.deleteLater()


# --- the cage -----------------------------------------------------------------------------------
def test_the_cage_drops_the_mouse_unlocks_it_and_the_cage_lifts_away():
    cage = _props("cage", "cage")
    assert cage[0][1].a < -40.0 and cage[0][0] == 0  # it comes from above
    landed = next(i for i, p in cage if p.a == 0.0)
    assert landed <= 3
    mouse = _props("cage", "mouse")
    key_in_lock = next(i for i, p in mouse if p.extra[2] == 2.0)
    unlocked = next(i for i, p in _props("cage", "padlock") if p.extra[0] == 1.0)
    lifted = next(i for i, p in cage if p.a < -5.0 and i > unlocked)
    assert landed < mouse[0][0] < key_in_lock <= unlocked < lifted  # nobody is freed before the key turns
    assert mouse[0][1].a > 65.0 and mouse[-1][1].a > 65.0  # in from the right, out to the right
    assert mouse[0][1].extra[1] == -1.0 and mouse[-1][1].extra[1] == 1.0  # runs in, runs off
    assert mouse[-1][0] > lifted


def test_in_the_cage_it_rattles_the_bars_paces_and_droops_before_the_wish():
    poses = [p for p, _ in _frames("cage")]
    first_peck = next(i for i, p in enumerate(poses) if p.tilt >= 18.0)
    paced = [i for i, p in enumerate(poses) if p.facing_left]
    drooped = [i for i, p in enumerate(poses) if p.eye_closed]
    wish = [i for i, _ in _props("cage", "thought")]
    assert first_peck < min(paced) < max(paced) < min(drooped) <= min(wish) <= max(drooped) + 1
    assert len(drooped) >= 3 and len(paced) >= 3


def test_the_padlock_and_the_wish_stay_with_the_cage():
    for i, (pose, props) in enumerate(_frames("cage")):
        cage = [p for p in props if p.kind == "cage"]
        lock = [p for p in props if p.kind == "padlock"]
        assert bool(cage) == bool(lock), i
        if cage:
            assert lock[0].b == pytest.approx(36.0 + cage[0].a)


# --- the foot -------------------------------------------------------------------------------------
def test_the_shadow_grows_before_the_foot_stomps_and_the_foot_lifts_the_flat_raven():
    shadow = _props("foot", "shadow")
    foot = {i: p.a for i, p in _props("foot", "foot")}
    first_foot = min(foot)
    sizes = [p.a for _, p in shadow if _ < first_foot]
    assert sizes == sorted(sizes) and sizes[0] < 0.5 and sizes[-1] == 1.0 and len(set(sizes)) >= 4  # it grows as the foot nears
    assert shadow[0][0] == 0
    assert [p.a for _, p in shadow][-1] < 0.3  # and fades once the foot has gone
    stomp = next(i for i in sorted(foot) if foot[i] == 0.0)
    poses = [p for p, _ in _frames("foot")]
    assert poses[stomp].squash < 0.2
    rising = [i for i in sorted(foot) if i > stomp and foot[i] < 0.0 and poses[i].squash < 0.2]
    assert len(rising) >= 3
    for i in rising:  # stuck to the sole: it rises with the foot
        assert abs(poses[i].y - foot[i]) <= 6.0
    dust = [(i, p.a) for i, p in _props("foot", "dust")]
    assert dust[0][0] == stomp and [a for _, a in dust] == sorted(a for _, a in dust)


def test_after_the_stomp_the_raven_pops_back_dizzy_with_a_feather_floating_down():
    poses = [p for p, _ in _frames("foot")]
    squash = [p.squash for p in poses]
    peak = max(range(len(squash)), key=lambda i: squash[i])
    assert squash[peak] > 1.15 and min(squash[peak - 3:peak]) < 0.6  # pumped up, overshoots
    dizzy = [i for i, _ in _props("foot", "dizzy")]
    assert dizzy and min(dizzy) > peak
    feather = [p.b for _, p in _props("foot", "feather")]
    assert feather == sorted(feather) and len(feather) >= 5  # drifting down


# --- snow -------------------------------------------------------------------------------------------
def test_it_snows_then_a_scarf_shivering_snow_on_its_back_and_a_shake():
    first = lambda kind: _props("snow", kind)[0][0]  # noqa: E731
    assert first("snow") < first("scarf") < first("snowcap")
    caps = [p.extra[0] for _, p in _props("snow", "snowcap")]
    assert max(caps) == 1.0 and caps.index(1.0) < len(caps) - 1
    shake = [i for i, p in _props("snow", "puff") if p.extra[1] == 1.0]
    assert shake and min(shake) > first("snowcap")
    poses = [p for p, _ in _frames("snow")]
    assert max(abs(poses[i].tilt) for i in shake) >= 12.0  # the shake itself
    assert [p.extra[0] for _, p in _props("snow", "puff") if p.extra[1] == 0.0][:2] == [0.0, 1.0]  # a breath


def test_the_scarf_is_tied_round_the_neck_and_follows_the_bird():
    for i, p in _props("snow", "scarf"):
        pose = st.frame("snow", i)[0]
        assert (p.a, p.b) == pytest.approx(rg.pose_point(pose, st._NECK_BACK))
        assert p.extra[:2] == pytest.approx(rg.pose_point(pose, st._NECK_FRONT))


# --- the kite ------------------------------------------------------------------------------------------
def test_the_kite_string_is_held_in_the_beak_until_it_snaps():
    kites = _props("kite", "kite")
    held = [(i, p) for i, p in kites if p.extra[3] >= 0.0]
    for i, p in held:
        beak = rg.pose_point(st.frame("kite", i)[0], rg.BEAK_TIP)
        assert p.extra[1:3] == pytest.approx(beak)
    snapped = [i for i, p in kites if p.extra[3] < 0.0]
    assert snapped and min(snapped) > max(i for i, _ in held)
    assert kites[-1][1].a > rg.SCENE_WIDTH + 2.0 - 0.0 or kites[-1][1].b < 0.0  # it flies off
    poses = [p for p, _ in _frames("kite")]
    assert min(p.y for p in poses) <= -3.0  # the gust nearly lifts the raven


# --- fishing ----------------------------------------------------------------------------------------------
def test_the_rod_is_in_the_beak_the_bite_comes_before_the_leap_and_the_fish_is_swallowed():
    for i, p in _props("fishing", "rod"):
        beak = rg.pose_point(st.frame("fishing", i)[0], rg.BEAK_TIP)
        assert p.extra[:2] == pytest.approx(beak)
    dips = [(i, p.extra[3]) for i, p in _props("fishing", "rod") if p.extra[4]]
    bite = max(dips, key=lambda d: d[1])[0]
    fish = [(i, p) for i, p in _props("fishing", "fish")]
    assert bite < fish[0][0]
    sizes = [p.extra[1] for _, p in fish]
    assert sizes[-1] < sizes[0] and sizes[-1] <= 0.3  # it disappears down the beak
    ponds = [p.b for _, p in _props("fishing", "pond")]
    assert ponds[0] < max(ponds) and ponds[-1] < max(ponds)  # the pond comes and goes
    assert _props("fishing", "fish")[0][1].b > _props("fishing", "fish")[2][1].b  # it leaps up


# --- the wizard ----------------------------------------------------------------------------------------------
def test_the_hat_drops_onto_the_head_flowers_grow_and_the_hat_flies_off():
    hats = _props("wizard", "hat")
    assert hats[0][1].b < hats[1][1].b < hats[2][1].b  # falling
    landed_at = hats[2][1]
    crown = rg.pose_point(st.frame("wizard", hats[2][0])[0], rg.CROWN)
    assert (landed_at.a, landed_at.b) == pytest.approx((crown[0], crown[1] + 0.4))
    blooms = _props("wizard", "bloom")
    assert {p.a for _, p in blooms} == {54.5, 59.5, 64.5}
    sizes = [p.b for _, p in blooms]
    assert max(sizes) == 1.0 and sizes[-1] < max(sizes)  # grown, then fading again
    assert blooms[0][0] > hats[2][0]  # the magic comes after the hat is on
    poses = [p for p, _ in _frames("wizard")]
    assert {p.wing for p in poses if p.wing} == {"up", "mid", "down"}


# --- bubbles ----------------------------------------------------------------------------------------------------
def test_two_bubbles_one_popped_by_a_jump_the_other_bursting_by_itself():
    frames = _frames("bubbles")
    most = max(sum(p.kind == "bubble" for p in props) for _, props in frames)
    assert most == 2
    pops = _props("bubbles", "pop")
    assert {p.a for _, p in pops} == {52.5, 62.5}  # two places
    jump = min(range(len(frames)), key=lambda i: frames[i][0].y)
    assert frames[jump][0].y <= -5.0 and min(i for i, p in pops if p.a == 52.5) > jump - 1
    gone_when_popped = [sum(p.kind == "bubble" for p in props) for _, props in frames]
    assert gone_when_popped[-1] == 0


# --- the egg --------------------------------------------------------------------------------------------------------
def test_the_egg_cracks_a_chick_hatches_hearts_float_and_it_hops_away():
    egg = _props("egg", "egg")
    cracks = [p.extra[1] for _, p in egg]
    assert cracks == sorted(cracks) and cracks[-1] == 1.0
    assert max(abs(p.extra[0]) for _, p in egg) >= 8.0  # it wobbles
    chick = _props("egg", "chick")
    assert chick[0][0] == egg[-1][0] + 1  # the chick is there as the egg goes
    assert len(_props("egg", "shell")) >= 6
    assert len({i for i, _ in _props("egg", "heart")}) >= 3
    assert chick[-1][1].a >= 66.0 and chick[-1][1].extra[0] == 1.0  # off to the right
    assert min(p.a for _, p in chick) < 52.0  # it came close to the raven


# --- the birthday ---------------------------------------------------------------------------------------------------------
def test_candle_hat_wish_blow_smoke_and_confetti_in_that_order():
    cake = _props("birthday", "cake")
    lit = [i for i, p in cake if p.extra[0] > 0.0]
    out = next(i for i, p in cake if p.extra[0] == 0.0 and i > lit[0])
    hat = _props("birthday", "hat")
    assert hat[0][0] > lit[0]
    poses = [p for p, _ in _frames("birthday")]
    assert poses[out - 1].tilt >= 20.0  # the candle goes out on the frame after the big blow
    smoke = [i for i, _ in _props("birthday", "smoke")]
    confetti = [i for i, _ in _props("birthday", "confetti")]
    assert min(smoke) == min(confetti) == out
    ages = [p.a for _, p in _props("birthday", "confetti")]
    assert ages == sorted(ages) and ages[-1] >= 8.0


# --- the disco ---------------------------------------------------------------------------------------------------------------
def test_the_ball_comes_down_the_raven_dances_to_the_beat_and_the_ball_goes_up():
    ball = {i: p.a for i, p in _props("disco", "discoball")}
    low = max(ball.values())
    assert ball[min(ball)] < low and ball[max(ball)] < low  # down, then up again
    lit = {i for i, _ in _props("disco", "beams")}
    assert lit == {i for i, _ in _props("disco", "floor")}  # lights and floor together
    poses = [st.frame("disco", i)[0] for i in range(st.frame_count("disco"))]
    dancing = [poses[i] for i in range(st.frame_count("disco")) if poses[i].wing]
    assert len(dancing) >= 10
    tilts = [p.tilt for p in dancing]
    assert all(a * b < 0 for a, b in zip(tilts, tilts[1:]))  # sways left, right, left ...
    assert len({p.facing_left for p in dancing}) == 2  # and turns round
