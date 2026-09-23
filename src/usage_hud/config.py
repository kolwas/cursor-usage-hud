"""Configuration for usage-hud (Windows + Linux/KDE)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def user_settings_path(state_dir: Path) -> Path:
    """Where the Settings dialog persists its edits — plain JSON in the same
    per-user state directory as history.json/providers.json/snooze.json, not
    in the repo and not in .env, so it survives a reinstall/update and never
    risks getting committed."""
    return state_dir / "settings.json"


def _load_user_settings(state_dir: Path) -> dict[str, Any]:
    path = user_settings_path(state_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_user_settings(state_dir: Path, values: dict[str, Any]) -> None:
    """Merge ``values`` into the persisted settings file (partial update —
    callers pass only the fields their form actually edits)."""
    path = user_settings_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = _load_user_settings(state_dir)
    current.update(values)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")


def _resolve_float(user: dict[str, Any], env_name: str, key: str, default: float) -> float:
    fallback = user.get(key, default)
    try:
        fallback = float(fallback)
    except (TypeError, ValueError):
        fallback = default
    return _env_float(env_name, fallback)


def _resolve_int(user: dict[str, Any], env_name: str, key: str, default: int) -> int:
    fallback = user.get(key, default)
    try:
        fallback = int(fallback)
    except (TypeError, ValueError):
        fallback = default
    return _env_int(env_name, fallback)


def _resolve_bool(user: dict[str, Any], env_name: str, key: str, default: bool) -> bool:
    fallback = user.get(key, default)
    if not isinstance(fallback, bool):
        fallback = default
    return _env_bool(env_name, fallback)


def _resolve_str(user: dict[str, Any], env_name: str, key: str, default: str = "") -> str:
    # An explicit environment variable is the power-user override and always
    # wins; otherwise fall back to whatever the Settings dialog last saved.
    env_val = os.environ.get(env_name, "").strip()
    if env_val:
        return env_val
    stored = user.get(key, default)
    return str(stored).strip() if stored else default


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
        # Everything below layers env var (power-user / packaging override,
        # always wins when set) over what the Settings dialog last saved
        # (state_dir/settings.json) over the hardcoded default — so a fresh
        # install with no .env and no dialog use behaves exactly as before.
        user = _load_user_settings(state)

        # Back-compat: USAGE_HUD_FLOATING=0 was never needed; MODE wins.
        mode = os.environ.get("USAGE_HUD_MODE", "").strip().lower()
        if not mode:
            stored_mode = str(user.get("ui_mode", "")).strip().lower()
            if stored_mode in {"quiet", "chip"}:
                mode = stored_mode
            else:
                # Explicit quiet opt-in; otherwise keep an always-visible chip.
                mode = "quiet" if _env_bool("USAGE_HUD_QUIET") else "chip"
        if mode not in {"quiet", "chip"}:
            mode = "chip"

        raw_disable = os.environ.get("USAGE_HUD_DISABLE", "").strip()
        disabled = frozenset(
            p.strip().lower() for p in raw_disable.split(",") if p.strip()
        )

        return cls(
            refresh_seconds=max(30, _resolve_int(user, "USAGE_HUD_REFRESH_SECONDS", "refresh_seconds", 180)),
            opacity=min(1.0, max(0.35, _resolve_float(user, "USAGE_HUD_OPACITY", "opacity", 0.94))),
            alert_burn_multiplier=max(
                1.1, _resolve_float(user, "USAGE_HUD_ALERT_BURN_MULTIPLIER", "alert_burn_multiplier", 2.0)
            ),
            alert_included_pct=_resolve_float(
                user, "USAGE_HUD_ALERT_INCLUDED_PCT", "alert_included_pct", 85.0
            ),
            alert_ondemand_pct=_resolve_float(
                user, "USAGE_HUD_ALERT_ONDEMAND_PCT", "alert_ondemand_pct", 70.0
            ),
            github_token=_resolve_str(user, "GITHUB_TOKEN", "github_token"),
            github_login=_resolve_str(user, "GITHUB_LOGIN", "github_login"),
            state_dir=state,
            ui_mode=mode,
            enable_cloud_stub=_resolve_bool(user, "USAGE_HUD_ENABLE_CLOUD", "enable_cloud_stub", False),
            popup_seconds=max(4, _resolve_int(user, "USAGE_HUD_POPUP_SECONDS", "popup_seconds", 12)),
            disabled_providers=disabled,
        )
