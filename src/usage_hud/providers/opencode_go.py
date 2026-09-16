"""OpenCode Go subscription windows (rolling / weekly / monthly)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from usage_hud.models import Metric, ProviderSnapshot, utc_now
from usage_hud.providers.base import Provider
from usage_hud.providers.opencode_auth import api_key_from_block, auth_block, load_opencode_auth

USAGE_URL = "https://opencode.ai/zen/go/v1/usage"
UA = "usage-hud/0.1"


class OpenCodeGoProvider(Provider):
    id = "opencode-go"
    title = "OpenCode Go"

    def fetch(self) -> ProviderSnapshot:
        now = utc_now()
        auth = load_opencode_auth()
        block = auth_block(auth, "opencode-go", "opencode")
        key = api_key_from_block(block)
        if not key:
            return ProviderSnapshot(
                provider_id=self.id,
                title=self.title,
                ok=False,
                fetched_at=now,
                error="no opencode-go key in OpenCode auth",
            )

        try:
            data = self._get(key)
        except _EntitlementError:
            # Key valid but no Go plan — silent skip (not an alert-worthy failure).
            return ProviderSnapshot(
                provider_id=self.id,
                title=self.title,
                ok=True,
                fetched_at=now,
                metrics=[],
                message="no Go subscription on this key",
                raw={"entitled": False},
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderSnapshot(
                provider_id=self.id,
                title=self.title,
                ok=False,
                fetched_at=now,
                error=str(exc),
            )

        usage = data.get("usage") or {}
        metrics: list[Metric] = []
        cycle_end = None
        for key_name, label in (
            ("rolling", "5h window"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
        ):
            window = usage.get(key_name) or {}
            if not isinstance(window, dict):
                continue
            if window.get("status") and window.get("status") != "ok":
                continue
            pct = window.get("percent")
            if pct is None:
                continue
            pct_f = float(pct)
            reset = _parse_reset(window.get("resetsAt"))
            metrics.append(
                Metric(
                    key=key_name,
                    label=label,
                    used=pct_f,
                    limit=100.0,
                    unit="%",
                    remaining=max(0.0, 100.0 - pct_f),
                    percent_used=pct_f,
                    detail=f"resets {window.get('resetsAt') or '?'}",
                    cycle_end=reset,
                )
            )
            if reset and (cycle_end is None or reset < cycle_end):
                cycle_end = reset

        return ProviderSnapshot(
            provider_id=self.id,
            title=self.title,
            ok=True,
            fetched_at=now,
            metrics=metrics,
            cycle_end=cycle_end,
            message="OpenCode Go plan",
            raw=data,
        )

    def _get(self, key: str) -> dict[str, Any]:
        req = urllib.request.Request(
            USAGE_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
                "User-Agent": UA,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 403 and "EntitlementError" in body:
                raise _EntitlementError(body) from exc
            raise RuntimeError(f"OpenCode Go HTTP {exc.code}: {body[:200]}") from exc


class _EntitlementError(RuntimeError):
    pass


def _parse_reset(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
