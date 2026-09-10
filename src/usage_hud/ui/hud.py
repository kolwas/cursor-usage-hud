"""Frameless translucent always-on-top HUD."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from usage_hud.models import Alert, AlertLevel, BurnProjection, ProviderSnapshot


def _pct_color(pct: float | None) -> str:
    if pct is None:
        return "#9aa3b2"
    if pct >= 95:
        return "#ff5c5c"
    if pct >= 80:
        return "#ffb020"
    if pct >= 60:
        return "#e6d35a"
    return "#3dd68c"


class HudWindow(QWidget):
    def __init__(self, opacity: float = 0.88, corner: str = "top-right") -> None:
        super().__init__()
        self._corner = corner
        self._drag_offset: QPoint | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(opacity)
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)

        self._body = QLabel()
        self._body.setTextFormat(Qt.TextFormat.RichText)
        self._body.setWordWrap(True)
        font = QFont("Segoe UI", 9)
        self._body.setFont(font)
        self._body.setStyleSheet("color: #e8ecf4; background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(self._body)

        self._dodge = QTimer(self)
        self._dodge.setInterval(250)
        self._dodge.timeout.connect(self._maybe_dodge)
        self._dodge.start()
        self._parked = False
        self._home: QPoint | None = None

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(18, 22, 30, 210))
        painter.setPen(QPen(QColor(80, 90, 110, 160), 1))
        painter.drawRoundedRect(rect, 12, 12)
        super().paintEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._parked = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._home = self.pos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def place_corner(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.adjustSize()
        margin = 16
        if self._corner == "top-left":
            pos = QPoint(geo.left() + margin, geo.top() + margin)
        elif self._corner == "bottom-left":
            pos = QPoint(geo.left() + margin, geo.bottom() - self.height() - margin)
        elif self._corner == "bottom-right":
            pos = QPoint(geo.right() - self.width() - margin, geo.bottom() - self.height() - margin)
        else:
            pos = QPoint(geo.right() - self.width() - margin, geo.top() + margin)
        self.move(pos)
        self._home = pos

    def _maybe_dodge(self) -> None:
        if not self.isVisible() or self._home is None:
            return
        cursor = QCursor.pos()
        frame = self.frameGeometry().adjusted(-28, -28, 28, 28)
        if frame.contains(cursor):
            if not self._parked:
                screen = QGuiApplication.primaryScreen()
                if screen is None:
                    return
                geo = screen.availableGeometry()
                # Slide toward opposite horizontal edge.
                if self.x() > geo.center().x():
                    self.move(geo.left() + 16, self.y())
                else:
                    self.move(geo.right() - self.width() - 16, self.y())
                self._parked = True
        elif self._parked:
            self.move(self._home)
            self._parked = False

    def update_view(
        self,
        snapshots: list[ProviderSnapshot],
        projections: list[BurnProjection],
        alerts: list[Alert],
    ) -> None:
        proj_map = {(p.provider_id, p.metric_key): p for p in projections}
        parts: list[str] = [
            '<div style="font-size:11px; letter-spacing:1px; color:#8b93a7;">USAGE HUD</div>'
        ]

        for snap in snapshots:
            parts.append(
                f'<div style="margin-top:8px; font-weight:600; color:#f2f5fa;">{_escape(snap.title)}</div>'
            )
            if not snap.ok:
                parts.append(
                    f'<div style="color:#ff8a80; font-size:11px;">{_escape(snap.error)}</div>'
                )
                continue
            for metric in snap.metrics:
                pct = metric.resolved_percent()
                color = _pct_color(pct)
                bar = _bar(pct)
                used_txt = _fmt(metric.used, metric.unit)
                lim_txt = _fmt(metric.limit, metric.unit) if metric.limit is not None else "∞"
                rem = metric.resolved_remaining()
                rem_txt = f" · left {_fmt(rem, metric.unit)}" if rem is not None else ""
                pct_txt = f"{pct:.0f}%" if pct is not None else "—"
                parts.append(
                    f'<div style="margin-top:4px; font-size:12px;">{_escape(metric.label)} '
                    f'<span style="color:{color}">{pct_txt}</span></div>'
                )
                parts.append(
                    f'<div style="font-family:Consolas,monospace; font-size:11px; color:#c5ccd8;">'
                    f"{bar} {used_txt}/{lim_txt}{rem_txt}</div>"
                )
                proj = proj_map.get((snap.provider_id, metric.key))
                if proj and proj.note:
                    parts.append(
                        f'<div style="font-size:10px; color:#9aa3b2;">'
                        f"today +{proj.used_today:.2f} · {_escape(proj.note)}</div>"
                    )

            if snap.cycle_end:
                left = snap.cycle_end - snap.fetched_at
                days = max(0.0, left.total_seconds() / 86400.0)
                parts.append(
                    f'<div style="font-size:10px; color:#7f8796; margin-top:2px;">'
                    f"cycle reset in {days:.1f}d</div>"
                )

        if alerts:
            top = alerts[0]
            color = {
                AlertLevel.INFO: "#8ec8ff",
                AlertLevel.WARN: "#ffb020",
                AlertLevel.CRITICAL: "#ff5c5c",
            }[top.level]
            parts.append(
                f'<div style="margin-top:10px; padding-top:6px; border-top:1px solid #2c3340;">'
                f'<span style="color:{color}; font-weight:600;">{_escape(top.title)}</span>'
                f'<div style="font-size:10px; color:#aab2c0;">{_escape(top.body)}</div></div>'
            )

        self._body.setText("".join(parts))
        self.adjustSize()
        if self._home is None:
            self.place_corner()


def _bar(pct: float | None, width: int = 12) -> str:
    if pct is None:
        return "[" + ("·" * width) + "]"
    filled = int(round((pct / 100.0) * width))
    filled = max(0, min(width, filled))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "$":
        return f"${value:.2f}"
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value))}{unit}"
    return f"{value:.1f}{unit}"


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
