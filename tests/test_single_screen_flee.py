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
