"""Runs provider fetches off the UI thread.

Every provider call is a blocking network or database read (up to 25 s each),
and they ran one after another on the UI thread. With the network down — after
a night of sleep, say — the window then stopped answering for over a minute,
Windows flagged it as not responding and closed it. Fetching in a worker
thread keeps the window alive no matter how slow or broken a provider is.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot

from usage_hud.config import Settings
from usage_hud.models import ProviderSnapshot, utc_now
from usage_hud.providers.base import Provider
from usage_hud.providers.registry import discover_providers


def _safe_fetch(provider: Provider) -> ProviderSnapshot:
    try:
        return provider.fetch()
    except Exception as exc:  # noqa: BLE001 - a provider must never take the app down
        return ProviderSnapshot(
            provider_id=provider.id,
            title=provider.title,
            ok=False,
            fetched_at=utc_now(),
            error=f"fetch failed ({type(exc).__name__})",
        )


class BackgroundFetcher(QObject):
    """``start()`` returns at once; ``on_result(providers, snapshots)`` is later
    called on the thread that created this object (the UI thread)."""

    _done = Signal(object, object)

    def __init__(
        self,
        on_result: Callable[[list[Provider], list[ProviderSnapshot]], None],
    ) -> None:
        super().__init__()
        self._on_result = on_result
        self._busy = False
        self._again = False
        self._settings: Settings | None = None
        # A slot of this QObject, so the signal is queued onto its own thread.
        self._done.connect(self._finish)

    @property
    def busy(self) -> bool:
        return self._busy

    def start(self, settings: Settings) -> None:
        self._settings = settings
        if self._busy:
            # Something asked for fresh data while a fetch is in flight —
            # run once more when it ends rather than ignoring the request.
            self._again = True
            return
        self._busy = True
        threading.Thread(target=self._work, args=(settings,), daemon=True).start()

    def _work(self, settings: Settings) -> None:
        try:
            providers = discover_providers(settings)
            snapshots = [_safe_fetch(p) for p in providers]
        except Exception:  # noqa: BLE001
            self._done.emit(None, None)
            return
        self._done.emit(providers, snapshots)

    @Slot(object, object)
    def _finish(self, providers, snapshots) -> None:
        self._busy = False
        if providers is not None:
            self._on_result(providers, snapshots)
        if self._again and self._settings is not None:
            self._again = False
            self.start(self._settings)
