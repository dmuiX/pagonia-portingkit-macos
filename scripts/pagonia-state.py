#!/usr/bin/env python3
"""Create and validate durable Pagonia staging deployment state."""

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import NoReturn

from pagonia_common import (
    STAGING_MARKER_NAME,
    STAGING_SCHEMA,
    STAGING_STATES,
    owner_controlled,
    staging_marker,
    staging_marker_state,
)

MARKER_NAME = STAGING_MARKER_NAME
EVIDENCE_NAME = ".pagonia-artifact-evidence.json"
SCHEMA = STAGING_SCHEMA
INCOMPLETE, COMPLETE = STAGING_STATES
STATES = STAGING_STATES
EXPECTED_BUILD = 25784167
EXPECTED_FILE_COUNT = 856
EXPECTED_TOTAL_SIZE = 7672576380


class StateError(Exception):
    """A staging deployment failed closed validation."""


def fail(message: str) -> NoReturn:
    raise StateError(message)


def absolute(path: str) -> Path:
    return Path(os.path.abspath(path))


def validate_parent(value: str) -> Path:
    parent = absolute(value)
    try:
        metadata = parent.lstat()
    except OSError as error:
        fail(f"Cannot inspect parent {parent}: {error}")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        fail(f"Parent must be a non-symlink directory: {parent}")
    if not owner_controlled(parent):
        fail(f"Parent must be owner-controlled by uid {os.getuid()}: {parent}")
    return parent


def validate_prefix(prefix: str) -> None:
    if not prefix or prefix in (".", "..") or Path(prefix).name != prefix:
        fail("Prefix must be a non-empty file-name prefix")


def staging_path(parent_value: str, path_value: str) -> tuple[Path, Path]:
    parent = validate_parent(parent_value)
    path = absolute(path_value)
    if path.parent != parent:
        fail(f"Staging deployment is not a direct child of {parent}: {path}")
    return parent, path


def open_staging(parent: Path, path: Path) -> tuple[int, int, tuple[int, int]]:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent_fd = staging_fd = -1
    try:
        parent_fd = os.open(parent, flags)
        staging_fd = os.open(path.name, flags, dir_fd=parent_fd)
        metadata = os.fstat(staging_fd)
        identity = (metadata.st_dev, metadata.st_ino)
        if metadata.st_uid != os.getuid():
            fail(f"Staging deployment is not owned by uid {os.getuid()}: {path}")
        if stat.S_IMODE(metadata.st_mode) != 0o700:
            fail(f"Staging deployment must have mode 0700: {path}")
        require_identity(parent_fd, path, identity)
        return parent_fd, staging_fd, identity
    except BaseException:
        if staging_fd >= 0:
            os.close(staging_fd)
        if parent_fd >= 0:
            os.close(parent_fd)
        raise


