"""Weather-style chip — stays on the idle monitor; flees on hover."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPen,
    QScreen,
)
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QVBoxLayout, QWidget

from usage_hud.branding import APP_NAME
from usage_hud.history import HistoryStore
from usage_hud.models import Alert, AlertLevel, BurnProjection, Metric, ProviderSnapshot
from usage_hud.ui import mini_charts
from usage_hud.ui.display import idle_screen, next_screen_after, screen_under_cursor
from usage_hud.ui.formatters import (
    badge_icon,
    chip_eta_parts,
    chip_metric_tag,
    chip_metrics,
    compact_title,
    eta_severity,
    format_chip_eta,
    format_renewal_offset,
    grouped_reset_etas,
    primary_eta_projection,
    reset_eta_parts,
    reset_fraction_remaining,
)

_ETA_COLOR = {"bad": "#ff8a80", "warn": "#ffb020", "ok": "#8ec8ff", "tentative": "#9aa3b2"}

# Single-monitor flee: with nowhere else to jump to, the chip hides itself
# instead — this is how far (px) the cursor can get before it's "nearby"
# and the chip ducks out of the way, not just when directly touching it.
_HOVER_MARGIN = 44
_PROXIMITY_POLL_MS = 250


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
    settings_requested = Signal()

    def __init__(self, opacity: float = 0.96, history: HistoryStore | None = None) -> None:
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
        # For the flyout's real sparkline (HistoryStore.series()) — distinct
        # from self._projections, which only carries the derived burn-rate
        # numbers, not the raw observed samples.
        self._history = history
        # True while parked on the single-monitor "away" (right) side — see
        # _check_single_screen_proximity and dock_to_taskbar's own guard.
        self._single_screen_away = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(max(0.85, opacity))
        self.setWindowTitle(APP_NAME)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._chip = QLabel()
        self._chip.setTextFormat(Qt.TextFormat.RichText)
        self._chip.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._chip.setFont(_ui_font(10, bold=True))
        self._chip.setStyleSheet("color: #f3f6fb; background: transparent;")
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

        # Single-monitor flee: enterEvent can't jump the chip to "another
        # screen" when there is only one, so a fast poll ducks it out of the
        # way on approach instead — enterEvent alone would also only fire
        # once the cursor is already touching the chip, not "nearby".
        self._proximity_timer = QTimer(self)
        self._proximity_timer.setInterval(_PROXIMITY_POLL_MS)
        self._proximity_timer.timeout.connect(self._check_single_screen_proximity)
        self._proximity_timer.start()

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

    def _flee_eligible(self) -> bool:
        return (
            self._flee_enabled
            and not self._pinned_details
            and not self._manual_pos
            and not self._expanded
            and self._drag_offset is None
        )

    def enterEvent(self, event) -> None:  # noqa: N802
        # Hover → jump to another screen so it doesn't sit under the cursor.
        if self._flee_eligible() and len(QGuiApplication.screens()) > 1:
            current = QGuiApplication.screenAt(self.frameGeometry().center())
            self._target_screen = next_screen_after(current)
            self.dock_to_taskbar(force=True)
        super().enterEvent(event)

    def _check_single_screen_proximity(self) -> None:
        """Single monitor only: enterEvent can't send the chip to "another
        screen" that doesn't exist, so instead it hops to the opposite side
        of THIS screen on approach — sitting on the left, hovering sends it
        right, and hovering again (it's now on the right) sends it back
        left. Triggers within _HOVER_MARGIN, not just on direct contact.

        While parked on the "away" side, dock_to_taskbar() is blocked (see
        its own guard) — without that, the unrelated periodic re-dock timer
        (_auto_dock, every 2.5s) kept silently snapping the chip back to its
        normal left-docked spot a couple of seconds after every flee, which
        looked like random flicker with the cursor just sitting there.
        """
        if len(QGuiApplication.screens()) > 1:
            self._single_screen_away = False
            return
        if not self._flee_eligible():
            return

        near = (
            self.frameGeometry()
            .adjusted(-_HOVER_MARGIN, -_HOVER_MARGIN, _HOVER_MARGIN, _HOVER_MARGIN)
            .contains(QCursor.pos())
        )
        if not near:
            return

        screen = self._target_screen or screen_under_cursor() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        geo = self.frameGeometry()
        on_right_half = geo.center().x() > avail.left() + avail.width() / 2
        x = avail.left() + 16 if on_right_half else avail.right() - self.width() - 16
        x = max(avail.left() + 8, min(x, avail.right() - self.width() - 8))
        self._single_screen_away = not on_right_half  # landing on the right now
        self.move(x, geo.top())
        if self.isVisible():
            self.raise_()

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
        menu.addSeparator()
        # Right on the chip, not just buried in the tray icon's own menu —
        # "easily accessible" meant reachable from where the user already is.
        act_settings = QAction("Settings…")
        act_settings.triggered.connect(self.settings_requested.emit)
        menu.addAction(act_settings)
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
        if self._single_screen_away:
            # Parked on the single-monitor "away" side to duck the cursor —
            # every caller here always docks back to the normal (left) spot,
            # force=True included, none of them know about the flee. Only
            # _check_single_screen_proximity's own hover-triggered move is
            # allowed to bring it back.
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
            # Chip is now one line per gauge, so its height grows with the
            # number of gauges shown instead of staying fixed at one line.
            chip_hint = self._chip.sizeHint()
            self.setFixedHeight(max(40, min(220, chip_hint.height() + 16)))
            # The table grew a lot wider once the reset countdown and the
            # ETA badge each split into separate days/hours/minutes columns
            # (10 columns total) — the old 420px cap was clipping them right
            # off the edge, invisibly. Let it size to its real content
            # (still with a sane ceiling so one long provider title can't
            # blow the chip up arbitrarily).
            self.setFixedWidth(max(220, min(720, chip_hint.width() + 36)))
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
        color = _ETA_COLOR.get(sev, "#8ec8ff")
        return f' <span style="color:{color}; font-weight:600;">{label}</span>'

    @staticmethod
    def _eta_parts_html(proj: BurnProjection | None) -> tuple[str, str, str]:
        """(days, hours, minutes) cells for the exhaustion/renewal badge —
        same split-column treatment as _reset_parts_html, so "podobny format
        z czasem do końca" (matching format for the time-to-exhaustion too):
        digits line up in their own columns instead of one "+13d"/"→9d"
        string. A tentative estimate gets a leading "~" (approximately) —
        a trailing "?" glued straight onto "d" read like a stray typo more
        than a hedge.
        """
        parts = chip_eta_parts(proj)
        if parts is None:
            return "", "", ""
        prefix, days, hours, minutes, sev = parts
        color = _ETA_COLOR.get(sev, "#8ec8ff")
        mark = "~" if sev == "tentative" else ""
        days_txt = f"{mark}{prefix}99d+" if days >= 99 else f"{mark}{prefix}{days}d"
        return (
            f'<span style="color:{color}; font-weight:600;">{days_txt}</span>',
            f'<span style="color:{color};">{hours}h</span>',
            f'<span style="color:{color};">{minutes:02d}m</span>',
        )

    @staticmethod
    def _clock_icon_only(snap: ProviderSnapshot, metric: Metric) -> str:
        """Pie-wedge clock (angle = time left) — no text, for the chip's
        table cell where the reset-time text gets its own column.

        The wedge's color tracks USAGE severity (same scale as the % text),
        not time — a clock winding down on a nearly-full gauge should look
        alarming even with plenty of time left, and vice versa. Unknown time
        (frac=None) draws a dashed hollow ring instead of nothing, so every
        row keeps the same shape.
        """
        frac = reset_fraction_remaining(snap, metric, snap.fetched_at)
        color = QColor(_pct_color(metric.resolved_percent())) if frac is not None else QColor("#5a6272")
        return mini_charts.clock_pie_icon(frac, color)

    @classmethod
    def _clock_pie_html(cls, snap: ProviderSnapshot, metric: Metric, text: str = "") -> str:
        """Flyout use: the clock icon plus its "Xh"/"Xd" text inline (the
        flyout gives the clock its own line, so icon+text stay one unit)."""
        pie = cls._clock_icon_only(snap, metric)
        if text:
            return f'{pie} <span style="color:#6f7686;">{text}</span>'
        return pie

    @staticmethod
    def _timeline_chart(
        snap: ProviderSnapshot, metric: Metric, proj: BurnProjection | None
    ) -> str:
        """Tiny burn timeline image, always drawn: track = current cycle,
        dim fill = elapsed so far (from the same cycle inference as the
        clock, so it never needs burn-rate history to appear), coloured
        flag = where the burn rate projects exhaustion once there is a
        prediction. See ``mini_charts.burn_timeline_icon`` for why a flag,
        not a dot.
        """
        frac_remaining = reset_fraction_remaining(snap, metric, snap.fetched_at)
        elapsed_frac = None if frac_remaining is None else max(0.0, 1.0 - frac_remaining)
        exhaust_frac = None
        marker = QColor("#5a6272")
        confident = True

        if (
            proj is not None
            and proj.days_elapsed is not None
            and proj.days_left is not None
            and proj.renewal_offset_days is not None
            and (proj.days_elapsed + proj.days_left) > 0
        ):
            window = proj.days_elapsed + proj.days_left
            elapsed_frac = proj.days_elapsed / window
            if proj.days_to_exhaust is not None:
                exhaust_frac = elapsed_frac + proj.days_to_exhaust / window
            confident = proj.confident
            # Tentative predictions get the neutral marker color, not a real
            # severity — an early noisy rate must not flash red before it has
            # earned that verdict.
            marker = QColor(
                _ETA_COLOR.get(eta_severity(proj.renewal_offset_days), "#8ec8ff")
                if confident
                else _ETA_COLOR["tentative"]
            )

        # Alarm state is colour only, never a different size — every row's
        # chart stays the SAME width. Widening just the alarming rows put
        # different-length bars inside one shared table column (Qt sizes a
        # column to its widest cell), which read as stray/uneven fragments
        # rather than something that stands out.
        rocketing = bool(proj and proj.rocketing)
        return mini_charts.burn_timeline_icon(
            elapsed_frac,
            exhaust_frac,
            QColor("#ff3b3b") if rocketing else marker,
            confident=confident,
        )

    def _sparkline_html(
        self, snap: ProviderSnapshot, metric: Metric, proj: BurnProjection | None
    ) -> str:
        """Flyout-only: the real observed % history for this gauge, with a
        spike badge when today's pace triggered the "burning hot" alert."""
        if self._history is None:
            return ""
        points = self._history.series(snap.provider_id, metric.key, max_points=40)
        if len(points) < 2:
            return ""
        values = [v for _, v in points]
        color = QColor(_pct_color(metric.resolved_percent()))
        hot = bool(proj and proj.hot)
        return mini_charts.sparkline_icon(values, color, hot=hot)

    # Chip table columns: Label | Clock | Days | Hours | Minutes | Percent |
    # Usage bar | ETA-Days | ETA-Hours | ETA-Minutes. Every days/hours/minutes
    # trio is three separate columns (not one "18d 21h 29m" or "+13d 2h 14m"
    # string) so each unit's digits line up down the table — a bare "18d"
    # next to "0d" doesn't visually align, three right-aligned numeric
    # columns do. The ETA badge gets the same treatment as the reset
    # countdown for the same reason.
    #
    # The chart column is a plain percent-used bar (mini_charts.usage_bar_
    # icon), not the richer cycle-progress-plus-exhaustion-flag timeline —
    # that one encodes two things at once (time elapsed AND a projected
    # date) and kept reading as unclear at chip scale through several
    # redesign passes. The flyout/expanded view still draws the full
    # timeline (_timeline_chart) next to the words that explain it.
    _CHIP_COLS = 10
    _CHIP_RIGHT_ALIGN = {2, 3, 4, 5, 7, 8, 9}
    _CHIP_TIGHT_PAD = {3, 4, 8, 9}  # hours/minutes sit close to their own days

    # A whole-row wash for a gauge that needs attention right now — a rocketing
    # spike or a confirmed (not tentative) risk of running out before reset.
    # Column widths stay identical (nothing resizes, unlike the earlier
    # attempt), but a tinted row is hard to miss scanning down a small chip,
    # which a single small coloured dot on the timeline chart wasn't.
    # #RRGGBBAA, not rgba(...) — Qt's rich-text CSS subset reliably parses
    # the hex-alpha form; rgba() support is not guaranteed across versions.
    _CHIP_ALARM_BG = "#ff3b3b29"

    @classmethod
    def _chip_cell(cls, html: str, *, index: int, highlight: bool = False) -> str:
        align = " text-align:right;" if index in cls._CHIP_RIGHT_ALIGN else ""
        if index == 0:
            pad = "0"
        elif index in cls._CHIP_TIGHT_PAD:
            pad = "3px"
        else:
            pad = "7px"
        bg = f" background-color:{cls._CHIP_ALARM_BG};" if highlight else ""
        return f'<td style="padding:3px 0 0 {pad}; white-space:nowrap;{align}{bg}">{html}</td>'

    def _chip_row(self, *cells: str, highlight: bool = False) -> str:
        return "<tr>" + "".join(
            self._chip_cell(c, index=i, highlight=highlight) for i, c in enumerate(cells)
        ) + "</tr>"

    @staticmethod
    def _reset_parts_html(
        snap: ProviderSnapshot, metric: Metric
    ) -> tuple[str, str, str]:
        """(days, hours, minutes) cells for the reset countdown — "" in all
        three when the reset time is unknown, so the row still has exactly
        _CHIP_COLS cells."""
        parts = reset_eta_parts(metric.cycle_end or snap.cycle_end, snap.fetched_at)
        if parts is None:
            return "", "", ""
        days, hours, minutes = parts
        muted = "color:#6f7686;"
        return (
            f'<span style="{muted}">{days}d</span>',
            f'<span style="{muted}">{hours}h</span>',
            f'<span style="{muted}">{minutes:02d}m</span>',
        )

    def _chip_html(self) -> str:
        # One table row per gauge, in fixed columns — cramming every provider
        # onto a single inline row (joined with " · ") got unreadable once
        # each gauge grew a clock icon and a prediction badge, and plain
        # space-joined lines still left every column drifting left/right
        # with its content's width. A real <table> lets Qt's rich-text engine
        # size each column to its widest cell, so the same kind of value
        # lines up in the same place on every row.
        etas = primary_eta_projection(self._snapshots, self._projections)
        proj_map = {(p.provider_id, p.metric_key): p for p in self._projections}
        rows: list[str] = []
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
                rows.append(
                    f'<tr><td colspan="{self._CHIP_COLS}" style="padding:3px 0 0 0;">'
                    f'<span style="color:#ff8a80;">{tag} !</span></td></tr>'
                )
                continue
            metrics = chip_metrics(snap)
            if not metrics:
                eta_html = self._eta_html(format_chip_eta(etas.get(snap.provider_id)))
                rows.append(
                    f'<tr><td colspan="{self._CHIP_COLS}" style="padding:3px 0 0 0;">'
                    f'<span style="color:#e8ecf4;">{tag}</span>{eta_html}</td></tr>'
                )
                continue

            multi = len(metrics) > 1
            for metric in metrics:
                pct = metric.resolved_percent()
                color = _pct_color(pct)
                # Multiple gauges: name each row's own gauge instead of
                # repeating just the provider tag, and give it its own ETA
                # badge — the one that matters (e.g. API) must not hide
                # behind another gauge's prediction.
                label = f"{tag} {chip_metric_tag(metric)}" if multi else tag
                days_html, hours_html, minutes_html = self._reset_parts_html(snap, metric)
                pct_html = (
                    f'<span style="color:{color}; font-weight:700;">{pct:.0f}%</span>'
                    if pct is not None
                    else '<span style="color:#5a6272;">—</span>'
                )
                proj = proj_map.get((snap.provider_id, metric.key)) if multi else etas.get(snap.provider_id)
                eta_days, eta_hours, eta_minutes = self._eta_parts_html(proj)
                # A genuinely alarming row (confirmed on track to exhaust, or
                # a real pace spike) gets its whole row tinted — colour alone
                # on the small chart/ETA cells was too easy to miss at a
                # glance; a tentative prediction does not tint, since it
                # hasn't earned the verdict yet.
                highlight = bool(proj and (proj.rocketing or (proj.will_exhaust and proj.confident)))
                rows.append(
                    self._chip_row(
                        f'<span style="color:#8a93a6;">{label}</span>',
                        self._clock_icon_only(snap, metric),
                        days_html,
                        hours_html,
                        minutes_html,
                        pct_html,
                        mini_charts.usage_bar_icon(pct, QColor(color)),
                        eta_days,
                        eta_hours,
                        eta_minutes,
                        highlight=highlight,
                    )
                )
        if not rows:
            return '<span style="color:#e8ecf4;">Usage …</span>'
        return (
            '<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;">'
            + "".join(rows)
            + "</table>"
        )

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
            # differ (Claude's 5h vs 7d) — always drawn, even without a
            # resolvable time (dashed = unknown), so every provider keeps
            # the same shape here.
            shared_reset, per_metric_reset = grouped_reset_etas(snap, snap.metrics)
            if shared_reset:
                parts.append(
                    f'<div style="margin-top:6px; font-size:10px;">'
                    f"{self._clock_pie_html(snap, snap.metrics[0], shared_reset)}</div>"
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
                if not shared_reset:
                    reset_eta = per_metric_reset.get(metric.key, "")
                    parts.append(
                        f'<div style="margin-top:7px; font-size:10px;">'
                        f"{self._clock_pie_html(snap, metric, reset_eta)}</div>"
                    )
                parts.append(
                    f'<div style="margin-top:1px; font-size:11px; '
                    f'color:#aeb6c4;">{_escape(metric.label)} '
                    f'<span style="color:{color};">{pct_txt}</span></div>'
                )
                parts.append(
                    f'<div style="font-family:Consolas,monospace; font-size:11px; color:#9aa3b2;">'
                    f"{bar} {detail}</div>"
                )
                proj = proj_map.get((snap.provider_id, metric.key))
                bits: list[str] = []
                if proj and "collecting" not in (proj.note or ""):
                    if proj.used_today:
                        bits.append(f"+{proj.used_today:.1f} today")
                    if proj.avg_daily > 0:
                        unit = "%/day" if metric.unit == "%" else "/day"
                        bits.append(f"~{proj.avg_daily:.2f}{unit}")
                    if proj.renewal_offset_days is not None:
                        eta = format_renewal_offset(proj.renewal_offset_days)
                        off = proj.renewal_offset_days
                        tag = "" if proj.confident else " (early est.)"
                        if off < 0:
                            bits.append(f"{eta} before renewal{tag}")
                        elif off > 0:
                            bits.append(f"{eta} after renewal{tag}")
                        else:
                            bits.append(f"0d (at renewal){tag}")
                    if proj.projected_cycle_end is not None:
                        bits.append(f"→{proj.projected_cycle_end:.0f}% at reset")
                chart = self._timeline_chart(snap, metric, proj)
                bits_html = f' {_escape(" · ".join(bits))}' if bits else ""
                parts.append(
                    f'<div style="margin-top:2px; font-size:10px; color:#7a8290;">'
                    f"{chart}{bits_html}</div>"
                )
                spark = self._sparkline_html(snap, metric, proj)
                if spark:
                    parts.append(f'<div style="margin-top:3px;">{spark}</div>')
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
