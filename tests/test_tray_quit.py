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


def test_unchanged_state_does_not_touch_the_tray_again(tmp_path):
    """setIcon/setToolTip are synchronous calls into Explorer, a place the
    window has hung on before — an identical refresh must not repeat them."""
    prefs = ProviderPrefs(tmp_path / "providers.json")
    tray = TrayController(
        on_refresh=MagicMock(),
        on_show_chip=MagicMock(),
        on_hide_chip=MagicMock(),
        on_open_details=MagicMock(),
        on_toggle_provider=MagicMock(),
        on_quit=MagicMock(),
        prefs=prefs,
    )
    tray._tray.setIcon = MagicMock(wraps=tray._tray.setIcon)  # type: ignore[method-assign]
    tray._tray.setToolTip = MagicMock(wraps=tray._tray.setToolTip)  # type: ignore[method-assign]

    tray.update([], [], notify=False)
    tray.update([], [], notify=False)
    tray.update([], [], notify=False)

    assert tray._tray.setIcon.call_count == 1
    assert tray._tray.setToolTip.call_count <= 1

    tray._tray.hide()
    tray._menu.deleteLater()
