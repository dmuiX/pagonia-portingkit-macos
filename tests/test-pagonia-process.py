#!/usr/bin/env python3
"""Tests for subprocess lifecycle and runtime separation."""

import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

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

    def test_timeout_stops_child_with_term_before_kill(self):
        with tempfile.TemporaryDirectory() as work:
            marker = Path(work) / "terminated"
            child = (
                "import pathlib,signal,time; "
                f"marker=pathlib.Path({str(marker)!r}); "
                "signal.signal(signal.SIGTERM, lambda *_: (marker.write_text('term'), exit(0))); "
                "time.sleep(20)"
            )
            with self.assertRaises(process.ProcessError):
                process.run_bounded(
                    [sys.executable, "-c", child],
                    Path(work) / "log", timeout=0.2, grace=1)
            self.assertEqual(marker.read_text(), "term")

    def test_keyboard_interrupt_stops_child_and_remains_interrupt(self):
        with tempfile.TemporaryDirectory() as work:
            marker = Path(work) / "terminated"
            child = (
                "import pathlib,signal,time; "
                f"marker=pathlib.Path({str(marker)!r}); "
                "signal.signal(signal.SIGTERM, lambda *_: (marker.write_text('term'), exit(0))); "
                "time.sleep(20)"
            )
            interrupt = threading.Timer(
                0.2, lambda: os.kill(os.getpid(), signal.SIGINT)
            )
            interrupt.start()
            try:
                with self.assertRaises(KeyboardInterrupt):
                    process.run_bounded(
                        [sys.executable, "-c", child],
                        Path(work) / "log", timeout=10, grace=1)
            finally:
                interrupt.cancel()
            self.assertEqual(marker.read_text(), "term")

    def test_combined_shutdown_terminates_child_when_wineserver_stop_fails(self):
        child = MagicMock()
        with patch.object(
            process, "stop_prefix", side_effect=process.ProcessError("shutdown failed")
        ), patch.object(process, "terminate_child") as terminate:
            with self.assertRaisesRegex(process.ProcessError, "shutdown failed"):
                process.stop_prefix_and_child(
                    Path("/tmp/prefix"), Path("/tmp/wine"), Path("/tmp/log"), child
                )
        terminate.assert_called_once_with(child)

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
