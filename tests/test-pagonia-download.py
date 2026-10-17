#!/usr/bin/env python3
"""Behavior tests for Wine 11 Steam acquisition and cleanup."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("pagonia_download", ROOT / "pagonia-download.py")
download = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = download
SPEC.loader.exec_module(download)


class DownloadTests(unittest.TestCase):
    def test_depot_readiness_does_not_hash_live_steam_files(self):
        transfer = MagicMock()
        transfer.DEPOT_OPTIONS = []
        ready = MagicMock(returncode=0)
        with patch.object(download, "load", return_value=transfer), \
             patch.object(download.subprocess, "run", return_value=ready):
            download.wait_for_depot(Path("/tmp/Steam"), timeout=1)
        transfer.command.assert_not_called()

    def test_resume_repairs_partial_steam_install_when_service_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "Steam Downloader.app"
            prefix = app / "Contents/SharedSupport/prefix"
            wine = app / "Contents/SharedSupport/wine"
            steam = prefix / "drive_c/Program Files (x86)/Steam"
            steam.mkdir(parents=True)
            wine.mkdir(parents=True)
            (steam / "steam.exe").write_bytes(b"partial install")
            setup = root / "SteamSetup.exe"
            setup.write_bytes(b"verified fixture")
            process = MagicMock()
            graphics = MagicMock()

            def loader(name: str):
                return {
                    "pagonia-process.py": process,
                    "pagonia-graphics.py": graphics,
                    "pagonia-window.py": MagicMock(),
                }[name]

            with patch.object(download, "load", side_effect=loader), \
                 patch.object(download, "prepare_wine") as prepare, \
                 patch.object(download, "install_steam") as install, \
                 patch.object(download, "start_visible_steam", return_value=MagicMock()), \
                 patch.object(download, "wait_for_login"), \
                 patch.object(download, "install_request"), \
                 patch.object(download, "wait_for_depot"):
                download.acquire(app, prefix, wine, fresh=False, setup=setup)

            prepare.assert_called_once()
            install.assert_called_once_with(app, prefix, wine, setup)


if __name__ == "__main__":
    unittest.main()
