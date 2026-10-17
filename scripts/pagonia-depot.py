#!/usr/bin/env python3
"""Validate and selectively install a pinned Pagonia Steam depot."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat

GAME_NAME = "Pioneers of Pagonia"


@dataclass(frozen=True)
class Expectations:
    manifest: Path
    manifest_sha256: str
    app_id: str
    build_id: str
    file_count: int
    total_size: int
    depot_id: str
    depot_manifest_id: str
    shared_depot_id: str
    shared_depot_app_id: str


def parse_keyvalues(text: str) -> dict[str, object]:
    token_pattern = re.compile(r'\s*(?:"((?:\\.|[^"\\])*)"|([{}]))', re.DOTALL)
    tokens: list[str] = []
    position = 0
    while position < len(text):
        if not text[position:].strip():
            break
        match = token_pattern.match(text, position)
        if not match:
            raise ValueError(f"Invalid appmanifest syntax at byte {position}")
        tokens.append(
            match.group(2) if match.group(2) is not None else match.group(1)
        )
        position = match.end()

    def object_at(index: int) -> tuple[dict[str, object], int]:
        if index >= len(tokens) or tokens[index] != "{":
            raise ValueError("Expected appmanifest object")
        index += 1
        result: dict[str, object] = {}
        while index < len(tokens) and tokens[index] != "}":
            key = tokens[index]
            if key == "{" or index + 1 >= len(tokens):
                raise ValueError("Invalid appmanifest entry")
            if key in result:
                raise ValueError(f"Duplicate appmanifest key: {key}")
            index += 1
            if tokens[index] == "{":
                result[key], index = object_at(index)
            elif tokens[index] == "}":
                raise ValueError(f"Missing appmanifest value for {key}")
            else:
                result[key] = tokens[index]
                index += 1
        if index >= len(tokens):
            raise ValueError("Unbalanced appmanifest braces")
        return result, index + 1

    if len(tokens) < 2 or tokens[0] != "AppState":
        raise ValueError("Appmanifest does not start with AppState")
    parsed, end = object_at(1)
    if end != len(tokens):
        raise ValueError("Trailing appmanifest data")
    return parsed


def require_owned(path: Path, info: os.stat_result) -> None:
    if info.st_uid != os.getuid():
        raise ValueError(f"Depot path is not owned by current uid: {path}")


def require_safe_source_file(path: Path, info: os.stat_result) -> None:
    require_owned(path, info)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError(f"Depot entry is not a regular unlinked file: {path}")
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError(f"Source file is group/other-writable: {path}")


def require_unlinked(steam: Path, path: Path) -> os.stat_result:
    try:
        relative = path.relative_to(steam)
    except ValueError as error:
        raise ValueError(f"Depot path escapes Steam root: {path}") from error
    current = steam
    root_info = current.lstat()
    if stat.S_ISLNK(root_info.st_mode):
        raise ValueError(f"Linked depot path is not permitted: {current}")
    require_owned(current, root_info)
    for part in relative.parts:
        current /= part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"Linked depot path is not permitted: {current}")
        require_owned(current, info)
    return info if relative.parts else root_info


def appmanifest_path(steam: Path, expected: Expectations) -> Path:
    return steam / "steamapps" / f"appmanifest_{expected.app_id}.acf"


def validated_appmanifest(steam: Path, expected: Expectations) -> dict[str, object]:
    path = appmanifest_path(steam, expected)
    info = require_unlinked(steam, path)
    try:
        require_safe_source_file(path, info)
    except ValueError as error:
        if "regular unlinked file" in str(error):
            raise ValueError(f"Appmanifest is not a regular unlinked file: {path}") from error
        raise
    fields = parse_keyvalues(path.read_text(encoding="utf-8", errors="strict"))
    required = {
        "appid": expected.app_id,
        "StateFlags": "4",
        "buildid": expected.build_id,
        "installdir": GAME_NAME,
        "SizeOnDisk": str(expected.total_size),
    }
    for key, value in required.items():
        if fields.get(key) != value:
            raise ValueError(f"Invalid appmanifest field {key}: {fields.get(key)!r}")
    depots = {
        expected.depot_id: {
            "manifest": expected.depot_manifest_id,
            "size": str(expected.total_size),
        }
    }
    if fields.get("InstalledDepots") != depots:
        raise ValueError("InstalledDepots does not match expected depot metadata")
    shared_depots = {expected.shared_depot_id: expected.shared_depot_app_id}
    if fields.get("SharedDepots") != shared_depots:
        raise ValueError("SharedDepots does not match expected depot metadata")
    return fields


def read_trusted_manifest(expected: Expectations) -> dict[PurePosixPath, str]:
    info = expected.manifest.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ValueError("Trusted SHA256 manifest is not a regular file")
    if not re.fullmatch(r"[0-9a-f]{64}", expected.manifest_sha256):
        raise ValueError("Trusted manifest SHA256 is invalid")
    if sha256(expected.manifest.read_bytes()).hexdigest() != expected.manifest_sha256:
        raise ValueError("Trusted SHA256 manifest identity mismatch")
    entries: dict[PurePosixPath, str] = {}
    for number, line in enumerate(
        expected.manifest.read_text(encoding="utf-8", errors="strict").splitlines(), 1
    ):
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError(f"Invalid SHA256 manifest line {number}")
        raw_path = match.group(2)
        relative = PurePosixPath(raw_path)
        if (
            relative.is_absolute()
            or "\\" in raw_path
            or not relative.parts
            or any(part in ("", ".", "..") for part in relative.parts)
            or relative.as_posix() != raw_path
            or relative in entries
        ):
            raise ValueError(f"Unsafe or duplicate manifest path: {raw_path}")
        entries[relative] = match.group(1)
    if len(entries) != expected.file_count:
        raise ValueError(
            f"Expected {expected.file_count} depot files, manifest has {len(entries)}"
        )
    return entries


def game_path(steam: Path) -> Path:
    return steam / "steamapps" / "common" / GAME_NAME


def hash_regular_unlinked(steam: Path, path: Path) -> tuple[str, int]:
    require_unlinked(steam, path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        require_safe_source_file(path, info)
        digest = sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
        return digest.hexdigest(), info.st_size
    finally:
        os.close(descriptor)


def validate_depot(steam: Path, expected: Expectations) -> dict[PurePosixPath, str]:
    validated_appmanifest(steam, expected)
    entries = read_trusted_manifest(expected)
    game = game_path(steam)
    game_info = require_unlinked(steam, game)
    if not stat.S_ISDIR(game_info.st_mode):
        raise ValueError(f"Depot game root is not a directory: {game}")

    actual: set[PurePosixPath] = set()
    for path in game.rglob("*"):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"Linked depot entry is not permitted: {path}")
        require_owned(path, info)
        if stat.S_ISDIR(info.st_mode):
            continue
        relative = PurePosixPath(path.relative_to(game).as_posix())
        require_safe_source_file(path, info)
        actual.add(relative)
    if actual != set(entries):
        unexpected = sorted(str(path) for path in actual - set(entries))
        missing = sorted(str(path) for path in set(entries) - actual)
        raise ValueError(f"Depot file set mismatch; unexpected={unexpected}, missing={missing}")

    total_size = 0
    for relative, digest in entries.items():
        actual_digest, size = hash_regular_unlinked(steam, game.joinpath(*relative.parts))
        if actual_digest != digest:
            raise ValueError(f"Depot file hash mismatch: {relative}")
        total_size += size
    if total_size != expected.total_size:
        raise ValueError(
            f"Expected depot size {expected.total_size}, found {total_size}"
        )
    return entries


def sanitized_appmanifest(expected: Expectations, steam_id: str) -> str:
    return f'''"AppState"
{{
\t"appid"\t\t"{expected.app_id}"
\t"Universe"\t\t"1"
\t"LauncherPath"\t\t"C:\\\\Program Files (x86)\\\\Steam\\\\steam.exe"
\t"name"\t\t"{GAME_NAME}"
\t"StateFlags"\t\t"4"
\t"installdir"\t\t"{GAME_NAME}"
\t"LastUpdated"\t\t"0"
\t"LastPlayed"\t\t"0"
\t"SizeOnDisk"\t\t"{expected.total_size}"
\t"StagingSize"\t\t"0"
\t"buildid"\t\t"{expected.build_id}"
\t"LastOwner"\t\t"{steam_id}"
\t"DownloadType"\t\t"1"
\t"UpdateResult"\t\t"0"
\t"BytesToDownload"\t\t"0"
\t"BytesDownloaded"\t\t"0"
\t"BytesToStage"\t\t"0"
\t"BytesStaged"\t\t"0"
\t"TargetBuildID"\t\t"{expected.build_id}"
\t"AutoUpdateBehavior"\t\t"0"
\t"AllowOtherDownloadsWhileRunning"\t\t"0"
\t"ScheduledAutoUpdate"\t\t"0"
\t"InstalledDepots"
\t{{
\t\t"{expected.depot_id}"
\t\t{{
\t\t\t"manifest"\t\t"{expected.depot_manifest_id}"
\t\t\t"size"\t\t"{expected.total_size}"
\t\t}}
\t}}
\t"SharedDepots"
\t{{
\t\t"{expected.shared_depot_id}"\t\t"{expected.shared_depot_app_id}"
\t}}
}}
'''


def require_destination_root(destination: Path) -> None:
    info = destination.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ValueError(
            f"Destination Steam root is not an unlinked directory: {destination}"
        )
    if info.st_uid != os.getuid():
        raise ValueError(
            f"Destination Steam root is not owned by current uid: {destination}"
        )


def make_destination_parents(destination: Path, relative: Path) -> Path:
    current = destination
    for part in relative.parts:
        current /= part
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.getuid()
            ):
                raise ValueError(f"Unsafe destination depot path: {current}")
        else:
            current.mkdir()
    return current


def install_depot(
    source: Path,
    destination: Path,
    steam_id: str,
    expected: Expectations,
) -> None:
    if not re.fullmatch(r"[0-9]{17}", steam_id):
        raise ValueError("Steam owner must be a 17-digit Steam ID")
    entries = validate_depot(source, expected)
    require_destination_root(destination)
    destination_game = destination / "steamapps" / "common" / GAME_NAME
    destination_acf = appmanifest_path(destination, expected)
    if destination_game.exists() or destination_game.is_symlink():
        raise ValueError(f"Destination depot already exists: {destination_game}")
    if destination_acf.exists() or destination_acf.is_symlink():
        raise ValueError(f"Destination appmanifest already exists: {destination_acf}")

    common = make_destination_parents(destination, Path("steamapps/common"))
    temporary_game = common / f".pagonia-depot-install-{os.getpid()}"
    if temporary_game.exists() or temporary_game.is_symlink():
        raise ValueError(f"Temporary depot path already exists: {temporary_game}")
    temporary_game.mkdir()
    source_game = game_path(source)
    try:
        for relative, expected_digest in entries.items():
            source_path = source_game.joinpath(*relative.parts)
            require_unlinked(source, source_path)
            target = temporary_game.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source_fd = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                source_info = os.fstat(source_fd)
                try:
                    require_safe_source_file(source_path, source_info)
                except ValueError as error:
                    raise ValueError(
                        f"Source depot file changed before install: {relative}"
                    ) from error
                digest = sha256()
                with (
                    os.fdopen(source_fd, "rb", closefd=False) as input_file,
                    target.open("xb") as output_file,
                ):
                    while chunk := input_file.read(1024 * 1024):
                        digest.update(chunk)
                        output_file.write(chunk)
                if digest.hexdigest() != expected_digest:
                    raise ValueError(f"Source depot file changed before install: {relative}")
                os.chmod(target, stat.S_IMODE(source_info.st_mode))
            finally:
                os.close(source_fd)
        temporary_game.rename(destination_game)
    except BaseException:
        shutil.rmtree(temporary_game, ignore_errors=True)
        raise

    try:
        with destination_acf.open("x", encoding="utf-8", newline="") as output:
            output.write(sanitized_appmanifest(expected, steam_id))
        destination_acf.chmod(0o644)
        validate_depot(destination, expected)
    except BaseException:
        try:
            destination_acf.unlink(missing_ok=True)
        finally:
            shutil.rmtree(destination_game, ignore_errors=True)
        raise


def expectations_from(arguments: argparse.Namespace) -> Expectations:
    identifiers = (
        arguments.expected_app_id,
        arguments.expected_build_id,
        arguments.expected_depot_id,
        arguments.expected_depot_manifest_id,
        arguments.expected_shared_depot_id,
        arguments.expected_shared_depot_app_id,
    )
    if any(not value.isdecimal() for value in identifiers):
        raise ValueError("Expected Steam application, build, and depot IDs must be decimal")
    if arguments.expected_file_count < 0 or arguments.expected_total_size < 0:
        raise ValueError("Expected file count and total size must be non-negative")
    return Expectations(
        manifest=arguments.manifest,
        manifest_sha256=arguments.manifest_sha256,
        app_id=arguments.expected_app_id,
        build_id=arguments.expected_build_id,
        file_count=arguments.expected_file_count,
        total_size=arguments.expected_total_size,
        depot_id=arguments.expected_depot_id,
        depot_manifest_id=arguments.expected_depot_manifest_id,
        shared_depot_id=arguments.expected_shared_depot_id,
        shared_depot_app_id=arguments.expected_shared_depot_app_id,
    )


def add_expectations(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--expected-app-id", required=True)
    parser.add_argument("--expected-build-id", required=True)
    parser.add_argument("--expected-file-count", required=True, type=int)
    parser.add_argument("--expected-total-size", required=True, type=int)
    parser.add_argument("--expected-depot-id", required=True)
    parser.add_argument("--expected-depot-manifest-id", required=True)
    parser.add_argument("--expected-shared-depot-id", required=True)
    parser.add_argument("--expected-shared-depot-app-id", required=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("source", type=Path)
    add_expectations(status)
    validate = subparsers.add_parser("validate")
    validate.add_argument("source", type=Path)
    add_expectations(validate)
    install = subparsers.add_parser("install")
    install.add_argument("source", type=Path)
    install.add_argument("destination", type=Path)
    install.add_argument("steam_id")
    add_expectations(install)
    arguments = parser.parse_args()
    expected = expectations_from(arguments)
    if arguments.command == "status":
        read_trusted_manifest(expected)
        validated_appmanifest(arguments.source, expected)
        print(
            f"ready app={expected.app_id} build={expected.build_id} "
            f"depot={expected.depot_id}"
        )
    elif arguments.command == "validate":
        validate_depot(arguments.source, expected)
        print(f"validated {expected.file_count} files ({expected.total_size} bytes)")
    else:
        install_depot(
            arguments.source, arguments.destination, arguments.steam_id, expected
        )
        print(f"installed {expected.file_count} files ({expected.total_size} bytes)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        raise SystemExit(f"ERROR: {error}")
