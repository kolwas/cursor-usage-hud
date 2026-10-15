"""quit() must actually end the app while the chip is showing."""

import subprocess
import sys
import textwrap


def _run(body: str) -> subprocess.CompletedProcess:
    code = textwrap.dedent(
        """
        import os, sys
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        sys.path.insert(0, "src")
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QMenu
        from usage_hud.ui.hud import WeatherPanel
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        panel = WeatherPanel()
        panel.show()
        """
    ) + textwrap.dedent(body)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=25)


def test_quit_ends_the_event_loop_when_the_panel_allows_close():
    result = _run(
        """
        panel.allow_close()
        QTimer.singleShot(300, app.quit)
        print("exec ->", app.exec())
        """
    )
    assert result.returncode == 0, result.stderr
    assert "exec -> 0" in result.stdout


def test_a_plain_close_is_still_turned_into_a_hide_menu_not_a_quit():
    result = _run(
        """
        seen = []
        def close_the_popup():
            popup = QApplication.activePopupWidget()
            seen.append(popup is not None)
            if popup is not None:
                popup.close()
        QTimer.singleShot(400, close_the_popup)
        accepted = panel.close()
        print("closed", accepted, "menu", bool(seen and seen[0]), "visible", panel.isVisible())
        """
    )
    assert result.returncode == 0, result.stderr
    assert "closed False menu True visible True" in result.stdout
