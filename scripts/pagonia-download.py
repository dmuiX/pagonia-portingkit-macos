#!/usr/bin/env python3
"""Wine 11 Steam authentication and approved Pagonia depot acquisition."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def load(filename: str):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_").replace(".", "_"),
                                                   ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def install_steam(app: Path, prefix: Path, wine: Path, setup: Path) -> None:
    proc = load("pagonia-process.py")
    steam = prefix / "drive_c/Program Files (x86)/Steam"
    destination = prefix / "drive_c/SteamSetup.exe"
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    shutil.copy2(setup, destination)
    log = app / "Contents/SharedSupport/Logs/SteamSetup.log"
    print("  Installing the pinned Steam client in Wine 11.17...", flush=True)
    argv, env = proc.wine_command(prefix, wine, str(destination), "/S", downloader=True)
    status = proc.run_bounded(argv, log, timeout=300, env=env)
    if status or not (steam / "steam.exe").is_file():
        raise RuntimeError("SteamSetup did not install Steam")
    destination.unlink()
    proc.stop_prefix(prefix, wine, log)
    service = prefix / "drive_c/Program Files (x86)/Common Files/Steam/steamservice.exe"
    if not service.is_file():
        raise RuntimeError("Steam Client Service is missing")
    argv, env = proc.wine_command(prefix, wine, str(service), "/Install", downloader=True)
    if proc.run_bounded(argv, log, timeout=60, env=env):
        raise RuntimeError("Steam Client Service failed")
    proc.stop_prefix(prefix, wine, log)


def prepare_wine(prefix: Path, wine: Path, downloader: bool, log: Path) -> None:
    proc = load("pagonia-process.py")
    argv, env = proc.wine_command(prefix, wine, "wineboot", "-u", downloader=downloader)
    print("  Initializing isolated Wine prefix...", flush=True)
    if proc.run_bounded(argv, log, timeout=180, env=env):
        raise RuntimeError("Wine prefix initialization failed")
    proc.stop_prefix(prefix, wine, log)


def wait_for_login(steam: Path, timeout: int = 1800) -> None:
    session = load("pagonia-steam-session.py")
    loginusers = steam / "config/loginusers.vdf"
    login_log = steam / "logs/steamui_login.txt"
    print("ACTION REQUIRED: Sign in to Steam and complete Steam Guard or QR confirmation.",
          flush=True)
    deadline = time.monotonic() + timeout
    last = time.monotonic()
    while time.monotonic() < deadline:
        if loginusers.is_file() and not loginusers.is_symlink() and login_log.is_file():
            text = login_log.read_text(errors="replace")
            if "Received logon success response" in text and "SetLoginState: Success - OK" in text:
                try:
                    session.authenticated_steam_id(loginusers)
                    return
                except (OSError, ValueError):
                    pass
        if time.monotonic() - last >= 25:
            print("  Waiting for persisted Steam authentication...", flush=True)
            last = time.monotonic()
        time.sleep(2)
    raise TimeoutError("Steam login did not complete within 30 minutes")


def install_request(prefix: Path, wine: Path, steam: Path, log: Path) -> None:
    proc = load("pagonia-process.py")
    argv, env = proc.wine_command(prefix, wine, str(steam / "steam.exe"),
                                  "steam://install/2155180", downloader=True)
    print("  Opening Pagonia install dialog...", flush=True)
    if proc.run_bounded(argv, log, timeout=30, env=env):
        raise RuntimeError("Steam URI installation request failed")
    print("ACTION REQUIRED: Confirm the preselected Steam installation dialog if requested.",
          flush=True)


def wait_for_depot(steam: Path, timeout: int = 21600) -> None:
    transfer = load("pagonia-steam-transfer.py")
    deadline = time.monotonic() + timeout
    last = time.monotonic()
    while time.monotonic() < deadline:
        status = subprocess.run(
            [sys.executable, str(ROOT / "pagonia-depot.py"), "status",
             str(steam), *transfer.DEPOT_OPTIONS],
            capture_output=True, timeout=25,
        )
        if status.returncode == 0:
            print("  Pagonia depot metadata ready; validating all 856 files...", flush=True)
            transfer.command("pagonia-depot.py", "validate", steam, *transfer.DEPOT_OPTIONS)
            return
        if time.monotonic() - last >= 25:
            print("  Waiting for approved Pagonia build 25784167...", flush=True)
            last = time.monotonic()
        time.sleep(2)
    raise TimeoutError("Pagonia depot download did not complete")


def acquire(app: Path, prefix: Path, wine: Path, *, fresh: bool,
            setup: Path | None = None) -> None:
    proc = load("pagonia-process.py")
    graphics = load("pagonia-graphics.py")
    window = load("pagonia-window.py")
    logs = app / "Contents/SharedSupport/Logs"
    logs.mkdir(parents=True, exist_ok=True)
    steam = prefix / "drive_c/Program Files (x86)/Steam"
    if fresh:
        if setup is None:
            raise ValueError("Fresh downloader needs the verified SteamSetup binary")
        prepare_wine(prefix, wine, True, logs / "wineboot.log")
        install_steam(app, prefix, wine, setup)
    elif not (steam / "steam.exe").is_file():
        if setup is None:
            raise ValueError("Incomplete resume requires verified SteamSetup")
        prepare_wine(prefix, wine, True, logs / "wineboot.log")
        install_steam(app, prefix, wine, setup)
    if not fresh and (steam / "steam.exe").is_file():
        service = prefix / "drive_c/Program Files (x86)/Common Files/Steam/steamservice.exe"
        if not service.is_file() or service.is_symlink():
            raise RuntimeError("Resumed Steam Client Service is missing or linked")
        argv, env = proc.wine_command(prefix, wine, str(service), "/Install", downloader=True)
        print("  Repairing the resumed Steam Client Service...", flush=True)
        if proc.run_bounded(argv, logs / "SteamServiceResume.log", timeout=60, env=env):
            raise RuntimeError("Steam Client Service repair failed")
        proc.stop_prefix(prefix, wine, logs / "Shutdown.log")
    graphics.configure_downloader(prefix, wine)
    (steam / "logs").mkdir(parents=True, exist_ok=True)
    # A Resume must not mistake a retained prior login log for a fresh success.
    for name in ("steamui_login.txt", "steamui_html.txt"):
        (steam / "logs" / name).unlink(missing_ok=True)
    child = proc.start_wine(prefix, wine, str(steam / "steam.exe"),
                            ["-no-cef-sandbox", "-vgui"],
                            logs / "SteamUI.log", downloader=True)
    try:
        window.wait_for_window(steam)
        wait_for_login(steam)
        print("  Steam sign-in completed.", flush=True)
        install_request(prefix, wine, steam, logs / "SteamInstallRequest.log")
        wait_for_depot(steam)
    finally:
        print("  Stopping the downloader before any cross-runtime transfer...", flush=True)
        proc.stop_prefix(prefix, wine, logs / "Shutdown.log")
        proc.terminate_child(child)
