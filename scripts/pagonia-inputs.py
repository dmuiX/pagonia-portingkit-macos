#!/usr/bin/env python3
"""Verify immutable files, archives, and extracted runtime inventories."""

from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import time

BUFFER_SIZE = 1024 * 1024


def require_owner_controlled(info: os.stat_result, description: str) -> None:
    if info.st_uid != os.getuid():
        raise ValueError(f"{description} is not owned by the current user")
    if stat.S_IMODE(info.st_mode) & 0o022:
        raise ValueError(f"{description} is writable by group or other users")


def hash_regular_file(path: Path, description: str) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError(f"{description} is not a singly-linked regular file")
        require_owner_controlled(info, description)
        digest = sha256()
        while chunk := os.read(descriptor, BUFFER_SIZE):
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def verify_file(expected_digest: str, path: Path) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise ValueError("Expected SHA256 must be 64 lowercase hexadecimal characters")
    if hash_regular_file(path, "Input file") != expected_digest:
        raise ValueError(f"SHA256 mismatch: {path}")


def safe_archive_name(member: tarfile.TarInfo) -> PurePosixPath:
    raw = member.name
    if member.isdir() and raw.endswith("/"):
        raw = raw[:-1]
    parts = raw.split("/")
    if (
        not raw
        or raw.startswith("/")
        or "\\" in raw
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise ValueError(f"Unsafe archive path: {member.name}")
    return PurePosixPath(*parts)


def normalized_link_target(member_path: PurePosixPath, target: str, symlink: bool) -> PurePosixPath:
    if not target or target.startswith("/") or "\\" in target:
        raise ValueError(f"Unsafe archive link target: {target}")
    result = list(member_path.parent.parts if symlink else ())
    for part in target.split("/"):
        if part in ("", "."):
            if part == "":
                raise ValueError(f"Unsafe archive link target: {target}")
            continue
        if part == "..":
            if not result:
                raise ValueError(f"Archive link escapes its root: {target}")
            result.pop()
        else:
            result.append(part)
    if not result:
        raise ValueError(f"Unsafe archive link target: {target}")
    return PurePosixPath(*result)


def verify_archive(path: Path, max_expanded_size: int) -> int:
    if max_expanded_size < 0:
        raise ValueError("Maximum expanded size must be non-negative")
    hash_regular_file(path, "Archive")
    members: dict[PurePosixPath, tarfile.TarInfo] = {}
    links: list[tuple[tarfile.TarInfo, PurePosixPath]] = []
    expanded_size = 0
    entries_seen = 0
    started = time.monotonic()
    last_status = started
    with tarfile.open(path, mode="r:*") as archive:
        for member in archive:
            entries_seen += 1
            now = time.monotonic()
            if now - last_status >= 25:
                print(
                    f"    Still verifying archive layout: {entries_seen} entries, "
                    f"{int(now - started)} elapsed seconds...",
                    flush=True,
                )
                last_status = now
            member_path = safe_archive_name(member)
            if member_path in members:
                raise ValueError(f"Duplicate archive path: {member_path}")
            if not member.isdir() and any(
                member_path in previous.parents for previous in members
            ):
                raise ValueError(f"Archive replaces an existing parent directory: {member_path}")
            if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                raise ValueError(f"Unsafe archive entry type: {member_path}")
            for parent in member_path.parents:
                parent_entry = members.get(parent)
                if parent_entry is not None and not parent_entry.isdir():
                    raise ValueError(f"Archive path has a non-directory parent: {member_path}")
            if member.isfile():
                if member.size < 0:
                    raise ValueError(f"Invalid archive entry size: {member_path}")
                expanded_size += member.size
                if expanded_size > max_expanded_size:
                    raise ValueError(
                        f"Archive expands beyond {max_expanded_size} bytes"
                    )
            elif member.issym() or member.islnk():
                target = normalized_link_target(
                    member_path, member.linkname, member.issym()
                )
                links.append((member, target))
            members[member_path] = member

    for member, target in links:
        if member.islnk():
            target_member = members.get(target)
            if target_member is None or not target_member.isfile():
                raise ValueError(
                    f"Archive hardlink does not name a regular archive file: {member.name}"
                )
    return expanded_size


def safe_manifest_path(raw: str) -> PurePosixPath:
    relative = PurePosixPath(raw)
    if (
        not raw
        or raw.startswith("/")
        or "\\" in raw
        or any(part in ("", ".", "..") for part in raw.split("/"))
        or relative.as_posix() != raw
    ):
        raise ValueError(f"Unsafe manifest path: {raw}")
    return relative


def read_runtime_manifest(manifest: Path) -> dict[PurePosixPath, tuple[str, str]]:
    hash_regular_file(manifest, "Runtime manifest")
    entries: dict[PurePosixPath, tuple[str, str]] = {}
    for number, line in enumerate(
        manifest.read_text(encoding="utf-8", errors="strict").splitlines(), 1
    ):
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"(file|symlink) ([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError(f"Invalid runtime manifest line {number}")
        relative = safe_manifest_path(match.group(3))
        if relative in entries:
            raise ValueError(f"Duplicate runtime manifest path: {relative}")
        entries[relative] = (match.group(1), match.group(2))
    return entries


def contained_symlink_target(root: Path, path: Path) -> str:
    target = os.readlink(path)
    if os.path.isabs(target):
        raise ValueError(f"Absolute runtime symlink is not permitted: {path}")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError(f"Runtime symlink escapes its root or is broken: {path}") from error
    return target


def runtime_inventory(root: Path) -> dict[PurePosixPath, tuple[str, str]]:
    root_info = root.lstat()
    if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode):
        raise ValueError("Runtime root is not an unlinked directory")
    require_owner_controlled(root_info, "Runtime root")
    resolved_root = root.resolve(strict=True)
    entries: dict[PurePosixPath, tuple[str, str]] = {}

    def visit(directory: Path) -> None:
        for child in directory.iterdir():
            info = child.lstat()
            relative = PurePosixPath(child.relative_to(root).as_posix())
            require_owner_controlled(info, f"Runtime entry {relative}")
            if stat.S_ISDIR(info.st_mode):
                visit(child)
            elif stat.S_ISREG(info.st_mode):
                if info.st_nlink != 1:
                    raise ValueError(f"Runtime file is hardlinked: {relative}")
                entries[relative] = (
                    "file",
                    hash_regular_file(child, f"Runtime file {relative}"),
                )
            elif stat.S_ISLNK(info.st_mode):
                target = contained_symlink_target(resolved_root, child)
                entries[relative] = (
                    "symlink",
                    sha256(os.fsencode(target)).hexdigest(),
                )
            else:
                raise ValueError(f"Unsupported runtime entry type: {relative}")

    visit(root)
    return entries


