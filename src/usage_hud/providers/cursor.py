"""Cursor subscription usage via local session + usage-summary API."""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from usage_hud.models import Metric, ProviderSnapshot, utc_now
from usage_hud.providers.base import Provider

USAGE_SUMMARY_URL = "https://cursor.com/api/usage-summary"
USER_AGENT = "usage-hud/0.1 (+local desktop monitor)"


def _default_state_db() -> Path:
    override = os.environ.get("CURSOR_STATE_DB")
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "Cursor"
        / "User"
        / "globalStorage"
        / "state.vscdb"
    )


def _jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("not a JWT")
    pad = "=" * ((4 - len(parts[1]) % 4) % 4)
    return json.loads(base64.urlsafe_b64decode(parts[1] + pad))


def read_cursor_session() -> tuple[str, str]:
    """Return (sub, jwt) from env or Cursor state.vscdb."""
    env = os.environ.get("CURSOR_SESSION_TOKEN", "").strip()
    if env:
        if "%3A%3A" in env:
            env = env.replace("%3A%3A", "::")
        if "::" in env:
            sub, _, jwt = env.partition("::")
            return sub, jwt
        payload = _jwt_payload(env)
        sub = str(payload.get("sub") or "")
        if not sub:
            raise RuntimeError("CURSOR_SESSION_TOKEN JWT missing sub")
        return sub, env

    db = _default_state_db()
    if not db.is_file():
        raise RuntimeError(f"Cursor state DB not found: {db}")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT value FROM ItemTable WHERE key=?",
            ("cursorAuth/accessToken",),
        ).fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        raise RuntimeError("cursorAuth/accessToken missing — sign in to Cursor")
    jwt = str(row[0])
    sub = str(_jwt_payload(jwt).get("sub") or "")
    if not sub:
        raise RuntimeError("session JWT missing sub claim")
    return sub, jwt


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _cents_to_dollars(cents: float | int | None) -> float:
    if cents is None:
        return 0.0
    return float(cents) / 100.0


class CursorProvider(Provider):
    id = "cursor"
    title = "Cursor"

    def fetch(self) -> ProviderSnapshot:
        now = utc_now()
        try:
            sub, jwt = read_cursor_session()
            data = self._get_usage_summary(sub, jwt)
        except Exception as exc:  # noqa: BLE001
            return ProviderSnapshot(
                provider_id=self.id,
                title=self.title,
                ok=False,
                fetched_at=now,
                error=str(exc),
            )

        individual = data.get("individualUsage") or {}
        plan = individual.get("plan") or {}
        on_demand = individual.get("onDemand") or {}
        membership = str(data.get("membershipType") or "unknown")

        metrics: list[Metric] = []

        plan_used = float(plan.get("used") or 0)
        plan_limit = plan.get("limit")
        plan_remaining = plan.get("remaining")
        total_pct = plan.get("totalPercentUsed")
        auto_pct = plan.get("autoPercentUsed")
        api_pct = plan.get("apiPercentUsed")
        breakdown = plan.get("breakdown") or {}

        detail_bits = []
        if breakdown:
            detail_bits.append(
                f"included {breakdown.get('included', '?')} + bonus {breakdown.get('bonus', '?')}"
            )
        if auto_pct is not None:
            detail_bits.append(f"auto {auto_pct}%")
        if api_pct is not None:
            detail_bits.append(f"API {api_pct}%")

        metrics.append(
            Metric(
                key="included",
                label="Included plan",
                used=plan_used,
                limit=float(plan_limit) if plan_limit is not None else None,
                unit="req$",
                remaining=float(plan_remaining) if plan_remaining is not None else None,
                percent_used=float(total_pct) if total_pct is not None else None,
                detail=" · ".join(detail_bits),
            )
        )

        if on_demand.get("enabled"):
            od_used = _cents_to_dollars(on_demand.get("used"))
            od_limit = on_demand.get("limit")
            od_remaining = on_demand.get("remaining")
            od_limit_d = _cents_to_dollars(od_limit) if od_limit is not None else None
            od_rem_d = _cents_to_dollars(od_remaining) if od_remaining is not None else None
            pct = None
            if od_limit_d and od_limit_d > 0:
                pct = 100.0 * od_used / od_limit_d
            metrics.append(
                Metric(
                    key="ondemand",
                    label="On-demand spend",
                    used=od_used,
                    limit=od_limit_d,
                    unit="$",
                    remaining=od_rem_d,
                    percent_used=pct,
                    detail="beyond included allowance",
                )
            )

        msg = str(
            data.get("namedModelSelectedDisplayMessage")
            or data.get("autoModelSelectedDisplayMessage")
            or ""
        )

        return ProviderSnapshot(
            provider_id=self.id,
            title=f"Cursor ({membership})",
            ok=True,
            fetched_at=now,
            metrics=metrics,
            cycle_start=_parse_iso(data.get("billingCycleStart")),
            cycle_end=_parse_iso(data.get("billingCycleEnd")),
            message=msg,
            raw=data,
        )

    def _get_usage_summary(self, sub: str, jwt: str) -> dict[str, Any]:
        req = urllib.request.Request(
            USAGE_SUMMARY_URL,
            headers={
                "Cookie": f"WorkosCursorSessionToken={sub}::{jwt}",
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            raise RuntimeError(f"Cursor API HTTP {exc.code}: {body}") from exc
