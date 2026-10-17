#!/usr/bin/env python3
"""Behavioral tests for durable staging deployment state."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/pagonia-state.py"
PREFIX = "Pagonia-GPTK4b3-deployment."
MARKER = ".pagonia-state.json"
EVIDENCE = ".pagonia-artifact-evidence.json"
DIGEST = "0123456789abcdef" * 4


def make_validator(directory: Path) -> Path:
    validator = directory / "fixture evidence validator.py"
    validator.write_text(
        """#!/usr/bin/env python3
import pathlib
import sys

artifact = pathlib.Path(sys.argv[1])
if len(sys.argv) != 2 or artifact.read_text(encoding="utf-8") != "trusted-artifact":
    raise SystemExit(1)
""",
        encoding="utf-8",
    )
    return validator


def validator_arguments(validator: Path, staging: Path) -> tuple[object, ...]:
    return (
        "--evidence-validator",
        sys.executable,
        validator,
        staging / "depot.artifact",
    )


def run(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(HELPER), *(str(argument) for argument in arguments)],
        check=False,
        capture_output=True,
        text=True,
    )


def require_success(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def create(parent: Path) -> Path:
    output = require_success(run("create", "--parent", parent, "--prefix", PREFIX))
    staging = Path(output)
    assert staging.parent == parent
    assert staging.name.startswith(PREFIX)
    assert staging.stat().st_mode & 0o777 == 0o700
    assert staging.lstat().st_uid == os.getuid()
    assert (staging / MARKER).stat().st_mode & 0o777 == 0o600
    return staging


def checkpoint(staging: Path, parent: Path, state: str, *extra: object) -> subprocess.CompletedProcess[str]:
    return run(
        "checkpoint",
        "--parent",
        parent,
        "--path",
        staging,
        "--state",
        state,
        *extra,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        parent = Path(directory)

        # Creation establishes the only safe initial durable classification.
        staging = create(parent)
        assert require_success(run("validate", "--parent", parent, "--path", staging)) == "valid"
        assert require_success(run("highest", "--parent", parent, "--path", staging)) == "downloader-incomplete"
        assert require_success(run("select", "--parent", parent, "--prefix", PREFIX)) == str(staging)

        # A caller-supplied digest cannot establish depot completion. The
        # explicit validator argv must prove the real artifact without a shell.
        validator = make_validator(parent)
        (staging / "depot.artifact").write_text("untrusted", encoding="utf-8")
        result = checkpoint(
            staging,
            parent,
            "depot-complete",
            "--artifact-sha256",
            DIGEST,
            *validator_arguments(validator, staging),
        )
        assert result.returncode != 0
        assert require_success(run("highest", "--parent", parent, "--path", staging)) == "downloader-incomplete"

        (staging / "depot.artifact").write_text("trusted-artifact", encoding="utf-8")
        result = checkpoint(
            staging,
            parent,
            "depot-complete",
            "--artifact-sha256",
            DIGEST,
            *validator_arguments(validator, staging),
        )
        assert require_success(result) == "depot-complete"
        result = run("highest", "--parent", parent, "--path", staging)
        assert result.returncode != 0
        assert "validator" in result.stderr.lower()
        assert require_success(
            run(
                "highest",
                "--parent",
                parent,
                "--path",
                staging,
                *validator_arguments(validator, staging),
            )
        ) == "depot-complete"
        result = checkpoint(staging, parent, "downloader-incomplete")
        assert result.returncode != 0
        assert require_success(
            run(
                "highest",
                "--parent",
                parent,
                "--path",
                staging,
                *validator_arguments(validator, staging),
            )
        ) == "depot-complete"
        evidence = json.loads((staging / EVIDENCE).read_text())
        assert evidence == {
            "build": 25784167,
            "file_count": 856,
            "schema": 1,
            "sha256": DIGEST,
            "total_size": 7672576380,
        }

        # An invalid checkpoint cannot replace the last valid marker.
        marker_before = (staging / MARKER).read_bytes()
        result = checkpoint(
            staging,
            parent,
            "depot-complete",
            "--artifact-sha256",
            "not-a-sha256",
        )
        assert result.returncode != 0
        assert (staging / MARKER).read_bytes() == marker_before
        assert not list(staging.glob(".pagonia-state.json.tmp-*"))
        result = checkpoint(
            staging,
            parent,
            "depot-complete",
            "--artifact-sha256",
            ("ab" * 31) + "  ",
        )
        assert result.returncode != 0
        assert (staging / MARKER).read_bytes() == marker_before

        # A marker cannot establish depot completion by itself.
        (staging / EVIDENCE).unlink()
        result = run("highest", "--parent", parent, "--path", staging)
        assert result.returncode != 0
        assert "evidence" in result.stderr.lower()

        # Evidence must have the exact schema and pinned depot identity.
        evidence_path = staging / EVIDENCE
        evidence_path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "build": 25784168,
                    "file_count": 856,
                    "total_size": 7672576380,
                    "sha256": DIGEST,
                }
            )
        )
        os.chmod(evidence_path, 0o600)
        assert run(
            "validate",
            "--parent",
            parent,
            "--path",
            staging,
            *validator_arguments(validator, staging),
        ).returncode != 0

        # Selection ignores unproven name matches and fails closed on ambiguity.
        staging = create(parent)
        unproven = parent / f"{PREFIX}unproven"
        unproven.mkdir(mode=0o700)
        assert require_success(run("select", "--parent", parent, "--prefix", PREFIX)) == str(staging)
        second = create(parent)
        result = run("select", "--parent", parent, "--prefix", PREFIX)
        assert result.returncode != 0
        assert str(staging) in result.stderr
        assert str(second) in result.stderr

    with tempfile.TemporaryDirectory() as directory:
        parent = Path(directory)
        assert require_success(run("select", "--parent", parent, "--prefix", PREFIX)) == "fresh"

        os.chmod(parent, 0o777)
        assert run("create", "--parent", parent, "--prefix", PREFIX).returncode != 0
        os.chmod(parent, 0o700)

        # A staging deployment must be a private, non-symlinked direct child.
        staging = create(parent)
        os.chmod(staging, 0o755)
        assert run("validate", "--parent", parent, "--path", staging).returncode != 0
        os.chmod(staging, 0o700)

        nested_parent = staging / "nested"
        nested_parent.mkdir()
        assert run("validate", "--parent", parent, "--path", nested_parent).returncode != 0

        link = parent / f"{PREFIX}link"
        link.symlink_to(staging, target_is_directory=True)
        assert run("validate", "--parent", parent, "--path", link).returncode != 0

        marker = staging / MARKER
        marker.unlink()
        marker.symlink_to("nested")
        assert run("validate", "--parent", parent, "--path", staging).returncode != 0


if __name__ == "__main__":
    main()
