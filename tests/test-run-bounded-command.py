#!/usr/bin/env python3
"""Regression tests for bounded child-process execution."""

from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/run-bounded-command.py"


def run(timeout: str, grace: str, log: Path, *command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HELPER), timeout, grace, str(log), *command], check=False
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        log = Path(directory) / "command.log"
        result = run("2", "0.2", log, "/bin/sh", "-c", "printf success")
        assert result.returncode == 0
        assert log.read_text() == "success"

        result = run("2", "0.2", log, "/bin/sh", "-c", "exit 7")
        assert result.returncode == 7

        started = time.monotonic()
        result = run(
            "0.2",
            "0.2",
            log,
            "/bin/sh",
            "-c",
            "trap '' TERM; while :; do sleep 1; done",
        )
        elapsed = time.monotonic() - started
        assert result.returncode == 124
        assert elapsed < 3


if __name__ == "__main__":
    main()
