#!/usr/bin/env python3
"""Run one command with bounded TERM/KILL shutdown and append-only logging."""

from pathlib import Path
import os
import signal
import subprocess
import sys


def main() -> int:
    if len(sys.argv) < 5:
        print(
            f"Usage: {Path(sys.argv[0]).name} TIMEOUT TERM_GRACE LOG COMMAND [ARG ...]",
            file=sys.stderr,
        )
        return 2
    timeout = float(sys.argv[1])
    term_grace = float(sys.argv[2])
    log_path = Path(sys.argv[3])
    command = sys.argv[4:]
    if timeout <= 0 or term_grace <= 0:
        print("Timeouts must be positive", file=sys.stderr)
        return 2
    log_path.parent.mkdir(parents=True, exist_ok=True)
    child = None

    def stop_child() -> None:
        if child is None or child.poll() is not None:
            return
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=term_grace)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()

    def forward(signum: int, _frame: object) -> None:
        stop_child()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGINT, forward)
    signal.signal(signal.SIGTERM, forward)
    with log_path.open("ab") as log:
        child = subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            return child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_child()
            return 124


if __name__ == "__main__":
    raise SystemExit(main())
