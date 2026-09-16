"""Windows ITaskbarList3 progress — imported only on win32."""

from __future__ import annotations

import ctypes
from ctypes import POINTER, byref, c_int, c_ulonglong, c_void_p, cast
from ctypes.wintypes import DWORD, HWND, WORD

from PySide6.QtWidgets import QWidget

from usage_hud.models import Alert, AlertLevel, ProviderSnapshot
from usage_hud.ui.formatters import badge_icon, compact_title, worst_percent

TBPF_NOPROGRESS = 0
TBPF_NORMAL = 0x2
TBPF_ERROR = 0x4
TBPF_PAUSED = 0x8


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", DWORD),
        ("Data2", WORD),
        ("Data3", WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> _GUID:
    g = _GUID()
    ctypes.oledll.ole32.CLSIDFromString(text, byref(g))
    return g


class WinTaskbarController:
    def __init__(self, window: QWidget) -> None:
        self._window = window
        self._tb: c_void_p | None = None
        try:
            ctypes.oledll.ole32.CoInitialize(None)
        except OSError:
            pass
        try:
            clsid = _guid("{56FDF344-FD6D-11D0-958A-006097C9A090}")
            iid = _guid("{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}")
            ptr = c_void_p()
            hr = ctypes.oledll.ole32.CoCreateInstance(
                byref(clsid), None, 1, byref(iid), byref(ptr)
            )
            if hr != 0 or not ptr.value:
                return
            vtbl_ptr = cast(ptr, POINTER(c_void_p)).contents
            vtbl = cast(vtbl_ptr, POINTER(c_void_p * 16)).contents
            self._tb = ptr
            self._HrInit = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p)(vtbl[3])
            self._SetProgressValue = ctypes.WINFUNCTYPE(
                ctypes.HRESULT, c_void_p, HWND, c_ulonglong, c_ulonglong
            )(vtbl[9])
            self._SetProgressState = ctypes.WINFUNCTYPE(
                ctypes.HRESULT, c_void_p, HWND, c_int
            )(vtbl[10])
            self._HrInit(ptr)
        except Exception:  # noqa: BLE001
            self._tb = None

    def update(self, snapshots: list[ProviderSnapshot], alerts: list[Alert]) -> None:
        title = compact_title(snapshots, alerts)
        self._window.setWindowTitle(title)
        self._window.setWindowIcon(badge_icon(snapshots, alerts))
        if self._tb is None:
            return
        hwnd = int(self._window.winId())
        if not hwnd:
            return
        pct = worst_percent(snapshots)
        try:
            if pct is None:
                self._SetProgressState(self._tb, hwnd, TBPF_NOPROGRESS)
                return
            if any(a.level == AlertLevel.CRITICAL for a in alerts) or pct >= 95:
                state = TBPF_ERROR
            elif any(a.level == AlertLevel.WARN for a in alerts) or pct >= 80:
                state = TBPF_PAUSED
            else:
                state = TBPF_NORMAL
            self._SetProgressState(self._tb, hwnd, state)
            self._SetProgressValue(self._tb, hwnd, int(min(100.0, max(0.0, pct))), 100)
        except Exception:  # noqa: BLE001
            pass
