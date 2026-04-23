"""Tiny persistence service for dashboard settings stored outside the UI state layer."""

from __future__ import annotations

from pathlib import Path

from ..backend.models import GatewaySettings
from ..support.settings_store import SettingsStore


class SettingsService:
    def __init__(self, store: SettingsStore) -> None:
        self.store = store
        self.settings = GatewaySettings.from_dict(store.load())

    @property
    def directory(self) -> Path:
        return self.store.directory

    def save(self) -> None:
        self.store.save(self.settings.as_dict())
