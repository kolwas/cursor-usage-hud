"""Windows taskbar progress (optional). No-op stub on non-Windows."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QWidget

from usage_hud.models import Alert, ProviderSnapshot
from usage_hud.ui.formatters import badge_icon, compact_title, worst_percent

__all__ = [
    "TaskbarController",
    "badge_icon",
    "compact_title",
    "worst_percent",
]


if sys.platform == "win32":
    from usage_hud.ui._taskbar_win_impl import WinTaskbarController as TaskbarController
else:

    class TaskbarController:  # type: ignore[no-redef]
        def __init__(self, window: QWidget) -> None:
            self._window = window

        def update(self, snapshots: list[ProviderSnapshot], alerts: list[Alert]) -> None:
            self._window.setWindowTitle(compact_title(snapshots, alerts))
            self._window.setWindowIcon(badge_icon(snapshots, alerts))
