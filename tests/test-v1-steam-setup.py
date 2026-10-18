#!/usr/bin/env python3
"""Exercise the real v1 setup-wait block without Wine or network access."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/install-pagonia-gptk4b3.sh'


class SetupWaitTests(unittest.TestCase):
    def run_wait(self, installed=True, active=False):
        source = SCRIPT.read_text()
        start = source.index('  SETUP_SEEN=0')
        end = source.index('  stop_wine_app "$APP"', start)
        block = source[start:end]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            steam = root / 'Steam'
            steam.mkdir()
            if installed:
                (steam / 'steam.exe').touch()
                (steam / 'uninstall.exe').touch()
            prelude = '''set -eu
jot() { printf '1\\n15\\n'; }
pgrep_mock() { return ACTIVE; }
sleep_mock() { :; }
PGREP_COMMAND=pgrep_mock
SLEEP_COMMAND=sleep_mock
APP=/test-app
STEAM=$1
'''.replace('ACTIVE', '0' if active else '1')
            return subprocess.run(['bash', '-c', prelude + block, 'test', str(steam)],
                                  capture_output=True, text=True, timeout=5)

    def test_completed_bootstrap_does_not_require_package_or_observed_process(self):
        result = self.run_wait()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_bootstrap_fails_with_diagnostic(self):
        result = self.run_wait(installed=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ERROR:', result.stderr)

    def test_active_setup_is_not_accepted(self):
        result = self.run_wait(active=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Still waiting', result.stdout)
        self.assertNotIn('syntax error', result.stderr)
        self.assertIn('30 seconds', result.stdout)

    def test_download_status_is_not_printed_on_every_poll(self):
        source = SCRIPT.read_text()
        start = source.index('  GAME_DOWNLOAD_COMPLETE=0')
        end = source.index('  stop_wine_app "$APP"', source.index('  if [[ $GAME_DOWNLOAD_COMPLETE', start))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'appmanifest.acf'
            manifest.write_text('"StateFlags" "1026"\n"buildid" "0"\n')
            prelude = '''set -eu
jot() { printf '1\\n15\\n16\\n30\\n'; }
pgrep_mock() { return 0; }
sleep_mock() { :; }
PGREP_COMMAND=pgrep_mock
SLEEP_COMMAND=sleep_mock
EXPECTED_BUILD_ID=25784167
APP=/test-app
GAME_MANIFEST=$1
STEAM=${1%/*}
'''
            result = subprocess.run(
                ['bash', '-c', prelude + source[start:end], 'test', str(manifest)],
                capture_output=True, text=True, timeout=5)
        self.assertNotIn('syntax error', result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 2, result.stdout)
        self.assertIn('30 seconds', result.stdout)
        self.assertIn('60 seconds', result.stdout)

    def test_status_counters_do_not_use_bash_special_underscore(self):
        source = SCRIPT.read_text()
        self.assertNotIn('for _ in $(jot', source)
        self.assertNotIn('(( _ %', source)


if __name__ == '__main__':
    unittest.main()
