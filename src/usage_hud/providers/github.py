"""GitHub Actions / storage billing usage."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any

from usage_hud.config import Settings
from usage_hud.models import Metric, ProviderSnapshot, utc_now
from usage_hud.providers.base import Provider

API = "https://api.github.com"
UA = "usage-hud/0.1"


class GitHubProvider(Provider):
    id = "github"
    title = "GitHub"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch(self) -> ProviderSnapshot:
        now = utc_now()
        token = self.settings.github_token or self._token_from_gh()
        if not token:
            return ProviderSnapshot(
                provider_id=self.id,
                title=self.title,
                ok=False,
                fetched_at=now,
                error="Set GITHUB_TOKEN or run `gh auth login`",
            )

        try:
            login = self.settings.github_login or self._whoami(token)
            actions = self._get(f"/users/{login}/settings/billing/actions", token)
            packages = self._get_optional(
                f"/users/{login}/settings/billing/packages", token
            )
            storage = self._get_optional(
                f"/users/{login}/settings/billing/shared-storage", token
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderSnapshot(
                provider_id=self.id,
                title=self.title,
                ok=False,
                fetched_at=now,
                error=str(exc),
            )

        metrics: list[Metric] = []
        used = float(actions.get("total_minutes_used") or 0)
        included = float(actions.get("included_minutes") or 0)
        paid = float(actions.get("total_paid_minutes_used") or 0)
        pct = (100.0 * used / included) if included > 0 else None
        metrics.append(
            Metric(
                key="actions",
                label="Actions minutes",
                used=used,
                limit=included if included > 0 else None,
                unit="min",
                remaining=(included - used) if included > 0 else None,
                percent_used=pct,
                detail=f"paid overage {paid:.0f} min" if paid else "",
            )
        )

        if packages:
            pkg_used = float(packages.get("total_gigabytes_bandwidth_used") or 0)
            pkg_inc = float(packages.get("included_gigabytes_bandwidth") or 0)
            metrics.append(
                Metric(
                    key="packages",
                    label="Packages bandwidth",
                    used=pkg_used,
                    limit=pkg_inc if pkg_inc > 0 else None,
                    unit="GB",
                    remaining=(pkg_inc - pkg_used) if pkg_inc > 0 else None,
                    percent_used=(100.0 * pkg_used / pkg_inc) if pkg_inc > 0 else None,
                )
            )

        if storage:
            # estimated_storage_for_period / estimated_paid_storage_for_period (GB-days etc.)
            est = storage.get("estimated_storage_for_month")
            if est is None:
                est = storage.get("estimated_storage_for_period")
            paid_s = storage.get("estimated_paid_storage_for_month")
            if paid_s is None:
                paid_s = storage.get("estimated_paid_storage_for_period")
            if est is not None:
                metrics.append(
                    Metric(
                        key="storage",
                        label="Shared storage",
                        used=float(est),
                        limit=None,
                        unit="GB-mo",
                        detail=f"paid est. {paid_s}" if paid_s is not None else "",
                    )
                )

        return ProviderSnapshot(
            provider_id=self.id,
            title=f"GitHub ({login})",
            ok=True,
            fetched_at=now,
            metrics=metrics,
            message="Personal account billing",
            raw={"actions": actions, "packages": packages, "storage": storage},
        )

    def _token_from_gh(self) -> str:
        gh = shutil.which("gh")
        if not gh:
            return ""
        try:
            out = subprocess.check_output(
                [gh, "auth", "token"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10,
            )
            return out.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return ""

    def _whoami(self, token: str) -> str:
        data = self._get("/user", token)
        login = data.get("login")
        if not login:
            raise RuntimeError("GitHub /user missing login")
        return str(login)

    def _get(self, path: str, token: str) -> dict[str, Any]:
        req = urllib.request.Request(
            API + path,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": UA,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:240]
            raise RuntimeError(f"GitHub {path} HTTP {exc.code}: {body}") from exc

    def _get_optional(self, path: str, token: str) -> dict[str, Any] | None:
        try:
            return self._get(path, token)
        except RuntimeError:
            return None
