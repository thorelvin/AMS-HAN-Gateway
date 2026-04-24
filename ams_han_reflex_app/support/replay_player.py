"""Replay helpers that normalize captured log lines and step through them like a live stream."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

VALID_PREFIXES = ("RSP:", "FRAME,", "SNAP,", "STATUS,")


def normalize_replay_line(line: str) -> str | None:
    raw = line.strip()
    if not raw:
        return None
    if " RX: " in raw:
        raw = raw.split(" RX: ", 1)[1].strip()
    elif raw.startswith("RX: "):
        raw = raw[4:].strip()
    elif raw.startswith("MOTTATT: "):
        raw = raw[8:].strip()
    for prefix in VALID_PREFIXES:
        if raw.startswith(prefix):
            return raw
    return None


@dataclass(slots=True)
class ReplaySummary:
    loaded: bool
    active: bool
    paused: bool
    demo: bool
    source_name: str
    position: int
    total: int

    @property
    def progress_text(self) -> str:
        if not self.loaded:
            return "No replay loaded"
        pct = 0.0 if self.total <= 0 else (100.0 * self.position / self.total)
        return f"{self.position}/{self.total} lines ({pct:.0f}%)"

    @property
    def status_text(self) -> str:
        if not self.loaded:
            return "Idle"
        if self.active and not self.paused:
            return "Playing"
        if self.paused:
            return "Paused"
        if self.position >= self.total:
            return "Finished"
        return "Loaded"


class ReplayPlayer:
    def __init__(self) -> None:
        self.entries: list[str] = []
        self.source_name = ""
        self.loaded = False
        self.active = False
        self.paused = False
        self.demo = False
        self.position = 0

    def load_lines(self, lines: list[str], source_name: str, demo: bool = False) -> None:
        entries = []
        for line in lines:
            normalized = normalize_replay_line(line)
            if normalized is not None:
                entries.append(normalized)
        self.entries = entries
        self.source_name = source_name
        self.loaded = bool(entries)
        self.active = False
        self.paused = False
        self.demo = demo
        self.position = 0

    def load_file(self, path: str | Path, demo: bool = False) -> None:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        self.load_lines(text.splitlines(), p.name, demo=demo)

    def start(self) -> None:
        if not self.loaded:
            return
        if self.position >= len(self.entries):
            self.position = 0
        self.active = True
        self.paused = False

    def pause(self) -> None:
        if self.loaded:
            self.paused = True
            self.active = False

    def resume(self) -> None:
        if self.loaded and self.position < len(self.entries):
            self.active = True
            self.paused = False

    def stop(self, unload: bool = False) -> None:
        self.active = False
        self.paused = False
        if unload:
            self.entries = []
            self.source_name = ""
            self.loaded = False
            self.position = 0
            self.demo = False

    def advance(self, max_lines: int = 3) -> list[str]:
        if not self.loaded or not self.active or self.paused:
            return []
        start = self.position
        end = min(len(self.entries), self.position + max(1, int(max_lines)))
        self.position = end
        chunk = self.entries[start:end]
        if self.position >= len(self.entries):
            self.active = False
            self.paused = False
        return chunk

    def summary(self) -> ReplaySummary:
        return ReplaySummary(
            loaded=self.loaded,
            active=self.active,
            paused=self.paused,
            demo=self.demo,
            source_name=self.source_name,
            position=self.position,
            total=len(self.entries),
        )
