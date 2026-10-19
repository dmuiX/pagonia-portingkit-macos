#!/usr/bin/env python3
"""Regression tests for sustained game-process launch verification."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install-pagonia-gptk4b3.sh"


class LaunchVerificationTests(unittest.TestCase):
    def run_verification(self, markers: bool, stays_running: bool = True):
        source = SCRIPT.read_text()
        start = source.index("run_launch_test() {")
        end = source.index("\nif [[ $VERIFY_EXISTING -eq 1 ]]; then", start)
        function = source[start:end]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "Pagonia.app"
            (app / "Contents/SharedSupport/Logs").mkdir(parents=True)
            wine_bin = app / "Contents/SharedSupport/wine/bin"
            wine_bin.mkdir(parents=True)
            for executable in ("wine64", "wineserver"):
                path = wine_bin / executable
                path.write_text("#!/bin/bash\nexit 0\n")
                path.chmod(0o700)
            steam = (app / "Contents/SharedSupport/prefix/drive_c/Program Files (x86)/Steam/steam.exe")
            steam.parent.mkdir(parents=True)
            steam.touch()
            ps_count = root / "ps-count"
            ps_count.write_text("0")
            ps_mock = root / "ps"
            ps_mock.write_text(
                "#!/bin/bash\n"
                "count=$(<\"$PS_COUNT\")\n"
                "printf '%s' \"$((count + 1))\" >\"$PS_COUNT\"\n"
                "if [[ $count -ge ${EXIT_AFTER_CALL:-6} ]]; then exit 0; fi\n"
                "echo 'Pioneers of Pagonia.exe -NoDX12DeviceFactory -NoDX12SDKVersionCheck'\n"
            )
            ps_mock.chmod(0o700)
            open_mock = root / "open"
            open_mock.write_text(
                "#!/bin/bash\n"
                "app=${!#}\n"
                "if [[ ${WRITE_MARKERS:-0} == 1 ]]; then\n"
                "  printf 'Created D3D12Device\\nCreated D3D12 Swapchain\\n' "
                '>"$app/Contents/SharedSupport/Logs/LastRunWine.log"\n'
                "fi\n"
            )
            open_mock.chmod(0o700)
            prelude = '''set -eu
OPEN_COMMAND=$2
PS_COMMAND=$3
SLEEP_COMMAND=true
LSOF_COMMAND=true
stop_if_running() { :; }
same_identity() { return 0; }
'''
            env = os.environ.copy()
            env["WRITE_MARKERS"] = "1" if markers else "0"
            env["EXIT_AFTER_CALL"] = "6" if stays_running else "1"
            env["PS_COUNT"] = str(ps_count)
            return subprocess.run(
                [
                    "bash", "-c", prelude + function +
                    '\nrun_launch_test "$1" 1 1\n',
                    "test", str(app), str(open_mock), str(ps_mock),
                ],
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )

    def test_running_game_is_verified_without_optional_markers(self):
        result = self.run_verification(markers=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("remained active for ten seconds", result.stdout)
        self.assertIn("installed and running", result.stdout)
        self.assertIn("Steam and the Pagonia Wine runtime have shut down", result.stdout)
        self.assertNotIn("D3D12 device and swapchain diagnostics", result.stdout)
        self.assertNotIn("WARNING:", result.stderr)

    def test_optional_markers_are_reported_when_present(self):
        result = self.run_verification(markers=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Game-launch checks passed", result.stdout)
        self.assertIn("Optional D3D12 device and swapchain diagnostics", result.stdout)
        self.assertNotIn("WARNING:", result.stderr)

    def test_game_that_exits_during_startup_is_rejected(self):
        result = self.run_verification(markers=False, stays_running=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exited during startup verification", result.stderr)
        self.assertNotIn("Game-launch checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
