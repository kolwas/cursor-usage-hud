"""Single-monitor hover flee — needs a real QApplication (QWidget geometry)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def panel(monkeypatch):
    from usage_hud.ui.hud import WeatherPanel

    p = WeatherPanel(opacity=0.9)
    p.show()
    p.collapse()
    p.resize(200, 40)
    p.adjustSize()
    # Start docked on the left, as dock_to_taskbar normally would.
    screen = QGuiApplication.primaryScreen()
    avail = screen.availableGeometry()
    p.move(avail.left() + 16, avail.top() + 4)
    yield p
    p.deleteLater()


def _set_cursor(monkeypatch, point: QPoint) -> None:
    from usage_hud.ui import hud as hud_module

    monkeypatch.setattr(hud_module.QCursor, "pos", staticmethod(lambda: point))


def _skip_if_multi_monitor():
    if len(QGuiApplication.screens()) > 1:
        pytest.skip("single-monitor flee only applies with exactly one screen")


def test_far_cursor_leaves_the_chip_where_it_is(panel, monkeypatch):
    _skip_if_multi_monitor()
    before = panel.frameGeometry().topLeft()
    _set_cursor(monkeypatch, QPoint(3000, 3000))
    panel._check_single_screen_proximity()
    assert panel.frameGeometry().topLeft() == before
    assert panel.isVisible()


def test_hover_on_the_left_sends_it_right(panel, monkeypatch):
    """"Or nearby" — must move before the cursor is literally inside the
    chip's own rectangle, not only on direct contact."""
    _skip_if_multi_monitor()
    avail = QGuiApplication.primaryScreen().availableGeometry()
    geo = panel.frameGeometry()
    assert geo.center().x() < avail.left() + avail.width() / 2  # starts on the left

    just_outside = QPoint(geo.right() + 20, geo.top())  # near, not touching
    assert not geo.contains(just_outside)

    _set_cursor(monkeypatch, just_outside)
    panel._check_single_screen_proximity()

    new_geo = panel.frameGeometry()
    assert new_geo.center().x() > avail.left() + avail.width() / 2
    assert panel.isVisible()  # never hidden — it relocates, it doesn't duck out


def test_hovering_again_on_the_right_sends_it_back_left(panel, monkeypatch):
    _skip_if_multi_monitor()
    avail = QGuiApplication.primaryScreen().availableGeometry()

    geo = panel.frameGeometry()
    _set_cursor(monkeypatch, QPoint(geo.right() + 20, geo.top()))
    panel._check_single_screen_proximity()
    right_geo = panel.frameGeometry()
    assert right_geo.center().x() > avail.left() + avail.width() / 2

    _set_cursor(monkeypatch, QPoint(right_geo.left() - 20, right_geo.top()))
    panel._check_single_screen_proximity()
    back_geo = panel.frameGeometry()
    assert back_geo.center().x() < avail.left() + avail.width() / 2


def test_pinned_details_are_never_relocated(panel, monkeypatch):
    _skip_if_multi_monitor()
    panel._pinned_details = True
    before = panel.frameGeometry().topLeft()
    geo = panel.frameGeometry()
    _set_cursor(monkeypatch, QPoint(geo.center().x(), geo.center().y()))
    panel._check_single_screen_proximity()
    assert panel.frameGeometry().topLeft() == before


def test_periodic_redock_does_not_flicker_it_back_while_fled(panel, monkeypatch):
    """Reproduces the reported flicker: mouse stationary on the left, chip
    flees right, then the unrelated periodic re-dock timer (_auto_dock,
    every 2.5s — and update_view()'s per-refresh dock_to_taskbar) used to
    silently snap it straight back to the left-docked spot a couple of
    seconds later, which put the still-stationary cursor "near" it again and
    fled it right again — an endless loop with the mouse never moving.
    """
    _skip_if_multi_monitor()
    avail = QGuiApplication.primaryScreen().availableGeometry()
    geo = panel.frameGeometry()
    left_cursor = QPoint(geo.right() + 20, geo.top())  # near the original left dock

    _set_cursor(monkeypatch, left_cursor)
    panel._check_single_screen_proximity()
    fled_geo = panel.frameGeometry()
    assert fled_geo.center().x() > avail.left() + avail.width() / 2  # now on the right

    # The cursor never moved. Every background re-dock call must be a no-op
    # while fled — none of them know a flee is in progress.
    panel._auto_dock()
    panel.dock_to_taskbar(force=True)
    panel.update_view(panel._snapshots, panel._projections, panel._alerts)
    assert panel.frameGeometry().topLeft() == fled_geo.topLeft()

    # Only the proximity check itself may bring it home, and only by hovering there.
    _set_cursor(monkeypatch, QPoint(fled_geo.left() - 20, fled_geo.top()))
    panel._check_single_screen_proximity()
    assert panel.frameGeometry().center().x() < avail.left() + avail.width() / 2
