"""The raven's longer adventures (raven_adventures / raven_art): each is a
timeline of poses and props, every kind of prop has a painter, props follow
the bird where they are held, and the scenes leave the pace as they found it.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from usage_hud.ui import raven_adventures as adv  # noqa: E402
from usage_hud.ui import raven_art, raven_gags  # noqa: E402
from usage_hud.ui import raven_glyph as rg  # noqa: E402

LINE, EYE = QColor("#cbbf8f"), QColor("#c9a24a")
OLD_KINDS = {"cage", "weight", "foot", "broom"}


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _kinds(name):
    return {p.kind for i in range(adv.frame_count(name)) for p in adv.frame(name, i)[1]}


def test_the_eight_adventures_are_registered_as_scenes():
    assert set(adv.NAMES) == {"rain", "butterfly", "worm", "treasure", "sleep", "music", "balloons", "fireworks"}
    assert set(adv.NAMES) <= set(raven_gags.GAG_NAMES)
    for name in adv.NAMES:
        assert raven_gags.gag_frame_count(name) == adv.frame_count(name) >= 10


def test_every_prop_the_scenes_use_has_a_painter():
    used = set().union(*(_kinds(n) for n in adv.NAMES))
    assert used <= raven_art.KINDS
    assert raven_art.KINDS.isdisjoint(OLD_KINDS)
    assert raven_art.BACK_KINDS <= raven_art.KINDS


def test_each_adventure_brings_its_own_props():
    assert _kinds("rain") == {"rain", "umbrella", "rainbow"}
    assert _kinds("butterfly") == {"butterfly"}
    assert _kinds("worm") == {"mound", "worm"}
    assert _kinds("treasure") == {"chest", "coin", "sparkle"}
    assert _kinds("sleep") == {"moon", "stars", "zzz", "alert"}
    assert _kinds("music") == {"note"}
    assert _kinds("balloons") == {"balloons"}
    assert _kinds("fireworks") == {"burst"}


def test_every_frame_renders_in_both_layers_without_error():
    for name in adv.NAMES:
        for i in range(adv.frame_count(name)):
            html = rg.raven_scene_html(line_color=LINE, eye_color=EYE, mode="gag", gag=name, index=i)
            assert html.startswith('<img src="data:image/png;base64,')


def test_an_adventure_is_animated_not_a_still():
    for name in adv.NAMES:
        frames = {
            rg.raven_scene_html(line_color=LINE, eye_color=EYE, mode="gag", gag=name, index=i)
            for i in range(adv.frame_count(name))
        }
        assert len(frames) >= adv.frame_count(name) - 4, name  # a few standing frames may repeat


def test_sky_and_weather_are_painted_behind_the_raven():
    assert {"rainbow", "rain", "moon", "stars", "burst"} <= set(raven_art.BACK_KINDS)
    assert "umbrella" not in raven_art.BACK_KINDS and "chest" not in raven_art.BACK_KINDS


def test_layers_split_props_between_behind_and_in_front_of_the_raven(monkeypatch):
    painted = []
    monkeypatch.setattr(raven_art, "paint", lambda painter, prop, line: painted.append(prop.kind))
    props = [adv.frame("music", 4)[1][0], adv.frame("fireworks", 4)[1][0]]  # a note, a burst
    raven_gags.paint_props(None, props, LINE, LINE, back=True)
    assert painted == ["burst"]
    painted.clear()
    raven_gags.paint_props(None, props, LINE, LINE)
    assert painted == ["note"]


def test_pose_point_follows_the_bird():
    still = rg.RavenPose(x=10.0)
    top = rg.FLOOR_Y - rg.RAVEN_BOX
    assert rg.pose_point(still, (0.0, 0.0)) == pytest.approx((10.0, top))
    lifted = rg.RavenPose(x=10.0, y=-5.0)
    assert rg.pose_point(lifted, rg.BEAK_TIP)[1] == pytest.approx(rg.pose_point(still, rg.BEAK_TIP)[1] - 5.0)
    tipped = rg.RavenPose(x=10.0, tilt=20.0, pivot=rg.FEET_PIVOT)
    assert rg.pose_point(tipped, rg.BEAK_TIP)[1] > rg.pose_point(still, rg.BEAK_TIP)[1]  # the beak dips
    mirrored = rg.RavenPose(x=10.0, facing_left=True)
    assert rg.pose_point(mirrored, rg.BEAK_TIP)[0] < rg.pose_point(still, rg.BEAK_TIP)[0]
    pivot = rg.FEET_PIVOT
    assert rg.pose_point(tipped, (pivot[0] / 1.05, pivot[1] / 1.05)) == pytest.approx(
        rg.pose_point(still, (pivot[0] / 1.05, pivot[1] / 1.05))
    )  # the point it tips about stays put


def test_the_umbrella_is_held_at_the_beak_and_follows_it():
    for i in range(adv.frame_count("rain")):
        pose, props = adv.frame("rain", i)
        umbrella = [p for p in props if p.kind == "umbrella"]
        if not umbrella:
            continue
        grip = rg.pose_point(pose, adv._GRIP)
        assert umbrella[0].extra[1:] == pytest.approx(grip)


def test_rain_stops_before_the_rainbow_is_at_full_strength():
    rain = [next((p.b for p in adv.frame("rain", i)[1] if p.kind == "rain"), 0.0) for i in range(adv.frame_count("rain"))]
    bow = [next((p.a for p in adv.frame("rain", i)[1] if p.kind == "rainbow"), 0.0) for i in range(adv.frame_count("rain"))]
    assert max(rain) == 1.0 and rain[-1] == 0.0
    assert bow.index(max(bow)) > rain.index(max(rain)) and bow[-1] == 0.0
    assert all(r == 0.0 for r, b in zip(rain, bow) if b >= 0.85)


def test_the_worm_is_pulled_from_the_ground_to_the_beak():
    count = adv.frame_count("worm")
    pulled = []
    for i in range(count):
        pose, props = adv.frame("worm", i)
        worm = next((p for p in props if p.kind == "worm"), None)
        if worm and worm.a != adv._WORM_X:  # the tip has left the mound
            beak = rg.pose_point(pose, rg.BEAK_TIP)
            assert abs(worm.a - beak[0]) < 1.0 and abs(worm.b - beak[1]) < 2.0
            pulled.append(i)
    assert len(pulled) >= 3
    assert adv.frame("worm", count - 1)[1] == []  # swallowed, mound gone


def test_the_coin_lands_in_the_beak_after_flying_out_of_the_chest():
    xs = []
    for i in range(adv.frame_count("treasure")):
        pose, props = adv.frame("treasure", i)
        coin = next((p for p in props if p.kind == "coin"), None)
        if coin:
            xs.append((i, coin.a, coin.b))
    assert min(b for _, _, b in xs) < 12.0  # it really flies up
    beak_x, beak_y = rg.pose_point(adv.frame("treasure", xs[-1][0])[0], rg.BEAK_TIP)
    assert abs(xs[-1][1] - beak_x) < 2.0 and abs(xs[-1][2] - beak_y) < 2.0


def test_the_chest_and_its_lid_stay_inside_the_scene():
    for i in range(adv.frame_count("treasure")):
        for p in adv.frame("treasure", i)[1]:
            if p.kind == "chest":
                assert p.a + 6.5 * p.extra[0] + 5.0 <= rg.SCENE_WIDTH


def test_the_raven_sleeps_with_shut_eyes_and_wakes_with_a_start():
    poses = [adv.frame("sleep", i)[0] for i in range(adv.frame_count("sleep"))]
    asleep = [i for i, p in enumerate(poses) if p.eye_closed]
    assert len(asleep) >= 6
    wake = next(i for i, p in enumerate(poses) if i > asleep[-1] and p.y < -4.0)
    assert wake == asleep[-1] + 1 and not poses[wake].eye_closed
    assert any(p.kind == "alert" for p in adv.frame("sleep", wake)[1])


def _raven_image(eye_closed):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPainter, QPixmap

    pix = QPixmap(60, 60)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    rg._draw_raven(painter, rg.RavenPose(x=5.0, eye_closed=eye_closed), LINE, EYE)
    painter.end()
    return pix.toImage()


def test_closed_eyes_look_different_from_open_ones():
    assert _raven_image(True) != _raven_image(False)


def test_the_song_keeps_its_notes_inside_the_scene_while_they_fade():
    for i in range(adv.frame_count("music")):
        for p in adv.frame("music", i)[1]:
            assert 0.0 <= p.a <= rg.SCENE_WIDTH and p.b > 0.0 and 0.0 < p.extra[1] <= 1.0


def test_fireworks_overlap_and_all_burn_out():
    live = [sum(p.kind == "burst" for p in adv.frame("fireworks", i)[1]) for i in range(adv.frame_count("fireworks"))]
    assert max(live) >= 2 and live[0] == 0 and live[-1] == 0


def test_balloons_carry_the_raven_off_and_it_glides_back_to_the_start():
    count = adv.frame_count("balloons")
    poses = [adv.frame("balloons", i)[0] for i in range(count)]
    assert max(p.x for p in poses if p.visible) > rg.SCENE_WIDTH  # carried off the right edge
    gone = [i for i, p in enumerate(poses) if not p.visible]
    assert gone and gone == list(range(gone[0], gone[-1] + 1))  # one unbroken absence
    assert poses[-1].x == rg.PATH_X_MIN and poses[-1].y == 0.0
    assert "balloons" in adv.LANDS_AT_START and "balloons" in raven_gags.LANDS_AT_START
    assert "shoo" in raven_gags.LANDS_AT_START and "rain" not in raven_gags.LANDS_AT_START


def test_the_strings_stay_tied_to_the_back_while_it_is_carried():
    approach = len(adv._BALLOON_APPROACH)
    for i in range(approach, adv.frame_count("balloons")):
        pose, props = adv.frame("balloons", i)
        if props:
            assert (props[0].a, props[0].b) == pytest.approx(rg.pose_point(pose, adv._BACK))


def test_after_a_balloon_trip_the_panel_resumes_the_pace_from_the_start(monkeypatch):
    from usage_hud.ui.hud import WeatherPanel

    panel = WeatherPanel(opacity=0.9)
    panel._raven_step = rg.WALK_CYCLE_STEPS // 2
    panel._start_gag("balloons")
    for _ in range(adv.frame_count("balloons")):
        panel._tick_raven_mark()
    assert panel._raven_mode == "walk" and panel._raven_step == 0
    panel.deleteLater()


def test_a_standing_adventure_gives_the_pace_back_where_it_took_it(monkeypatch):
    from usage_hud.ui.hud import WeatherPanel

    panel = WeatherPanel(opacity=0.9)
    panel._raven_step = rg.WALK_CYCLE_STEPS // 2
    panel._start_gag("sleep")
    for _ in range(adv.frame_count("sleep")):
        panel._tick_raven_mark()
    assert panel._raven_mode == "walk" and panel._raven_step == rg.WALK_CYCLE_STEPS // 2
    panel.deleteLater()
