#!/usr/bin/env python3
"""Discover and delete installer-owned Pagonia managed state."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import sys
from typing import Any

from pagonia_common import STAGING_MARKER_NAME, owner_controlled, staging_marker_state

INSTALLATION_MARKER = Path("Contents/SharedSupport/pagonia-managed-state.json")
STAGING_MARKER = Path(STAGING_MARKER_NAME)
INSTALLATION_IDENTITY = {
    "format": 1,
    "kind": "managed-installation",
    "owner": "pagonia-gptk4b3-installer",
    "product": "pioneers-of-pagonia",
}
BUNDLE_ID = "com.soad1337.pioneersofpagonia.gptk4b3"
STAGING_NAME = re.compile(r"Pagonia-GPTK4b3-deployment\.[A-Za-z0-9]+\Z")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _exact_marker(path: Path, expected: dict[str, object]) -> bool:
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
            return False
        encoded = os.read(descriptor, 4097)
        if len(encoded) > 4096:
            return False
        value = json.loads(encoded.decode("utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return False
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return (
        type(value) is dict
        and value.keys() == expected.keys()
        and all(
            type(value[key]) is type(item) and value[key] == item
            for key, item in expected.items()
        )
    )


def _verified_installation(path: Path) -> bool:
    try:
        if path.is_symlink() or not path.is_dir() or not owner_controlled(path):
            return False
        contents = path / "Contents"
        shared_support = contents / "SharedSupport"
        marker = path / INSTALLATION_MARKER
        plist = contents / "Info.plist"
        executable_directory = contents / "MacOS"
        if any(
            component.is_symlink() or not component.is_dir() or not owner_controlled(component)
            for component in (contents, shared_support)
        ):
            return False
        if (not _exact_marker(marker, INSTALLATION_IDENTITY)
                or not owner_controlled(marker, private=True)
                or not _regular_file(plist)
                or not owner_controlled(plist)):
            return False
        if executable_directory.is_symlink() or not executable_directory.is_dir() or not owner_controlled(executable_directory):
            return False
        if marker.resolve().is_relative_to(path.resolve()) is False:
            return False
        with plist.open("rb") as stream:
            metadata = plistlib.load(stream)
        return metadata.get("CFBundleIdentifier") == BUNDLE_ID
    except (OSError, ValueError, plistlib.InvalidFileException):
        return False




def _canonical_staging_marker(path: Path) -> bool:
    """Accept only the shared, validated staging identity and checkpoint state."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
                return False
            data = os.read(fd, 4097)
        finally:
            os.close(fd)
        marker = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
        staging_marker_state(marker)
        return True
    except (OSError, UnicodeError, ValueError):
        return False

def _verified_staging(path: Path) -> bool:
    try:
        info = path.lstat()
        return (
            STAGING_NAME.fullmatch(path.name) is not None
            and stat.S_ISDIR(info.st_mode)
            and not path.is_symlink()
            and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o700
            and owner_controlled(path / STAGING_MARKER, private=True)
            and _canonical_staging_marker(path / STAGING_MARKER)
        )
    except OSError:
        return False


def discover(destination: Path, staging_parent: Path) -> dict[str, list[dict[str, str]]]:
    managed: list[dict[str, str]] = []
    unverified: list[dict[str, str]] = []
    if os.path.lexists(destination):
        if _verified_installation(destination):
            managed.append({"kind": "managed-installation", "path": str(destination)})
        else:
            unverified.append({"path": str(destination), "reason": "broad-name-match"})

    try:
        children = sorted(staging_parent.iterdir(), key=lambda item: item.name)
    except OSError:
        children = []
    for path in children:
        if STAGING_NAME.fullmatch(path.name) is None:
            continue
        if _verified_staging(path):
            managed.append({"kind": "staging-deployment", "path": str(path)})
        else:
            unverified.append({"path": str(path), "reason": "broad-name-match"})
    return {"managed": managed, "unverified": unverified}


@dataclass(frozen=True)
class RecordedTree:
    item: dict[str, str]
    path: Path
    root_identity: tuple[int, int]
    entries: dict[tuple[str, ...], tuple[int, int, int]]


def _still_verified(item: dict[str, str], path: Path) -> bool:
    if item["kind"] == "managed-installation":
        return _verified_installation(path)
    return _verified_staging(path)


