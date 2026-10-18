#!/usr/bin/env python3
"""Test the real icon pipeline in a disposable app using the installed Steam ICO."""
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/install-pagonia-gptk4b3.sh'
STEAM = Path('/Applications/Pioneers of Pagonia.app/Contents/SharedSupport/prefix/'
             'drive_c/Program Files (x86)/Steam')


class IconTests(unittest.TestCase):
    def test_uses_verified_game_ico_without_promotional_padding(self):
        source = SCRIPT.read_text()
        self.assertIn('ARTWORK="$STEAM/steam/games/$GAME_ICON_NAME"', source)
        self.assertNotIn('library_capsule.jpg', source)
        self.assertNotIn('--padToHeightWidth', source)

    def test_registration_removes_the_stale_entry_before_refreshing(self):
        source = SCRIPT.read_text()
        start = source.index('if [[ -x "$LSREGISTER" ]]; then')
        end = source.index('\nfi', start) + len('\nfi')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recorder = root / 'lsregister'
            recorder.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >>"$EVENTS"\n')
            recorder.chmod(0o700)
            events = root / 'events'
            prelude = ('set -eu\nLSREGISTER=$1/lsregister\nexport EVENTS=$1/events\n'
                       'DESTINATION="/Applications/Pioneers of Pagonia.app"\n')
            subprocess.run(['bash', '-c', prelude + source[start:end],
                            'test', str(root)], check=True, timeout=5)
            self.assertEqual(events.read_text().splitlines(), [
                '-u /Applications/Pioneers of Pagonia.app',
                '-f /Applications/Pioneers of Pagonia.app'])

    def test_native_icon_generation_and_bundle_reference(self):
        source = SCRIPT.read_text()
        constants = '\n'.join(l for l in source.splitlines()
                              if l.startswith(('GAME_ICON_NAME=', 'EXPECTED_GAME_ICON=')))
        name = next(l.split("'", 2)[1] for l in constants.splitlines()
                    if l.startswith('GAME_ICON_NAME='))
        if not (STEAM / 'steam/games' / name).exists():
            self.skipTest('Requires the installed official Steam game icon')
        start = source.index('# Use the actual transparent game icon')
        end = source.index("printf '%s\\n' '7/7", start)
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / 'Test.app'
            (app / 'Contents/Resources').mkdir(parents=True)
            plist = app / 'Contents/Info.plist'
            plist.write_bytes(plistlib.dumps({'CFBundleIconFile': 'old.icns'}))
            prelude = '''set -eu
APP=$1
PLIST=$APP/Contents/Info.plist
STEAM=$2
require_hash() { [[ "$(shasum -a 256 "$1" | awk '{print $1}')" == "$2" ]]; }
remove_stopped_tree() { rm -rf -- "$@"; }
'''
            result = subprocess.run(['bash', '-c', prelude + constants + '\n' +
                                     source[start:end], 'test', str(app), str(STEAM)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('CGColor', result.stdout + result.stderr)
            icon = app / 'Contents/Resources/PagoniaGame.icns'
            self.assertGreater(icon.stat().st_size, 0)
            self.assertEqual(plistlib.loads(plist.read_bytes())['CFBundleIconFile'],
                             'PagoniaGame.icns')
            refresh_start = source.index('if ! /usr/bin/osascript -l JavaScript')
            refresh_end = source.index('\nif [[ -x "$LSREGISTER" ]]', refresh_start)
            refresh = subprocess.run(['bash', '-c', 'set -eu\nDESTINATION=$1\n' +
                                      source[refresh_start:refresh_end], 'test', str(app)],
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(refresh.returncode, 0, refresh.stderr)
            self.assertNotIn('WARNING:', refresh.stderr)
            self.assertTrue((app / 'Icon\r').exists())
            attributes = subprocess.check_output(['xattr', str(app)], text=True)
            self.assertIn('com.apple.FinderInfo', attributes)


if __name__ == '__main__':
    unittest.main()
