#!/usr/bin/env python3
"""Behavior tests for strict, selective Pagonia depot handling."""

from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/pagonia-depot.py"
APP_ID = "2155180"
BUILD_ID = "42"
DEPOT_ID = "2155181"
DEPOT_MANIFEST_ID = "1234567890123456789"
SHARED_DEPOT_ID = "228989"
SHARED_DEPOT_APP_ID = "228980"
STEAM_ID = "76561198000000000"
GAME_NAME = "Pioneers of Pagonia"
FILES = {
    "Pioneers of Pagonia.exe": b"tiny executable\n",
    "Data/config.ini": b"fixture=true\n",
}
TOTAL_SIZE = sum(map(len, FILES.values()))

SPEC = importlib.util.spec_from_file_location("pagonia_depot", HELPER)
assert SPEC is not None and SPEC.loader is not None
DEPOT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DEPOT
SPEC.loader.exec_module(DEPOT)


def expectations(manifest: Path):
    return DEPOT.Expectations(
        manifest=manifest,
        manifest_sha256=sha256(manifest.read_bytes()).hexdigest(),
        app_id=APP_ID,
        build_id=BUILD_ID,
        file_count=len(FILES),
        total_size=TOTAL_SIZE,
        depot_id=DEPOT_ID,
        depot_manifest_id=DEPOT_MANIFEST_ID,
        shared_depot_id=SHARED_DEPOT_ID,
        shared_depot_app_id=SHARED_DEPOT_APP_ID,
    )


