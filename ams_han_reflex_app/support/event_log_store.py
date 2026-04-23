"""Small JSON-backed store for keeping the event timeline persistent between runs."""

from __future__ import annotations

import json
import time
from pathlib import Path

class EventLogStore:
    def __init__(self, path: Path, max_items: int = 1200, flush_interval_s: float = 5.0, flush_every_n: int = 5) -> None:
        self.path = Path(path)
        self.max_items = max_items
        self.flush_interval_s = flush_interval_s
        self.flush_every_n = flush_every_n
        self._dirty = 0
        self._last_flush = 0.0

    def load(self) -> list[dict[str, str]]:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if isinstance(data, list):
                    return [dict(x) for x in data[-self.max_items:] if isinstance(x, dict)]
        except Exception:
            pass
        return []

    def mark_dirty(self) -> None:
        self._dirty += 1

    def flush_if_needed(self, rows: list[dict[str, str]]) -> bool:
        now = time.time()
        if self._dirty <= 0:
            return False
        if self._dirty < self.flush_every_n and (now - self._last_flush) < self.flush_interval_s:
            return False
        self.flush(rows)
        return True

    def flush(self, rows: list[dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows[-self.max_items:], indent=2), encoding='utf-8')
        self._dirty = 0
        self._last_flush = time.time()
