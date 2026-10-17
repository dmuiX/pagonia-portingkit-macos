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
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "pagonia-state.py"
MANAGED = ROOT / "pagonia-managed-state.py"
PARENT = Path("/private/tmp")
PREFIX = "Pagonia-GPTK4b3-deployment."
DESTINATION = Path("/Applications/Pioneers of Pagonia.app")


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
        deleted = json.loads(helper(
            MANAGED, "delete", "--destination", str(DESTINATION),
            "--staging-parent", str(PARENT)))
        for item in deleted["deleted"]:
            print(f"  Deleted: {item['path']}")


def choose_state(resume: str | None) -> tuple[str, str | None]:
    flow = load("pagonia-flow.py")

    def validate(value: str) -> None:
        candidate = Path(value)
        if not candidate.is_absolute() or candidate.parent != PARENT:
            raise RuntimeError("--resume must name a direct child of /private/tmp")
        helper(STATE, "highest", "--parent", str(PARENT), "--path", value,
               "--evidence-validator", *flow.depot_validator(candidate))

    if resume:
        validate(resume)
        return "resume", resume

    found = inventory()
    staging = [item["path"] for item in found["managed"]
               if item["kind"] == "staging-deployment"]
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


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--fresh", action="store_true",
                       help="Delete managed state and start a new deployment")
    modes.add_argument("--resume", metavar="PATH",
                       help="Resume the specified validated staging deployment")
    modes.add_argument("--delete", action="store_true",
                       help="Remove verified managed state without installing")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Confirm only global managed-state deletion")
    parser.add_argument("--gptk-lib", type=Path, metavar="PATH",
                        help="Mounted GPTK 4.0 beta 3 redist/lib directory")
    return parser.parse_args()


def main() -> int:
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
        gptk = preflight.locate_gptk(arguments.gptk_lib)
        if arguments.fresh:
            # Authenticate inputs before destructive managed-state removal.
            preflight.preflight(gptk)
            remove_managed(arguments.yes)
            mode, path = "fresh", None
        else:
            mode, path = choose_state(arguments.resume)
        print(f"Deployment mode: {mode}", flush=True)
        if path:
            print(f"Validated staging deployment: {path}", flush=True)
        flow = load("pagonia-flow.py")
        flow.deploy(mode, Path(path) if path else None, gptk)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
