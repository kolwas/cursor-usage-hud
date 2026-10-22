"""raven_glyph: the chip's side watermark is a little scene, not a single
static glyph — the raven paces back and forth (walk_pose) and, once in a
while when it crosses the middle, hops over a bush (jump_pose, paint_bush)
instead of walking past. This covers the pose math renders distinct,
non-crashing frames, and that WeatherPanel's own timer drives the walk/jump
state machine correctly, without needing a live Qt event loop tick.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def test_walk_steps_render_distinct_poses():
    from usage_hud.ui.raven_glyph import WALK_CYCLE_STEPS, raven_scene_html

    frames = [
        raven_scene_html(line_color=QColor("#cbbf8f"), eye_color=QColor("#c9a24a"), mode="walk", index=i)
        for i in range(2 * WALK_CYCLE_STEPS)
    ]
    assert len(set(frames)) > 1


def test_walk_cycle_wraps_around():
    from usage_hud.ui.raven_glyph import WALK_CYCLE_STEPS, raven_scene_html

    first = raven_scene_html(line_color=QColor("#cbbf8f"), mode="walk", index=0)
    wrapped = raven_scene_html(line_color=QColor("#cbbf8f"), mode="walk", index=2 * WALK_CYCLE_STEPS)
    assert first == wrapped


def test_walk_turns_around_at_each_end_of_the_path():
    from usage_hud.ui.raven_glyph import WALK_CYCLE_STEPS, walk_pose

    _, _, _, _, _, facing_left_start = walk_pose(0)
    _, _, _, _, _, facing_left_after_turn = walk_pose(WALK_CYCLE_STEPS + 1)
    assert facing_left_start is False
    assert facing_left_after_turn is True


def test_jump_frames_render_without_crashing_and_include_a_bush():
    from usage_hud.ui.raven_glyph import JUMP_FRAME_COUNT, raven_scene_html

    for f in range(JUMP_FRAME_COUNT):
        html = raven_scene_html(
            line_color=QColor("#cbbf8f"),
            eye_color=QColor("#c9a24a"),
            bush_color=QColor("#5c6b3f"),
            mode="jump",
            index=f,
        )
        assert html.startswith('<img src="data:image/png;base64,')


def test_jump_without_a_bush_color_still_renders():
    """bush_color is optional — WeatherPanel always passes one for jump
    frames, but the function itself must not require it."""
    from usage_hud.ui.raven_glyph import raven_scene_html

    html = raven_scene_html(line_color=QColor("#cbbf8f"), mode="jump", index=3)
    assert html.startswith('<img src="data:image/png;base64,')


def test_weather_panel_advances_the_walk_on_each_tick():
    from usage_hud.ui.hud import WeatherPanel

    panel = WeatherPanel(opacity=0.9)
    before = panel._raven_mark.text()
    before_step = panel._raven_step
    panel._tick_raven_mark()
    assert panel._raven_step != before_step
    assert panel._raven_mark.text() != before
    panel.deleteLater()


def test_weather_panel_jump_sequence_returns_to_walking(monkeypatch):
    """Force the dice roll so the jump path is actually exercised, then
    confirm it lands back in "walk" mode after JUMP_FRAME_COUNT ticks
    rather than getting stuck mid-hop."""
    from usage_hud.ui import hud as hud_module
    from usage_hud.ui.hud import WeatherPanel
    from usage_hud.ui.raven_glyph import JUMP_FRAME_COUNT, WALK_CYCLE_STEPS

    panel = WeatherPanel(opacity=0.9)
    monkeypatch.setattr(hud_module.random, "random", lambda: 0.0)  # always "jump"

    # Advance until the pace reaches a spot where a hop can start.
    for _ in range(2 * WALK_CYCLE_STEPS):
        panel._tick_raven_mark()
        if panel._raven_mode == "jump":
            break
    assert panel._raven_mode == "jump"

    for _ in range(JUMP_FRAME_COUNT):
        panel._tick_raven_mark()
    assert panel._raven_mode == "walk"
    panel.deleteLater()


def test_fly_frames_render_and_the_bird_is_out_of_sight_in_the_middle():
    from usage_hud.ui.raven_glyph import (
        FLY_CLIMB_FRAMES,
        FLY_FRAME_COUNT,
        FLY_GONE_FRAMES,
        fly_pose,
        raven_scene_html,
    )

    for f in range(FLY_FRAME_COUNT):
        html = raven_scene_html(line_color=QColor("#cbbf8f"), eye_color=QColor("#c9a24a"), mode="fly", index=f)
        assert html.startswith('<img src="data:image/png;base64,')

    visible = [fly_pose(f)[0] for f in range(FLY_FRAME_COUNT)]
    gone = visible[FLY_CLIMB_FRAMES : FLY_CLIMB_FRAMES + FLY_GONE_FRAMES]
    assert not any(gone)
    assert all(visible[:FLY_CLIMB_FRAMES]) and all(visible[FLY_CLIMB_FRAMES + FLY_GONE_FRAMES :])


def test_flight_flaps_and_ends_standing_at_the_start_of_the_path():
    from usage_hud.ui.raven_glyph import FLY_CLIMB_FRAMES, FLY_FRAME_COUNT, _WALK_X_MIN, fly_pose

    wings = {fly_pose(f)[4] for f in range(FLY_CLIMB_FRAMES)}
    assert len(wings) >= 2 and None not in wings
    visible, x, y, tilt, wing, legs_down = fly_pose(FLY_FRAME_COUNT - 1)
    assert (visible, x, y, tilt, wing, legs_down) == (True, _WALK_X_MIN, 0.0, 0.0, None, True)


def test_every_wing_pose_is_a_closed_non_empty_shape():
    from usage_hud.ui.raven_glyph import wing_path

    for pose in ("up", "mid", "down"):
        assert not wing_path(1.0, pose).isEmpty()


def test_weather_panel_flight_returns_to_walking_from_the_left_end(monkeypatch):
    from usage_hud.ui import hud as hud_module
    from usage_hud.ui.hud import WeatherPanel
    from usage_hud.ui.raven_glyph import FLY_FRAME_COUNT, WALK_CYCLE_STEPS

    panel = WeatherPanel(opacity=0.9)
    monkeypatch.setattr(hud_module.random, "random", lambda: 0.99)  # never hop
    monkeypatch.setattr(hud_module, "FLY_CHANCE", 1.0)  # always take off at the right end
    for _ in range(2 * WALK_CYCLE_STEPS):
        panel._tick_raven_mark()
        if panel._raven_mode == "fly":
            break
    assert panel._raven_mode == "fly"

    for _ in range(FLY_FRAME_COUNT):
        panel._tick_raven_mark()
    assert panel._raven_mode == "walk"
    assert panel._raven_step == 0
    panel.deleteLater()


def test_alert_chart_swap_does_not_interrupt_a_flight():
    from usage_hud.ui.hud import WeatherPanel

    panel = WeatherPanel(opacity=0.9)
    panel._raven_mode = "fly"
    panel._raven_fly_frame = 3
    panel._hot_gauges = lambda: [object(), object()]  # type: ignore[method-assign]
    panel._render = lambda: None  # type: ignore[method-assign]
    panel._tick_alert_cycle()
    assert panel._raven_mode == "fly"
    panel.deleteLater()


def test_jump_starts_where_the_raven_is_walking_not_somewhere_else():
    from usage_hud.ui.raven_glyph import jump_pose, walk_pose

    x, *_ = walk_pose(2)
    assert jump_pose(0, x, False).x == x
    assert jump_pose(0, x, True).x == x


def test_jump_is_mirrored_when_heading_left():
    from usage_hud.ui.raven_glyph import JUMP_FRAME_COUNT, JUMP_LENGTH, jump_pose

    right = [jump_pose(f, 30.0, False) for f in range(JUMP_FRAME_COUNT)]
    left = [jump_pose(f, 30.0, True) for f in range(JUMP_FRAME_COUNT)]
    assert right[-1].x == 30.0 + JUMP_LENGTH and left[-1].x == 30.0 - JUMP_LENGTH
    assert not right[0].facing_left and left[0].facing_left
    assert [p.y for p in right] == [p.y for p in left]


def test_jump_crouches_flies_with_open_wings_and_lands_crouching():
    from usage_hud.ui.raven_glyph import JUMP_FRAME_COUNT, jump_pose

    poses = [jump_pose(f, 5.0) for f in range(JUMP_FRAME_COUNT)]
    assert poses[0].squash < 1.0 and poses[-1].squash == 1.0  # crouch, then recovered
    assert min(p.y for p in poses) < -8.0  # clears the bush
    assert any(p.wing for p in poses)
    assert any(p.squash < 1.0 for p in poses[-3:-1])  # landing squash


def test_pace_resumes_exactly_where_the_hop_landed():
    from usage_hud.ui.hud import WeatherPanel
    from usage_hud.ui.raven_glyph import JUMP_FRAME_COUNT, jump_end_x, walk_pose

    panel = WeatherPanel(opacity=0.9)
    for start_step in (2, 18):  # one hop per direction
        panel._raven_step = start_step
        panel._start_jump()
        x0, left = panel._raven_jump_x0, panel._raven_jump_left
        for _ in range(JUMP_FRAME_COUNT):
            panel._tick_raven_mark()
        assert panel._raven_mode == "walk"
        x, *_rest, facing_left = walk_pose(panel._raven_step)
        assert facing_left == left
        assert abs(x - jump_end_x(x0, left)) < 1.6  # no jump back along the path
    panel.deleteLater()


def test_a_hop_never_runs_off_the_end_of_the_path():
    from usage_hud.ui.hud import WeatherPanel
    from usage_hud.ui.raven_glyph import JUMP_LENGTH, PATH_X_MAX, PATH_X_MIN

    panel = WeatherPanel(opacity=0.9)
    panel._raven_step = 15  # near the right end, heading right
    panel._start_jump()
    assert panel._raven_jump_left is True
    panel._raven_mode = "walk"
    panel._raven_step = 31  # near the left end, heading left
    panel._start_jump()
    assert panel._raven_jump_left is False
    assert PATH_X_MIN <= panel._raven_jump_x0 + JUMP_LENGTH <= PATH_X_MAX + 6
    panel.deleteLater()


def test_every_gag_frame_renders_and_each_starts_and_ends_standing():
    from usage_hud.ui import raven_gags as gags
    from usage_hud.ui.raven_glyph import CENTRE_X, PATH_X_MIN, raven_scene_html

    for name in gags.GAG_NAMES:
        count = gags.gag_frame_count(name)
        for f in range(count):
            html = raven_scene_html(line_color=QColor("#cbbf8f"), eye_color=QColor("#c9a24a"), mode="gag", gag=name, index=f)
            assert html.startswith('<img src="data:image/png;base64,')
        first, _ = gags.gag_frame(name, 0)
        last, last_props = gags.gag_frame(name, count - 1)
        assert first.visible and last.visible
        if name == "shoo":
            assert last.x == PATH_X_MIN  # chased off, lands back at the start
        else:
            assert (last.x, last.squash, last.tilt) == (CENTRE_X, 1.0, 0.0)
            assert last_props == []  # the props are gone again


def test_props_actually_appear_during_their_scene():
    from usage_hud.ui import raven_gags as gags

    for name, kind in (("cage", "cage"), ("weight", "weight"), ("foot", "foot"), ("shoo", "broom")):
        kinds = {p.kind for f in range(gags.gag_frame_count(name)) for p in gags.gag_frame(name, f)[1]}
        assert kinds == {kind}


def test_weight_and_foot_flatten_the_raven_then_let_it_spring_back():
    from usage_hud.ui import raven_gags as gags

    for name in ("weight", "foot"):
        squash = [gags.gag_frame(name, f)[0].squash for f in range(gags.gag_frame_count(name))]
        assert min(squash) < 0.3 and max(squash) > 1.1 and squash[-1] == 1.0


def test_peck_bobs_the_head_down_several_times():
    from usage_hud.ui import raven_gags as gags

    tilts = [gags.gag_frame("peck", f)[0].tilt for f in range(gags.gag_frame_count("peck"))]
    assert sum(1 for t in tilts if t > 15.0) >= 3


def test_pick_gag_reaches_every_scene_and_is_usually_nothing():
    from usage_hud.ui import raven_gags as gags

    assert gags.pick_gag(0.0) == "peck"
    assert gags.pick_gag(0.999) is None
    reached = {gags.pick_gag(i / 10000.0) for i in range(10000)}
    assert set(gags.GAG_NAMES) <= reached
    assert sum(gags.pick_gag(i / 10000.0) is not None for i in range(10000)) < 2000


def test_weather_panel_gag_runs_to_the_end_and_resumes_the_pace(monkeypatch):
    from usage_hud.ui import hud as hud_module
    from usage_hud.ui import raven_gags as gags
    from usage_hud.ui.hud import WeatherPanel
    from usage_hud.ui.raven_glyph import WALK_CYCLE_STEPS

    panel = WeatherPanel(opacity=0.9)
    monkeypatch.setattr(hud_module, "pick_gag", lambda _roll: "cage")
    monkeypatch.setattr(hud_module.random, "random", lambda: 0.99)  # no hop, no flight
    for _ in range(2 * WALK_CYCLE_STEPS):
        panel._tick_raven_mark()
        if panel._raven_mode == "gag":
            break
    assert panel._raven_mode == "gag" and panel._raven_gag == "cage"
    step_at_start = panel._raven_step

    for _ in range(gags.gag_frame_count("cage")):
        panel._tick_raven_mark()
    assert panel._raven_mode == "walk"
    assert panel._raven_step == step_at_start  # carries on from where it stood
    panel.deleteLater()


def test_ctrl_click_preview_plays_every_scene_in_turn():
    from usage_hud.ui.hud import WeatherPanel

    panel = WeatherPanel(opacity=0.9)
    seen = []
    for _ in range(8):
        panel._play_next_scene()
        seen.append((panel._raven_mode, panel._raven_gag if panel._raven_mode == "gag" else None))
        panel._raven_mode = "walk"  # skip ahead to the next one
    modes = {m for m, _ in seen}
    gags_seen = {g for _, g in seen if g}
    assert {"jump", "gag", "fly"} <= modes
    assert gags_seen == {"peck", "cage", "weight", "foot", "shoo"}
    panel.deleteLater()
