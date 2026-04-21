from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    # Keep the launch path simple for local Windows development.
    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], repo_root)
    run([sys.executable, "-m", "reflex", "run"], repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
