#!/usr/bin/env python3
"""Behavior tests for fail-closed staging process ownership."""

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/pagonia-ownership.py"
sys.path.insert(0, str(HELPER.parent))
SPEC = importlib.util.spec_from_file_location("pagonia_ownership", HELPER)
ownership = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ownership
SPEC.loader.exec_module(ownership)


class OwnershipTests(unittest.TestCase):
    def test_windows_and_unix_wine_process_names_are_targeted(self):
        commands = (
            r"C:\windows\system32\wine64 Z:\private\tmp\stage\Steam.exe",
            r"C:\windows\system32\winedevice.exe",
            r"C:\Program Files (x86)\Steam\steam.exe -vgui",
            "/private/tmp/stage/wine/bin/wineserver",
            '"/private/tmp/stage/Pioneers of Pagonia.exe" -NoDX12DeviceFactory',
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(ownership.targeted(command))

    def test_unrelated_process_makes_ownership_ambiguous(self):
        stage = Path("/private/tmp/Pagonia-GPTK4b3-deployment.Test")
        rows = [
            (101, f"{stage}/wine/bin/wineserver"),
            (102, r"C:\windows\system32\winedevice.exe"),
        ]
        with patch.object(ownership, "process_table", return_value=rows):
            with self.assertRaises(ownership.AmbiguousOwnership):
                ownership.active_for_staging(stage)


if __name__ == "__main__":
    unittest.main()
