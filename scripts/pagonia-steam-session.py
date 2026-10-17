#!/usr/bin/env python3
"""Create and install a narrowly scoped, integrity-checked Steam login session."""

from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import tempfile
import zlib

MANIFEST_NAME = ".pagonia-steam-session-SHA256SUMS"
STEAM_ID_NAME = ".pagonia-steamid"
STEAM_ID_BASE = 76561197960265728
MAX_FILE_SIZE = 64 * 1024 * 1024
MAX_SNAPSHOT_SIZE = 128 * 1024 * 1024
CLIENT_MANIFEST_NAME = ".pagonia-steam-client-SHA256SUMS"
CLIENT_INVENTORY = Path("package/steam_client_win64.installed")
MAX_CLIENT_FILE_SIZE = 1024 * 1024 * 1024
MAX_CLIENT_SNAPSHOT_SIZE = 2 * 1024 * 1024 * 1024
CLIENT_EXCLUDED_PARTS = {
    "appcache",
    "cache",
    "config",
    "depotcache",
    "dumps",
    "htmlcache",
    "logs",
    "package",
    "steamapps",
    "userdata",
}


def parse_keyvalues(text: str) -> dict[str, object]:
    token_pattern = re.compile(r'"((?:\\.|[^"\\])*)"|([{}])')
    tokens: list[str] = []
    position = 0
    for match in token_pattern.finditer(text):
        if text[position : match.start()].strip():
            raise ValueError("Unexpected text in Steam KeyValues file")
        if match.group(2):
            tokens.append(match.group(2))
        else:
            value = re.sub(r"\\([\\\"])", r"\1", match.group(1))
            tokens.append(value)
        position = match.end()
    if text[position:].strip():
        raise ValueError("Trailing text in Steam KeyValues file")

    def object_at(index: int, *, braced: bool) -> tuple[dict[str, object], int]:
        if braced:
            if index >= len(tokens) or tokens[index] != "{":
                raise ValueError("Missing opening brace in Steam KeyValues file")
            index += 1
        result: dict[str, object] = {}
        while index < len(tokens) and tokens[index] != "}":
            key = tokens[index]
            if key in ("{", "}") or index + 1 >= len(tokens):
                raise ValueError("Invalid Steam KeyValues entry")
            index += 1
            if tokens[index] == "{":
                value, index = object_at(index, braced=True)
            else:
                value = tokens[index]
                index += 1
            if key in result:
                raise ValueError(f"Duplicate Steam KeyValues key: {key}")
            result[key] = value
        if braced:
            if index >= len(tokens) or tokens[index] != "}":
                raise ValueError("Missing closing brace in Steam KeyValues file")
            index += 1
        return result, index

    parsed, end = object_at(0, braced=False)
    if end != len(tokens):
        raise ValueError("Unexpected closing brace in Steam KeyValues file")
    return parsed


def resolve_owned_directory(path: Path, description: str) -> Path:
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
    ):
        raise ValueError(f"{description} is not an owned, unlinked directory: {path}")
    return path.resolve(strict=True)


def require_unlinked_path(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ValueError(f"Steam session path escapes root: {path}")
    current = root
    for part in relative.parts:
        current /= part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"Linked Steam session path: {current}")


def authenticated_steam_id(loginusers: Path) -> str:
    parsed = parse_keyvalues(loginusers.read_text(encoding="utf-8", errors="strict"))
    users = parsed.get("users")
    if not isinstance(users, dict):
        raise ValueError("Steam loginusers.vdf has no users object")
    accounts = []
    for steam_id, values in users.items():
        if re.fullmatch(r"7656119\d{10}", steam_id) and isinstance(values, dict):
            accounts.append((steam_id, values))
    recent = [account for account in accounts if account[1].get("MostRecent") == "1"]
    if len(recent) == 1:
        steam_id, values = recent[0]
    elif not recent and len(accounts) == 1:
        steam_id, values = accounts[0]
    else:
        raise ValueError("Steam loginusers.vdf does not identify one active account")
    if not any(
        values.get(field) == "1"
        for field in ("RememberPassword", "AllowAutoLogin", "AutoLogin")
    ):
        raise ValueError("Steam account did not persist automatic login")
    return steam_id


