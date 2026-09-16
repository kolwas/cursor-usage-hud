"""Which providers are shown — persisted + optional env denylist."""

from __future__ import annotations

import json
from pathlib import Path

# Stable IDs used across registry / chip tags / tray.
KNOWN_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("cursor", "Cursor"),
    ("copilot", "Copilot"),
    ("opencode-go", "OpenCode Go"),
    ("openai", "OpenAI"),
    ("anthropic", "Claude"),
    ("github", "GitHub"),
    ("cloud", "Cloud"),
)


class ProviderPrefs:
    """disabled = hidden from chip/tray/fetch. Missing file → all enabled."""

    def __init__(self, path: Path, *, env_disabled: set[str] | None = None) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._env_disabled = {x.strip().lower() for x in (env_disabled or set()) if x.strip()}
        self._disabled: set[str] = set()
        self.load()

    def load(self) -> None:
        disabled: set[str] = set(self._env_disabled)
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                for item in data.get("disabled") or []:
                    disabled.add(str(item).strip().lower())
            except (OSError, json.JSONDecodeError, TypeError):
                pass
        self._disabled = disabled

    def save(self) -> None:
        # Persist only toggles beyond env defaults so .env still applies on fresh file.
        persisted = sorted(self._disabled - self._env_disabled)
        # Also persist explicit re-enables of env-disabled? Keep simple: store full disabled set.
        payload = {"disabled": sorted(self._disabled)}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def is_enabled(self, provider_id: str) -> bool:
        return provider_id.lower() not in self._disabled

    def set_enabled(self, provider_id: str, enabled: bool) -> None:
        pid = provider_id.lower()
        if enabled:
            self._disabled.discard(pid)
        else:
            self._disabled.add(pid)
        self.save()

    def disabled_ids(self) -> set[str]:
        return set(self._disabled)
