"""ChatGPT / OpenAI Plus quota via OpenCode OAuth token."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from usage_hud.cycle import window_end_from_seconds
from usage_hud.models import Metric, ProviderSnapshot, utc_now
from usage_hud.providers.base import Provider
from usage_hud.providers.opencode_auth import auth_block, load_opencode_auth

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
UA = "usage-hud/0.1"


class OpenAIProvider(Provider):
    id = "openai"
    title = "OpenAI"

    def fetch(self) -> ProviderSnapshot:
        now = utc_now()
        auth = load_opencode_auth()
        block = auth_block(auth, "openai", "chatgpt", "openai-codex")
        if not block:
            return ProviderSnapshot(
                provider_id=self.id,
                title=self.title,
                ok=False,
                fetched_at=now,
                error="OpenAI not connected in OpenCode",
            )
        token = str(block.get("access") or block.get("token") or block.get("key") or "").strip()
        if not token:
            return ProviderSnapshot(
                provider_id=self.id,
                title=self.title,
                ok=False,
                fetched_at=now,
                error="OpenAI token empty",
            )

        try:
            data = self._get(token, block.get("accountId") or block.get("account_id"))
        except Exception as exc:  # noqa: BLE001
            return ProviderSnapshot(
                provider_id=self.id,
                title=self.title,
                ok=False,
                fetched_at=now,
                error=str(exc),
            )

        plan = str(data.get("plan_type") or "ChatGPT")
        rate = data.get("rate_limit") or {}
        metrics: list[Metric] = []
        primary_end = None
        for key, label in (
            ("primary_window", "Primary window"),
            ("secondary_window", "Daily window"),
        ):
            window = rate.get(key) or {}
            if not isinstance(window, dict):
                continue
            used_pct = window.get("used_percent")
            if used_pct is None:
                continue
            pct = float(used_pct)
            reset_at = window_end_from_seconds(now, window.get("reset_after_seconds"))
            if key == "primary_window":
                primary_end = reset_at
            metrics.append(
                Metric(
                    key=key,
                    label=label,
                    used=pct,
                    limit=100.0,
                    unit="%",
                    remaining=max(0.0, 100.0 - pct),
                    percent_used=pct,
                    detail=f"reset in {window.get('reset_after_seconds', '?')}s",
                    cycle_end=reset_at,
                )
            )

        return ProviderSnapshot(
            provider_id=self.id,
            title=f"OpenAI ({plan})",
            ok=True,
            fetched_at=now,
            metrics=metrics,
            cycle_end=primary_end,
            message=plan,
            raw=data,
        )

    def _get(self, token: str, account_id: Any) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": UA,
            "Accept": "application/json",
        }
        if account_id:
            headers["ChatGPT-Account-Id"] = str(account_id)
        req = urllib.request.Request(USAGE_URL, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            raise RuntimeError(f"OpenAI usage HTTP {exc.code}: {body}") from exc
