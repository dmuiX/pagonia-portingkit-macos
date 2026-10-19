#!/usr/bin/env python3
"""Exercise the public existing-deployment verification mode."""
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install-pagonia-gptk4b3.sh"


class VerifyExistingTests(unittest.TestCase):
    def test_missing_destination_fails_before_installation_preflight(self):
        destination = Path("/Applications/Pagonia Missing Verification Test.app")
        self.assertFalse(destination.exists())
        result = subprocess.run(
            [str(SCRIPT), "--verify-existing", "--destination", str(destination)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No installed deployment to verify", result.stderr)
        self.assertNotIn("Preflight:", result.stdout)

    def test_verify_mode_rejects_installation_options(self):
        result = subprocess.run(
            [str(SCRIPT), "--verify-existing", "--fresh"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be combined", result.stderr)


if __name__ == "__main__":
    unittest.main()