def _record_tree(item: dict[str, str]) -> RecordedTree:
    path = Path(item["path"])
    root = path.lstat()
    if not stat.S_ISDIR(root.st_mode) or path.is_symlink():
        raise OSError(f"refusing symlink or non-directory managed path: {path}")
    if not _still_verified(item, path):
        raise OSError(f"managed path identity changed after discovery: {path}")
    entries: dict[tuple[str, ...], tuple[int, int, int]] = {}

    def visit(directory: Path, relative: tuple[str, ...]) -> None:
        for child in os.scandir(directory):
            child_path = Path(child.path)
            info = child_path.lstat()
            child_relative = relative + (child.name,)
            if stat.S_ISLNK(info.st_mode):
                raise OSError(f"refusing symlink in managed tree: {child_path}")
            if info.st_dev != root.st_dev:
                raise OSError(f"refusing cross-filesystem managed tree: {child_path}")
            entries[child_relative] = (info.st_dev, info.st_ino, info.st_mode)
            if stat.S_ISDIR(info.st_mode):
                visit(child_path, child_relative)

    visit(path, ())
    current = path.lstat()
    if (current.st_dev, current.st_ino) != (root.st_dev, root.st_ino):
        raise OSError(f"managed path changed while recording identity: {path}")
    return RecordedTree(item, path, (root.st_dev, root.st_ino), entries)


def _identity(info: os.stat_result) -> tuple[int, int, int]:
    return (info.st_dev, info.st_ino, info.st_mode)


def _remove_recorded_tree(tree: RecordedTree) -> None:
    path = tree.path
    current = path.lstat()
    if path.is_symlink() or (current.st_dev, current.st_ino) != tree.root_identity:
        raise OSError(f"managed path identity changed before deletion: {path}")
    if not _still_verified(tree.item, path):
        raise OSError(f"managed marker or structure changed before deletion: {path}")

    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | nofollow
    parent_fd = os.open(path.parent, directory_flags)
    root_fd = os.open(path.name, directory_flags, dir_fd=parent_fd)
    try:
        opened = os.fstat(root_fd)
        if (opened.st_dev, opened.st_ino) != tree.root_identity:
            raise OSError(f"managed path changed while opening for deletion: {path}")

        def remove_contents(directory_fd: int, relative: tuple[str, ...]) -> None:
            expected_names = {
                parts[len(relative)]
                for parts in tree.entries
                if len(parts) == len(relative) + 1 and parts[: len(relative)] == relative
            }
            actual_names = set(os.listdir(directory_fd))
            if actual_names != expected_names:
                raise OSError(f"managed tree changed before deletion: {path.joinpath(*relative)}")
            for name in sorted(expected_names):
                child_relative = relative + (name,)
                expected = tree.entries[child_relative]
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if _identity(info) != expected:
                    raise OSError(
                        "managed tree entry changed before deletion: "
                        f"{path.joinpath(*child_relative)}"
                    )
                if stat.S_ISDIR(info.st_mode):
                    child_fd = os.open(name, directory_flags, dir_fd=directory_fd)
                    try:
                        if _identity(os.fstat(child_fd)) != expected:
                            raise OSError(
                                "managed directory changed while opening: "
                                f"{path.joinpath(*child_relative)}"
                            )
                        remove_contents(child_fd, child_relative)
                    finally:
                        os.close(child_fd)
                    final = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                    if (final.st_dev, final.st_ino) != expected[:2]:
                        raise OSError(
                            "managed directory changed before removal: "
                            f"{path.joinpath(*child_relative)}"
                        )
                    os.rmdir(name, dir_fd=directory_fd)
                else:
                    os.unlink(name, dir_fd=directory_fd)

        remove_contents(root_fd, ())
    finally:
        os.close(root_fd)
    try:
        final = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (final.st_dev, final.st_ino) != tree.root_identity:
            raise OSError(f"managed path changed before final removal: {path}")
        os.rmdir(path.name, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)


def _managed_process_running() -> bool:
    try:
        result = subprocess.run(
            ["/bin/ps", "-axo", "uid=,command="],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        raise OSError("could not verify that Wine, Steam, and Pagonia processes are exited")
    uid = str(os.getuid())
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) != 2 or fields[0] != uid:
            continue
        command = fields[1]
        if re.search(
            r"(?:^|/)(?:wine(?:64)?(?:-preloader)?|wineserver|"
            r"steam(?:webhelper|service)?\.exe|Pioneers of Pagonia\.exe)(?:\s|$)",
            command,
            re.IGNORECASE,
        ):
            return True
    return False


def delete_managed(
    destination: Path, staging_parent: Path
) -> dict[str, list[dict[str, str]]]:
    listing = discover(destination, staging_parent)
    trees = [_record_tree(item) for item in listing["managed"]]
    if trees and _managed_process_running():
        raise OSError("exit all Wine, Steam, and Pagonia processes before deletion")
    for tree in trees:
        _remove_recorded_tree(tree)
    return {"deleted": listing["managed"], "unverified": listing["unverified"]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("list", "delete"))
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--staging-parent", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    if (
        not arguments.destination.is_absolute()
        or not arguments.staging_parent.is_absolute()
    ):
        print("destination and staging parent must be absolute paths", file=sys.stderr)
        return 2
    try:
        if arguments.command == "delete":
            result = delete_managed(arguments.destination, arguments.staging_parent)
        else:
            result = discover(arguments.destination, arguments.staging_parent)
    except OSError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
