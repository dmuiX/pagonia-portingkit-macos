#!/usr/bin/env python3
"""Verified, immutable input preflight for the split-runtime Pagonia installer."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess

ROOT = Path(__file__).resolve().parent
PINS = {
    "WS12WineSikarugir10.0_2-20251028-pagonia.tar.xz": "0598a60af56d67b1efd35ac0751cbcc34a30a0329e2788e182dd67a5698f9353",
    "WineCX-11.17-SteamDownloader-4.7.3.tar.xz": "064de70024679010b65b3619c0de9f2993b432dc511bb018a55fc3b31aefece9",
    "Wineskin-3.0.6-2.app.tar.xz": "dc97a4ff0f75b74a62b8571d4fe56387648f3755169e1dd8186b8f3d39aa597b",
    "pagonia-build-25784167-SHA256SUMS": "f1c7dafea25540477c6201e3224b742bafaac178b027456cb4bc19541794ff6d",
    "gptk-4.0b3-SHA256SUMS": "702296dc74d7522c43eb95d7ae1d697cd4ac1eb5523d643c47fc9c13ff89432c",
    "gptk-4.0b3-SYMLINKS": "26fbf032714eccd6254d3a1745cb39c12b886e58a6cec747ed4e15744a4bc952",
}


def regular_sha256(path: Path) -> str:
    meta = path.lstat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
        raise ValueError(f"Unsafe input file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_inputs(root: Path = ROOT) -> None:
    for name, expected in PINS.items():
        path = root / name
        if regular_sha256(path) != expected:
            raise ValueError(f"Immutable input hash changed: {name}")


def parse_hash_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError("Malformed SHA-256 manifest")
        relative = match.group(2)
        p = Path(relative)
        if p.is_absolute() or not p.parts or ".." in p.parts or relative in entries:
            raise ValueError("Invalid or repeated manifest path")
        entries[relative] = match.group(1)
    return entries


def verify_gptk_files(lib: Path, hashes: Path, symlinks: Path) -> None:
    if lib.is_symlink() or not lib.is_dir() or not str(lib).startswith("/Volumes/"):
        raise ValueError("GPTK source is not a directory")
    # Validate the exact symlink and file tree. No extra entries are accepted.
    expected_files = parse_hash_manifest(hashes)
    expected_links: dict[str, str] = {}
    for line in symlinks.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        relative, sep, target = line.partition("\t")
        if not sep or relative in expected_links or relative in expected_files:
            raise ValueError("Invalid GPTK symlink manifest")
        expected_links[relative] = target
    files = set()
    links = set()
    for current in lib.rglob("*"):
        relative = current.relative_to(lib).as_posix()
        mode = current.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if stat.S_ISLNK(mode):
            if relative not in expected_links or os.readlink(current) != expected_links[relative]:
                raise ValueError(f"Unexpected GPTK symbolic link: {relative}")
            links.add(relative)
        elif stat.S_ISREG(mode):
            if relative not in expected_files or regular_sha256(current) != expected_files[relative]:
                raise ValueError(f"Unexpected or modified GPTK file: {relative}")
            files.add(relative)
        else:
            raise ValueError(f"Unsupported GPTK entry: {relative}")
    if files != set(expected_files) or links != set(expected_links):
        raise ValueError("GPTK inventory mismatch")
    for root in ("external", "wine"):
        if (lib / root).is_symlink() or not (lib / root).is_dir():
            raise ValueError(f"Missing or linked GPTK root: {root}")
    info = subprocess.run(["/bin/df", str(lib)], check=True, capture_output=True,
                          text=True).stdout.splitlines()
    device = info[-1].split()[0]
    mount_info = plistlib.loads(subprocess.run(
        ["/usr/sbin/diskutil", "info", "-plist", device],
        check=True, capture_output=True, timeout=30).stdout)
    if mount_info.get("Writable", True) or mount_info.get("WritableVolume", True):
        raise ValueError("GPTK source volume is writable")
    mount = Path(mount_info["MountPoint"]).resolve(strict=True)
    resolved = lib.resolve(strict=True)
    if mount != resolved and mount not in resolved.parents:
        raise ValueError("GPTK source is outside verified mount")
    signed = 0
    for name in expected_files:
        path = lib / name
        with path.open("rb") as source:
            signature = source.read(4)
        if signature not in (
            bytes.fromhex("cffaedfe"), bytes.fromhex("cafebabe"),
            bytes.fromhex("feedfacf"), bytes.fromhex("bebafeca"),
        ):
            continue
        check = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict", "-R=anchor apple", str(path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
        )
        if check.returncode:
            raise ValueError(f"GPTK binary is not Apple-signed: {name}")
        signed += 1
    if signed != 6:
        raise ValueError(f"Expected six Apple-signed GPTK binaries; found {signed}")



def verify_destination(destination: Path) -> None:
    if destination != Path("/Applications/Pioneers of Pagonia.app"):
        raise ValueError("Fixed /Applications destination required")
    parent = destination.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("Unsafe Applications parent")
    if os.path.lexists(destination) and destination.is_symlink():
        raise ValueError("Destination symlink rejected")


def verify_screen_recording() -> None:
    command = ["/usr/bin/swift", "-e",
               "import CoreGraphics; import Darwin; exit(CGPreflightScreenCaptureAccess() ? 0 : 1)"]
    result = subprocess.run(command, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=30)
    if result.returncode:
        raise ValueError("Screen Recording permission is required")


def preflight(gptk_lib: Path) -> None:
    verify_inputs()
    verify_destination(Path("/Applications/Pioneers of Pagonia.app"))
    verify_screen_recording()
    verify_gptk_files(gptk_lib, ROOT / "gptk-4.0b3-SHA256SUMS",
                      ROOT / "gptk-4.0b3-SYMLINKS")
    return None


def locate_gptk(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    for path in sorted(Path("/Volumes").glob("*/redist/lib")):
        if (path / "wine/x86_64-windows/d3d12.dll").is_file():
            return path
    import re
    downloads = Path.home() / "Downloads"
    for dmg in sorted(downloads.glob("*.dmg"), key=lambda p: p.stat().st_mtime, reverse=True):
        normalized = re.sub(r"[^a-z0-9]+", " ", dmg.name.lower())
        if ("game porting toolkit" in normalized or "evaluation environment for windows games" in normalized) and re.search(r"\\b4(?: 0)? beta 3\\b", normalized):
            subprocess.run(["/usr/sbin/diskutil", "image", "attach", "--nobrowse",
                            "--readOnly", str(dmg)], check=True, timeout=120)
            for path in sorted(Path("/Volumes").glob("*/redist/lib")):
                if (path / "wine/x86_64-windows/d3d12.dll").is_file():
                    return path
            raise ValueError("Mounted GPTK image has no expected redist/lib")
    raise ValueError("GPTK 4.0 beta 3 is not mounted and its DMG was not found in Downloads")
