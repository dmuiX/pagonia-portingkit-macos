#!/usr/bin/env python3
"""Tests for the independent modular installer state-selection contract."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("new_pagonia_installer", SCRIPTS / "pagonia-installer.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerSelectionTests(unittest.TestCase):
    def test_explicit_resume_requires_direct_child(self):
        with self.assertRaisesRegex(RuntimeError, "direct child"):
            installer.choose_state("/Applications/Other.app")

    def test_auto_fresh_when_no_valid_staging(self):
        with patch.object(installer, "helper", return_value="fresh"):
            self.assertEqual(installer.choose_state(None), ("fresh", None))

    def test_auto_resume_uses_validated_selector(self):
        value = "/private/tmp/Pagonia-GPTK4b3-deployment.Ab123"
        with patch.object(installer, "helper", return_value=value):
            self.assertEqual(installer.choose_state(None), ("resume", value))

    def test_multiple_staging_error_is_not_suppressed(self):
        with patch.object(installer, "helper", side_effect=RuntimeError("Multiple valid")):
            with self.assertRaisesRegex(RuntimeError, "Multiple valid"):
                installer.choose_state(None)

    def test_delete_does_not_touch_unverified_paths(self):
        existing = {
            "managed": [],
            "unverified": [{"path": "/private/tmp/Pagonia-GPTK4b3-deployment.unknown"}],
        }
        with patch.object(installer, "inventory", return_value=existing), \
             patch.object(installer, "helper") as run:
            installer.remove_managed(True)
            run.assert_not_called()

    def test_unreleased_fresh_does_not_delete(self):
        args = type("Args", (), {"fresh": True, "resume": None, "delete": False, "yes": True})()
        with patch.object(installer, "cli", return_value=args), \
             patch.object(installer.os, "geteuid", return_value=501), \
             patch.object(installer.sys, "platform", "darwin"), \
             patch.object(installer, "remove_managed") as delete:
            with self.assertRaisesRegex(RuntimeError, "not implemented"):
                installer.main()
            delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
