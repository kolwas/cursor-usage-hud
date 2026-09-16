"""Shared OpenCode auth.json access (Windows + Linux/KDE)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def opencode_auth_path() -> Path:
    override = os.environ.get("OPENCODE_AUTH_JSON", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".local" / "share" / "opencode" / "auth.json"


def antigravity_accounts_path() -> Path:
    override = os.environ.get("OPENCODE_ANTIGRAVITY_JSON", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "opencode" / "antigravity-accounts.json"


def load_opencode_auth() -> dict[str, Any]:
    path = opencode_auth_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def auth_block(auth: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        block = auth.get(key)
        if isinstance(block, dict) and block:
            return block
    return None


def api_key_from_block(block: dict[str, Any] | None) -> str:
    if not block:
        return ""
    for field in ("key", "apiKey", "api_key", "token", "access"):
        val = block.get(field)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""
