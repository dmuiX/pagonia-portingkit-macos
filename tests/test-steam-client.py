#!/usr/bin/env python3
"""Behavior tests for Steam clean-client snapshots."""

from pathlib import Path
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/pagonia-steam-session.py"


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


def inventory_line(windows_path: str, data: bytes) -> str:
    return f"{windows_path},{len(data)};0;{zlib.crc32(data)}"


def make_client(root: Path) -> Path:
    steam = root / "Steam"
    package = steam / "package"
    runtime = steam / "bin"
    package.mkdir(parents=True)
    runtime.mkdir()
    files = {
        "steam.exe": b"steam executable\n",
        "bin\\client.dll": b"client library\n",
    }
    for relative, data in files.items():
        path = steam.joinpath(*relative.replace("\\", "/").split("/"))
        path.write_bytes(data)
    (package / "steam_client_win64.installed").write_text(
        "VERSION=1\nSHA1=" + "A" * 40 + "\n"
        + "\n".join(inventory_line(path, data) for path, data in files.items())
        + "\n",
        encoding="utf-8",
    )
    (steam / "config").mkdir()
    (steam / "config/loginusers.vdf").write_text("must not transfer\n")
    (steam / "logs").mkdir()
    (steam / "logs/connection_log.txt").write_text("must not transfer\n")
    return steam


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_client(root)
        snapshot = root / "snapshot"
        destination = root / "destination"
        destination.mkdir()

        run("client-create", str(steam), str(snapshot))
        run("client-validate", str(snapshot))
        run("client-install", str(snapshot), str(destination))

        assert (snapshot / "steam.exe").read_bytes() == b"steam executable\n"
        assert (snapshot / "bin/client.dll").read_bytes() == b"client library\n"
        assert (snapshot / "package/steam_client_win64.installed").is_file()
        assert not (snapshot / "config").exists()
        assert not (snapshot / "logs").exists()
        assert (destination / "steam.exe").is_file()
        assert (destination / "bin/client.dll").is_file()

        (snapshot / "steam.exe").write_bytes(b"tampered\n")
        run("client-validate", str(snapshot), success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_client(root)
        manifest = steam / "package/steam_client_win64.installed"
        manifest.write_text(
            manifest.read_text() + inventory_line("config\\loginusers.vdf", b"must not transfer\n") + "\n"
        )
        run("client-create", str(steam), str(root / "snapshot"), success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_client(root)
        (steam / "steam.exe").write_bytes(b"wrong contents\n")
        run("client-create", str(steam), str(root / "snapshot"), success=False)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        steam = make_client(root)
        external = root / "external.exe"
        external.write_bytes(b"steam executable\n")
        (steam / "steam.exe").unlink()
        (steam / "steam.exe").symlink_to(external)
        run("client-create", str(steam), str(root / "snapshot"), success=False)


if __name__ == "__main__":
    main()
