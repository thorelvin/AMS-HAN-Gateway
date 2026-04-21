from __future__ import annotations

from pathlib import Path

from ..support.replay_player import ReplayPlayer, ReplaySummary


class ReplayService:
    def __init__(self, player: ReplayPlayer | None = None) -> None:
        self.player = player or ReplayPlayer()

    def load_file(self, path: str | Path, *, demo: bool = False) -> None:
        self.player.load_file(path, demo=demo)

    def load_lines(self, lines: list[str], source_name: str, *, demo: bool = False) -> None:
        self.player.load_lines(lines, source_name, demo=demo)

    def start(self) -> None:
        self.player.start()

    def pause(self) -> None:
        self.player.pause()

    def resume(self) -> None:
        self.player.resume()

    def stop(self, *, unload: bool = False) -> None:
        self.player.stop(unload=unload)

    def advance(self, max_lines: int = 3) -> list[str]:
        return self.player.advance(max_lines)

    def summary(self) -> ReplaySummary:
        return self.player.summary()
