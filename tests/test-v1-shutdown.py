#!/usr/bin/env python3
"""Exercise shutdown ordering with fake server/process probes, never real Wine."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/install-pagonia-gptk4b3.sh'


class ShutdownTests(unittest.TestCase):
    def shutdown(self, stuck=False):
        source = SCRIPT.read_text()
        start = source.index('stop_wine_app() {')
        end = source.index('\nstop_if_running() {', start)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / 'Test.app'
            server = app / 'Contents/SharedSupport/wine/bin/wineserver'
            server.parent.mkdir(parents=True)
            server.write_text('#!/bin/bash\nprintf "server:%s\\n" "$*" >>"$EVENTS"\n')
            server.chmod(0o700)
            (app / 'Contents/SharedSupport/prefix').mkdir()
            events = root / 'events'
            count = root / 'count'
            count.write_text('0')
            prelude = '''set -eu
export EVENTS=$1/events
COUNT=$1/count
WINE_PROCESS_PATTERN=fixture-process-pattern
pgrep_mock() {
  local n
  n=$(<"$COUNT")
  printf '%s' "$((n + 1))" >"$COUNT"
  if [[ STUCK == 1 || $n -lt 2 ]]; then return 0; fi
  return 1
}
sleep_mock() { echo sleep >>"$EVENTS"; }
PGREP_COMMAND=pgrep_mock
SLEEP_COMMAND=sleep_mock
'''.replace('STUCK', '1' if stuck else '0')
            result = subprocess.run(['bash', '-c', prelude + source[start:end] +
                                     '\nstop_wine_app "$1/Test.app"\n', 'test', str(root)],
                                    capture_output=True, text=True, timeout=5)
            return result, events.read_text().splitlines()

    def test_waits_for_launcher_and_server_before_returning(self):
        result, events = self.shutdown()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ['server:-k', 'sleep', 'sleep', 'sleep'])
        self.assertIn('shutdown confirmed', result.stdout)

    def test_stuck_processes_fail_without_another_launch_or_forced_kill(self):
        result, events = self.shutdown(stuck=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ERROR:', result.stderr)
        self.assertEqual(events.count('server:-k'), 1)
        self.assertNotIn('shutdown confirmed', result.stdout)

    def test_live_process_blocks_directory_removal(self):
        source = SCRIPT.read_text()
        start = source.index('remove_stopped_tree() {')
        end = source.index('\nfind_resume_staging() {', start)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'keep'
            path.mkdir()
            result = subprocess.run(['bash', '-c', 'set -eu\n'
                                     'stop_if_running() { return 1; }\n' +
                                     source[start:end] + '\nremove_stopped_tree "$1"',
                                     'test', str(path)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(path.is_dir())


if __name__ == '__main__':
    unittest.main()
