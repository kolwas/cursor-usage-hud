"""Placeholder for Cursor Cloud Agents / other cloud spend."""

from __future__ import annotations

from usage_hud.models import Metric, ProviderSnapshot, utc_now
from usage_hud.providers.base import Provider


class CloudStubProvider(Provider):
    id = "cloud"
    title = "Cloud"

    def fetch(self) -> ProviderSnapshot:
        return ProviderSnapshot(
            provider_id=self.id,
            title="Cloud Agents",
            ok=True,
            fetched_at=utc_now(),
            metrics=[
                Metric(
                    key="stub",
                    label="Cloud spend",
                    used=0.0,
                    limit=None,
                    unit="$",
                    detail="coming soon — wire CURSOR_API_KEY / Agents API",
                )
            ],
            message="Stub provider — enable later",
        )
