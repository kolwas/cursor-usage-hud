"""Multi-monitor + presentation-mode helpers (Windows + Linux/KDE)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QCursor, QGuiApplication, QScreen


def screen_under_cursor() -> QScreen | None:
    screen = QGuiApplication.screenAt(QCursor.pos())
    return screen or QGuiApplication.primaryScreen()


def idle_screen(prefer_away_from: QScreen | None = None) -> QScreen | None:
    """Pick a monitor the user is *not* working on.

    Prefer any screen other than the one under the cursor / given screen.
    Falls back to primary when only one display exists.
    """
    screens = list(QGuiApplication.screens())
    if not screens:
        return None
    if len(screens) == 1:
        return screens[0]

    active = prefer_away_from or screen_under_cursor()
    others = [s for s in screens if s is not active]
    if not others:
        return active

    # Prefer a non-primary secondary (typical "side" monitor), else first other.
    primary = QGuiApplication.primaryScreen()
    non_primary = [s for s in others if s is not primary]
    return non_primary[0] if non_primary else others[0]


def next_screen_after(current: QScreen | None) -> QScreen | None:
    """Cycle to another monitor (used when cursor hovers the chip)."""
    screens = list(QGuiApplication.screens())
    if not screens:
        return None
    if len(screens) == 1:
        return screens[0]
    if current is None or current not in screens:
        return idle_screen()
    idx = screens.index(current)
    return screens[(idx + 1) % len(screens)]


def is_presentation_mode() -> bool:
    """Best-effort detection — hide the chip during presentations.

    Windows: Mobility Center presentation settings registry flag, plus
    common presenter processes with a fullscreen-ish foreground window.
    Linux/KDE: fullscreen active window via xdotool/qdbus when available;
    also honor USAGE_HUD_PRESENTATION=1.
    """
    if os.environ.get("USAGE_HUD_PRESENTATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True

    if sys.platform == "win32":
        return _windows_presentation()
    return _linux_presentation()


def _windows_presentation() -> bool:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\PresentationSettings",
        )
        try:
            val, _ = winreg.QueryValueEx(key, "NoScreenSave")
            if int(val) == 1:
                return True
        finally:
            winreg.CloseKey(key)
    except OSError:
        pass

    # Foreground window covers nearly an entire monitor → treat as presenting.
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        # Match against any screen geometry (±2% tolerance).
        for screen in QGuiApplication.screens():
            g = screen.geometry()
            if w >= int(g.width() * 0.97) and h >= int(g.height() * 0.97):
                # Ignore our own tiny tool windows.
                if w * h > 800 * 600:
                    return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _linux_presentation() -> bool:
    # Manual / scripted presentation marker (portable across DEs).
    xdg_state = os.environ.get("XDG_STATE_HOME", "").strip()
    state_root = Path(xdg_state).expanduser() if xdg_state else Path.home() / ".local" / "state"
    if (state_root / "usage-hud-presentation").is_file():
        return True

    # KWin: ask whether the active window is fullscreen.
    try:
        import subprocess

        out = subprocess.check_output(
            [
                "qdbus",
                "org.kde.KWin",
                "/KWin",
                "org.kde.KWin.queryWindowInfo",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
        )
        lowered = out.lower()
        if "fullscreen" in lowered and ("true" in lowered or "1" in lowered):
            return True
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        pass

    # Fallback: xprop on active window (_NET_WM_STATE_FULLSCREEN).
    try:
        import subprocess

        wid = subprocess.check_output(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
        )
        # e.g. _NET_ACTIVE_WINDOW(WINDOW): window id # 0x123456
        parts = wid.strip().split()
        window_id = parts[-1] if parts else ""
        if window_id.startswith("0x"):
            state = subprocess.check_output(
                ["xprop", "-id", window_id, "_NET_WM_STATE"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.5,
            )
            if "_NET_WM_STATE_FULLSCREEN" in state:
                return True
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        pass

    return False
