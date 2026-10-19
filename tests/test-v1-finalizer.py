#!/usr/bin/env python3
"""Exercise the installer's real Wineskin finalizer packaging functions."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/install-pagonia-gptk4b3.sh"
FINALIZER = ROOT / "scripts/PagoniaFinalizer"


class FinalizerPackagingTests(unittest.TestCase):
    def run_fixture(self, corrupt=False):
        source = INSTALLER.read_text()
        start = source.index("install_wrapper_finalizer() {")
        end = source.index("\nstop_wine_app() {", start)
        functions = source[start:end]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "Pagonia.app"
            scripts = app / "Contents/Resources/Scripts"
            scripts.mkdir(parents=True)
            packaged = root / "PagoniaFinalizer"
            packaged.write_bytes(FINALIZER.read_bytes())
            command = ('require_file() { [[ -f "$1" && ! -L "$1" ]]; }\n' +
                       functions + '\ninstall_wrapper_finalizer "$APP"\n')
            if corrupt:
                command += 'printf corrupt >>"$APP/Contents/Resources/Scripts/PagoniaFinalizer"\n'
            command += 'verify_wrapper_finalizer "$APP"\n'
            return subprocess.run(
                ["bash", "-c", "set -euo pipefail\n" + command],
                capture_output=True,
                text=True,
                env={
                    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                    "SCRIPT_DIR": str(root),
                    "APP": str(app),
                },
                timeout=5,
            ), scripts

    def test_installs_and_verifies_all_lifecycle_hooks(self):
        result, _ = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("finalizer installed", result.stdout)
        self.assertIn("finalizer and lifecycle hooks verified", result.stdout)

    def test_verification_rejects_modified_finalizer(self):
        result, _ = self.run_fixture(corrupt=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("differs from the packaged finalizer", result.stderr)


if __name__ == "__main__":
    unittest.main()
