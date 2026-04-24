from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    python = sys.executable

    # Keep one local quality command for contributors: lint, formatting check, then tests.
    run([python, "-m", "ruff", "check", "ams_han_reflex_app", "tests", "scripts"], repo_root)
    run([python, "-m", "black", "--check", "ams_han_reflex_app", "tests", "scripts"], repo_root)
    run([python, "-m", "unittest"], repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
