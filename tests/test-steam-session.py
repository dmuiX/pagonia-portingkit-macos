#!/usr/bin/env python3
"""Regression tests for the selective Steam login-session transfer."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/pagonia-steam-session.py"
STEAM_ID = "76561198000000000"
ACCOUNT_ID = "39734272"


def run(*arguments: str, success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["python3", str(HELPER), *arguments],
        check=False,
        text=True,
        capture_output=True,
    )
    if success and result.returncode != 0:
        raise AssertionError(result.stderr)
    if not success and result.returncode == 0:
        raise AssertionError("Command unexpectedly succeeded")
    return result


def make_steam(root: Path) -> Path:
    steam = root / "Steam"
    config = steam / "config"
    user_config = steam / "userdata" / ACCOUNT_ID / "config"
    config.mkdir(parents=True)
    user_config.mkdir(parents=True)
    (config / "loginusers.vdf").write_text(
        f'"users"\n{{\n"{STEAM_ID}"\n{{\n'
        '"RememberPassword" "1"\n"MostRecent" "1"\n}\n}\n'
    )
    (config / "config.vdf").write_text(
        '"InstallConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n"Steam"\n{\n}\n}\n}\n}\n'
    )
    (config / "unrelated-sentinel.vdf").write_text("must not transfer\n")
    (user_config / "localconfig.vdf").write_text(
        '"UserLocalConfigStore"\n{\n"AuthData"\n{\n"fixture" "value"\n}\n'
        '"SharedAuth"\n{\n"fixture" "value"\n}\n}\n'
    )
    (user_config / "unrelated-sentinel.vdf").write_text("must not transfer\n")
    (steam / "ssfn123").write_text("machine authorization\n")
    return steam


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_steam(root)
        snapshot = root / "snapshot"
        destination = root / "destination"
        destination.mkdir()

        run("create", str(steam), str(snapshot))
        run("validate", str(snapshot))
        assert not (snapshot / "config/unrelated-sentinel.vdf").exists()
        assert not (
            snapshot / "userdata" / ACCOUNT_ID / "config/unrelated-sentinel.vdf"
        ).exists()
        assert run("steam-id", str(snapshot)).stdout.strip() == STEAM_ID
        assert run("install", str(snapshot), str(destination)).stdout.strip() == STEAM_ID
        assert (destination / "config/loginusers.vdf").is_file()
        assert (destination / "config/config.vdf").is_file()
        assert (
            destination / "userdata" / ACCOUNT_ID / "config/localconfig.vdf"
        ).is_file()
        assert (destination / "ssfn123").is_file()

        changed = snapshot / "config/config.vdf"
        changed.write_text(changed.read_text() + "changed\n")
        run("validate", str(snapshot), success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_steam(root)
        loginusers = steam / "config/loginusers.vdf"
        loginusers.write_text(
            '"users"\n{\n'
            f'"{STEAM_ID}"\n{{\n"RememberPassword" "1"\n"MostRecent" "1"\n}}\n'
            '"76561198000000001"\n{\n"RememberPassword" "1"\n"MostRecent" "1"\n}\n'
            '}\n'
        )
        run("create", str(steam), str(root / "snapshot"), success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_steam(root)
        snapshot = root / "snapshot"
        run("create", str(steam), str(snapshot))
        (snapshot / "dangling-link").symlink_to("missing")
        run("validate", str(snapshot), success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_steam(root)
        external = root / "external-config"
        (steam / "config").rename(external)
        (steam / "config").symlink_to(external, target_is_directory=True)
        run("create", str(steam), str(root / "snapshot"), success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_steam(root)
        snapshot = root / "snapshot"
        run("create", str(steam), str(snapshot))
        nested_manifest = snapshot / "config/.pagonia-steam-session-SHA256SUMS"
        nested_manifest.write_text("unlisted\n")
        run("validate", str(snapshot), success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_steam(root)
        loginusers = steam / "config/loginusers.vdf"
        loginusers.write_text(
            loginusers.read_text().replace(
                '"RememberPassword" "1"', '"AllowAutoLogin" "1"'
            )
        )
        run("create", str(steam), str(root / "snapshot"))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_steam(root)
        loginusers = steam / "config/loginusers.vdf"
        loginusers.write_text(
            loginusers.read_text()
            .replace('"MostRecent" "1"\n', "")
            .replace('"RememberPassword" "1"', '"AutoLogin" "1"')
        )
        run("create", str(steam), str(root / "snapshot"))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_steam(root)
        loginusers = steam / "config/loginusers.vdf"
        loginusers.write_text(
            loginusers.read_text().replace(
                '"RememberPassword" "1"', '"RememberPassword" "0"'
            )
        )
        run("create", str(steam), str(root / "snapshot"), success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_steam(root)
        localconfig = steam / "userdata" / ACCOUNT_ID / "config/localconfig.vdf"
        localconfig.write_text('"UserLocalConfigStore"\n{\n}\n')
        run("create", str(steam), str(root / "snapshot"), success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_steam(root)
        config = steam / "config/config.vdf"
        config.chmod(0o666)
        run("create", str(steam), str(root / "snapshot"), success=False)


if __name__ == "__main__":
    main()
