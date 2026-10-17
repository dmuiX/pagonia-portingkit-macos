#!/usr/bin/env python3
"""Behavior tests for managed-state discovery and deletion."""

from pathlib import Path
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/pagonia-managed-state.py"
STATE_HELPER = ROOT / "scripts/pagonia-state.py"
INSTALLATION_MARKER = Path("Contents/SharedSupport/pagonia-managed-state.json")
STAGING_MARKER = Path(".pagonia-state.json")

INSTALLATION_IDENTITY = {
    "format": 1,
    "kind": "managed-installation",
    "owner": "pagonia-gptk4b3-installer",
    "product": "pioneers-of-pagonia",
}
STAGING_IDENTITY = {
    "schema": 1,
    "kind": "staging-deployment",
    "owner": "pagonia-gptk4b3-installer",
    "product": "pioneers-of-pagonia",
    "state": "downloader-incomplete",
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def make_installation(path: Path, marker: object = INSTALLATION_IDENTITY) -> None:
    write_json(path / INSTALLATION_MARKER, marker)
    os.chmod(path / INSTALLATION_MARKER, 0o600)
    (path / "Contents/MacOS").mkdir()
    with (path / "Contents/Info.plist").open("wb") as stream:
        plistlib.dump(
            {"CFBundleIdentifier": "com.soad1337.pioneersofpagonia.gptk4b3"},
            stream,
        )


def make_staging(path: Path, marker: object = STAGING_IDENTITY) -> None:
    path.mkdir()
    path.chmod(0o700)
    write_json(path / STAGING_MARKER, marker)
    os.chmod(path / STAGING_MARKER, 0o600)


def run_helper(command: str, destination: Path, staging_parent: Path):
    result = subprocess.run(
        [
            sys.executable,
            str(HELPER),
            command,
            "--destination",
            str(destination),
            "--staging-parent",
            str(staging_parent),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout) if result.stdout else None
    return result, payload


class ManagedStateTests(unittest.TestCase):
    def test_list_distinguishes_verified_state_from_broad_name_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            destination = sandbox / "Pioneers of Pagonia.app"
            staging_parent = sandbox / "staging"
            staging_parent.mkdir()
            make_installation(destination)
            managed_staging = staging_parent / "Pagonia-GPTK4b3-deployment.A1b2"
            broad_match = staging_parent / "Pagonia-GPTK4b3-deployment.lookalike"
            make_staging(managed_staging)
            broad_match.mkdir()

            result, payload = run_helper("list", destination, staging_parent)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                payload,
                {
                    "managed": [
                        {"kind": "managed-installation", "path": str(destination)},
                        {"kind": "staging-deployment", "path": str(managed_staging)},
                    ],
                    "unverified": [
                        {"path": str(broad_match), "reason": "broad-name-match"}
                    ],
                },
            )

    def test_list_and_delete_include_verified_publication_backups_and_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            destination = sandbox / "Pioneers of Pagonia.app"
            staging_parent = sandbox / "staging"
            staging_parent.mkdir()
            backup = sandbox / "Pioneers of Pagonia.app.backup-abc123"
            failed = sandbox / "Pioneers of Pagonia.app.failed-def456"
            unverified = sandbox / "Pioneers of Pagonia.app.failed-personal"
            make_installation(backup)
            make_installation(failed)
            unverified.mkdir()

            listed, payload = run_helper("list", destination, staging_parent)
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertEqual(
                payload["managed"],
                [
                    {"kind": "managed-installation", "path": str(backup)},
                    {"kind": "managed-installation", "path": str(failed)},
                ],
            )
            self.assertEqual(
                payload["unverified"],
                [{"path": str(unverified), "reason": "broad-name-match"}],
            )

            deleted, payload = run_helper("delete", destination, staging_parent)
            self.assertEqual(deleted.returncode, 0, deleted.stderr)
            self.assertFalse(backup.exists())
            self.assertFalse(failed.exists())
            self.assertTrue(unverified.exists())

    def test_strict_markers_and_structure_are_not_managed_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            destination = sandbox / "Pioneers of Pagonia.app"
            staging_parent = sandbox / "staging"
            staging_parent.mkdir()
            marker_with_extra_field = dict(INSTALLATION_IDENTITY, release="untrusted")
            make_installation(destination, marker_with_extra_field)
            wrong_kind = staging_parent / "Pagonia-GPTK4b3-deployment.Wrong"
            make_staging(wrong_kind, INSTALLATION_IDENTITY)
            boolean_format = staging_parent / "Pagonia-GPTK4b3-deployment.Boolean"
            make_staging(boolean_format, dict(STAGING_IDENTITY, format=True))
            duplicate_key = staging_parent / "Pagonia-GPTK4b3-deployment.Duplicate"
            make_staging(duplicate_key)
            (duplicate_key / STAGING_MARKER).write_text(
                '{"schema":1,"schema":1,"kind":"staging-deployment",'
                '"owner":"pagonia-gptk4b3-installer",'
                '"product":"pioneers-of-pagonia",'
                '"state":"downloader-incomplete"}',
                encoding="utf-8",
            )

            result, payload = run_helper("list", destination, staging_parent)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["managed"], [])
            self.assertEqual(
                {item["path"] for item in payload["unverified"]},
                {
                    str(destination),
                    str(wrong_kind),
                    str(boolean_format),
                    str(duplicate_key),
                },
            )

    def test_state_created_staging_is_discovered_and_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            destination = sandbox / "Pioneers of Pagonia.app"
            staging_parent = sandbox / "staging"
            staging_parent.mkdir(mode=0o700)
            created = subprocess.run(
                [
                    sys.executable,
                    str(STATE_HELPER),
                    "create",
                    "--parent",
                    str(staging_parent),
                    "--prefix",
                    "Pagonia-GPTK4b3-deployment.",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            staging = Path(created.stdout.strip())

            listed, payload = run_helper("list", destination, staging_parent)
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertEqual(
                payload["managed"],
                [{"kind": "staging-deployment", "path": str(staging)}],
            )

            deleted, payload = run_helper("delete", destination, staging_parent)
            self.assertEqual(deleted.returncode, 0, deleted.stderr)
            self.assertEqual(
                payload["deleted"],
                [{"kind": "staging-deployment", "path": str(staging)}],
            )
            self.assertFalse(staging.exists())

    def test_delete_removes_all_and_only_verified_managed_state_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            destination = sandbox / "Pioneers of Pagonia.app"
            staging_parent = sandbox / "staging"
            staging_parent.mkdir()
            make_installation(destination)
            executable = destination / "Contents/MacOS/wineserver"
            sentinel = sandbox / "candidate-code-ran"
            executable.write_text(f"#!/bin/sh\ntouch {sentinel!s}\n", encoding="utf-8")
            executable.chmod(0o755)
            managed_staging = staging_parent / "Pagonia-GPTK4b3-deployment.DeleteMe"
            make_staging(managed_staging)
            (managed_staging / "payload").write_text("state", encoding="utf-8")
            broad_match = staging_parent / "Pagonia-GPTK4b3-deployment.KeepMe"
            broad_match.mkdir()
            (broad_match / "personal-data").write_text("keep", encoding="utf-8")

            result, payload = run_helper("delete", destination, staging_parent)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                payload,
                {
                    "deleted": [
                        {"kind": "managed-installation", "path": str(destination)},
                        {"kind": "staging-deployment", "path": str(managed_staging)},
                    ],
                    "unverified": [
                        {"path": str(broad_match), "reason": "broad-name-match"}
                    ],
                },
            )
            self.assertFalse(destination.exists())
            self.assertFalse(managed_staging.exists())
            self.assertTrue((broad_match / "personal-data").is_file())
            self.assertFalse(sentinel.exists())

    def test_delete_requires_wine_processes_to_exit(self) -> None:
        process_names = (
            "wineserver",
            r"C:\windows\system32\wine64",
            r"C:\Program Files (x86)\Steam\steam.exe",
            r"C:\windows\system32\winedevice.exe",
        )
        for process_name in process_names:
            with self.subTest(process_name=process_name), tempfile.TemporaryDirectory() as temporary:
                sandbox = Path(temporary)
                destination = sandbox / "Pioneers of Pagonia.app"
                staging_parent = sandbox / "staging"
                staging_parent.mkdir()
                make_installation(destination)
                process = subprocess.Popen(
                    [process_name, "10"], executable="/bin/sleep"
                )
                try:
                    result, payload = run_helper("delete", destination, staging_parent)
                finally:
                    process.terminate()
                    process.wait(timeout=2)

                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(payload)
                self.assertTrue(destination.is_dir())
                self.assertIn("exit all Wine", result.stderr)

    def test_delete_unlinks_internal_symlinks_without_following_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            destination = sandbox / "Pioneers of Pagonia.app"
            staging_parent = sandbox / "staging"
            staging_parent.mkdir()
            managed_staging = staging_parent / "Pagonia-GPTK4b3-deployment.Linked"
            make_staging(managed_staging)
            external = sandbox / "personal-data"
            external.write_text("keep", encoding="utf-8")
            (managed_staging / "runtime-link").symlink_to(external)

            result, payload = run_helper("delete", destination, staging_parent)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(managed_staging.exists())
            self.assertEqual(external.read_text(), "keep")

    def test_delete_refuses_a_symlinked_managed_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            real_destination = sandbox / "real.app"
            destination = sandbox / "Pioneers of Pagonia.app"
            staging_parent = sandbox / "staging"
            staging_parent.mkdir()
            make_installation(real_destination)
            destination.symlink_to(real_destination, target_is_directory=True)

            result, payload = run_helper("delete", destination, staging_parent)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(destination.is_symlink())
            self.assertTrue(real_destination.is_dir())
            self.assertIn(str(destination), {item["path"] for item in payload["unverified"]})

    def test_owner_control_is_required_for_roots_and_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            destination = sandbox / "Pioneers of Pagonia.app"
            staging_parent = sandbox / "staging"
            staging_parent.mkdir(mode=0o700)
            make_installation(destination)
            os.chmod(destination, 0o777)

            result, payload = run_helper("list", destination, staging_parent)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["managed"], [])

            os.chmod(destination, 0o700)
            os.chmod(destination / INSTALLATION_MARKER, 0o666)
            result, payload = run_helper("list", destination, staging_parent)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["managed"], [])

            os.chmod(staging_parent, 0o777)
            result, payload = run_helper("list", destination, staging_parent)
            self.assertNotEqual(result.returncode, 0)
            self.assertIsNone(payload)
            self.assertIn("owner-controlled", result.stderr)

    def test_cli_requires_absolute_sandbox_paths(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(HELPER),
                "list",
                "--destination",
                "relative.app",
                "--staging-parent",
                "relative-staging",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
