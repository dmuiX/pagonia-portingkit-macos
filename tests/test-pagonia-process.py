#!/usr/bin/env python3
"""Tests for subprocess lifecycle and runtime separation."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/pagonia-process.py"
SPEC = importlib.util.spec_from_file_location("pagonia_process", HELPER)
process = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(process)


class ProcessTests(unittest.TestCase):
    def test_success_and_exit_status(self):
        with tempfile.TemporaryDirectory() as work:
            log = Path(work) / "out.log"
            status = process.run_bounded(
                [sys.executable, "-c", "print('ok')"], log, timeout=4
            )
            self.assertEqual(status, 0)
            self.assertIn("ok", log.read_text())

    def test_failure_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as work:
            result = process.run_bounded(
                [sys.executable, "-c", "raise SystemExit(7)"],
                Path(work) / "log", timeout=4)
            self.assertEqual(result, 7)

    def test_timeout_stops_child(self):
        with tempfile.TemporaryDirectory() as work:
            with self.assertRaises(process.ProcessError):
                process.run_bounded(
                    [sys.executable, "-c", "import time; time.sleep(20)"],
                    Path(work) / "log", timeout=0.1, grace=0.1)

    def test_wine_prefixes_use_separate_environments(self):
        downloader = Path("/tmp/downloader")
        gameplay = Path("/tmp/gameplay")
        runtime = Path("/tmp/runtime")
        first = process.wine_environment(downloader, runtime, True)
        second = process.wine_environment(gameplay, runtime, False)
        self.assertNotEqual(first["WINEPREFIX"], second["WINEPREFIX"])
        self.assertEqual(first["STEAM_RUNTIME"], "0")
        self.assertNotIn("WINEDLLOVERRIDES",
                         {k: v for k, v in second.items()
                          if k not in ("WINEPREFIX",) and k not in
                          __import__("os").environ})


if __name__ == "__main__":
    unittest.main()