def safe_files(root: Path) -> list[Path]:
    files: list[Path] = []
    total_size = 0
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError(f"Unsafe Steam session entry: {path}")
        if info.st_mode & 0o022:
            raise ValueError(f"Writable-by-group-or-other Steam session entry: {path}")
        if path.is_dir():
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_FILE_SIZE:
            raise ValueError(f"Invalid Steam session file: {path}")
        total_size += info.st_size
        if total_size > MAX_SNAPSHOT_SIZE:
            raise ValueError("Steam session snapshot exceeds size limit")
        files.append(path)
    return files


def transferable_steam_id(steam: Path) -> str:
    """Validate that Steam persisted the allowlisted state needed for transfer."""
    steam = resolve_owned_directory(steam, "Steam root")
    config = steam / "config"
    loginusers = config / "loginusers.vdf"
    config_vdf = config / "config.vdf"
    for required in (loginusers, config_vdf):
        require_unlinked_path(steam, required)
        info = required.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_mode & 0o022
            or info.st_size > MAX_FILE_SIZE
        ):
            raise ValueError(f"Unsafe Steam login file: {required}")
    steam_id = authenticated_steam_id(loginusers)
    account_id = str(int(steam_id) - STEAM_ID_BASE)
    localconfig = steam / "userdata" / account_id / "config/localconfig.vdf"
    require_unlinked_path(steam, localconfig)
    local_info = localconfig.lstat()
    if (
        not stat.S_ISREG(local_info.st_mode)
        or stat.S_ISLNK(local_info.st_mode)
        or local_info.st_uid != os.getuid()
        or local_info.st_nlink != 1
        or local_info.st_mode & 0o022
        or local_info.st_size > MAX_FILE_SIZE
    ):
        raise ValueError(f"Unsafe Steam account localconfig: {localconfig}")
    localconfig_data = localconfig.read_bytes()
    if not all(marker in localconfig_data for marker in (b'"AuthData"', b'"SharedAuth"')):
        raise ValueError("Steam localconfig has no persisted authentication data")
    optional = config / "SteamAppData.vdf"
    candidates = [optional] if optional.exists() or optional.is_symlink() else []
    candidates.extend(
        entry
        for entry in steam.iterdir()
        if re.fullmatch(r"ssfn\d+", entry.name, flags=re.IGNORECASE)
    )
    for candidate in candidates:
        require_unlinked_path(steam, candidate)
        info = candidate.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_mode & 0o022
            or info.st_size > MAX_FILE_SIZE
        ):
            raise ValueError(f"Unsafe optional Steam login file: {candidate}")
    return steam_id


def create_snapshot(steam: Path, snapshot: Path) -> None:
    steam = resolve_owned_directory(steam, "Steam root")
    if snapshot.exists():
        raise ValueError(f"Steam session snapshot already exists: {snapshot}")
    steam_id = transferable_steam_id(steam)
    account_id = str(int(steam_id) - STEAM_ID_BASE)
    config = steam / "config"
    loginusers = config / "loginusers.vdf"
    config_vdf = config / "config.vdf"
    localconfig = steam / "userdata" / account_id / "config/localconfig.vdf"

    snapshot.mkdir(mode=0o700)
    selected = [loginusers, config_vdf, localconfig]
    steam_app_data = config / "SteamAppData.vdf"
    if steam_app_data.exists():
        selected.append(steam_app_data)
    for source in selected:
        require_unlinked_path(steam, source)
        info = source.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_mode & 0o022
            or info.st_size > MAX_FILE_SIZE
        ):
            raise ValueError(f"Unsafe Steam login file: {source}")
        relative = source.relative_to(steam)
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copy2(source, target)
        target.chmod(0o600)
    for entry in steam.iterdir():
        if re.fullmatch(r"ssfn\d+", entry.name, flags=re.IGNORECASE):
            info = entry.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.getuid()
                or info.st_mode & 0o022
                or info.st_size > MAX_FILE_SIZE
            ):
                raise ValueError(f"Unsafe Steam machine-authorization file: {entry}")
            shutil.copy2(entry, snapshot / entry.name)
            (snapshot / entry.name).chmod(0o600)

    steam_id_path = snapshot / STEAM_ID_NAME
    steam_id_path.write_text(steam_id + "\n", encoding="ascii")
    steam_id_path.chmod(0o600)
    entries = []
    for path in safe_files(snapshot):
        relative = path.relative_to(snapshot).as_posix()
        entries.append(f"{sha256(path.read_bytes()).hexdigest()}  {relative}")
    manifest = snapshot / MANIFEST_NAME
    manifest.write_text("\n".join(entries) + "\n", encoding="utf-8")
    manifest.chmod(0o600)
    validate_snapshot(snapshot, exact=True)


