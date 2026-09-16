"""Configuration for usage-hud (Windows + Linux/KDE)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def default_state_dir() -> Path:
    override = os.environ.get("USAGE_HUD_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "usage-hud"
    # XDG — works for KDE / GNOME / etc.
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "usage-hud"


@dataclass(frozen=True)
class Settings:
    refresh_seconds: int = 180
    opacity: float = 0.94
    alert_burn_multiplier: float = 2.0
    alert_included_pct: float = 85.0
    alert_ondemand_pct: float = 70.0
    github_token: str = ""
    github_login: str = ""
    state_dir: Path = Path()
    # quiet = tray only (tooltip + alerts)
    # chip  = always-visible compact summary above the panel/taskbar (default)
    ui_mode: str = "chip"
    enable_cloud_stub: bool = False
    popup_seconds: int = 12
    # Comma-separated provider IDs to hide (cursor,copilot,openai,…).
    disabled_providers: frozenset[str] = frozenset()

    @classmethod
    def load(cls) -> Settings:
        here = Path(__file__).resolve().parents[2]
        _load_dotenv(here / ".env")
        state = default_state_dir()
        state.mkdir(parents=True, exist_ok=True)

        # Back-compat: USAGE_HUD_FLOATING=0 was never needed; MODE wins.
        mode = os.environ.get("USAGE_HUD_MODE", "").strip().lower()
        if not mode:
            # Explicit quiet opt-in; otherwise keep an always-visible chip.
            mode = "quiet" if _env_bool("USAGE_HUD_QUIET") else "chip"
        if mode not in {"quiet", "chip"}:
            mode = "chip"

        raw_disable = os.environ.get("USAGE_HUD_DISABLE", "").strip()
        disabled = frozenset(
            p.strip().lower() for p in raw_disable.split(",") if p.strip()
        )

        return cls(
            refresh_seconds=max(30, _env_int("USAGE_HUD_REFRESH_SECONDS", 180)),
            opacity=min(1.0, max(0.35, _env_float("USAGE_HUD_OPACITY", 0.94))),
            alert_burn_multiplier=max(1.1, _env_float("USAGE_HUD_ALERT_BURN_MULTIPLIER", 2.0)),
            alert_included_pct=_env_float("USAGE_HUD_ALERT_INCLUDED_PCT", 85.0),
            alert_ondemand_pct=_env_float("USAGE_HUD_ALERT_ONDEMAND_PCT", 70.0),
            github_token=os.environ.get("GITHUB_TOKEN", "").strip(),
            github_login=os.environ.get("GITHUB_LOGIN", "").strip(),
            state_dir=state,
            ui_mode=mode,
            enable_cloud_stub=_env_bool("USAGE_HUD_ENABLE_CLOUD"),
            popup_seconds=max(4, _env_int("USAGE_HUD_POPUP_SECONDS", 12)),
            disabled_providers=disabled,
        )
