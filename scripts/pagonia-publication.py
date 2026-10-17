#!/usr/bin/env python3
"""Publish a validated Pagonia app with no-replace rename and rollback."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import plistlib
import secrets
import stat

DESTINATION = Path("/Applications/Pioneers of Pagonia.app")
IDENTITY = {"format": 1, "kind": "managed-installation",
            "owner": "pagonia-gptk4b3-installer", "product": "pioneers-of-pagonia"}
BUNDLE_ID = "com.soad1337.pioneersofpagonia.gptk4b3"


def check_application(app: Path) -> None:
    if app.is_symlink() or not app.is_dir():
        raise ValueError("Gameplay application is not a directory")
    with (app / "Contents/Info.plist").open("rb") as stream:
        plist = plistlib.load(stream)
    if plist.get("CFBundleIdentifier") != BUNDLE_ID:
        raise ValueError("Gameplay application identity mismatch")
    prefix = app / "Contents/SharedSupport/prefix"
    steam = prefix / "drive_c/Program Files (x86)/Steam"
    required = [
        app / "Contents/MacOS/wineskinlauncher",
        app / "Contents/SharedSupport/wine/bin/wine64",
        steam / "steam.exe",
        steam / "steamapps/appmanifest_2155180.acf",
        steam / "steamapps/common/Pioneers of Pagonia/Pioneers of Pagonia.exe",
    ]
    for file in required:
        if file.is_symlink() or not file.is_file():
            raise ValueError(f"Missing or linked application input: {file}")


def mark_application(app: Path) -> None:
    check_application(app)
    marker = app / "Contents/SharedSupport/pagonia-managed-state.json"
    with marker.open("x", encoding="utf-8") as output:
        os.chmod(marker, 0o600)
        json.dump(IDENTITY, output, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
        raise ValueError(f"Unsafe application path: {path}")
    return info.st_dev, info.st_ino


def rename_no_replace(source: Path, destination: Path) -> None:
    """Use macOS renameatx_np(RENAME_EXCL) to prevent destination clobber."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    source_parent_fd = os.open(source.parent, flags)
    destination_parent_fd = os.open(destination.parent, flags)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        rename = libc.renameatx_np
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(source_parent_fd, os.fsencode(source.name),
                  destination_parent_fd, os.fsencode(destination.name), 4) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(destination))
    finally:
        os.close(source_parent_fd)
        os.close(destination_parent_fd)


def publish(app: Path, destination: Path = DESTINATION) -> Path | None:
    check_application(app)
    marker = app / "Contents/SharedSupport/pagonia-managed-state.json"
    if not marker.is_file():
        raise ValueError("Unmarked gameplay application is not publishable")
    if destination != DESTINATION:
        raise ValueError("Only the fixed /Applications destination is permitted")
    if app.stat().st_dev != destination.parent.stat().st_dev:
        raise ValueError("Staging and destination must share a filesystem")
    parent = destination.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("Destination parent changed")
    existing = os.path.lexists(destination)
    if existing:
        from importlib.util import module_from_spec, spec_from_file_location
        source = Path(__file__).with_name("pagonia-managed-state.py")
        spec = spec_from_file_location("pagonia_managed", source)
        module = module_from_spec(spec)
        import sys
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        if not module._verified_installation(destination):
            raise ValueError("Refusing to replace an unmanaged installation")
        original = identity(destination)
    else:
        original = None
    backup = None
    if existing:
        backup = parent / (destination.name + ".backup-" + secrets.token_hex(12))
        if identity(destination) != original:
            raise ValueError("Existing installation changed before backup")
        rename_no_replace(destination, backup)
    try:
        rename_no_replace(app, destination)
    except BaseException:
        if backup is not None and not os.path.lexists(destination):
            rename_no_replace(backup, destination)
        raise
    return backup


def rollback(destination: Path, backup: Path | None) -> None:
    """Quarantine a failed new deployment; restore old installation if present."""
    if os.path.lexists(destination):
        quarantined = destination.parent / (destination.name + ".failed-" + secrets.token_hex(12))
        rename_no_replace(destination, quarantined)
    if backup is not None:
        rename_no_replace(backup, destination)