def read_manifest(root: Path) -> dict[Path, str]:
    manifest = root / MANIFEST_NAME
    info = manifest.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o022
    ):
        raise ValueError(f"Invalid Steam session manifest: {manifest}")
    expected: dict[Path, str] = {}
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError(f"Invalid Steam session manifest line {number}")
        relative = Path(match.group(2))
        if relative.is_absolute() or ".." in relative.parts or relative in expected:
            raise ValueError(f"Unsafe or duplicate Steam session path: {relative}")
        expected[relative] = match.group(1)
    required = {Path("config/loginusers.vdf"), Path("config/config.vdf"), Path(STEAM_ID_NAME)}
    if not required <= set(expected):
        raise ValueError("Steam session manifest is missing required files")
    return expected


def validate_snapshot(root: Path, *, exact: bool) -> str:
    root = resolve_owned_directory(root, "Steam session snapshot")
    expected = read_manifest(root)
    actual: set[Path] = set()
    for relative, digest in expected.items():
        path = root / relative
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_mode & 0o022
            or sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError(f"Changed or unsafe Steam session file: {path}")
        actual.add(relative)
    if exact:
        listed = set()
        allowed_directories = {
            parent
            for relative in expected
            for parent in relative.parents
            if parent != Path('.')
        }
        for path in root.rglob("*"):
            info = path.lstat()
            relative = path.relative_to(root)
            if stat.S_ISDIR(info.st_mode):
                if relative not in allowed_directories:
                    raise ValueError(f"Unlisted Steam session directory: {path}")
                continue
            if relative != Path(MANIFEST_NAME):
                listed.add(relative)
        if listed != actual:
            raise ValueError(f"Steam session inventory mismatch: {sorted(listed ^ actual)}")
    steam_id = (root / STEAM_ID_NAME).read_text(encoding="ascii").strip()
    if not re.fullmatch(r"7656119\d{10}", steam_id):
        raise ValueError("Invalid Steam ID in session snapshot")
    return steam_id


def install_snapshot(snapshot: Path, steam: Path) -> str:
    snapshot = resolve_owned_directory(snapshot, "Steam session snapshot")
    steam = resolve_owned_directory(steam, "Steam destination")
    steam_id = validate_snapshot(snapshot, exact=True)
    expected = read_manifest(snapshot)
    for relative in sorted(expected, key=lambda path: path.as_posix()):
        if relative == Path(STEAM_ID_NAME):
            continue
        source = snapshot / relative
        target = steam / relative
        current = steam
        for part in relative.parts[:-1]:
            current /= part
            if current.exists() and current.is_symlink():
                raise ValueError(f"Linked Steam session destination: {current}")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(source.read_bytes())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, target)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        if sha256(target.read_bytes()).hexdigest() != expected[relative]:
            raise ValueError(f"Steam session installation mismatch: {target}")
    return steam_id


