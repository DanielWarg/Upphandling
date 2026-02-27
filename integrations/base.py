"""Base interface for external integrations."""

from abc import ABC, abstractmethod


class BaseIntegration(ABC):
    name: str = "base"
    description: str = ""
    enabled: bool = False

    @abstractmethod
    def push_procurement(self, procurement: dict) -> bool:
        """Push a procurement to the external service. Returns True on success."""
        ...

    @abstractmethod
    def sync_status(self) -> dict:
        """Check integration status. Returns dict with 'connected', 'message'."""
        ...

    def configure(self, config: dict):
        """Apply configuration from .env or UI."""
        pass
