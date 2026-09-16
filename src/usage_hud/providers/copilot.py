"""GitHub Copilot quota via OpenCode OAuth session."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from usage_hud.cycle import prev_month_same_day
from usage_hud.models import Metric, ProviderSnapshot, utc_now
from usage_hud.providers.base import Provider
from usage_hud.providers.opencode_auth import auth_block, load_opencode_auth, opencode_auth_path

COPILOT_USER_URL = "https://api.github.com/copilot_internal/user"
UA_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "GitHubCopilotChat/0.35.0",
    "Editor-Version": "vscode/1.107.0",
    "Editor-Plugin-Version": "copilot-chat/0.35.0",
    "Copilot-Integration-Id": "vscode-chat",
}


def read_opencode_copilot_token() -> str:
    """Return OAuth access token stored by OpenCode for github-copilot."""
    env = os.environ.get("GITHUB_COPILOT_TOKEN", "").strip()
    if env:
        return env
    path = opencode_auth_path()
    if not path.is_file():
        raise RuntimeError(f"OpenCode auth not found: {path}")
    data = load_opencode_auth()
    block = auth_block(data, "github-copilot", "github_copilot")
    if not block:
        raise RuntimeError("OpenCode auth.json has no github-copilot entry — log in via OpenCode")
    token = str(block.get("access") or "").strip()
    if not token:
        raise RuntimeError("github-copilot.access empty — re-auth Copilot in OpenCode")
    return token


def _parse_reset(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if len(text) == 10 and text[4] == "-":
        return datetime(int(text[0:4]), int(text[5:7]), int(text[8:10]), tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


class CopilotProvider(Provider):
    id = "copilot"
    title = "Copilot"

    def fetch(self) -> ProviderSnapshot:
        now = utc_now()
        try:
            token = read_opencode_copilot_token()
            data = self._get_user(token)
        except Exception as exc:  # noqa: BLE001
            return ProviderSnapshot(
                provider_id=self.id,
                title=self.title,
                ok=False,
                fetched_at=now,
                error=str(exc),
            )

        login = str(data.get("login") or "")
        plan = str(data.get("copilot_plan") or "unknown")
        snapshots = data.get("quota_snapshots") or {}
        metrics: list[Metric] = []

        premium = snapshots.get("premium_interactions") or {}
        if premium:
            metrics.append(self._metric_from_quota("premium", "Premium requests", premium))

        for key, label in (("chat", "Chat"), ("completions", "Completions")):
            raw = snapshots.get(key) or {}
            if raw and not raw.get("unlimited"):
                metrics.append(self._metric_from_quota(key, label, raw))

        overage = int(premium.get("overage_count") or 0)
        overage_ok = bool(premium.get("overage_permitted"))
        msg_bits = [f"plan {plan}"]
        if overage:
            msg_bits.append(f"overage {overage}")
        elif overage_ok:
            msg_bits.append("overage allowed")

        title = f"Copilot ({plan})"
        if login:
            title = f"Copilot · {login}"

        cycle_end = _parse_reset(
            data.get("quota_reset_date") or data.get("quota_reset_date_utc")
        )
        cycle_start = prev_month_same_day(cycle_end) if cycle_end else None

        return ProviderSnapshot(
            provider_id=self.id,
            title=title,
            ok=True,
            fetched_at=now,
            metrics=metrics,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            message=" · ".join(msg_bits),
            raw=data,
        )

    def _metric_from_quota(self, key: str, label: str, raw: dict[str, Any]) -> Metric:
        entitlement = float(raw.get("entitlement") or 0)
        remaining = raw.get("remaining")
        if remaining is None:
            remaining = raw.get("quota_remaining")
        remaining_f = float(remaining) if remaining is not None else None
        used = None
        if remaining_f is not None and entitlement:
            used = max(0.0, entitlement - remaining_f)
        if raw.get("credits_used") is not None and entitlement:
            used = float(raw["credits_used"])
            if remaining_f is None:
                remaining_f = max(0.0, entitlement - used)

        pct_rem = raw.get("percent_remaining")
        pct_used = None
        if pct_rem is not None:
            pct_used = max(0.0, 100.0 - float(pct_rem))
        elif used is not None and entitlement > 0:
            pct_used = 100.0 * used / entitlement

        detail = ""
        if raw.get("overage_count"):
            detail = f"overage {raw['overage_count']}"
        if raw.get("token_based_billing"):
            detail = (detail + " · token billing").strip(" ·")

        return Metric(
            key=key,
            label=label,
            used=float(used or 0.0),
            limit=entitlement if entitlement > 0 else None,
            unit="",
            remaining=remaining_f,
            percent_used=pct_used,
            detail=detail,
        )

    def _get_user(self, token: str) -> dict[str, Any]:
        req = urllib.request.Request(
            COPILOT_USER_URL,
            headers={**UA_HEADERS, "Authorization": f"Bearer {token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:240]
            raise RuntimeError(f"Copilot API HTTP {exc.code}: {body}") from exc
