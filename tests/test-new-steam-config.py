#!/usr/bin/env python3
"""Tests for the transferred Steam account's Pagonia launch settings."""

from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("pagonia_config", ROOT / "pagonia-steam-config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

STEAM_ID = "76561198000000000"
ACCOUNT = int(STEAM_ID) - config.STEAM_BASE


def localconfig(steam: Path, body: str) -> Path:
    path = steam / f"userdata/{ACCOUNT}/config/localconfig.vdf"
    path.parent.mkdir(parents=True)
    path.write_text(body)
    return path


STRUCTURE = '''
"UserLocalConfigStore"
{
 "Software"
 {
  "Valve"
  {
   "Steam"
   {
    "apps"
    {
    }
   }
  }
 }
}
'''


class SteamConfigTests(unittest.TestCase):
    def test_options_injected_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            steam = Path(directory)
            path = localconfig(steam, STRUCTURE)
            config.launch_options(steam, STEAM_ID)
            config.launch_options(steam, STEAM_ID)
            text = path.read_text()
            self.assertEqual(text.count('"LaunchOptions"'), 1)
            self.assertIn(config.OPTIONS, text)

    def test_bad_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                config.launch_options(Path(directory), "123")

    def test_linked_localconfig_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            steam = Path(directory)
            linked_target = steam / "outside"
            linked_target.write_text(STRUCTURE)
            file = localconfig(steam, STRUCTURE)
            file.unlink()
            file.symlink_to(linked_target)
            with self.assertRaisesRegex(ValueError, "Linked Steam"):
                config.launch_options(steam, STEAM_ID)


if __name__ == "__main__":
    unittest.main()
