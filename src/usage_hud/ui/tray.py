"""System tray icon + menu + Windows balloon alerts."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from usage_hud.models import Alert, AlertLevel, ProviderSnapshot


def severity_color(snapshots: list[ProviderSnapshot], alerts: list[Alert]) -> QColor:
    if any(a.level == AlertLevel.CRITICAL for a in alerts):
        return QColor("#ff5c5c")
    if any(a.level == AlertLevel.WARN for a in alerts) or any(not s.ok for s in snapshots):
        return QColor("#ffb020")
    pcts = [s.primary_percent() for s in snapshots if s.ok]
    pcts = [p for p in pcts if p is not None]
    if pcts and max(pcts) >= 85:
        return QColor("#ffb020")
    return QColor("#3dd68c")


def make_dot_icon(color: QColor) -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(color)
    painter.setPen(QColor(20, 24, 32))
    painter.drawEllipse(8, 8, 48, 48)
    painter.end()
    return QIcon(pix)


class TrayController:
    def __init__(
        self,
        *,
        on_refresh: Callable[[], None],
        on_toggle_hud: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_refresh = on_refresh
        self._tray = QSystemTrayIcon(make_dot_icon(QColor("#9aa3b2")))
        menu = QMenu()
        act_refresh = QAction("Refresh now")
        act_refresh.triggered.connect(on_refresh)
        act_toggle = QAction("Show / hide HUD")
        act_toggle.triggered.connect(on_toggle_hud)
        act_quit = QAction("Quit")
        act_quit.triggered.connect(on_quit)
        menu.addAction(act_refresh)
        menu.addAction(act_toggle)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._activated)
        self._on_toggle_hud = on_toggle_hud
        self._last_codes: set[str] = set()
        self._tray.show()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_toggle_hud()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_refresh()

    def update(
        self,
        snapshots: list[ProviderSnapshot],
        alerts: list[Alert],
    ) -> None:
        color = severity_color(snapshots, alerts)
        self._tray.setIcon(make_dot_icon(color))
        lines = []
        for snap in snapshots:
            if not snap.ok:
                lines.append(f"{snap.title}: ERR")
                continue
            pct = snap.primary_percent()
            pct_txt = f"{pct:.0f}%" if pct is not None else "—"
            lines.append(f"{snap.title}: {pct_txt}")
        if alerts:
            lines.append(alerts[0].title)
        self._tray.setToolTip("Usage HUD\n" + "\n".join(lines))

        codes = {f"{a.provider_id}:{a.code}" for a in alerts if a.level != AlertLevel.INFO}
        new_codes = codes - self._last_codes
        self._last_codes = codes
        for alert in alerts:
            key = f"{alert.provider_id}:{alert.code}"
            if key not in new_codes:
                continue
            icon = (
                QSystemTrayIcon.MessageIcon.Critical
                if alert.level == AlertLevel.CRITICAL
                else QSystemTrayIcon.MessageIcon.Warning
            )
            self._tray.showMessage(alert.title, alert.body, icon, 8000)
