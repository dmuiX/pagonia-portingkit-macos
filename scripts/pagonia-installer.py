#!/usr/bin/env python3
"""Pagonia macOS installer: one state machine for Fresh and Resume."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "pagonia-state.py"
MANAGED = ROOT / "pagonia-managed-state.py"
PARENT = Path("/private/tmp")
PREFIX = "Pagonia-GPTK4b3-deployment."
DESTINATION = Path("/Applications/Pioneers of Pagonia.app")


def interrupt(_signum: int, _frame: object) -> None:
    """Enter normal Python unwinding so owned children and staging are cleaned."""
    raise KeyboardInterrupt


def install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, interrupt)


def load(filename: str):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_").replace(".", "_"),
                                                   ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def helper(path: Path, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(path), *map(str, args)],
        capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"{path.name} failed")
    return result.stdout.strip()


def inventory() -> dict:
    return json.loads(helper(
        MANAGED, "list", "--destination", str(DESTINATION),
        "--staging-parent", str(PARENT)))


def confirmation(items: list[dict], assume_yes: bool) -> None:
    for item in items:
        print(f"  {item['kind']}: {item['path']}")
    if not items:
        print("  No managed state found.")
        return
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise RuntimeError("Deletion requires a terminal or --yes")
    if input("Delete ALL verified managed state permanently? [y/N] ").strip().lower() not in ("y", "yes"):
        raise RuntimeError("Managed-state deletion cancelled")


def remove_managed(assume_yes: bool) -> None:
    found = inventory()
    print("Managed state to delete:")
    confirmation(found["managed"], assume_yes)
    for item in found["unverified"]:
        print(f"  Unverified name match preserved: {item['path']}")
    if found["managed"]:
        expected_arguments = [
            argument
            for item in found["managed"]
            for argument in ("--expected-path", item["path"])
        ]
        deleted = json.loads(helper(
            MANAGED, "delete", "--destination", str(DESTINATION),
            "--staging-parent", str(PARENT), *expected_arguments))
        for item in deleted["deleted"]:
            print(f"  Deleted: {item['path']}")


def reject_unmanaged_destination(found: dict) -> None:
    if any(item["path"] == str(DESTINATION) for item in found["unverified"]):
        raise RuntimeError(
            f"Refusing to replace unmanaged destination: {DESTINATION}"
        )


def choose_state(resume: str | None) -> tuple[str, str | None]:
    flow = load("pagonia-flow.py")

    def validate(value: str) -> None:
        candidate = Path(value)
        print(f"  Validating Resume candidate: {candidate}", flush=True)
        if not candidate.is_absolute() or candidate.parent != PARENT:
            raise RuntimeError("--resume must name a direct child of /private/tmp")
        helper(STATE, "highest", "--parent", str(PARENT), "--path", value,
               "--evidence-validator", *flow.depot_validator(candidate))

    if resume:
        candidate = Path(resume)
        if not candidate.is_absolute() or candidate.parent != PARENT:
            raise RuntimeError("--resume must name a direct child of /private/tmp")

    found = inventory()
    reject_unmanaged_destination(found)

    staging = [item["path"] for item in found["managed"]
               if item["kind"] == "staging-deployment"]
    if resume:
        if resume not in staging:
            raise RuntimeError(
                f"Resume path is not verified managed staging: {resume}"
            )
        validate(resume)
        return "resume", resume
    for path in staging:
        validate(path)
    if len(staging) > 1:
        raise RuntimeError("Multiple validated staging deployments; use --resume PATH:\n"
                           + "\n".join(staging))
    return ("resume", staging[0]) if staging else ("fresh", None)


@contextlib.contextmanager
def installer_lock():
    path = PARENT / f"Pagonia-GPTK4b3-installer-{os.getuid()}.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or (
            stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise RuntimeError("Installer lock has unsafe permissions or owner")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another Pagonia installer is already running") from exc
        yield
    finally:
        os.close(descriptor)


def current_destination_identity() -> tuple[int, int] | None:
    if not os.path.lexists(DESTINATION):
        return None
    metadata = DESTINATION.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or DESTINATION.is_symlink():
        raise RuntimeError(f"Unsafe destination: {DESTINATION}")
    return metadata.st_dev, metadata.st_ino


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--fresh", action="store_true",
                       help="Delete managed state and start a new deployment")
    modes.add_argument("--resume", metavar="PATH",
                       help="Resume the specified validated staging deployment")
    modes.add_argument("--delete", action="store_true",
                       help="Remove verified managed state without installing")
    parser.add_argument("--yes", action="store_true",
                        help="Confirm only global managed-state deletion")
    return parser.parse_args()


def main() -> int:
    install_signal_handlers()
    arguments = cli()
    if os.geteuid() == 0:
        raise RuntimeError("Do not run the installer as root")
    if sys.platform != "darwin":
        raise RuntimeError("Pagonia deployment requires macOS")
    if not PARENT.is_dir() or PARENT.is_symlink():
        raise RuntimeError("Invalid system staging parent")
    with installer_lock():
        if arguments.delete:
            remove_managed(arguments.yes)
            return 0

        preflight = load("pagonia-preflight.py")
        gptk = preflight.locate_gptk()
        if arguments.fresh:
            # Authenticate inputs before destructive managed-state removal.
            preflight.preflight(gptk)
            remove_managed(arguments.yes)
            reject_unmanaged_destination(inventory())
            mode, path = "fresh", None
        else:
            print("State selection: Discovering managed Fresh/Resume state...", flush=True)
            mode, path = choose_state(arguments.resume)
        print(f"Deployment mode: {mode}", flush=True)
        if path:
            print(f"Validated staging deployment: {path}", flush=True)
        expected_destination_identity = current_destination_identity()
        flow = load("pagonia-flow.py")
        flow.deploy(
            mode,
            Path(path) if path else None,
            gptk,
            preflight_done=arguments.fresh,
            destination_identity=expected_destination_identity,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted; validated Resume staging is preserved.", file=sys.stderr)
        raise SystemExit(130)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
