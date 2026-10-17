#!/usr/bin/env python3
"""Fail-closed ownership checks for installer-associated Wine processes."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time

from pagonia_common import targeted_process


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
    return targeted_process(command)


def owned_for_staging(staging: Path) -> dict[int, str]:
    """Every targeted process must explicitly identify the selected staging."""
    root = str(staging)
    owned: dict[int, str] = {}
    for pid, command in process_table():
        if not targeted(command):
            continue
        if root in command:
            owned[pid] = command
        else:
            raise AmbiguousOwnership(
                "Wine/Steam process ownership is ambiguous; exit unrelated Wine programs"
            )
    return owned


def active_for_staging(staging: Path) -> list[int]:
    return list(owned_for_staging(staging))


def stop_orphans(staging: Path, grace: int = 10) -> None:
    signalled: dict[int, str] = {}
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        current = owned_for_staging(staging)
        if not current:
            return
        for pid, command in current.items():
            previous = signalled.get(pid)
            if previous is not None and previous != command:
                raise AmbiguousOwnership("Managed process identity changed before shutdown")
            if previous is None:
                os.kill(pid, signal.SIGTERM)
                signalled[pid] = command
        time.sleep(0.2)

    current = owned_for_staging(staging)
    for pid, command in current.items():
        if signalled.get(pid) != command:
            raise AmbiguousOwnership("Managed process identity changed before forced shutdown")
        os.kill(pid, signal.SIGKILL)
    time.sleep(0.2)
    if owned_for_staging(staging):
        raise AmbiguousOwnership("Managed Wine/Steam processes did not exit")
