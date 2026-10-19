#!/usr/bin/env python3
"""Test resume discovery in isolated fixtures, without Wine or installer execution."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/install-pagonia-gptk4b3.sh'
DESTINATION = '/Applications/Pioneers of Pagonia.app'


class ResumeTests(unittest.TestCase):
    def candidate(self, parent, suffix='ABC123', marked=True):
        root = parent / ('Pagonia-GPTK4b3-deployment.' + suffix)
        root.mkdir(mode=0o700)
        app = root / 'Pioneers of Pagonia.app'
        for relative in ('Contents/Info.plist', 'Contents/MacOS/wineskinlauncher',
                         'Contents/SharedSupport/d3d12core-engine.dll',
                         'Contents/SharedSupport/wine/bin/wine64',
                         'Contents/SharedSupport/wine/bin/wineserver'):
            target = app / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        (app / 'Contents/SharedSupport/prefix/drive_c').mkdir(parents=True)
        if marked:
            (root / '.pagonia-resume-v1').write_text(
                'pagonia-wine10-download-v1\n' + DESTINATION + '\n')
        return root

    def discover(self, parent):
        source = SCRIPT.read_text()
        start = source.index('find_resume_staging() {')
        end = source.index('\nverify_existing_deployment() {', start)
        return subprocess.run(['bash', '-c', 'set -eu\nDESTINATION=$2\n' +
                               source[start:end] + '\nfind_resume_staging "$1"',
                               'test', str(parent), DESTINATION],
                              capture_output=True, text=True, timeout=5)

    def test_unmarked_legacy_staging_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            self.candidate(parent, marked=False)
            result = self.discover(parent)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '')

    def test_single_valid_staging_is_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = self.candidate(parent)
            result = self.discover(parent)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(root))

    def test_multiple_candidates_fail_without_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            self.candidate(parent)
            self.candidate(parent, 'DEF456')
            result = self.discover(parent)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')

    def test_changed_missing_linked_and_public_staging_fail(self):
        for change in ('destination', 'missing', 'linked', 'permissions', 'marker-link'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory)
                root = self.candidate(parent)
                marker = root / '.pagonia-resume-v1'
                binary = root / 'Pioneers of Pagonia.app/Contents/SharedSupport/wine/bin/wine64'
                if change == 'destination':
                    marker.write_text('pagonia-wine10-download-v1\n/Applications/Other.app\n')
                elif change == 'missing':
                    binary.unlink()
                elif change == 'linked':
                    binary.unlink()
                    binary.symlink_to('/bin/sh')
                elif change == 'permissions':
                    root.chmod(0o755)
                else:
                    other = parent / 'marker'
                    marker.rename(other)
                    marker.symlink_to(other)
                result = self.discover(parent)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
