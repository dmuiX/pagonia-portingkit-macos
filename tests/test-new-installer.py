#!/usr/bin/env python3
"""End-to-end state-selection safety tests for the new modular entry point."""

from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("pagonia_installer", ROOT / "pagonia-installer.py")
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


class InstallerSelectionTests(unittest.TestCase):
    def test_explicit_resume_rejects_outside_parent(self):
        with self.assertRaisesRegex(RuntimeError, "direct child"):
            installer.choose_state("/Applications/Other.app")

    def test_auto_fresh_without_staging(self):
        with patch.object(installer, "inventory", return_value={"managed": [], "unverified": []}):
            self.assertEqual(installer.choose_state(None), ("fresh", None))

    def test_auto_resume_validates_exact_staging(self):
        value = "/private/tmp/Pagonia-GPTK4b3-deployment.Ab123"
        listing = {"managed": [{"kind": "staging-deployment", "path": value}], "unverified": []}
        with patch.object(installer, "inventory", return_value=listing), \
             patch.object(installer, "helper", return_value="depot-complete") as run:
            self.assertEqual(installer.choose_state(None), ("resume", value))
            self.assertEqual(run.call_count, 1)
            self.assertIn("--evidence-validator", run.call_args.args)

    def test_multiple_stagings_fail_closed(self):
        listing = {"managed": [{"kind": "staging-deployment",
                                "path": f"/private/tmp/Pagonia-GPTK4b3-deployment.{name}"}
                               for name in ("Alpha", "Beta")], "unverified": []}
        with patch.object(installer, "inventory", return_value=listing), \
             patch.object(installer, "helper", return_value="downloader-incomplete"):
            with self.assertRaisesRegex(RuntimeError, "Multiple validated staging"):
                installer.choose_state(None)

    def test_delete_does_not_touch_unverified_paths(self):
        listing = {"managed": [], "unverified": [{"path": "/private/tmp/Pagonia-unknown"}]}
        with patch.object(installer, "inventory", return_value=listing), \
             patch.object(installer, "helper") as run:
            installer.remove_managed(True)
            run.assert_not_called()

    def test_fresh_preflight_fails_before_deletion(self):
        args = type("Args", (), {"fresh": True, "resume": None, "delete": False,
                                "yes": True, "gptk_lib": Path("/Volumes/fake/redist/lib")})()
        guard = MagicMock()
        guard.locate_gptk.return_value = args.gptk_lib
        guard.preflight.side_effect = ValueError("missing pinned input")
        with patch.object(installer, "cli", return_value=args), \
             patch.object(installer.os, "geteuid", return_value=501), \
             patch.object(installer.sys, "platform", "darwin"), \
             patch.object(installer, "PARENT", Path(tempfile.gettempdir())), \
             patch.object(installer, "installer_lock"), \
             patch.object(installer, "load", return_value=guard), \
             patch.object(installer, "remove_managed") as remove:
            with self.assertRaisesRegex(ValueError, "missing pinned input"):
                installer.main()
            remove.assert_not_called()


if __name__ == "__main__":
    unittest.main()
