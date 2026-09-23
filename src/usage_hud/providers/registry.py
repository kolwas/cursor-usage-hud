"""Discover and instantiate providers from local auth + always-on Cursor."""

from __future__ import annotations

from usage_hud.config import Settings
from usage_hud.providers.anthropic import AnthropicProvider, claude_present_locally
from usage_hud.providers.base import Provider
from usage_hud.providers.cloud import CloudStubProvider
from usage_hud.providers.copilot import CopilotProvider
from usage_hud.providers.cursor import CursorProvider
from usage_hud.providers.github import GitHubProvider
from usage_hud.providers.openai_chatgpt import OpenAIProvider
from usage_hud.providers.opencode_auth import (
    antigravity_accounts_path,
    auth_block,
    load_opencode_auth,
)
from usage_hud.providers.opencode_go import OpenCodeGoProvider


def discover_providers(settings: Settings | None = None) -> list[Provider]:
    """Return providers for every detected subscription.

    Always includes Cursor (editor session). OpenCode auth.json drives the rest.
    Providers without credentials are omitted (not shown as errors).
    Disabled IDs (prefs / USAGE_HUD_DISABLE) are skipped.
    """
    settings = settings or Settings.load()
    from usage_hud.providers_pref import ProviderPrefs

    prefs = ProviderPrefs(
        settings.state_dir / "providers.json",
        env_disabled=set(settings.disabled_providers),
    )

    candidates: list[Provider] = []
    if prefs.is_enabled("cursor"):
        candidates.append(CursorProvider())

    auth = load_opencode_auth()

    if prefs.is_enabled("copilot") and auth_block(auth, "github-copilot", "github_copilot"):
        candidates.append(CopilotProvider())

    if prefs.is_enabled("opencode-go") and auth_block(auth, "opencode-go", "opencode"):
        candidates.append(OpenCodeGoProvider())

    if prefs.is_enabled("openai") and auth_block(auth, "openai", "chatgpt", "openai-codex"):
        candidates.append(OpenAIProvider())

    # Claude is read from local Claude files only — an OpenCode Anthropic login
    # would need the account API, which this HUD deliberately does not call.
    if prefs.is_enabled("anthropic") and claude_present_locally():
        candidates.append(AnthropicProvider())

    if settings.enable_cloud_stub or antigravity_accounts_path().is_file():
        if settings.enable_cloud_stub and prefs.is_enabled("cloud"):
            candidates.append(CloudStubProvider())

    # GitHub Actions/storage billing has no local file to auto-detect a
    # subscription from the way the other providers do, and it isn't an AI
    # service at all — it must only appear once someone has explicitly typed
    # a token into the Settings dialog (or set GITHUB_TOKEN themselves), not
    # merely because a `gh` CLI session happens to exist on this machine.
    # Ambient `gh` auto-detection surprised a user who never configured it.
    if prefs.is_enabled("github") and settings.github_token:
        candidates.append(GitHubProvider(settings))

    return candidates


def visible_snapshots(snapshots: list) -> list:
    """Hide empty 'not subscribed' successes from the chip."""
    out = []
    for snap in snapshots:
        if snap.ok and not snap.metrics and "no Go subscription" in (snap.message or ""):
            continue
        if snap.ok and not snap.metrics:
            continue
        out.append(snap)
    return out
