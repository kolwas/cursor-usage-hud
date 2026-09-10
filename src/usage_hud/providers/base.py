"""Provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from usage_hud.models import ProviderSnapshot


class Provider(ABC):
    id: str
    title: str

    @abstractmethod
    def fetch(self) -> ProviderSnapshot:
        raise NotImplementedError
