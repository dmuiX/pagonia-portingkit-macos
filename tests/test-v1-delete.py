#!/usr/bin/env python3
"""Exercise deletion only in disposable fixture directories; never run Wine."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/install-pagonia-gptk4b3.sh'


class DeleteTests(unittest.TestCase):
    def run_delete(self, root, marker=True, linked=False, confirm=True, running=False):
        app = root / 'Pagonia.app'
        shared = app / 'Contents/SharedSupport'
        (shared / 'wine/bin').mkdir(parents=True)
        (shared / 'wine/bin/wine64').write_text('fixture-runtime')
        if marker:
            (shared / 'Pagonia-GPTK4b3-deployment.txt').write_text(
                'Pioneers of Pagonia GPTK deployment\n')
        if linked:
            alias = root / 'alias.app'
            alias.symlink_to(app, target_is_directory=True)
            destination = alias
        else:
            destination = app
        source = SCRIPT.read_text()
        start = source.index('if [[ $DELETE_MODE -eq 1 ]]; then')
        end = source.index("echo 'Preflight:", start)
        prelude = '''set -eu
DELETE_MODE=1
DESTINATION=$1
ASSUME_YES=0
EXPECTED_WINE64=fixture-runtime
require_file() { [[ -f "$1" && ! -L "$1" ]]; }
require_hash() { [[ "$(<"$1")" == "$2" ]]; }
yes_no() { return CONFIRM; }
stop_if_running() { return RUNNING; }
same_identity() { [[ "$(stat -f '%d' "$1")" == "$2" && "$(stat -f '%i' "$1")" == "$3" ]]; }
'''.replace('CONFIRM', '0' if confirm else '1').replace('RUNNING', '1' if running else '0')
        guard_start = source.index('remove_stopped_tree() {')
        guard_end = source.index('\nfind_resume_staging() {', guard_start)
        result = subprocess.run(['bash', '-c', prelude + source[guard_start:guard_end] + source[start:end],
                                 'test', str(destination)], capture_output=True,
                                text=True, timeout=5)
        return result, app

    def test_verified_app_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            result, app = self.run_delete(Path(directory))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(app.exists())

    def test_cancel_foreign_linked_and_running_are_preserved(self):
        for options in ({'confirm': False}, {'marker': False},
                        {'linked': True}, {'running': True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                result, app = self.run_delete(Path(directory), **options)
                self.assertTrue(app.exists(), result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
