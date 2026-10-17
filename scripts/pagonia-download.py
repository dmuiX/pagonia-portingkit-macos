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
    child = proc.start_wine(prefix, wine, str(destination), ["/S"], log,
                            downloader=True)
    print("  Waiting for SteamSetup.exe to finish...", flush=True)
    deadline = time.monotonic() + 300
    last_status = time.monotonic()
    try:
        while time.monotonic() < deadline:
            active = subprocess.run(["/usr/bin/pgrep", "-u", str(__import__("os").getuid()),
                                     "-f", r"SteamSetup\.exe"],
                                    capture_output=True)
            if ((steam / "steam.exe").is_file()
                    and (steam / "uninstall.exe").is_file()
                    and active.returncode == 1):
                break
            if child.poll() is not None and child.returncode not in (None, 0):
                raise RuntimeError("SteamSetup exited unsuccessfully")
            if time.monotonic() - last_status >= 25:
                print("  Still waiting for SteamSetup completion...", flush=True)
                last_status = time.monotonic()
            time.sleep(2)
        else:
            raise TimeoutError("SteamSetup did not finish within five minutes")
    finally:
        proc.stop_prefix_and_child(
            prefix, wine, log, child, downloader=True
        )
    destination.unlink()
    service = prefix / "drive_c/Program Files (x86)/Common Files/Steam/steamservice.exe"
    if not service.is_file():
        raise RuntimeError("Steam Client Service is missing")
    argv, env = proc.wine_command(prefix, wine, str(service), "/Install", downloader=True)
    if proc.run_bounded(argv, log, timeout=60, env=env):
        raise RuntimeError("Steam Client Service failed")
    proc.stop_prefix(prefix, wine, log, downloader=True)


def prepare_wine(prefix: Path, wine: Path, downloader: bool, log: Path) -> None:
    proc = load("pagonia-process.py")
    argv, env = proc.wine_command(prefix, wine, "wineboot", "-u", downloader=downloader)
    print("  Initializing isolated Wine prefix...", flush=True)
    if proc.run_bounded(argv, log, timeout=180, env=env):
        raise RuntimeError("Wine prefix initialization failed")
    proc.stop_prefix(prefix, wine, log, downloader=downloader)


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
                    session.transferable_steam_id(steam)
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
            print(
                "  Pagonia depot metadata ready; final validation follows after Steam shutdown...",
                flush=True,
            )
            return
        if time.monotonic() - last >= 25:
            print("  Waiting for approved Pagonia build 25784167...", flush=True)
            last = time.monotonic()
        time.sleep(2)
    raise TimeoutError("Pagonia depot download did not complete")


def clear_cef_cache(prefix: Path) -> None:
    """Remove only recognized user-owned CEF cache directories between retries."""
    import os
    import stat
    import shutil
    users = prefix / "drive_c/users"
    if not users.is_dir() or users.is_symlink():
        raise RuntimeError("Unsafe Steam CEF user-profile root")
    for profile in users.iterdir():
        cache = profile / "AppData/Local/Steam/htmlcache"
        if not cache.exists() and not cache.is_symlink():
            continue
        current = users
        for component in cache.relative_to(users).parts:
            current = current / component
            if current.is_symlink():
                raise RuntimeError("Linked Steam CEF cache path")
        info = cache.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError("Untrusted Steam CEF cache directory")
        shutil.rmtree(cache)


def start_visible_steam(app: Path, prefix: Path, wine: Path, steam: Path,
                        logs: Path):
    process = load("pagonia-process.py")
    window = load("pagonia-window.py")
    for attempt in (1, 2):
        for name in ("steamui_login.txt", "steamui_html.txt"):
            (steam / "logs" / name).unlink(missing_ok=True)
        print(f"  Starting Steam UI (retry {attempt - 1}/1)...", flush=True)
        child = process.start_wine(prefix, wine, str(steam / "steam.exe"),
                                   ["-no-cef-sandbox", "-vgui"],
                                   logs / "SteamUI.log", downloader=True)
        try:
            window.wait_for_window(steam)
            return child
        except (RuntimeError, TimeoutError, subprocess.TimeoutExpired):
            process.stop_prefix_and_child(
                prefix, wine, logs / "SteamUIShutdown.log", child,
                downloader=True,
            )
            if attempt == 2:
                raise
            print("  Rechecking Steam CEF after a controlled restart...", flush=True)
            clear_cef_cache(prefix)
        except BaseException:
            process.stop_prefix_and_child(
                prefix, wine, logs / "SteamUIShutdown.log", child,
                downloader=True,
            )
            raise
    raise RuntimeError("Steam UI is not visibly rendered")


def acquire(app: Path, prefix: Path, wine: Path, *, fresh: bool,
            setup: Path | None = None) -> None:
    proc = load("pagonia-process.py")
    graphics = load("pagonia-graphics.py")
    window = load("pagonia-window.py")
    logs = app / "Contents/SharedSupport/Logs"
    logs.mkdir(parents=True, exist_ok=True)
    steam = prefix / "drive_c/Program Files (x86)/Steam"
    service = prefix / "drive_c/Program Files (x86)/Common Files/Steam/steamservice.exe"
    needs_setup = (
        fresh
        or not (steam / "steam.exe").is_file()
        or not service.is_file()
        or service.is_symlink()
    )
    if needs_setup:
        if setup is None:
            raise ValueError("Incomplete Steam installation requires verified SteamSetup")
        prepare_wine(prefix, wine, True, logs / "wineboot.log")
        install_steam(app, prefix, wine, setup)
    elif not fresh:
        argv, env = proc.wine_command(prefix, wine, str(service), "/Install", downloader=True)
        print("  Repairing the resumed Steam Client Service...", flush=True)
        if proc.run_bounded(argv, logs / "SteamServiceResume.log", timeout=60, env=env):
            raise RuntimeError("Steam Client Service repair failed")
        proc.stop_prefix(
            prefix, wine, logs / "Shutdown.log", downloader=True
        )
    graphics.configure_downloader(prefix, wine)
    (steam / "logs").mkdir(parents=True, exist_ok=True)
    child = start_visible_steam(app, prefix, wine, steam, logs)
    try:
        wait_for_login(steam)
        print("  Steam sign-in completed.", flush=True)
        install_request(prefix, wine, steam, logs / "SteamInstallRequest.log")
        wait_for_depot(steam)
    finally:
        print("  Stopping the downloader before any cross-runtime transfer...", flush=True)
        proc.stop_prefix_and_child(
            prefix, wine, logs / "Shutdown.log", child, downloader=True
        )
