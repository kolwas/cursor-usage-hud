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
    p.move(100, 100)
    p.resize(200, 40)
    p.adjustSize()
    yield p
    p.deleteLater()


def _set_cursor(monkeypatch, point: QPoint) -> None:
    from usage_hud.ui import hud as hud_module

    monkeypatch.setattr(hud_module.QCursor, "pos", staticmethod(lambda: point))


def _skip_if_multi_monitor():
    if len(QGuiApplication.screens()) > 1:
        pytest.skip("single-monitor flee only applies with exactly one screen")


def test_far_cursor_leaves_the_chip_visible(panel, monkeypatch):
    _skip_if_multi_monitor()
    _set_cursor(monkeypatch, QPoint(3000, 3000))
    panel._check_single_screen_proximity()
    assert panel.isVisible()
    assert panel._single_screen_fled is False


def test_cursor_in_the_margin_hides_it_before_actual_contact(panel, monkeypatch):
    """"Or nearby" — must duck out of the way before the cursor is literally
    inside the chip's own rectangle, not only on direct contact."""
    _skip_if_multi_monitor()
    geo = panel.frameGeometry()
    just_outside = QPoint(geo.left() - 20, geo.top())  # outside the rect, inside the margin
    assert not geo.contains(just_outside)

    _set_cursor(monkeypatch, just_outside)
    panel._check_single_screen_proximity()
    assert not panel.isVisible()
    assert panel._single_screen_fled is True


def test_cursor_backing_off_brings_it_back(panel, monkeypatch):
    _skip_if_multi_monitor()
    geo = panel.frameGeometry()
    _set_cursor(monkeypatch, QPoint(geo.left() - 20, geo.top()))
    panel._check_single_screen_proximity()
    assert not panel.isVisible()

    _set_cursor(monkeypatch, QPoint(3000, 3000))
    panel._check_single_screen_proximity()
    assert panel.isVisible()
    assert panel._single_screen_fled is False


def test_pinned_details_are_never_fled(panel, monkeypatch):
    _skip_if_multi_monitor()
    panel._pinned_details = True
    geo = panel.frameGeometry()
    _set_cursor(monkeypatch, QPoint(geo.center().x(), geo.center().y()))
    panel._check_single_screen_proximity()
    assert panel.isVisible()
    assert panel._single_screen_fled is False
