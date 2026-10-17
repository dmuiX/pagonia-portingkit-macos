#!/usr/bin/env python3
"""Isolated unit tests for the new runtime configuration."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"scripts/pagonia-graphics.py"
SPEC=importlib.util.spec_from_file_location("graphics",SOURCE)
GRAPHICS=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRAPHICS)

class GraphicsTests(unittest.TestCase):
    def test_registry_idempotence(self):
        with tempfile.TemporaryDirectory() as root:
            prefix=Path(root)
            (prefix/"user.reg").write_text("WINE REGISTRY Version 2\n")
            for _ in range(2):
                GRAPHICS.registry_overrides(prefix,{"dxgi":"native,builtin"},"steam.exe")
            text=(prefix/"user.reg").read_text()
            self.assertEqual(text.count('"dxgi"="native,builtin"'),1)

    def test_registry_rejects_injected_names(self):
        with tempfile.TemporaryDirectory() as root:
            prefix=Path(root)
            (prefix/"user.reg").write_text("header\n")
            with self.assertRaises(ValueError):
                GRAPHICS.registry_overrides(prefix,{'bad\nkey':'native,builtin'})

    def test_runtime_hash_rejects_change(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"runtime"
            path.write_bytes(b"invalid")
            with self.assertRaises(ValueError):
                GRAPHICS.verify_digest(path,"0"*64)

if __name__=="__main__":
    unittest.main()