def verify_runtime(manifest: Path, root: Path) -> int:
    expected = read_runtime_manifest(manifest)
    actual = runtime_inventory(root)
    if actual != expected:
        unexpected = sorted(str(path) for path in actual.keys() - expected.keys())
        missing = sorted(str(path) for path in expected.keys() - actual.keys())
        changed = sorted(
            str(path)
            for path in actual.keys() & expected.keys()
            if actual[path] != expected[path]
        )
        raise ValueError(
            "Runtime inventory mismatch; "
            f"unexpected={unexpected}, missing={missing}, changed={changed}"
        )
    return len(expected)


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    file_parser = commands.add_parser("verify-file")
    file_parser.add_argument("hash")
    file_parser.add_argument("path", type=Path)

    archive_parser = commands.add_parser("verify-archive")
    archive_parser.add_argument("archive", type=Path)
    archive_parser.add_argument("--max-expanded-size", required=True, type=int)

    runtime_parser = commands.add_parser("verify-runtime")
    runtime_parser.add_argument("manifest", type=Path)
    runtime_parser.add_argument("root", type=Path)

    arguments = parser.parse_args()
    if arguments.command == "verify-file":
        verify_file(arguments.hash, arguments.path)
        print("verified file")
    elif arguments.command == "verify-archive":
        expanded_size = verify_archive(arguments.archive, arguments.max_expanded_size)
        print(f"verified archive ({expanded_size} expanded bytes)")
    else:
        count = verify_runtime(arguments.manifest, arguments.root)
        print(f"verified runtime ({count} entries)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, tarfile.TarError, ValueError) as error:
        raise SystemExit(f"ERROR: {error}")
