"""App identity — name shown to the OS, and the raven icon.

A single place for both so the taskbar/tray/.desktop entry/autostart
shortcut all agree, instead of the name or icon path being retyped at each
call site.
"""

from __future__ import annotations

from importlib import resources

from PySide6.QtGui import QIcon

APP_NAME = "Przepiórka"
DESKTOP_FILE_NAME = "przepiorka"  # matches packaging/przepiorka.desktop


def icon_path() -> str:
    # usage-hud is always run from a regular (non-zipped) install, so the
    # traversable resolves straight to a real filesystem path — no need for
    # the as_file() extraction context manager, whose temp path would go
    # stale the moment it's returned from this function anyway.
    return str(resources.files("usage_hud.assets") / "przepiorka.ico")


def app_icon() -> QIcon:
    return QIcon(icon_path())
