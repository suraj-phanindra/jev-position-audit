import importlib.util
import json
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from preflight.recover import SUPERVISOR


class IdlePauseChecks(unittest.TestCase):
    def test_real_process_stops_only_with_no_unsettled_requests(self):
        self.assertIsNotNone(importlib.util.find_spec('preflight.idle_pause'))
        from preflight.idle_pause import attempt, group
        for pending in (False, True):
            with self.subTest(pending=pending), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); terminal = root/'exit.json'
                db = sqlite3.connect(root/'spending.sqlite')
                db.execute('CREATE TABLE attempts (provider TEXT, charged INTEGER)')
                if pending: db.execute("INSERT INTO attempts VALUES ('together', NULL)")
                db.commit(); db.close()
                child = subprocess.Popen([sys.executable, '-u', '-c', SUPERVISOR, str(terminal),
                    sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
                job = dict(provider='together', supervisor_pid=child.pid,
                           exit_record=str(terminal), console=str(root/'console.log'))
                (root/'active-processes.json').write_text(json.dumps([job]))
                try:
                    deadline = time.monotonic()+5
                    while time.monotonic() < deadline:
                        members = group(child.pid)
                        if len(members) == 2: break
                        time.sleep(.01)
                    self.assertEqual(len(members), 2)
                    with patch('preflight.idle_pause.verified_group', return_value=members):
                        result = attempt('together', root=root)
                    if pending:
                        self.assertIsNone(result)
                        self.assertIsNone(child.poll())
                        self.assertFalse(any(r['stat'].startswith('T') for r in group(child.pid)))
                    else:
                        self.assertEqual(result['status'], 'stopped_at_verified_idle_checkpoint')
                        self.assertEqual(json.loads(terminal.read_text())['exit_code'], -signal.SIGKILL)
                        child.wait(timeout=5)
                finally:
                    if child.poll() is None:
                        import os
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=5)

    def test_race_that_adds_request_after_first_check_resumes_group(self):
        self.assertIsNotNone(importlib.util.find_spec('preflight.idle_pause'))
        from preflight.idle_pause import attempt
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = dict(provider='together', supervisor_pid=111, exit_record=str(root/'exit.json'))
            (root/'active-processes.json').write_text(json.dumps([job]))
            members = [dict(pid=111, ppid=1, pgid=111, stat='T'),
                       dict(pid=112, ppid=111, pgid=111, stat='T')]
            with patch('preflight.idle_pause.pending', side_effect=[0, 1]), \
                 patch('preflight.idle_pause.verified_group', return_value=members), \
                 patch('preflight.idle_pause.group', return_value=members), \
                 patch('preflight.idle_pause.os.killpg') as killpg, \
                 patch('preflight.idle_pause.os.kill') as kill:
                self.assertIsNone(attempt('together', root=root))
                self.assertEqual([c.args[1] for c in killpg.call_args_list],
                                 [signal.SIGSTOP, signal.SIGCONT])
                kill.assert_not_called()


if __name__ == '__main__': unittest.main()
