"""Application orchestration: poll providers, update HUD/tray, alert."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from usage_hud.alerts import evaluate_alerts
from usage_hud.config import Settings
from usage_hud.history import HistoryStore
from usage_hud.providers.cloud import CloudStubProvider
from usage_hud.providers.cursor import CursorProvider
from usage_hud.providers.github import GitHubProvider
from usage_hud.ui.hud import HudWindow
from usage_hud.ui.tray import TrayController


class UsageHudApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.providers = [CursorProvider(), GitHubProvider(settings)]
        if settings.enable_cloud_stub:
            self.providers.append(CloudStubProvider())
        self.history = HistoryStore(settings.state_dir / "history.json")
        self.hud = HudWindow(opacity=settings.opacity, corner=settings.hud_corner)
        self.tray = TrayController(
            on_refresh=self.refresh,
            on_toggle_hud=self.toggle_hud,
            on_quit=self.quit,
        )
        self._timer = QTimer()
        self._timer.setInterval(settings.refresh_seconds * 1000)
        self._timer.timeout.connect(self.refresh)
        self.hud.show()
        self.hud.place_corner()
        self._timer.start()
        self.refresh()

    def toggle_hud(self) -> None:
        if self.hud.isVisible():
            self.hud.hide()
        else:
            self.hud.show()
            self.hud.raise_()

    def refresh(self) -> None:
        snapshots = [p.fetch() for p in self.providers]
        self.history.record(snapshots)
        projections = self.history.projections(
            snapshots, burn_multiplier=self.settings.alert_burn_multiplier
        )
        alerts = evaluate_alerts(snapshots, projections, self.settings)
        self.hud.update_view(snapshots, projections, alerts)
        self.tray.update(snapshots, alerts)

    def quit(self) -> None:
        self._timer.stop()
        QApplication.instance().quit()


def run() -> int:
    settings = Settings.load()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Usage HUD")
    _ = UsageHudApp(settings)
    return app.exec()
