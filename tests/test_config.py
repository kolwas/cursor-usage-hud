"""Settings.load() layering: env var (power-user override) beats whatever
the Settings dialog last saved to state_dir/settings.json, which beats the
hardcoded default. A fresh install with neither must behave exactly like
before the dialog existed.
"""

from __future__ import annotations

import json

import pytest

from usage_hud import config
from usage_hud.config import Settings, save_user_settings

_ENV_KEYS = (
    "USAGE_HUD_REFRESH_SECONDS",
    "USAGE_HUD_OPACITY",
    "USAGE_HUD_ALERT_BURN_MULTIPLIER",
    "USAGE_HUD_ALERT_INCLUDED_PCT",
    "USAGE_HUD_ALERT_ONDEMAND_PCT",
    "USAGE_HUD_ENABLE_CLOUD",
    "USAGE_HUD_POPUP_SECONDS",
    "USAGE_HUD_MODE",
    "USAGE_HUD_QUIET",
    "USAGE_HUD_DISABLE",
    "GITHUB_TOKEN",
    "GITHUB_LOGIN",
)


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Point state_dir at a scratch dir and strip every settings-relevant env
    var so a developer's real shell (or a real GITHUB_TOKEN) can't leak into
    an assertion."""
    monkeypatch.setenv("USAGE_HUD_STATE_DIR", str(tmp_path))
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield tmp_path


def test_fresh_install_matches_the_hardcoded_defaults(tmp_path):
    settings = Settings.load()
    assert settings.refresh_seconds == 180
    assert settings.opacity == pytest.approx(0.94)
    assert settings.github_token == ""
    assert settings.ui_mode == "chip"


def test_dialog_saved_value_is_picked_up_without_any_env_var(tmp_path):
    save_user_settings(tmp_path, {"refresh_seconds": 90, "opacity": 0.7})
    settings = Settings.load()
    assert settings.refresh_seconds == 90
    assert settings.opacity == pytest.approx(0.7)


def test_env_var_wins_over_a_saved_dialog_value(tmp_path, monkeypatch):
    save_user_settings(tmp_path, {"refresh_seconds": 90})
    monkeypatch.setenv("USAGE_HUD_REFRESH_SECONDS", "45")
    settings = Settings.load()
    assert settings.refresh_seconds == 45


def test_github_token_round_trips_through_the_saved_file(tmp_path):
    save_user_settings(tmp_path, {"github_token": "ghp_abc123", "github_login": "kolwas"})
    settings = Settings.load()
    assert settings.github_token == "ghp_abc123"
    assert settings.github_login == "kolwas"


def test_save_user_settings_merges_instead_of_overwriting(tmp_path):
    save_user_settings(tmp_path, {"refresh_seconds": 90})
    save_user_settings(tmp_path, {"opacity": 0.5})
    data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert data["refresh_seconds"] == 90
    assert data["opacity"] == 0.5


def test_corrupt_settings_file_falls_back_to_defaults_without_raising(tmp_path):
    (tmp_path / "settings.json").write_text("not json{{{", encoding="utf-8")
    settings = Settings.load()
    assert settings.refresh_seconds == 180


def test_saved_ui_mode_is_respected_without_env_override(tmp_path):
    save_user_settings(tmp_path, {"ui_mode": "quiet"})
    assert Settings.load().ui_mode == "quiet"


def test_invalid_saved_ui_mode_falls_back_instead_of_crashing(tmp_path):
    save_user_settings(tmp_path, {"ui_mode": "nonsense"})
    assert Settings.load().ui_mode == "chip"


def test_user_settings_path_lives_under_state_dir(tmp_path):
    assert config.user_settings_path(tmp_path) == tmp_path / "settings.json"
