"""System tray — StatusNotifier (KDE) / notification area (Windows)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from usage_hud.models import Alert, AlertLevel, BurnProjection, ProviderSnapshot
from usage_hud.providers_pref import KNOWN_PROVIDERS, ProviderPrefs
from usage_hud.snooze import SNOOZE_CHOICES
from usage_hud.ui.formatters import (
    compact_title,
    format_chip_eta,
    format_renewal_offset,
    format_reset_eta,
    icon_severity,
    primary_eta_projection,
)
from usage_hud.ui.emblem_glyph import paint_emblem_solid

_TRAY_PLATE = QColor(35, 42, 53)  # same dark plate as the app/taskbar icon


def severity_color(snapshots: list[ProviderSnapshot], alerts: list[Alert]) -> QColor:
    """Kept for callers that only want the color (not the urgency flag)."""
    return icon_severity(snapshots, alerts)[0]


def make_status_icon(snapshots: list[ProviderSnapshot], alerts: list[Alert]) -> QIcon:
    """The boar (from the emblem — see ui/emblem_glyph.py), tinted by
    status: color says fine/watch/critical (same convention as before — no
    raw percent number, a blanket "highest % anywhere" badge used to show
    e.g. Cursor's API-models 70% with no real alert behind it), a small "!"
    badge only when something has actually crossed an alert threshold.

    Solid silhouette, not a stroked outline: the tray is always rendered at
    16-24px regardless of the source pixmap's size, and at that scale even
    ONE detailed stroked contour smears into a smudge, let alone the boar
    AND a perched raven both — see emblem_glyph.SOLID_MAX_SIZE. The raven
    stays perched on the boar's back only on the static branding icon
    (tools/make_icon.py), where there is room for both at full detail; the
    live status dot is the boar alone, colored live.
    """
    color, urgent = icon_severity(snapshots, alerts)
    size = 64
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = size / 32.0
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_TRAY_PLATE)
    painter.drawRoundedRect(0, 0, size, size, 7 * s, 7 * s)

    paint_emblem_solid(painter, s, fill_color=color)

    if urgent:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ff3b3b"))
        badge_c = QPointF(size - 12.0, size - 12.0)
        painter.drawEllipse(badge_c, 11.0, 11.0)
        painter.setPen(QColor("#141821"))
        font = QFont()
        font.setStyleHint(QFont.StyleHint.SansSerif)
        font.setBold(True)
        font.setPointSize(13)
        painter.setFont(font)
        painter.drawText(
            QRectF(badge_c.x() - 11.0, badge_c.y() - 11.0, 22.0, 22.0),
            int(Qt.AlignmentFlag.AlignCenter),
            "!",
        )
    painter.end()
    return QIcon(pix)


def _provider_tag(provider_id: str) -> str:
    return {
        "cursor": "Cursor",
        "copilot": "Copilot",
        "opencode-go": "OpenCode Go",
        "openai": "OpenAI",
        "anthropic": "Claude",
        "github": "GitHub",
        "cloud": "Cloud",
    }.get(provider_id, provider_id)


class TrayController:
    def __init__(
        self,
        *,
        on_refresh: Callable[[], None],
        on_show_chip: Callable[[], None],
        on_hide_chip: Callable[[int | None], None],
        on_open_details: Callable[[], None],
        on_toggle_provider: Callable[[str, bool], None],
        on_quit: Callable[[], None],
        prefs: ProviderPrefs,
        chip_visible: bool = True,
        on_open_settings: Callable[[], None] | None = None,
    ) -> None:
        self._on_refresh = on_refresh
        self._on_show_chip = on_show_chip
        self._on_hide_chip = on_hide_chip
        self._on_open_details = on_open_details
        self._on_toggle_provider = on_toggle_provider
        self._on_quit = on_quit
        self._on_open_settings = on_open_settings
        self._prefs = prefs
        self._chip_visible = chip_visible
        self._snooze_label = ""
        self._projections: list[BurnProjection] = []
        self._tray = QSystemTrayIcon(make_status_icon([], []))
        self._menu = QMenu()
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._activated)
        self._last_codes: set[str] = set()
        self._tray.setToolTip("Usage HUD")
        self._rebuild_menu([])
        self._tray.show()

    def set_chip_visible(self, visible: bool, snooze_label: str = "") -> None:
        self._chip_visible = visible
        self._snooze_label = snooze_label

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Left / double / middle click → pinned details (does not flee).
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.MiddleClick,
        }:
            self._on_open_details()

    def _rebuild_menu(self, snapshots: list[ProviderSnapshot]) -> None:
        self._menu.clear()
        header = QAction("Subscriptions")
        header.setEnabled(False)
        self._menu.addAction(header)
        self._menu.addSeparator()

        proj_map = {(p.provider_id, p.metric_key): p for p in self._projections}
        if not snapshots:
            empty = QAction("(waiting for data…)")
            empty.setEnabled(False)
            self._menu.addAction(empty)
        else:
            for snap in snapshots:
                name = _provider_tag(snap.provider_id)
                if not snap.ok:
                    act = QAction(f"{name}: ERR — {snap.error[:40]}")
                    act.setEnabled(False)
                    self._menu.addAction(act)
                    continue
                pct = snap.primary_percent()
                pct_txt = f"{pct:.0f}%" if pct is not None else "—"
                head = QAction(f"{name}: {pct_txt}")
                head.setEnabled(False)
                self._menu.addAction(head)
                for metric in snap.metrics[:4]:
                    mp = metric.resolved_percent()
                    if mp is None:
                        continue
                    line = f"    {metric.label} {mp:.0f}%"
                    proj = proj_map.get((snap.provider_id, metric.key))
                    if proj and proj.renewal_offset_days is not None:
                        eta = format_renewal_offset(proj.renewal_offset_days)
                        if eta:
                            line += f"  {eta}"
                    row = QAction(line)
                    row.setEnabled(False)
                    self._menu.addAction(row)

        self._menu.addSeparator()
        act_details = QAction("Open details…")
        act_details.triggered.connect(self._on_open_details)
        self._menu.addAction(act_details)

        if self._chip_visible:
            hide_menu = self._menu.addMenu("Hide chip")
            for label, minutes in SNOOZE_CHOICES:
                act = QAction(label, hide_menu)

                def _make(m: int | None):
                    return lambda checked=False: self._on_hide_chip(m)

                act.triggered.connect(_make(minutes))
                hide_menu.addAction(act)
        else:
            show = QAction("Show chip")
            show.triggered.connect(self._on_show_chip)
            self._menu.addAction(show)
            if self._snooze_label:
                info = QAction(f"Hidden: {self._snooze_label}")
                info.setEnabled(False)
                self._menu.addAction(info)

        prov_menu = self._menu.addMenu("Providers")
        for pid, label in KNOWN_PROVIDERS:
            act = QAction(label, prov_menu)
            act.setCheckable(True)
            act.blockSignals(True)
            act.setChecked(self._prefs.is_enabled(pid))
            act.blockSignals(False)

            def _toggle(checked: bool, provider_id: str = pid) -> None:
                self._on_toggle_provider(provider_id, checked)

            act.toggled.connect(_toggle)
            prov_menu.addAction(act)

        act_refresh = QAction("Refresh")
        act_refresh.triggered.connect(self._on_refresh)
        self._menu.addAction(act_refresh)
        if self._on_open_settings is not None:
            act_settings = QAction("Settings…")
            act_settings.triggered.connect(self._on_open_settings)
            self._menu.addAction(act_settings)
        act_quit = QAction("Quit")
        act_quit.triggered.connect(self._on_quit)
        self._menu.addSeparator()
        self._menu.addAction(act_quit)

    def update(
        self,
        snapshots: list[ProviderSnapshot],
        alerts: list[Alert],
        *,
        notify: bool = True,
        chip_visible: bool | None = None,
        snooze_label: str = "",
        projections: list[BurnProjection] | None = None,
    ) -> None:
        if chip_visible is not None:
            self._chip_visible = chip_visible
        if snooze_label:
            self._snooze_label = snooze_label
        elif self._chip_visible:
            self._snooze_label = ""
        self._projections = projections or []
        self._tray.setIcon(make_status_icon(snapshots, alerts))
        self._rebuild_menu(snapshots)

        lines = [compact_title(snapshots, alerts)]
        if not self._chip_visible:
            lines.append(
                f"(chip hidden — {self._snooze_label or 'snoozed'}; click icon for details)"
            )
        lines.append("")
        etas = primary_eta_projection(snapshots, self._projections)
        for snap in snapshots:
            name = _provider_tag(snap.provider_id)
            if not snap.ok:
                lines.append(f"{name}: {snap.error}")
                continue
            pct = snap.primary_percent()
            pct_txt = f"{pct:.0f}%" if pct is not None else "—"
            extra = []
            for metric in snap.metrics[1:3]:
                mp = metric.resolved_percent()
                if mp is not None:
                    extra.append(f"{metric.label} {mp:.0f}%")
            suffix = f" ({', '.join(extra)})" if extra else ""
            chip_eta = format_chip_eta(etas.get(snap.provider_id))
            eta_txt = f" · {chip_eta[0]}" if chip_eta else ""
            reset_eta = format_reset_eta(snap.cycle_end, snap.fetched_at)
            reset = f" · reset {reset_eta}" if reset_eta else ""
            lines.append(f"{name}: {pct_txt}{suffix}{eta_txt}{reset}")
        lines.append("")
        lines.append("Click icon → pinned details")
        lines.append("Right-click → Providers / Hide chip")
        self._tray.setToolTip("\n".join(lines))

        if not notify:
            return
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
            self._tray.showMessage(alert.title, alert.body, icon, 7000)
