#!/usr/bin/env python3
"""Fail-closed ownership checks for installer-associated Wine processes."""

from __future__ import annotations

import os
from pathlib import Path
import re
import signal
import subprocess
import time


class AmbiguousOwnership(RuntimeError):
    pass


def process_table() -> list[tuple[int, str]]:
    output = subprocess.run(["/bin/ps", "-axo", "uid=,pid=,command="],
                            capture_output=True, text=True, check=True, timeout=15)
    rows = []
    for line in output.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) == 3 and parts[0] == str(os.getuid()):
            rows.append((int(parts[1]), parts[2]))
    return rows


def targeted(command: str) -> bool:
    return bool(re.search(r"(?:^|[/\s])(?:wine(?:64)?(?:-preloader)?|wineserver|"
                          r"steam(?:webhelper|service)?\.exe|"
                          r"Pioneers of Pagonia\.exe)(?:\s|$)",
                          command, flags=re.IGNORECASE))


def active_for_staging(staging: Path) -> list[int]:
    """Every targeted process must explicitly identify the selected staging."""
    root = str(staging)
    owned = []
    for pid, command in process_table():
        if not targeted(command):
            continue
        if root in command:
            owned.append(pid)
        else:
            raise AmbiguousOwnership(
                "Wine/Steam process ownership is ambiguous; exit unrelated Wine programs"
            )
    return owned


def stop_orphans(staging: Path, grace: int = 10) -> None:
    pids = active_for_staging(staging)
    for pid in pids:
        os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        alive = {pid for pid, _ in process_table() if pid in pids}
        if not alive:
            return
        time.sleep(0.2)
    for pid in pids:
        if any(row_pid == pid for row_pid, _ in process_table()):
            os.kill(pid, signal.SIGKILL)
    if any(pid in pids for pid, _ in process_table()):
        raise AmbiguousOwnership("Managed Wine/Steam processes did not exit")