def require_identity(parent_fd: int, path: Path, expected: tuple[int, int]) -> None:
    try:
        metadata = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        fail(f"Staging deployment identity changed: {path}: {error}")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        fail(f"Staging deployment must be a non-symlink directory: {path}")
    if (metadata.st_dev, metadata.st_ino) != expected:
        fail(f"Staging deployment identity changed: {path}")


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def read_private_json(
    directory_fd: int, directory: Path, name: str, description: str
) -> dict[str, object]:
    path = directory / name
    descriptor = -1
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            fail(f"{description.capitalize()} must be a regular, non-symlink file: {path}")
        if metadata.st_uid != os.getuid():
            fail(f"{description.capitalize()} is not owned by uid {os.getuid()}: {path}")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            fail(f"{description.capitalize()} must have mode 0600: {path}")
        with os.fdopen(descriptor, "r", encoding="utf-8") as source:
            descriptor = -1
            value = json.load(source, object_pairs_hook=reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        fail(f"Missing or invalid {description} JSON {path}: {error}")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if type(value) is not dict:
        fail(f"Invalid {description} schema: expected an object")
    return value


def validate_marker(value: dict[str, object]) -> str:
    try:
        return staging_marker_state(value)
    except ValueError as error:
        fail(str(error))


def validate_evidence(value: dict[str, object]) -> None:
    if set(value) != {"schema", "build", "file_count", "total_size", "sha256"}:
        fail("Invalid artifact evidence schema")
    expected_integers = {
        "schema": SCHEMA,
        "build": EXPECTED_BUILD,
        "file_count": EXPECTED_FILE_COUNT,
        "total_size": EXPECTED_TOTAL_SIZE,
    }
    for key, expected in expected_integers.items():
        if type(value[key]) is not int or value[key] != expected:
            fail(f"Invalid artifact evidence {key}")
    digest = value["sha256"]
    if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        fail("Invalid artifact evidence SHA-256 digest")


def validate_artifacts(argv: list[str] | None) -> None:
    if not argv:
        fail("Depot-complete state requires an explicit evidence-validator command")
    try:
        result = subprocess.run(
            argv,
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        fail(f"Evidence validator could not run: {error}")
    if result.returncode != 0:
        detail = result.stderr.strip()
        suffix = f": {detail}" if detail else ""
        fail(f"Evidence validator rejected the depot{suffix}")


def read_state(
    staging_fd: int, path: Path, evidence_validator: list[str] | None = None
) -> str:
    marker = read_private_json(staging_fd, path, MARKER_NAME, "staging marker")
    state = validate_marker(marker)
    if state == COMPLETE:
        evidence = read_private_json(staging_fd, path, EVIDENCE_NAME, "artifact evidence")
        validate_evidence(evidence)
        validate_artifacts(evidence_validator)
    return state


def highest_state(
    parent_value: str,
    path_value: str,
    evidence_validator: list[str] | None = None,
) -> str:
    parent, path = staging_path(parent_value, path_value)
    parent_fd, staging_fd, identity = open_staging(parent, path)
    try:
        state = read_state(staging_fd, path, evidence_validator)
        require_identity(parent_fd, path, identity)
        return state
    finally:
        os.close(staging_fd)
        os.close(parent_fd)


def atomic_json(directory_fd: int, name: str, value: dict[str, object]) -> None:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = -1
    temporary = f"{name}.tmp-{os.getpid()}-{os.urandom(8).hex()}"
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        temporary = ""
        os.fsync(directory_fd)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except FileNotFoundError:
                pass


def marker_value(state: str) -> dict[str, object]:
    return staging_marker(state)


def command_create(arguments: argparse.Namespace) -> None:
    parent = validate_parent(arguments.parent)
    validate_prefix(arguments.prefix)
    path = Path(tempfile.mkdtemp(prefix=arguments.prefix, dir=parent))
    os.chmod(path, 0o700)
    try:
        directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            atomic_json(directory_fd, MARKER_NAME, marker_value(INCOMPLETE))
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            path.rmdir()
        except OSError:
            pass
        raise
    print(path)


def command_validate(arguments: argparse.Namespace) -> None:
    highest_state(arguments.parent, arguments.path, arguments.evidence_validator)
    print("valid")


def command_highest(arguments: argparse.Namespace) -> None:
    print(
        highest_state(
            arguments.parent, arguments.path, arguments.evidence_validator
        )
    )


def command_checkpoint(arguments: argparse.Namespace) -> None:
    parent, path = staging_path(arguments.parent, arguments.path)
    parent_fd, staging_fd, identity = open_staging(parent, path)
    try:
        current = read_state(
            staging_fd,
            path,
            arguments.evidence_validator if arguments.state == COMPLETE else None,
        )
        if current == COMPLETE and arguments.state == INCOMPLETE:
            fail("Cannot regress a depot-complete staging deployment")
        if arguments.state == COMPLETE:
            validate_artifacts(arguments.evidence_validator)
            require_identity(parent_fd, path, identity)
            digest = arguments.artifact_sha256
            if digest is None or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                fail("Depot completion requires a lowercase SHA-256 artifact digest")
            evidence = {
                "schema": SCHEMA,
                "build": EXPECTED_BUILD,
                "file_count": EXPECTED_FILE_COUNT,
                "total_size": EXPECTED_TOTAL_SIZE,
                "sha256": digest,
            }
            require_identity(parent_fd, path, identity)
            atomic_json(staging_fd, EVIDENCE_NAME, evidence)
        elif arguments.artifact_sha256 is not None:
            fail("Artifact digest is only valid for depot-complete")
        require_identity(parent_fd, path, identity)
        atomic_json(staging_fd, MARKER_NAME, marker_value(arguments.state))
        require_identity(parent_fd, path, identity)
    finally:
        os.close(staging_fd)
        os.close(parent_fd)
    print(arguments.state)


def command_select(arguments: argparse.Namespace) -> None:
    parent = validate_parent(arguments.parent)
    validate_prefix(arguments.prefix)
    valid: list[Path] = []
    try:
        children = list(parent.iterdir())
    except OSError as error:
        fail(f"Cannot list staging parent {parent}: {error}")
    for path in children:
        if not path.name.startswith(arguments.prefix):
            continue
        try:
            highest_state(
                str(parent), str(path), arguments.evidence_validator
            )
        except StateError:
            continue
        valid.append(path)
    valid.sort(key=lambda path: path.name)
    if not valid:
        print("fresh")
    elif len(valid) == 1:
        print(valid[0])
    else:
        paths = "\n".join(str(path) for path in valid)
        fail(f"Multiple valid staging deployments; select one explicitly:\n{paths}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create")
    create.add_argument("--parent", required=True)
    create.add_argument("--prefix", required=True)
    create.set_defaults(handler=command_create)

    for name, handler in (("validate", command_validate), ("highest", command_highest)):
        command = commands.add_parser(name)
        command.add_argument("--parent", required=True)
        command.add_argument("--path", required=True)
        command.add_argument("--evidence-validator", nargs=argparse.REMAINDER)
        command.set_defaults(handler=handler)

    checkpoint = commands.add_parser("checkpoint")
    checkpoint.add_argument("--parent", required=True)
    checkpoint.add_argument("--path", required=True)
    checkpoint.add_argument("--state", required=True, choices=STATES)
    checkpoint.add_argument("--artifact-sha256")
    checkpoint.add_argument("--evidence-validator", nargs=argparse.REMAINDER)
    checkpoint.set_defaults(handler=command_checkpoint)

    select = commands.add_parser("select")
    select.add_argument("--parent", required=True)
    select.add_argument("--prefix", required=True)
    select.add_argument("--evidence-validator", nargs=argparse.REMAINDER)
    select.set_defaults(handler=command_select)
    return result


def main() -> int:
    try:
        arguments = parser().parse_args()
        arguments.handler(arguments)
        return 0
    except StateError as error:
        print(f"pagonia-state: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"pagonia-state: filesystem error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
