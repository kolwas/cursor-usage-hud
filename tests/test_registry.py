"""discover_providers: GitHub Actions/storage billing has no local file to
auto-detect a subscription from (unlike Cursor/Copilot/OpenCode Go/OpenAI/
Claude), and it isn't an AI service at all — it must only appear once
someone has explicitly configured a token (Settings dialog or GITHUB_TOKEN).
A `gh` CLI session existing on the machine must NOT be enough on its own:
that ambient-detection behaviour once made the row appear for a user who
had never configured it, which read as "what is this, I didn't ask for it".
"""

import shutil

import pytest

from usage_hud.config import Settings
from usage_hud.providers.registry import discover_providers


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Point every local-file/auth signal at paths that don't exist, so this
    test's outcome depends only on the GitHub token condition under test —
    not on whatever happens to be signed in on this machine."""
    monkeypatch.setenv("USAGE_HUD_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("OPENCODE_AUTH_JSON", str(tmp_path / "missing-auth.json"))
    monkeypatch.setenv("OPENCODE_ANTIGRAVITY_JSON", str(tmp_path / "missing-antigravity.json"))
    monkeypatch.setenv("CLAUDE_DESKTOP_DIR", str(tmp_path / "missing-claude"))
    monkeypatch.setenv("CLAUDE_JSON", str(tmp_path / "missing-claude.json"))
    for key in ("GITHUB_TOKEN", "GITHUB_LOGIN", "USAGE_HUD_ENABLE_CLOUD", "USAGE_HUD_DISABLE"):
        monkeypatch.delenv(key, raising=False)
    yield


def test_github_is_omitted_without_a_configured_token(monkeypatch):
    settings = Settings.load()
    providers = discover_providers(settings)
    ids = {p.id for p in providers}
    assert "github" not in ids
    assert "cursor" in ids  # sanity: discovery still ran normally


def test_a_gh_cli_session_alone_does_not_activate_it(monkeypatch):
    """Ambient tooling on the machine must never be enough by itself — only
    an explicit token (typed into Settings, or GITHUB_TOKEN) counts as
    "configured"."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    settings = Settings.load()
    providers = discover_providers(settings)
    assert "github" not in {p.id for p in providers}


def test_github_is_included_once_a_token_is_configured(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_whatever")
    settings = Settings.load()
    providers = discover_providers(settings)
    assert "github" in {p.id for p in providers}


def test_github_can_still_be_disabled_via_provider_prefs(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_whatever")
    settings = Settings.load()

    from usage_hud.providers_pref import ProviderPrefs

    prefs = ProviderPrefs(settings.state_dir / "providers.json")
    prefs.set_enabled("github", False)

    providers = discover_providers(settings)
    assert "github" not in {p.id for p in providers}
