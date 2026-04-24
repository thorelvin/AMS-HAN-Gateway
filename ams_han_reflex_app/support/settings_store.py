"""JSON-backed settings persistence used by the dashboard services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SettingsStore:
    def __init__(self, path: Path, defaults: dict[str, Any]) -> None:
        self.path = Path(path)
        self.defaults = dict(defaults)

    @property
    def directory(self) -> Path:
        return self.path.parent

    def load(self) -> dict[str, Any]:
        data = dict(self.defaults)
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception:
            pass
        return data

    def save(self, settings: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        merged = dict(self.defaults)
        merged.update(settings)
        self.path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
