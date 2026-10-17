#!/usr/bin/env python3
"""One Fresh/Resume installation path with durable depot validation."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
PARENT = Path("/private/tmp")
PREFIX = "Pagonia-GPTK4b3-deployment."
DESTINATION = Path("/Applications/Pioneers of Pagonia.app")


def load(filename: str):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_").replace(".", "_"),
                                                   ROOT / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def state_command(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(ROOT / "pagonia-state.py"), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def depot_validator(stage: Path) -> list[str]:
    transfer = load("pagonia-steam-transfer.py")
    steam = transfer.steam_folder(
        stage / "Steam Downloader.app/Contents/SharedSupport/prefix")
    return [sys.executable, str(ROOT / "pagonia-depot.py"), "validate",
            str(steam), *transfer.DEPOT_OPTIONS]


def validated_state(stage: Path) -> str:
    return state_command("highest", "--parent", str(PARENT), "--path", str(stage),
                         "--evidence-validator", *depot_validator(stage))


def create_stage() -> Path:
    raw = state_command("create", "--parent", str(PARENT), "--prefix", PREFIX)
    stage = Path(raw)
    if stage.parent != PARENT:
        raise ValueError("Unexpected staging deployment location")
    return stage


def pin_steam_setup(stage: Path) -> Path:
    transfer = load("pagonia-steam-transfer.py")
    setup = stage / "SteamSetup.exe"
    if not setup.exists():
        print("  Downloading verified SteamSetup.exe...", flush=True)
        transfer.fetch_setup(setup)
    else:
        if transfer.sha256(setup.read_bytes()).hexdigest() != transfer.STEAM_INSTALLER_HASH:
            raise ValueError("Saved SteamSetup binary hash mismatch")
    return setup


def mark_depot_complete(stage: Path) -> None:
    transfer = load("pagonia-steam-transfer.py")
    steam = transfer.steam_folder(
        stage / "Steam Downloader.app/Contents/SharedSupport/prefix")
    transfer.command("pagonia-depot.py", "validate", steam, *transfer.DEPOT_OPTIONS)
    appmanifest = steam / "steamapps/appmanifest_2155180.acf"
    digest = hashlib.sha256(appmanifest.read_bytes()).hexdigest()
    state_command("checkpoint", "--parent", str(PARENT), "--path", str(stage),
                  "--state", "depot-complete", "--artifact-sha256", digest,
                  "--evidence-validator", *depot_validator(stage))


def downloader(stage: Path, complete: bool) -> Path:
    runtime = load("pagonia-runtime.py")
    download = load("pagonia-download.py")
    transfer = load("pagonia-steam-transfer.py")
    ownership = load("pagonia-ownership.py")
    app = stage / "Steam Downloader.app"
    if app.exists():
        ownership.stop_orphans(stage)
    if complete:
        prefix = app / "Contents/SharedSupport/prefix"
        steam = transfer.steam_folder(prefix)
        print("  Revalidating completed Pagonia depot; no Steam login needed...", flush=True)
        transfer.command("pagonia-depot.py", "validate", steam, *transfer.DEPOT_OPTIONS)
        return prefix

    if not app.exists():
        print("  Creating Wine 11.17 downloader...", flush=True)
        app, prefix, wine = runtime.build_app(stage, "downloader")
        fresh = True
    else:
        print("  Validating and refreshing an incomplete downloader...", flush=True)
        runtime.refresh_downloader(stage)
        prefix = app / "Contents/SharedSupport/prefix"
        wine = app / "Contents/SharedSupport/wine"
        fresh = not transfer.steam_folder(prefix).joinpath("steam.exe").is_file()
    setup = pin_steam_setup(stage) if fresh else None
    download.acquire(app, prefix, wine, fresh=fresh, setup=setup)
    mark_depot_complete(stage)
    return prefix


def acceptance(app: Path) -> None:
    """The final visible-terrain test cannot be replaced by D3D12 log markers."""
    import plistlib
    with (app / "Contents/Info.plist").open("rb") as handle:
        flags = plistlib.load(handle)["Program Flags"]
    if not all(part in flags for part in (
        "-applaunch 2155180", "-NoDX12DeviceFactory", "-NoDX12SDKVersionCheck"
    )):
        raise ValueError("Pagonia launch flags are incomplete")
    log = app / "Contents/SharedSupport/Logs/LastRunWine.log"
    if log.is_symlink():
        raise ValueError("Linked launch log is not trusted")
    log.unlink(missing_ok=True)
    print("  Launching published Pagonia for gameplay acceptance...", flush=True)
    subprocess.run(["/usr/bin/open", "-n", str(app)], check=True, timeout=30)
    print("  If Steam displays a Cloud conflict, resolve it manually.", flush=True)
    started = time.monotonic()
    last_report = started
    while time.monotonic() - started < 180:
        processes = subprocess.run(["/bin/ps", "-U", str(os.getuid()), "-o", "command="],
                                   capture_output=True, text=True, check=True, timeout=10).stdout
        game_commands = [line for line in processes.splitlines()
                         if "Pioneers of Pagonia.exe" in line]
        command_valid = any(all(option in line for option in
                            ("-NoDX12DeviceFactory", "-NoDX12SDKVersionCheck"))
                            for line in game_commands)
        if command_valid and log.is_file():
            text = log.read_text(errors="replace")
            if "Created D3D12Device" in text and "Created D3D12 Swapchain" in text:
                print("  D3D12 device and swapchain confirmed.", flush=True)
                if not sys.stdin.isatty():
                    raise RuntimeError("Visible terrain requires interactive confirmation")
                answer = input("ACTION REQUIRED: Is the game's terrain visibly rendered? [y/N] ")
                if answer.strip().lower() != "y":
                    raise RuntimeError("Visible terrain was not confirmed")
                return
        if time.monotonic() - last_report >= 25:
            print("  Waiting for the expected game command and D3D12 markers...", flush=True)
            last_report = time.monotonic()
        time.sleep(2)
    raise RuntimeError("Game did not satisfy D3D12 initialization acceptance")


def deploy(mode: str, stage: Path | None, gptk: Path) -> None:
    preflight = load("pagonia-preflight.py")
    publication = load("pagonia-publication.py")
    if mode == "fresh":
        preflight.preflight(gptk)
        stage = create_stage()
        print(f"Fresh staging deployment: {stage}", flush=True)
    elif stage is None:
        raise ValueError("Resume requires validated staging")
    else:
        print(f"Resume staging deployment: {stage}", flush=True)
    try:
        complete = validated_state(stage) == "depot-complete"
        if not complete:
            preflight.verify_inputs()
        source = downloader(stage, complete)
        preflight.verify_gptk_files(
            gptk, ROOT / "gptk-4.0b3-SHA256SUMS", ROOT / "gptk-4.0b3-SYMLINKS")
        print("  Constructing Wine 10 gameplay app...", flush=True)
        gameplay = load("pagonia-gameplay.py")
        app = gameplay.build(stage, source, gptk)
        publication.mark_application(app)
        backup = publication.publish(app)
        try:
            acceptance(DESTINATION)
        except BaseException:
            # Do not move a still-running Wineskin game during rollback.
            process = load("pagonia-process.py")
            published_prefix = DESTINATION / "Contents/SharedSupport/prefix"
            published_wine = DESTINATION / "Contents/SharedSupport/wine"
            try:
                process.stop_prefix(published_prefix, published_wine,
                                    DESTINATION / "Contents/SharedSupport/Logs/RollbackShutdown.log")
            except BaseException as stop_error:
                raise RuntimeError(
                    "Published Wine processes did not stop; leaving backup and deployment "
                    "unchanged rather than moving a live application"
                ) from stop_error
            publication.rollback(DESTINATION, backup)
            raise
        print(f"Deployment accepted: {DESTINATION}", flush=True)
    except BaseException:
        print(f"Preserved Resume staging deployment: {stage}", file=sys.stderr)
        raise
    # Only private, installer-owned staging artifacts remain here.
    if stage.is_dir() and not stage.is_symlink() and stage.parent == PARENT:
        shutil.rmtree(stage)
