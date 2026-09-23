"""Settings must be reachable straight from the chip's own right-click menu,
not only buried in the system tray icon's menu — this is the wiring that
makes that true: the chip emits settings_requested, and UsageHudApp connects
it to open_settings (see app.py)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def test_chip_exposes_a_settings_requested_signal():
    from usage_hud.ui.hud import WeatherPanel

    panel = WeatherPanel(opacity=0.9)
    seen = []
    panel.settings_requested.connect(lambda: seen.append(True))
    panel.settings_requested.emit()
    assert seen == [True]
    panel.deleteLater()
