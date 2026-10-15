"""Application orchestration — chip always on until timed/forever hide."""

from __future__ import annotations

import faulthandler
import sys
import traceback
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from usage_hud import lifecycle
from usage_hud.alerts import evaluate_alerts
from usage_hud.branding import APP_NAME, DESKTOP_FILE_NAME, app_icon
from usage_hud.config import Settings
from usage_hud.fetcher import BackgroundFetcher
from usage_hud.history import HistoryStore
from usage_hud.providers.registry import discover_providers, visible_snapshots
from usage_hud.providers_pref import ProviderPrefs
from usage_hud.snooze import SnoozeStore
from usage_hud.ui.hud import WeatherPanel
from usage_hud.ui.settings_dialog import SettingsDialog
from usage_hud.ui.tray import TrayController


class UsageHudApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.prefs = ProviderPrefs(
            settings.state_dir / "providers.json",
            env_disabled=set(settings.disabled_providers),
        )
        self.providers = discover_providers(settings)
        self._fetcher = BackgroundFetcher(self._apply)
        self.history = HistoryStore(settings.state_dir / "history.json")
        self.snooze_store = SnoozeStore(settings.state_dir / "snooze.json")
        self._snooze = self.snooze_store.load()

        self.panel = WeatherPanel(opacity=settings.opacity, history=self.history)
        self.panel.hide_requested.connect(self.hide_to_tray)
        self.panel.settings_requested.connect(self.open_settings)

        self.tray = TrayController(
            on_refresh=self.refresh,
            on_show_chip=self.show_from_tray,
            on_hide_chip=self.hide_to_tray,
            on_open_details=self.open_pinned_details,
            on_toggle_provider=self.toggle_provider,
            on_quit=self.quit,
            prefs=self.prefs,
            chip_visible=not self._snooze.active,
            on_open_settings=self.open_settings,
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

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, parent=self.panel)
        if not dialog.exec():
            return
        # Reload from disk: the dialog wrote state_dir/settings.json (general
        # knobs, GitHub token/login) and its own ProviderPrefs instance wrote
        # providers.json — self.prefs is a separate in-memory copy of that
        # same file and needs an explicit re-read to see the new toggles.
        self.settings = Settings.load()
        self.prefs.load()
        self._timer.setInterval(self.settings.refresh_seconds * 1000)
        self.panel.setWindowOpacity(max(0.85, self.settings.opacity))
        if self.settings.ui_mode == "chip" and not self._snooze.active:
            self.panel.show()
            self.panel.collapse()
            self.panel.dock_to_taskbar(force=True)
        elif self.settings.ui_mode != "chip":
            self.panel.hide()
        self.refresh()

    def _tick_ui(self) -> None:
        _arm_hang_dump()
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
        """Ask for fresh data; the window is updated by _apply when it arrives."""
        self._fetcher.start(self.settings)

    def _apply(self, providers: list, snapshots: list) -> None:
        self.providers = providers
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
        self.panel.allow_close()
        QApplication.instance().quit()


_HANG_DUMP_SECONDS = 20
_hang_log = None


def _arm_hang_dump() -> None:
    """Re-armed by the UI thread every couple of seconds. If the UI thread
    ever stops for longer than _HANG_DUMP_SECONDS, faulthandler's own watchdog
    thread writes every thread's stack to crash.log — showing exactly where
    the window got stuck (it works even if the main thread is blocked in a
    system call)."""
    if _hang_log is not None:
        faulthandler.dump_traceback_later(_HANG_DUMP_SECONDS, file=_hang_log)


def _install_crash_log(settings: Settings) -> None:
    """pythonw has no console, so a crash used to vanish without a trace."""
    global _hang_log
    try:
        settings.state_dir.mkdir(parents=True, exist_ok=True)
        log = open(settings.state_dir / "crash.log", "a", buffering=1, encoding="utf-8")  # noqa: SIM115
    except OSError:
        return
    faulthandler.enable(log)
    _hang_log = log

    def _hook(exc_type, exc, tb) -> None:
        log.write(f"\n--- {datetime.now().isoformat(timespec='seconds')} ---\n")
        traceback.print_exception(exc_type, exc, tb, file=log)

    sys.excepthook = _hook


def run() -> int:
    settings = Settings.load()
    _install_crash_log(settings)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setOrganizationName("usage-hud")
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(app_icon())
    # Helps Plasma map the Status Notifier item to the .desktop file.
    app.setDesktopFileName(DESKTOP_FILE_NAME)

    lifecycle.start(settings.state_dir)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        lifecycle.no_tray(settings.state_dir)
        print(
            "No system tray available.\n"
            "KDE Plasma: add a System Tray (Status Notifier) widget to the panel.\n"
            "Windows: check the notification area / overflow.",
            file=sys.stderr,
        )
        return 2

    app.aboutToQuit.connect(lambda: lifecycle.clean_exit(settings.state_dir))
    pulse_timer = QTimer()
    pulse_timer.setInterval(60_000)
    pulse_timer.timeout.connect(lambda: lifecycle.pulse(settings.state_dir))
    pulse_timer.start()

    hud = UsageHudApp(settings)

    def _session_ending(*_args) -> None:
        lifecycle.session_ending(settings.state_dir)
        hud.panel.allow_close()

    app.commitDataRequest.connect(_session_ending)
    return app.exec()
