#!/usr/bin/env python3
"""New Pagonia state-selection orchestrator (unreleased implementation)."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "pagonia-state.py"
MANAGED = ROOT / "pagonia-managed-state.py"
PARENT = Path("/private/tmp")
PREFIX = "Pagonia-GPTK4b3-deployment."
DESTINATION = Path("/Applications/Pioneers of Pagonia.app")


def helper(path: Path, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(path), *args],
        capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"{path.name} failed")
    return result.stdout.strip()


def inventory() -> dict:
    return json.loads(helper(
        MANAGED, "list", "--destination", str(DESTINATION),
        "--staging-parent", str(PARENT),
    ))


def confirmation(items: list[dict], assume_yes: bool) -> None:
    for item in items:
        print(f"  {item['kind']}: {item['path']}")
    if not items:
        print("  No managed state found.")
        return
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise RuntimeError("Deletion requires a terminal or explicit --yes")
    answer = input("Delete ALL verified managed state permanently? [y/N] ")
    if answer.strip().lower() not in ("y", "yes"):
        raise RuntimeError("Deletion cancelled")


def remove_managed(assume_yes: bool) -> None:
    found = inventory()
    print("Managed state to delete:")
    confirmation(found["managed"], assume_yes)
    for suspect in found["unverified"]:
        print(f"  Unverified name match (preserved): {suspect['path']}")
    if found["managed"]:
        deleted = json.loads(helper(
            MANAGED, "delete", "--destination", str(DESTINATION),
            "--staging-parent", str(PARENT),
        ))
        for item in deleted["deleted"]:
            print(f"  Deleted: {item['path']}")


def choose_state(resume: str | None) -> tuple[str, str | None]:
    if resume:
        candidate = Path(resume)
        if not candidate.is_absolute() or candidate.parent != PARENT:
            raise RuntimeError("--resume must name a direct child of /private/tmp")
        helper(STATE, "validate", "--parent", str(PARENT), "--path", resume)
        return "resume", resume
    result = helper(
        STATE, "select", "--parent", str(PARENT), "--prefix", PREFIX,
    )
    if result == "fresh":
        return "fresh", None
    return "resume", result


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Modular Pagonia installer: managed state and durable resume."
    )
    exclusive = parser.add_mutually_exclusive_group()
    exclusive.add_argument("--fresh", action="store_true")
    exclusive.add_argument("--resume", metavar="PATH")
    exclusive.add_argument("--delete", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Confirm only managed-state deletion")
    return parser.parse_args()


def main() -> int:
    args = cli()
    if os.geteuid() == 0:
        raise RuntimeError("Do not run the installer as root")
    if sys.platform != "darwin":
        raise RuntimeError("The deployment requires macOS")
    if not PARENT.is_dir():
        raise RuntimeError("Missing /private/tmp staging parent")

    # State selection is non-mutating unless an explicit mode requests deletion.
    if args.delete:
        remove_managed(args.yes)
        return 0
    if args.fresh:
        remove_managed(args.yes)
        mode, path = "fresh", None
    else:
        mode, path = choose_state(args.resume)
    print(f"Selected deployment mode: {mode}")
    if path:
        print(f"Validated staging deployment: {path}")

    # No untrusted downloader/runtime is executed at this incomplete boundary.
    # The next module must verify immutable inputs and process ownership before
    # creating or consuming a staging deployment.
    raise RuntimeError(
        "New modular Wine/Steam deployment phases are not implemented yet; "
        "no Wine runtime has been executed."
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
