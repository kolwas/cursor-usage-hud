"""Configuration for usage-hud."""

from __future__ import annotations

import os
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


@dataclass(frozen=True)
class Settings:
    refresh_seconds: int = 120
    opacity: float = 0.88
    alert_burn_multiplier: float = 2.0
    alert_included_pct: float = 85.0
    alert_ondemand_pct: float = 70.0
    github_token: str = ""
    github_login: str = ""
    state_dir: Path = Path()
    hud_corner: str = "top-right"  # top-right | top-left | bottom-right | bottom-left
    enable_cloud_stub: bool = False

    @classmethod
    def load(cls) -> Settings:
        # Project .env (optional) then process env.
        here = Path(__file__).resolve().parents[2]
        _load_dotenv(here / ".env")
        state = Path(os.environ.get("USAGE_HUD_STATE_DIR") or "").expanduser()
        if not str(state):
            appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
            state = Path(appdata) / "usage-hud"
        state.mkdir(parents=True, exist_ok=True)
        return cls(
            refresh_seconds=max(30, _env_int("USAGE_HUD_REFRESH_SECONDS", 120)),
            opacity=min(1.0, max(0.35, _env_float("USAGE_HUD_OPACITY", 0.88))),
            alert_burn_multiplier=max(1.1, _env_float("USAGE_HUD_ALERT_BURN_MULTIPLIER", 2.0)),
            alert_included_pct=_env_float("USAGE_HUD_ALERT_INCLUDED_PCT", 85.0),
            alert_ondemand_pct=_env_float("USAGE_HUD_ALERT_ONDEMAND_PCT", 70.0),
            github_token=os.environ.get("GITHUB_TOKEN", "").strip(),
            github_login=os.environ.get("GITHUB_LOGIN", "").strip(),
            state_dir=state,
            hud_corner=os.environ.get("USAGE_HUD_CORNER", "top-right").strip().lower(),
            enable_cloud_stub=os.environ.get("USAGE_HUD_ENABLE_CLOUD", "").strip().lower()
            in {"1", "true", "yes"},
        )