def run(
    command: str,
    source: Path,
    trusted_manifest: Path,
    *extra: str,
    success: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [
            "python3",
            str(HELPER),
            command,
            str(source),
            *extra,
            "--manifest",
            str(trusted_manifest),
            "--manifest-sha256",
            sha256(trusted_manifest.read_bytes()).hexdigest(),
            "--expected-app-id",
            APP_ID,
            "--expected-build-id",
            BUILD_ID,
            "--expected-file-count",
            str(len(FILES)),
            "--expected-total-size",
            str(TOTAL_SIZE),
            "--expected-depot-id",
            DEPOT_ID,
            "--expected-depot-manifest-id",
            DEPOT_MANIFEST_ID,
            "--expected-shared-depot-id",
            SHARED_DEPOT_ID,
            "--expected-shared-depot-app-id",
            SHARED_DEPOT_APP_ID,
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if success and result.returncode != 0:
        raise AssertionError(result.stderr)
    if not success and result.returncode == 0:
        raise AssertionError("Command unexpectedly succeeded")
    return result


def appmanifest(*, state: str = "4", build: str = BUILD_ID, depot: str = DEPOT_ID) -> str:
    return f'''"AppState"
{{
    "appid" "{APP_ID}"
    "name" "{GAME_NAME}"
    "StateFlags" "{state}"
    "installdir" "{GAME_NAME}"
    "SizeOnDisk" "{TOTAL_SIZE}"
    "buildid" "{build}"
    "InstalledDepots"
    {{
        "{depot}"
        {{
            "manifest" "{DEPOT_MANIFEST_ID}"
            "size" "{TOTAL_SIZE}"
        }}
    }}
    "SharedDepots"
    {{
        "{SHARED_DEPOT_ID}" "{SHARED_DEPOT_APP_ID}"
    }}
}}
'''


def make_depot(root: Path) -> tuple[Path, Path]:
    steam = root / "Steam"
    game = steam / "steamapps/common" / GAME_NAME
    game.mkdir(parents=True)
    lines = []
    for relative, data in FILES.items():
        path = game / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        lines.append(f"{sha256(data).hexdigest()}  {relative}")
    trusted_manifest = root / "trusted-SHA256SUMS"
    trusted_manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (steam / f"steamapps/appmanifest_{APP_ID}.acf").write_text(
        appmanifest(), encoding="utf-8"
    )
    return steam, trusted_manifest


def main() -> None:
    # Status is a strict readiness gate, not a permissive field scraper.
    with tempfile.TemporaryDirectory() as directory:
        steam, manifest = make_depot(Path(directory))
        assert run("status", steam, manifest).stdout.strip() == (
            f"ready app={APP_ID} build={BUILD_ID} depot={DEPOT_ID}"
        )
        appmanifest_path = steam / f"steamapps/appmanifest_{APP_ID}.acf"
        appmanifest_path.write_text(appmanifest(state="2"), encoding="utf-8")
        run("status", steam, manifest, success=False)
        appmanifest_path.write_text(appmanifest(build="41"), encoding="utf-8")
        run("status", steam, manifest, success=False)
        appmanifest_path.write_text(appmanifest(depot="999"), encoding="utf-8")
        run("status", steam, manifest, success=False)
        appmanifest_path.write_text(
            appmanifest().replace(SHARED_DEPOT_APP_ID, "999999"), encoding="utf-8"
        )
        run("status", steam, manifest, success=False)

    # Validation proves an exact set of regular, unlinked, hash-pinned files.
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        assert run("validate", steam, manifest).stdout.strip() == (
            f"validated {len(FILES)} files ({TOTAL_SIZE} bytes)"
        )
        extra = steam / "steamapps/common" / GAME_NAME / "download.tmp"
        extra.write_text("not allowlisted\n", encoding="utf-8")
        run("validate", steam, manifest, success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        game = steam / "steamapps/common" / GAME_NAME
        (game / "Data/config.ini").write_bytes(b"tampered\n")
        run("validate", steam, manifest, success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        game = steam / "steamapps/common" / GAME_NAME
        external = root / "external"
        external.write_bytes(FILES["Data/config.ini"])
        (game / "Data/config.ini").unlink()
        (game / "Data/config.ini").symlink_to(external)
        run("validate", steam, manifest, success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        game = steam / "steamapps/common" / GAME_NAME
        (root / "hardlink").hardlink_to(game / "Data/config.ini")
        result = run("validate", steam, manifest, success=False)
        assert "regular unlinked file" in result.stderr

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        source_acf = steam / f"steamapps/appmanifest_{APP_ID}.acf"
        (root / "appmanifest-hardlink").hardlink_to(source_acf)
        result = run("status", steam, manifest, success=False)
        assert "regular unlinked file" in result.stderr

    # Every source file must be owner-controlled and not group/other writable.
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        source_acf = steam / f"steamapps/appmanifest_{APP_ID}.acf"
        source_acf.chmod(0o666)
        result = run("status", steam, manifest, success=False)
        assert "group/other-writable" in result.stderr

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        source_file = steam / "steamapps/common" / GAME_NAME / "Data/config.ini"
        source_file.chmod(0o666)
        result = run("validate", steam, manifest, success=False)
        assert "group/other-writable" in result.stderr

    # Ownership cannot normally be changed by an unprivileged test process, so
    # simulate a different current uid at the public validation boundaries.
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        with mock.patch.object(DEPOT.os, "getuid", return_value=os.getuid() + 1):
            try:
                DEPOT.validate_depot(steam, expectations(manifest))
            except ValueError as error:
                assert "not owned by current uid" in str(error)
            else:
                raise AssertionError("Source with a different owner was accepted")

    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / "destination-Steam"
        destination.mkdir()
        with mock.patch.object(DEPOT.os, "getuid", return_value=os.getuid() + 1):
            try:
                DEPOT.require_destination_root(destination)
            except ValueError as error:
                assert "not owned by current uid" in str(error)
            else:
                raise AssertionError("Destination with a different owner was accepted")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        real_steamapps = root / "real-steamapps"
        (steam / "steamapps").rename(real_steamapps)
        (steam / "steamapps").symlink_to(real_steamapps, target_is_directory=True)
        result = run("validate", steam, manifest, success=False)
        assert "Linked depot path" in result.stderr

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        manifest.write_text(manifest.read_text().splitlines()[0] + "\n", encoding="utf-8")
        run("validate", steam, manifest, success=False)

    # Install copies only the inventory and emits a sanitized owner-bound manifest.
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        source_acf = steam / f"steamapps/appmanifest_{APP_ID}.acf"
        source_acf.write_text(
            source_acf.read_text().replace(
                '    "InstalledDepots"',
                '    "UserConfig" { "language" "secret" }\n    "InstalledDepots"',
            ),
            encoding="utf-8",
        )
        destination = root / "destination-Steam"
        destination.mkdir()
        result = run("install", steam, manifest, str(destination), STEAM_ID)
        assert result.stdout.strip() == f"installed {len(FILES)} files ({TOTAL_SIZE} bytes)"
        installed_game = destination / "steamapps/common" / GAME_NAME
        assert {
            path.relative_to(installed_game).as_posix()
            for path in installed_game.rglob("*")
            if path.is_file()
        } == set(FILES)
        for relative, data in FILES.items():
            assert (installed_game / relative).read_bytes() == data
        installed_acf = destination / f"steamapps/appmanifest_{APP_ID}.acf"
        installed_text = installed_acf.read_text(encoding="utf-8")
        assert f'"LastOwner"\t\t"{STEAM_ID}"' in installed_text
        assert '"UserConfig"' not in installed_text
        assert f'"buildid"\t\t"{BUILD_ID}"' in installed_text
        assert f'"{DEPOT_MANIFEST_ID}"' in installed_text
        run("validate", destination, manifest)

    # Success is reported only after the installed output validates. A failed
    # post-install validation rolls back both newly installed artifacts.
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        destination = root / "destination-Steam"
        destination.mkdir()
        expected = expectations(manifest)
        real_validate = DEPOT.validate_depot
        validations = 0

        def fail_after_validation(path, values):
            nonlocal validations
            result = real_validate(path, values)
            validations += 1
            if validations == 2:
                raise ValueError("simulated installed-output validation failure")
            return result

        with mock.patch.object(DEPOT, "validate_depot", side_effect=fail_after_validation):
            try:
                DEPOT.install_depot(steam, destination, STEAM_ID, expected)
            except ValueError as error:
                assert "installed-output validation failure" in str(error)
            else:
                raise AssertionError("Install skipped output validation")
        assert validations == 2
        assert not (destination / "steamapps/common" / GAME_NAME).exists()
        assert not (destination / f"steamapps/appmanifest_{APP_ID}.acf").exists()

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        destination = root / "destination-Steam"
        destination.mkdir()
        run("install", steam, manifest, str(destination), "123", success=False)
        assert not (destination / "steamapps").exists()

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam, manifest = make_depot(root)
        destination = root / "destination-Steam"
        (destination / "steamapps/common" / GAME_NAME).mkdir(parents=True)
        sentinel = destination / "steamapps/common" / GAME_NAME / "keep.txt"
        sentinel.write_text("keep\n", encoding="utf-8")
        run("install", steam, manifest, str(destination), STEAM_ID, success=False)
        assert sentinel.read_text(encoding="utf-8") == "keep\n"


if __name__ == "__main__":
    main()
