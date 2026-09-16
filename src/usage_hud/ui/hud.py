"""Weather-style chip — stays on the idle monitor; flees on hover."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPen,
    QScreen,
)
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QVBoxLayout, QWidget

from usage_hud.models import Alert, AlertLevel, BurnProjection, ProviderSnapshot
from usage_hud.ui.display import idle_screen, next_screen_after, screen_under_cursor
from usage_hud.ui.formatters import (
    badge_icon,
    chip_metric_tag,
    chip_metrics,
    compact_title,
    format_chip_eta,
    format_renewal_offset,
    format_reset_eta,
    grouped_reset_etas,
    primary_eta_projection,
)

_CLOCK = "\U0001f550"  # 🕐 — a plain "time left" glyph, not a status color


def _ui_font(point_size: int = 9, bold: bool = False) -> QFont:
    """Prefer system UI font (Noto/Sans on KDE, Segoe on Windows)."""
    font = QFont()
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setPointSize(point_size)
    font.setBold(bold)
    return font


def _pct_color(pct: float | None) -> str:
    if pct is None:
        return "#c8d0dc"
    if pct >= 95:
        return "#ff6b6b"
    if pct >= 80:
        return "#ffb020"
    if pct >= 60:
        return "#e6d35a"
    return "#5ddea0"


class WeatherPanel(QWidget):
    """Compact chip on an idle monitor; click expands details."""

    toggled = Signal(bool)
    # minutes; None = forever
    hide_requested = Signal(object)

    def __init__(self, opacity: float = 0.96) -> None:
        super().__init__()
        self._expanded = False
        self._drag_offset: QPoint | None = None
        self._manual_pos = False
        self._flee_enabled = True
        self._pinned_details = False
        self._target_screen: QScreen | None = None
        self._snapshots: list[ProviderSnapshot] = []
        self._projections: list[BurnProjection] = []
        self._alerts: list[Alert] = []

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(max(0.85, opacity))
        self.setWindowTitle("Usage HUD")
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._chip = QLabel()
        self._chip.setTextFormat(Qt.TextFormat.RichText)
        self._chip.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._chip.setFont(_ui_font(10, bold=True))
        self._chip.setStyleSheet("color: #f3f6fb; background: transparent;")
        self._chip.setFixedHeight(32)
        self._chip.setMouseTracking(True)

        self._flyout = QLabel()
        self._flyout.setTextFormat(Qt.TextFormat.RichText)
        self._flyout.setWordWrap(True)
        self._flyout.setFont(_ui_font(9))
        self._flyout.setStyleSheet("color: #e8ecf4; background: transparent;")
        self._flyout.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)
        layout.addWidget(self._chip)
        layout.addWidget(self._flyout)

        self.setMinimumWidth(200)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self._reposition_timer = QTimer(self)
        self._reposition_timer.setInterval(2500)
        self._reposition_timer.timeout.connect(self._auto_dock)
        self._reposition_timer.start()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        # Pinned tray details stay open until explicit collapse — no click-away.
        if self._pinned_details:
            return super().eventFilter(obj, event)
        if (
            self._expanded
            and event.type() == QEvent.Type.MouseButtonPress
            and isinstance(event, QMouseEvent)
        ):
            if not self.frameGeometry().contains(event.globalPosition().toPoint()):
                self.collapse()
        return super().eventFilter(obj, event)

    def enterEvent(self, event) -> None:  # noqa: N802
        # Hover → jump to another screen so it doesn't sit under the cursor.
        if (
            self._flee_enabled
            and not self._pinned_details
            and not self._manual_pos
            and not self._expanded
            and self._drag_offset is None
            and len(QGuiApplication.screens()) > 1
        ):
            current = QGuiApplication.screenAt(self.frameGeometry().center())
            self._target_screen = next_screen_after(current)
            self.dock_to_taskbar(force=True)
        super().enterEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        if self._expanded:
            painter.setBrush(QColor(28, 30, 36, 245))
            painter.setPen(QPen(QColor(120, 170, 255, 90), 1))
            radius = 12
        else:
            painter.setBrush(QColor(24, 28, 36, 250))
            painter.setPen(QPen(QColor(100, 160, 255, 140), 1))
            radius = 10
        painter.drawRoundedRect(rect, radius, radius)
        super().paintEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                self._manual_pos = True
            else:
                # Left click only expands/collapses details — never hides to tray.
                self.toggle()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._manual_pos = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & (
            Qt.MouseButton.LeftButton | Qt.MouseButton.MiddleButton
        ):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        # Closing does not quit — offer timed hide at the window.
        event.ignore()
        menu = QMenu(self)
        menu.addMenu(self._hide_submenu())
        menu.exec(self.mapToGlobal(self.rect().center()))

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        act_details = QAction("Details…" if not self._expanded else "Collapse")
        act_details.triggered.connect(self.toggle)
        menu.addAction(act_details)
        menu.addMenu(self._hide_submenu())
        menu.exec(self.mapToGlobal(pos))

    def _hide_submenu(self) -> QMenu:
        from usage_hud.snooze import SNOOZE_CHOICES

        sub = QMenu("Hide to tray", self)
        for label, minutes in SNOOZE_CHOICES:
            act = QAction(label, sub)

            def _make(m: int | None):
                return lambda checked=False: self.hide_requested.emit(m)

            act.triggered.connect(_make(minutes))
            sub.addAction(act)
        return sub

    def toggle(self) -> None:
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self) -> None:
        self._expanded = True
        self._flyout.show()
        self._render()
        if not self._pinned_details:
            self.dock_to_taskbar(force=True)
        self.raise_()
        self.toggled.emit(True)

    def collapse(self) -> None:
        was_pinned = self._pinned_details
        self._expanded = False
        self._pinned_details = False
        self._flee_enabled = True
        if was_pinned:
            self._manual_pos = False
        self._flyout.hide()
        self._render()
        self.dock_to_taskbar(force=True)
        self.toggled.emit(False)

    def show_pinned_details(self) -> None:
        """Open expanded details from tray — no flee, stays put until collapse."""
        self._pinned_details = True
        self._flee_enabled = False
        self._manual_pos = True
        self.show()
        self.expand()
        self._place_on_active_screen()
        self.raise_()
        self.activateWindow()

    def _place_on_active_screen(self) -> None:
        screen = screen_under_cursor() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        self.adjustSize()
        x = avail.left() + (avail.width() - self.width()) // 2
        y = avail.top() + max(24, (avail.height() - self.height()) // 5)
        self.move(x, y)

    def _auto_dock(self) -> None:
        if self._manual_pos or self._pinned_details or self._drag_offset is not None:
            return
        # Keep on idle monitor as the user moves between screens.
        active = screen_under_cursor()
        desired = idle_screen(prefer_away_from=active)
        self._target_screen = desired
        self.dock_to_taskbar(force=False)

    def dock_to_taskbar(self, force: bool = True) -> None:
        """Park above the panel/taskbar on the idle (or target) monitor."""
        if self._manual_pos and not force:
            return
        if self._drag_offset is not None:
            return
        screen = self._target_screen or idle_screen()
        if screen is None:
            return
        # If somehow on the active screen and we have another, flip.
        active = screen_under_cursor()
        if (
            not self._expanded
            and active is not None
            and screen is active
            and len(QGuiApplication.screens()) > 1
        ):
            screen = idle_screen(prefer_away_from=active) or screen
            self._target_screen = screen

        avail = screen.availableGeometry()
        full = screen.geometry()
        self.adjustSize()
        x = avail.left() + 16
        if avail.bottom() < full.bottom() - 2:
            y = avail.bottom() - self.height() - 4
        elif avail.top() > full.top() + 2:
            y = avail.top() + 4
        else:
            y = avail.bottom() - self.height() - 4
        if y < avail.top():
            y = avail.top() + 4
        if x + self.width() > avail.right():
            x = max(avail.left() + 8, avail.right() - self.width() - 8)
        self.move(x, y)
        if self.isVisible():
            self.raise_()

    def update_view(
        self,
        snapshots: list[ProviderSnapshot],
        projections: list[BurnProjection],
        alerts: list[Alert],
    ) -> None:
        self._snapshots = snapshots
        self._projections = projections
        self._alerts = alerts
        self.setWindowTitle(compact_title(snapshots, alerts))
        self.setWindowIcon(badge_icon(snapshots, alerts))
        self._render()
        if self.isVisible() and not self._manual_pos:
            self.dock_to_taskbar(force=True)

    def _render(self) -> None:
        self._chip.setText(self._chip_html())
        if self._expanded:
            self._flyout.setText(self._flyout_html())
        self.adjustSize()
        if not self._expanded:
            self.setFixedHeight(44)
            hint_w = self._chip.sizeHint().width() + 36
            self.setFixedWidth(max(220, min(720, hint_w)))
        else:
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.setMinimumWidth(280)
            self.setMaximumWidth(360)
            self.setFixedSize(
                self.sizeHint().boundedTo(self.maximumSize()).expandedTo(self.minimumSize())
            )

    @staticmethod
    def _eta_html(chip_eta: tuple[str, str] | None) -> str:
        if chip_eta is None:
            return ""
        label, sev = chip_eta
        color = {"bad": "#ff8a80", "warn": "#ffb020", "ok": "#8ec8ff"}.get(sev, "#8ec8ff")
        return f' <span style="color:{color}; font-weight:600;">{label}</span>'

    def _chip_html(self) -> str:
        # One shared badge for providers with a single chip gauge (unchanged
        # behaviour); a badge per gauge for providers showing several, so e.g.
        # Cursor's API prediction doesn't hide behind Included's.
        etas = primary_eta_projection(self._snapshots, self._projections)
        proj_map = {(p.provider_id, p.metric_key): p for p in self._projections}
        parts: list[str] = []
        for snap in self._snapshots:
            tag = {
                "cursor": "Cur",
                "copilot": "Cop",
                "opencode-go": "Go",
                "openai": "OAI",
                "anthropic": "Cla",
                "github": "GH",
                "cloud": "Cld",
            }.get(snap.provider_id, snap.provider_id[:3].title())
            if not snap.ok:
                parts.append(f'<span style="color:#ff8a80;">{tag} !</span>')
                continue
            metrics = chip_metrics(snap)
            if not metrics:
                eta_html = self._eta_html(format_chip_eta(etas.get(snap.provider_id)))
                parts.append(f'<span style="color:#e8ecf4;">{tag}</span>{eta_html}')
                continue

            def _clock(text: str) -> str:
                return f'<span style="color:#6f7686;">{_CLOCK}{text}</span> ' if text else ""

            # Order is always tag → clock → percent. Gauges sharing one
            # billing cycle (Cursor's Included/API/Auto) get ONE countdown at
            # the provider tag instead of repeating it per gauge; gauges with
            # genuinely different resets (Claude's 5h vs 7d) get their own.
            multi = len(metrics) > 1
            shared_reset, per_metric_reset = grouped_reset_etas(snap, metrics) if multi else ("", {})

            segs: list[str] = []
            for metric in metrics:
                pct = metric.resolved_percent()
                color = _pct_color(pct)
                # Multiple gauges: label each one instead of repeating the
                # provider tag, and give each its own ETA badge — the one
                # that matters (e.g. API) must not hide behind another's.
                seg_tag = chip_metric_tag(metric) if multi else tag
                if multi:
                    own_reset = "" if shared_reset else per_metric_reset.get(metric.key, "")
                else:
                    own_reset = format_reset_eta(metric.cycle_end or snap.cycle_end, snap.fetched_at)
                pct_html = (
                    f'<span style="color:{color}; font-weight:700;">{pct:.0f}%</span>'
                    if pct is not None
                    else ""
                )
                seg_eta = (
                    self._eta_html(format_chip_eta(proj_map.get((snap.provider_id, metric.key))))
                    if multi
                    else ""
                )
                segs.append(
                    f'<span style="color:#8a93a6;">{seg_tag}</span> '
                    f"{_clock(own_reset)}{pct_html}{seg_eta}".rstrip()
                )
            body = f'<span style="color:#3a4152;">/</span>'.join(segs)
            prefix_bits = []
            if multi:
                prefix_bits.append(f'<span style="color:#d7dde8;">{tag}</span>')
            if multi and shared_reset:
                prefix_bits.append(_clock(shared_reset).rstrip())
            prefix = " ".join(prefix_bits) + (" " if prefix_bits else "")
            eta_html = "" if multi else self._eta_html(format_chip_eta(etas.get(snap.provider_id)))
            parts.append(prefix + body + eta_html)
        if not parts:
            return '<span style="color:#e8ecf4;">Usage …</span>'
        sep = '<span style="color:#7a8494;"> · </span>'
        return sep.join(parts)

    def _flyout_html(self) -> str:
        proj_map = {(p.provider_id, p.metric_key): p for p in self._projections}
        parts: list[str] = [
            '<div style="font-size:10px; color:#8b93a7; letter-spacing:0.6px;">USAGE</div>'
        ]
        for snap in self._snapshots:
            short = snap.title.split("·")[0].strip() if snap.ok else snap.title
            parts.append(
                f'<div style="margin-top:8px; font-size:12px; font-weight:600; color:#f2f5fa;">'
                f"{_escape(short)}</div>"
            )
            if not snap.ok:
                parts.append(
                    f'<div style="color:#ff8a80; font-size:11px;">{_escape(snap.error)}</div>'
                )
                continue
            # One clock for the whole provider when every gauge shares a
            # billing cycle (Cursor); one per gauge when they genuinely
            # differ (Claude's 5h vs 7d) — always clock, then the % below it.
            shared_reset, per_metric_reset = grouped_reset_etas(snap, snap.metrics)
            if shared_reset:
                parts.append(
                    f'<div style="margin-top:6px; font-size:10px; color:#6f7686; '
                    f'letter-spacing:0.3px;">{_CLOCK} {shared_reset}</div>'
                )
            for metric in snap.metrics:
                pct = metric.resolved_percent()
                color = _pct_color(pct)
                rem = metric.resolved_remaining()
                pct_txt = f"{pct:.0f}%" if pct is not None else "—"
                if metric.unit == "$" and rem is not None:
                    detail = f"{_fmt(metric.used, '$')} · left {_fmt(rem, '$')}"
                elif rem is not None:
                    detail = f"left {_fmt(rem, metric.unit)}"
                else:
                    detail = _fmt(metric.used, metric.unit)
                bar = _bar(pct)
                reset_eta = "" if shared_reset else per_metric_reset.get(metric.key, "")
                if reset_eta:
                    parts.append(
                        f'<div style="margin-top:7px; font-size:10px; color:#6f7686; '
                        f'letter-spacing:0.3px;">{_CLOCK} {reset_eta}</div>'
                    )
                parts.append(
                    f'<div style="margin-top:{1 if reset_eta else 3}px; font-size:11px; '
                    f'color:#aeb6c4;">{_escape(metric.label)} '
                    f'<span style="color:{color};">{pct_txt}</span></div>'
                )
                parts.append(
                    f'<div style="font-family:Consolas,monospace; font-size:11px; color:#9aa3b2;">'
                    f"{bar} {detail}</div>"
                )
                proj = proj_map.get((snap.provider_id, metric.key))
                if proj and "collecting" not in (proj.note or ""):
                    bits: list[str] = []
                    if proj.used_today:
                        bits.append(f"+{proj.used_today:.1f} today")
                    if proj.avg_daily > 0:
                        unit = "%/day" if metric.unit == "%" else "/day"
                        bits.append(f"~{proj.avg_daily:.2f}{unit}")
                    if proj.renewal_offset_days is not None:
                        eta = format_renewal_offset(proj.renewal_offset_days)
                        off = proj.renewal_offset_days
                        if off < 0:
                            bits.append(f"{eta} before renewal")
                        elif off > 0:
                            bits.append(f"{eta} after renewal")
                        else:
                            bits.append("0d (at renewal)")
                    if proj.projected_cycle_end is not None:
                        bits.append(f"→{proj.projected_cycle_end:.0f}% at reset")
                    if bits:
                        parts.append(
                            f'<div style="font-size:10px; color:#7a8290;">'
                            f"{_escape(' · '.join(bits))}</div>"
                        )
        if self._alerts:
            top = self._alerts[0]
            color = {
                AlertLevel.INFO: "#8ec8ff",
                AlertLevel.WARN: "#ffb020",
                AlertLevel.CRITICAL: "#ff6b6b",
            }[top.level]
            parts.append(
                f'<div style="margin-top:10px; padding-top:6px; border-top:1px solid #3a3a3a;">'
                f'<span style="color:{color}; font-size:11px;">{_escape(top.title)}</span>'
                f'<div style="font-size:10px; color:#9aa3b2;">{_escape(top.body)}</div></div>'
            )
        parts.append(
            '<div style="margin-top:8px; font-size:9px; color:#5c6370;">'
            "right-click → Hide (60m / 180m / day / forever)</div>"
        )
        return "".join(parts)


def _bar(pct: float | None, width: int = 10) -> str:
    if pct is None:
        return "[" + ("·" * width) + "]"
    filled = max(0, min(width, int(round((pct / 100.0) * width))))
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


HudWindow = WeatherPanel
