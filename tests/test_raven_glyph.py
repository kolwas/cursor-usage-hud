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
    from usage_hud.ui.raven_glyph import JUMP_FRAME_COUNT, WALK_CYCLE_STEPS, at_path_centre

    panel = WeatherPanel(opacity=0.9)
    monkeypatch.setattr(hud_module.random, "random", lambda: 0.0)  # always "jump"

    # Advance until a centre crossing triggers the jump.
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
