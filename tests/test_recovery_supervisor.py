from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import subprocess
import time
import unittest
from unittest.mock import patch

from preflight.supervise_recovery import main, state


class RecoverySupervisorCheck(unittest.TestCase):
    def test_zombie_child_is_terminal_not_live(self):
        child = os.fork()
        if child == 0: os._exit(0)
        try:
            deadline = time.monotonic()+5
            while time.monotonic() < deadline:
                status = subprocess.check_output(['ps','-p',str(child),'-o','stat='],text=True).strip()
                if status.startswith('Z'): break
                time.sleep(.01)
            self.assertTrue(status.startswith('Z'))
            with tempfile.TemporaryDirectory() as directory:
                terminal=Path(directory)/'exit.json'
                terminal.write_text(json.dumps(dict(exit_code=0)))
                self.assertEqual(state(dict(supervisor_pid=child,exit_record=str(terminal)),
                                       datetime.now(timezone.utc)), 'complete')
        finally:
            try: os.waitpid(child,0)
            except ChildProcessError: pass

    def test_launch_limit_and_validation_refusal_end_recovery(self):
        previous=Path.cwd()
        try:
            for case in ('limit','refusal','deadline'):
                refusal=case=='refusal'
                with tempfile.TemporaryDirectory() as directory:
                    root=Path(directory);runs=root/'runs/main-v1';runs.mkdir(parents=True)
                    jobs=[dict(provider=p,exit_record=p+'.json') for p in ('typesafe','anthropic','together')]
                    (runs/'active-processes.json').write_text(json.dumps(jobs))
                    status=lambda job,now: 'retry'
                    with patch('preflight.supervise_recovery.ROOT',root), \
                         patch('preflight.supervise_recovery.verify_amendment',return_value='fixed'), \
                         patch('preflight.supervise_recovery.MAX_RECOVERIES',1), \
                         patch('preflight.supervise_recovery.MAX_HOURS',0 if case=='deadline' else 6), \
                         patch('preflight.supervise_recovery.state',side_effect=status), \
                         patch('preflight.supervise_recovery.time.sleep') as sleep, \
                         patch('preflight.supervise_recovery.recover',side_effect=ValueError('invalid HTTP 200') if refusal else None) as launch:
                        self.assertEqual(main(),1)
                        if case=='deadline':launch.assert_not_called()
                        else:launch.assert_called_once_with('typesafe',initiator='amendment 003 bounded supervisor')
                        sleep.assert_not_called()
                    result=json.loads(next(runs.glob('*-exit.json')).read_text())
                    self.assertEqual(result['recoveries'],0 if case=='deadline' else 1)
                    self.assertEqual(result['status'],'review_required' if refusal else 'supervision_limit')
                    if refusal:self.assertIn('typesafe',result['disabled'])
        finally:os.chdir(previous)

    def test_live_terminal_cooldown_backoff_and_attempt_cap(self):
        previous=Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.chdir(directory)
                root=Path('runs/main-v1/typesafe/screening');root.mkdir(parents=True)
                segment=root/'segment.jsonl';segment.write_text(json.dumps(dict(status=529,attempt=0))+'\n')
                now=datetime.now(timezone.utc);terminal=Path('exit.json')
                terminal.write_text(json.dumps(dict(exit_code=1,finished_at=(now-timedelta(seconds=90)).isoformat())))
                job=dict(provider='typesafe',supervisor_pid=123,exit_record=str(terminal))
                with patch('preflight.supervise_recovery.process_running',return_value=True):
                    self.assertEqual(state(job,now),'live')
                with patch('preflight.supervise_recovery.process_running',return_value=False):
                    self.assertEqual(state(job,now),'retry')
                    job['cooldown_until']=(now+timedelta(minutes=40)).isoformat()
                    self.assertEqual(state(job,now),'wait');del job['cooldown_until']
                    segment.write_text(json.dumps(dict(status=None,attempt=1))+'\n')
                    self.assertEqual(state(job,now),'wait')
                    self.assertEqual(state(job,now+timedelta(seconds=31)),'retry')
                    segment.write_text(json.dumps(dict(status=529,attempt=2))+'\n')
                    with self.assertRaises(ValueError):state(job,now)
                    terminal.write_text(json.dumps(dict(exit_code=0)))
                    self.assertEqual(state(job,now),'complete')
                    terminal.unlink()
                    with self.assertRaises(FileNotFoundError):state(job,now)
        finally:os.chdir(previous)
