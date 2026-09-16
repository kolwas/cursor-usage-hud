"""Application orchestration — chip always on until timed/forever hide."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from usage_hud.alerts import evaluate_alerts
from usage_hud.config import Settings
from usage_hud.history import HistoryStore
from usage_hud.providers.registry import discover_providers, visible_snapshots
from usage_hud.providers_pref import ProviderPrefs
from usage_hud.snooze import SnoozeStore
from usage_hud.ui.hud import WeatherPanel
from usage_hud.ui.tray import TrayController


class UsageHudApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.prefs = ProviderPrefs(
            settings.state_dir / "providers.json",
            env_disabled=set(settings.disabled_providers),
        )
        self.providers = discover_providers(settings)
        self.history = HistoryStore(settings.state_dir / "history.json")
        self.snooze_store = SnoozeStore(settings.state_dir / "snooze.json")
        self._snooze = self.snooze_store.load()

        self.panel = WeatherPanel(opacity=settings.opacity, history=self.history)
        self.panel.hide_requested.connect(self.hide_to_tray)

        self.tray = TrayController(
            on_refresh=self.refresh,
            on_show_chip=self.show_from_tray,
            on_hide_chip=self.hide_to_tray,
            on_open_details=self.open_pinned_details,
            on_toggle_provider=self.toggle_provider,
            on_quit=self.quit,
            prefs=self.prefs,
            chip_visible=not self._snooze.active,
        )

        self._timer = QTimer()
        self._timer.setInterval(settings.refresh_seconds * 1000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

        # Idle-monitor dock + snooze expiry (no auto-hide otherwise).
        self._ui_timer = QTimer()
        self._ui_timer.setInterval(2000)
        self._ui_timer.timeout.connect(self._tick_ui)
        self._ui_timer.start()

        if settings.ui_mode == "chip" and not self._snooze.active:
            self.panel.show()
            self.panel.collapse()
            self.panel.dock_to_taskbar(force=True)
        else:
            self.panel.hide()

        self.refresh()

    def hide_to_tray(self, minutes: int | None = None) -> None:
        """Explicit hide: 60 / 180 / day minutes, or None = forever."""
        self._snooze = self.snooze_store.snooze(minutes)
        self.panel.collapse()
        self.panel.hide()
        self.tray.set_chip_visible(False, snooze_label=self._snooze.remaining_label())
        self.refresh()

    def show_from_tray(self) -> None:
        self.snooze_store.clear()
        self._snooze = self.snooze_store.load()
        self.panel.show()
        self.panel.collapse()
        self.panel.dock_to_taskbar(force=True)
        self.panel.raise_()
        self.tray.set_chip_visible(True)
        self.refresh()

    def open_pinned_details(self) -> None:
        """Tray icon / menu — details that stay put (no hover-flee)."""
        if self._snooze.active:
            self.snooze_store.clear()
            self._snooze = self.snooze_store.load()
            self.tray.set_chip_visible(True)
        self.panel.show_pinned_details()

    def toggle_provider(self, provider_id: str, enabled: bool) -> None:
        self.prefs.set_enabled(provider_id, enabled)
        self.refresh()

    def _tick_ui(self) -> None:
        if self._snooze.active and not self._snooze.forever:
            self._snooze = self.snooze_store.load()
            if not self._snooze.active and self.settings.ui_mode == "chip":
                self.show_from_tray()
                return
        if (
            self.settings.ui_mode == "chip"
            and not self._snooze.active
            and self.panel.isVisible()
            and not self.panel._manual_pos  # noqa: SLF001
            and not self.panel._pinned_details  # noqa: SLF001
        ):
            self.panel.dock_to_taskbar(force=False)

    def refresh(self) -> None:
        self.providers = discover_providers(self.settings)
        snapshots = [p.fetch() for p in self.providers]
        shown = visible_snapshots(snapshots)
        self.history.record(shown)
        projections = self.history.projections(
            shown, burn_multiplier=self.settings.alert_burn_multiplier
        )
        alerts = evaluate_alerts(shown, projections, self.settings)
        self.panel.update_view(shown, projections, alerts)

        hidden = self._snooze.active or self.settings.ui_mode == "quiet"
        # Keep pinned details visible even in quiet/snooze-clear edge cases.
        if self.panel._pinned_details:  # noqa: SLF001
            self.panel.show()
        elif hidden:
            self.panel.hide()
        elif self.settings.ui_mode == "chip" and not self.panel.isVisible():
            self.panel.show()
            self.panel.collapse()
            self.panel.dock_to_taskbar(force=True)

        self.tray.update(
            shown,
            alerts,
            notify=True,
            chip_visible=not hidden,
            snooze_label=self._snooze.remaining_label() if self._snooze.active else "",
            projections=projections,
        )

    def quit(self) -> None:
        self._timer.stop()
        self._ui_timer.stop()
        QApplication.instance().quit()


def run() -> int:
    settings = Settings.load()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setOrganizationName("usage-hud")
    app.setApplicationName("Usage HUD")
    app.setApplicationDisplayName("Usage HUD")
    # Helps Plasma map the Status Notifier item to the .desktop file.
    app.setDesktopFileName("usage-hud")

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print(
            "No system tray available.\n"
            "KDE Plasma: add a System Tray (Status Notifier) widget to the panel.\n"
            "Windows: check the notification area / overflow.",
            file=sys.stderr,
        )
        return 2

    _ = UsageHudApp(settings)
    return app.exec()
