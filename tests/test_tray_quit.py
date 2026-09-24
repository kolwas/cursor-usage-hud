"""Tray left-click must surface Quit (menu popup), not only open details."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

from usage_hud.providers_pref import ProviderPrefs  # noqa: E402
from usage_hud.ui.tray import TrayController  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def test_left_click_pops_menu_with_quit(tmp_path):
    prefs = ProviderPrefs(tmp_path / "providers.json")
    on_quit = MagicMock()
    tray = TrayController(
        on_refresh=MagicMock(),
        on_show_chip=MagicMock(),
        on_hide_chip=MagicMock(),
        on_open_details=MagicMock(),
        on_toggle_provider=MagicMock(),
        on_quit=on_quit,
        prefs=prefs,
    )
    popup = MagicMock()
    tray._menu.popup = popup  # type: ignore[method-assign]

    tray._activated(QSystemTrayIcon.ActivationReason.Trigger)

    popup.assert_called_once()
    labels = [a.text() for a in tray._menu.actions()]
    assert "Quit" in labels

    tray._tray.hide()
    tray._menu.deleteLater()
