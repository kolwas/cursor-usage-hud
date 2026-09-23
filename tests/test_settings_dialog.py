"""SettingsDialog: opens against a real Settings instance, edits a couple of
fields, saves, and checks the values actually round-trip through disk (not
just the widget's own state)."""

import pytest

pytest.importorskip("PySide6")

from dataclasses import replace  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

from usage_hud.config import Settings  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _settings(tmp_path) -> Settings:
    return replace(Settings(), state_dir=tmp_path)


def test_save_persists_general_and_github_fields(tmp_path):
    from usage_hud.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(_settings(tmp_path))
    dialog._refresh.setValue(75)
    dialog._opacity.setValue(60)
    dialog._github_token.setText("ghp_test_token")
    dialog._github_login.setText("kolwas")
    dialog._save()

    from usage_hud.config import _load_user_settings

    saved = _load_user_settings(tmp_path)
    assert saved["refresh_seconds"] == 75
    assert saved["opacity"] == pytest.approx(0.6)
    assert saved["github_token"] == "ghp_test_token"
    assert saved["github_login"] == "kolwas"


def test_disabling_a_provider_checkbox_persists_to_provider_prefs(tmp_path):
    from usage_hud.providers_pref import ProviderPrefs
    from usage_hud.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(_settings(tmp_path))
    dialog._enabled_checks["copilot"].setChecked(False)
    dialog._save()

    prefs = ProviderPrefs(tmp_path / "providers.json")
    assert not prefs.is_enabled("copilot")
    assert prefs.is_enabled("cursor")


def test_claude_service_box_has_no_credential_field(tmp_path):
    """Hard constraint from this project: Claude/Anthropic reads local files
    only, zero credentials, zero network calls — the dialog must not grow a
    token field for it the way it did for GitHub."""
    from usage_hud.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(_settings(tmp_path))
    for name in ("_claude_token", "_anthropic_token", "_claude_key"):
        assert not hasattr(dialog, name)
