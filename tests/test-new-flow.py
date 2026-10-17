#!/usr/bin/env python3
"""Mocked lifecycle tests for the new shared Fresh/Resume coordinator."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("pagonia_flow", ROOT / "pagonia-flow.py")
flow = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = flow
spec.loader.exec_module(flow)


class FlowTests(unittest.TestCase):
    def fake_modules(self):
        preflight = MagicMock()
        publication = MagicMock()
        publication.publish.return_value = None
        gameplay = MagicMock()
        gameplay.build.return_value = Path("/tmp/Pioneers of Pagonia.app")

        def loader(filename):
            return {
                "pagonia-preflight.py": preflight,
                "pagonia-publication.py": publication,
                "pagonia-gameplay.py": gameplay,
            }[filename]
        return loader, preflight, publication, gameplay

    def test_fresh_runs_all_phases_and_retires_successful_staging(self):
        loader, preflight, publication, gameplay = self.fake_modules()
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            stage = root / "Pagonia-GPTK4b3-deployment.Test"
            stage.mkdir()
            with patch.object(flow, "load", side_effect=loader), \
                 patch.object(flow, "create_stage", return_value=stage), \
                 patch.object(flow, "validated_state", return_value="downloader-incomplete"), \
                 patch.object(flow, "downloader", return_value=stage / "downloader-prefix") as download, \
                 patch.object(flow, "acceptance") as acceptance, \
                 patch.object(flow, "PARENT", root):
                flow.deploy("fresh", None, Path("/Volumes/example/redist/lib"))
                preflight.preflight.assert_called_once()
                preflight.verify_inputs.assert_called_once()
                download.assert_called_once_with(stage, False)
                gameplay.build.assert_called_once()
                publication.mark_application.assert_called_once()
                publication.publish.assert_called_once()
                acceptance.assert_called_once_with(flow.DESTINATION)
                self.assertFalse(stage.exists())

    def test_completed_resume_skips_fresh_preflight_and_wine_login(self):
        loader, preflight, publication, gameplay = self.fake_modules()
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            stage = root / "Pagonia-GPTK4b3-deployment.Test"
            stage.mkdir()
            with patch.object(flow, "load", side_effect=loader), \
                 patch.object(flow, "validated_state", return_value="depot-complete"), \
                 patch.object(flow, "downloader", return_value=stage / "downloader-prefix") as download, \
                 patch.object(flow, "acceptance"), \
                 patch.object(flow, "PARENT", root):
                flow.deploy("resume", stage, Path("/Volumes/example/redist/lib"))
                preflight.preflight.assert_not_called()
                download.assert_called_once_with(stage, True)
                self.assertFalse(stage.exists())

    def test_failed_acceptance_rolls_back_and_preserves_resume(self):
        loader, preflight, publication, gameplay = self.fake_modules()
        backup = Path("/Applications/Pioneers of Pagonia.app.backup-test")
        publication.publish.return_value = backup
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            stage = root / "Pagonia-GPTK4b3-deployment.Test"
            stage.mkdir()
            with patch.object(flow, "load", side_effect=loader), \
                 patch.object(flow, "validated_state", return_value="depot-complete"), \
                 patch.object(flow, "downloader", return_value=stage / "downloader-prefix"), \
                 patch.object(flow, "acceptance", side_effect=RuntimeError("terrain missing")), \
                 patch.object(flow, "PARENT", root):
                with self.assertRaisesRegex(RuntimeError, "terrain missing"):
                    flow.deploy("resume", stage, Path("/Volumes/example/redist/lib"))
                publication.rollback.assert_called_once_with(flow.DESTINATION, backup)
                self.assertTrue(stage.exists())


if __name__ == "__main__":
    unittest.main()
