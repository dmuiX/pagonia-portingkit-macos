#!/usr/bin/env python3
"""Construct and verify the Wine 10 gameplay prefix without running SteamSetup."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
GAME = "Pioneers of Pagonia"


def load(filename: str):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_").replace(".", "_"),
                                                   ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify_online(prefix: Path, wine: Path, steam: Path, steam_id: str,
                  timeout: int = 180) -> None:
    process = load("pagonia-process.py")
    log = prefix / "steam-session-verification.log"
    connection = steam / "logs/connection_log.txt"
    connection.unlink(missing_ok=True)
    account_id = str(int(steam_id) - 76561197960265728)
    print("  Verifying transferred Steam session online under Wine 10...", flush=True)
    # This workaround is scoped to current Steam under historical Wine 10.
    # Wine 11 downloader rendering remains GPU-enabled and never receives it.
    child = process.start_wine(prefix, wine, str(steam / "steam.exe"),
                               ["-cef-disable-gpu", "-no-cef-sandbox", "-silent"],
                               log, downloader=False)
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = subprocess.run(
                [sys.executable, str(ROOT / "check-steam-login-log.py"),
                 str(connection), account_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if status.returncode == 0:
                print("  Wine 10 accepted the transferred Steam account.", flush=True)
                return
            time.sleep(2)
        raise RuntimeError("Wine 10 did not prove online session authentication")
    finally:
        process.stop_prefix_and_child(
            prefix, wine, prefix / "WineShutdown.log", child
        )


def verify_gameplay(app: Path, prefix: Path, wine: Path, gptk: Path) -> None:
    graphics = load("pagonia-graphics.py")
    required = {
        wine / "bin/wine64": "08bbcc27b5a76e4473e8003007e140f74b529d67a164256d86d5163d88518300",
        wine / "bin/wineserver": "dcfd293ca9d7dc29bb9fb1a413850319c85c9823368a8f1a76bb22339b64cd45",
        wine / "lib/wine/x86_64-unix/ntdll.so": "cf836b0727c47f4d9fb667628de226395697a6a5089678acea09ae32a7fb279e",
        wine / "lib/wine/x86_64-windows/ntdll.dll": "5549f99494e8e004cd112e72f0d721f6ffbb1bab1487871bff9f7d80c0b6a5da",
        app / "Contents/MacOS/wineskinlauncher": "217d7f3cf154d7117103934c9ec9b952b7209412132f2ad61565fb24d6e56697",
        prefix / "drive_c/windows/system32/dxgi.dll": "d53d9ea91935f0de126ba528264fc4c9b4dfea8bfe43f3f1256bd3e8963d67ee",
        prefix / "drive_c/windows/system32/d3d12.dll": "3174fac027d3ff10971645ac41b665cd53949c87d6d2d7d53b0073bf4bb36981",
        prefix / "drive_c/windows/system32/d3d12core.dll": "b8cabb79a3f0a14babcbfd575cca70814e4d1d3e71606dfc1670421aaa39b97e",
        prefix / f"drive_c/Program Files (x86)/Steam/steamapps/common/{GAME}/dxil.dll":
            "9cccc7ef419da73fa314fdaecae831c6c20206ae70732c9093f95193378ced10",
    }
    for file, digest in required.items():
        if file.is_symlink():
            # Pinned Wine archives may contain internal executable symlinks.
            resolved = file.resolve(strict=True)
            if wine.resolve(strict=True) not in resolved.parents or wine not in file.parents:
                raise ValueError(f"External or untrusted critical file symlink: {file}")
        graphics.verify_digest(file, digest)
    game = prefix / f"drive_c/Program Files (x86)/Steam/steamapps/common/{GAME}"
    if (game / "D3D12Core.dll").exists():
        raise ValueError("Unexpected obsolete game-local D3D12Core patch")
    with (app / "Contents/Info.plist").open("rb") as input_file:
        info = plistlib.load(input_file)
    flags = info["Program Flags"]
    for arg in ("-applaunch 2155180", "-NoDX12DeviceFactory",
                "-NoDX12SDKVersionCheck"):
        if arg not in flags:
            raise ValueError(f"Missing required Steam launch flag: {arg}")
    if info.get("D3DMETAL") != 1 or info.get("D3DMETAL_FORCE") != 1:
        raise ValueError("D3DMetal wrapper setup invalid")


def build(staging: Path, downloader_prefix: Path, gptk: Path):
    runtime = load("pagonia-runtime.py")
    process = load("pagonia-process.py")
    graphics = load("pagonia-graphics.py")
    transfer = load("pagonia-steam-transfer.py")
    config = load("pagonia-steam-config.py")
    downloader_steam = transfer.steam_folder(downloader_prefix)
    app, prefix, wine = runtime.build_app(staging, "gameplay")
    log = app / "Contents/SharedSupport/Logs/WineBoot.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    argv, env = process.wine_command(prefix, wine, "wineboot", "-u", downloader=False)
    print("  Initializing isolated Wine 10 gameplay prefix...", flush=True)
    if process.run_bounded(argv, log, timeout=180, env=env):
        raise RuntimeError("Wine 10 wineboot failed")
    process.stop_prefix(prefix, wine, log)

    # Both snapshots are created from the stopped and validated downloader.
    print("  Creating disjoint clean-client and authenticated-session snapshots...", flush=True)
    session, client = transfer.session_and_client(downloader_prefix, staging)
    try:
        print("  Installing Steam client, session, and validated depot into Wine 10...", flush=True)
        steam_id = transfer.transfer(downloader_prefix, prefix, session, client)
    finally:
        if client.exists():
            shutil.rmtree(client)
        if session.exists():
            shutil.rmtree(session)

    steam = transfer.steam_folder(prefix)
    config.launch_options(steam, steam_id)
    print("  Verifying every GPTK file before installing D3DMetal...", flush=True)
    preflight = load("pagonia-preflight.py")
    preflight.verify_gptk_files(gptk, ROOT / "gptk-4.0b3-SHA256SUMS",
                                ROOT / "gptk-4.0b3-SYMLINKS")
    graphics.configure_gameplay(prefix, wine, gptk)
    verify_online(prefix, wine, steam, steam_id)
    transfer.command("pagonia-depot.py", "validate", steam, *transfer.DEPOT_OPTIONS)

    plist = app / "Contents/Info.plist"
    with plist.open("rb") as input_file:
        info = plistlib.load(input_file)
    # Keep Wine 10's Steam CEF workaround separate from Wine 11's GPU path.
    info["Program Flags"] = (
        "-cef-disable-gpu -no-cef-sandbox -applaunch 2155180 "
        "-NoDX12DeviceFactory -NoDX12SDKVersionCheck"
    )
    resources = app / "Contents/Resources"
    shutil.copy2(resources / "Wineskin.icns", resources / "Pagonia.icns")
    info["CFBundleIconFile"] = "Pagonia.icns"
    with plist.open("wb") as output:
        plistlib.dump(info, output)
    verify_gameplay(app, prefix, wine, gptk)
    return app
