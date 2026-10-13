"""A monitor unplugged while the chip still holds it as its target screen."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from usage_hud.ui.hud import WeatherPanel  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _DeadScreen:
    """Stands in for a QScreen whose C++ object is gone."""

    def availableGeometry(self):  # noqa: N802
        raise RuntimeError("Internal C++ object (PySide6.QtGui.QScreen) already deleted.")

    geometry = availableGeometry

    def __eq__(self, other):
        raise RuntimeError("already deleted")

    __hash__ = None


def test_live_screen_rejects_a_dead_or_unknown_screen():
    assert WeatherPanel._live_screen(None) is None
    assert WeatherPanel._live_screen(_DeadScreen()) is None
    real = QGuiApplication.primaryScreen()
    assert WeatherPanel._live_screen(real) is real


def test_docking_survives_a_dead_target_screen():
    panel = WeatherPanel()
    panel._target_screen = _DeadScreen()
    panel.dock_to_taskbar(force=True)
    panel.dock_to_taskbar(force=False)