def parse_client_inventory(steam: Path) -> dict[Path, tuple[int, int]]:
    inventory = steam / CLIENT_INVENTORY
    require_unlinked_path(steam, inventory)
    info = inventory.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o022
    ):
        raise ValueError(f"Unsafe Steam installed-file inventory: {inventory}")

    entries: dict[str, tuple[Path, int, int]] = {}
    total_size = 0
    for number, raw in enumerate(inventory.read_text(encoding="utf-8", errors="strict").splitlines(), 1):
        if re.fullmatch(r"(?:OSVER|VERSION)=\d+|SHA1=[0-9A-Fa-f]{40}", raw):
            continue
        try:
            windows_name, metadata = raw.rsplit(",", 1)
            size_text, _, crc_text = metadata.split(";")
            size = int(size_text)
            crc = int(crc_text)
        except (ValueError, UnicodeError):
            raise ValueError(f"Invalid Steam package inventory line {number}")
        if size < 0:
            continue
        windows_path = PureWindowsPath(windows_name)
        if windows_path.is_absolute() or ".." in windows_path.parts:
            raise ValueError(f"Unsafe Steam package path: {windows_name}")
        relative = Path(*windows_path.parts)
        if not relative.parts or any("\n" in part or "\r" in part for part in relative.parts):
            raise ValueError(f"Unsafe Steam package path: {windows_name}")
        if {part.lower() for part in relative.parts} & CLIENT_EXCLUDED_PARTS:
            raise ValueError(f"Mutable state listed as Steam client content: {windows_name}")
        if size > MAX_CLIENT_FILE_SIZE:
            raise ValueError(f"Steam client file exceeds size limit: {windows_name}")
        total_size += size
        if total_size > MAX_CLIENT_SNAPSHOT_SIZE:
            raise ValueError("Steam client snapshot exceeds size limit")
        key = relative.as_posix().lower()
        candidate = (relative, size, crc)
        if key in entries:
            raise ValueError(f"Duplicate Steam package entry: {windows_name}")
        entries[key] = candidate
    parsed = {relative: (size, crc) for relative, size, crc in entries.values()}
    if Path("steam.exe") not in parsed:
        raise ValueError("Steam package inventory does not contain steam.exe")
    return parsed


def read_client_snapshot_manifest(root: Path) -> dict[Path, str]:
    manifest = root / CLIENT_MANIFEST_NAME
    info = manifest.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o022
    ):
        raise ValueError(f"Invalid Steam client snapshot manifest: {manifest}")
    expected: dict[Path, str] = {}
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError(f"Invalid Steam client snapshot manifest line {number}")
        relative = Path(match.group(2))
        if relative.is_absolute() or ".." in relative.parts or relative in expected:
            raise ValueError(f"Unsafe or duplicate Steam client path: {relative}")
        expected[relative] = match.group(1)
    required = {Path("steam.exe"), CLIENT_INVENTORY}
    if not required <= set(expected):
        raise ValueError("Steam client snapshot manifest is missing required files")
    return expected


def validate_client_snapshot(root: Path) -> None:
    root = resolve_owned_directory(root, "Steam client snapshot")
    expected = read_client_snapshot_manifest(root)
    actual: set[Path] = set()
    allowed_directories = {
        parent
        for relative in expected
        for parent in relative.parents
        if parent != Path(".")
    }
    for path in root.rglob("*"):
        info = path.lstat()
        relative = path.relative_to(root)
        if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise ValueError(f"Unsafe Steam client snapshot entry: {path}")
        if stat.S_ISDIR(info.st_mode):
            if relative not in allowed_directories:
                raise ValueError(f"Unlisted Steam client snapshot directory: {path}")
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError(f"Invalid Steam client snapshot file: {path}")
        if relative == Path(CLIENT_MANIFEST_NAME):
            continue
        actual.add(relative)
        digest = expected.get(relative)
        if digest is None or sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Unlisted or changed Steam client snapshot file: {path}")
    if actual != set(expected):
        raise ValueError(f"Steam client snapshot inventory mismatch: {sorted(actual ^ set(expected))}")


