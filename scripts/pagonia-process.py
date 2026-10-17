#!/usr/bin/env python3
"""Bounded Wine child lifecycle and prefix isolation. No shell invocation."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time


class ProcessError(RuntimeError):
    pass


def run_bounded(argv: list[str], log: Path, timeout: float = 120, grace: float = 5,
                env: dict[str, str] | None = None) -> int:
    if not argv or timeout <= 0 or grace <= 0:
        raise ValueError("Invalid bounded command")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as output:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=output,
                                 stderr=subprocess.STDOUT, env=env,
                                 start_new_session=True)
        try:
            return child.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            raise ProcessError(f"Bounded command stopped: {argv[0]}")


def wine_environment(prefix: Path, wine: Path, downloader: bool) -> dict[str, str]:
    env = dict(os.environ)
    env.update(WINEPREFIX=str(prefix), WINEDEBUG="fixme-all", WINEESYNC="0",
               WINEMSYNC="0", WINEFSYNC="0", LANG="en_US.UTF-8",
               LC_ALL="en_US.UTF-8", LC_NUMERIC="C", LC_TIME="C")
    if downloader:
        env.update(CEF_DISABLE_SANDBOX="1", STEAM_DISABLE_CEF_SANDBOX="1",
                   STEAM_RUNTIME="0", WINEDLLOVERRIDES="dxgi,d3d10core,d3d11=n,b",
                   WINHTTP_CONNECT_TIMEOUT="90000", WINHTTP_RECEIVE_TIMEOUT="180000")
        framework = wine.parent.parent / "Frameworks"
        env["DYLD_FALLBACK_LIBRARY_PATH"] = f"{framework}:{wine / 'lib'}"
    return env


def wine_command(prefix: Path, wine: Path, program: str, *args: str,
                 downloader: bool = False) -> tuple[list[str], dict[str, str]]:
    if not prefix.is_dir() or not wine.is_dir():
        raise ProcessError("Wine prefix or runtime missing")
    executable = wine / "bin/wine64"
    if not executable.exists():
        raise ProcessError(f"Missing Wine binary: {executable}")
    return ([str(executable), program, *args],
            wine_environment(prefix, wine, downloader))


def stop_prefix(prefix: Path, wine: Path, log: Path) -> None:
    command = wine / "bin/wineserver"
    if not command.exists():
        raise ProcessError(f"Missing wineserver: {command}")
    env = wine_environment(prefix, wine, False)
    run_bounded([str(command), "-k"], log, timeout=15, grace=3, env=env)
    result = run_bounded([str(command), "-w"], log, timeout=30, grace=3, env=env)
    if result:
        raise ProcessError("Wine server failed to stop cleanly")


def start_wine(prefix: Path, wine: Path, program: str, args: list[str], log: Path,
               downloader: bool) -> subprocess.Popen:
    argv, env = wine_command(prefix, wine, program, *args, downloader=downloader)
    log.parent.mkdir(parents=True, exist_ok=True)
    stream = log.open("ab")
    try:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stream,
                                 stderr=subprocess.STDOUT, env=env,
                                 start_new_session=True)
    finally:
        stream.close()
    return child


def terminate_child(child: subprocess.Popen, grace: float = 5) -> None:
    if child.poll() is not None:
        return
    os.killpg(child.pid, signal.SIGTERM)
    try:
        child.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait()