def create_client_snapshot(steam: Path, snapshot: Path) -> None:
    steam = resolve_owned_directory(steam, "Steam root")
    if snapshot.exists() or snapshot.is_symlink():
        raise ValueError(f"Steam client snapshot already exists: {snapshot}")
    entries = parse_client_inventory(steam)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{snapshot.name}.", dir=snapshot.parent))
    temporary.chmod(0o700)
    try:
        hashes: list[str] = []
        for relative, (expected_size, expected_crc) in sorted(
            entries.items(), key=lambda item: item[0].as_posix().lower()
        ):
            source = steam / relative
            require_unlinked_path(steam, source)
            info = source.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_nlink != 1
                or info.st_mode & 0o022
                or info.st_size != expected_size
            ):
                raise ValueError(f"Invalid installed Steam client file: {source}")
            data = source.read_bytes()
            if zlib.crc32(data) != expected_crc:
                raise ValueError(f"Steam package CRC mismatch: {source}")
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            target.write_bytes(data)
            target.chmod(0o600)
            hashes.append(f"{sha256(data).hexdigest()}  {relative.as_posix()}")

        inventory = steam / CLIENT_INVENTORY
        inventory_data = inventory.read_bytes()
        inventory_target = temporary / CLIENT_INVENTORY
        inventory_target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        inventory_target.write_bytes(inventory_data)
        inventory_target.chmod(0o600)
        hashes.append(f"{sha256(inventory_data).hexdigest()}  {CLIENT_INVENTORY.as_posix()}")
        manifest = temporary / CLIENT_MANIFEST_NAME
        manifest.write_text("\n".join(hashes) + "\n", encoding="utf-8")
        manifest.chmod(0o600)
        validate_client_snapshot(temporary)
        temporary.rename(snapshot)
    except BaseException:
        shutil.rmtree(temporary)
        raise


def install_client_snapshot(snapshot: Path, steam: Path) -> None:
    snapshot = resolve_owned_directory(snapshot, "Steam client snapshot")
    steam = resolve_owned_directory(steam, "Steam destination")
    validate_client_snapshot(snapshot)
    expected = read_client_snapshot_manifest(snapshot)
    for relative in sorted(expected, key=lambda path: path.as_posix()):
        source = snapshot / relative
        target = steam / relative
        current = steam
        for part in relative.parts[:-1]:
            current /= part
            if current.exists() and current.is_symlink():
                raise ValueError(f"Linked Steam client destination: {current}")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(source.read_bytes())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, target)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        if sha256(target.read_bytes()).hexdigest() != expected[relative]:
            raise ValueError(f"Steam client installation mismatch: {target}")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("steam", type=Path)
    create.add_argument("snapshot", type=Path)
    validate = subparsers.add_parser("validate")
    validate.add_argument("snapshot", type=Path)
    install = subparsers.add_parser("install")
    install.add_argument("snapshot", type=Path)
    install.add_argument("steam", type=Path)
    steam_id = subparsers.add_parser("steam-id")
    steam_id.add_argument("snapshot", type=Path)
    client_create = subparsers.add_parser("client-create")
    client_create.add_argument("steam", type=Path)
    client_create.add_argument("snapshot", type=Path)
    client_validate = subparsers.add_parser("client-validate")
    client_validate.add_argument("snapshot", type=Path)
    client_install = subparsers.add_parser("client-install")
    client_install.add_argument("snapshot", type=Path)
    client_install.add_argument("steam", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "create":
        create_snapshot(arguments.steam, arguments.snapshot)
    elif arguments.command == "validate":
        validate_snapshot(arguments.snapshot, exact=True)
    elif arguments.command == "install":
        print(install_snapshot(arguments.snapshot, arguments.steam))
    elif arguments.command == "steam-id":
        print(validate_snapshot(arguments.snapshot, exact=True))
    elif arguments.command == "client-create":
        create_client_snapshot(arguments.steam, arguments.snapshot)
    elif arguments.command == "client-validate":
        validate_client_snapshot(arguments.snapshot)
    else:
        install_client_snapshot(arguments.snapshot, arguments.steam)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
