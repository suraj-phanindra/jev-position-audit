import base64
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from harness.audit import digest, encode, read_jsonl
from harness.billing import SpendingLedger
from preflight.live_check import MODELS, payload
from preflight.repeats import resume


class ScheduledPauseChecks(unittest.TestCase):
    def test_pause_drains_inflight_preserves_receipts_and_resume(self):
        self.assertIsNotNone(importlib.util.find_spec('preflight.scheduled_pause'),
                             'Scheduled pause must exist before overnight collection')
        from preflight.scheduled_pause import Paused, run
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); control = root/'control.json'; output = root/'run.jsonl'
            control.write_text(json.dumps({'state': 'running', 'stop_at':
                (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}))
            body = encode(payload('together'))
            rows = [dict(provider='together', request_body=body, request_sha256=digest(body),
                         meta={'id': i}, replicate=0, sample=0, attempt=0) for i in range(10)]
            calls = []; lock = threading.Lock()
            def fetch(row, key):
                with lock:
                    calls.append(row)
                    if len(calls) == 2:
                        control.write_text(json.dumps({'state': 'pause', 'stop_at':
                            (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}))
                time.sleep(.08)
                data = {'model': MODELS['together'], 'usage': {'prompt_tokens': 100, 'completion_tokens': 10},
                        'choices': [{'finish_reason': 'stop', 'message':
                            {'content': encode({'noul': 'true', 'choice': 'X', 'score': '2'})}}]}
                return {**row, 'status': 200, 'response_body_b64':
                        base64.b64encode(encode(data).encode()).decode()}
            ledger = SpendingLedger(root/'budget.sqlite', 10)
            try:
                with patch.dict('os.environ', TOGETHER_API_KEY='test-only'), \
                     patch('preflight.repeats.fetch', side_effect=fetch):
                    with self.assertRaises(Paused):
                        run(rows, output, 10, 200, 3, ledger, control=control)
                saved = read_jsonl(output)
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(saved), 2)
                self.assertEqual(ledger.summary()['unsettled_attempts'], 0)
                self.assertEqual(len(resume(rows, saved)), 8)
                self.assertTrue(all(r['request_body'] == body for r in saved))
                receipt = json.loads(Path(str(output)+'.pause.json').read_text())
                self.assertEqual(receipt['status'], 'paused_and_drained')
                self.assertEqual(receipt['completed'], 2)
            finally:
                ledger.close()

    def test_deadline_invalid_control_and_real_failure_are_distinct(self):
        self.assertIsNotNone(importlib.util.find_spec('preflight.scheduled_pause'))
        from preflight.scheduled_pause import Paused, due, run
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); control = root/'control.json'
            now = datetime.now(timezone.utc)
            control.write_text(json.dumps({'state': 'running', 'stop_at': now.isoformat()}))
            self.assertTrue(due(control, now=now))
            self.assertFalse(due(control, now=now-timedelta(seconds=1)))
            control.write_text(json.dumps({'state': 'running', 'stop_at': '2026-09-24T07:25:00'}))
            with self.assertRaises(ValueError): due(control)
            control.write_text(json.dumps({'state': 'other', 'stop_at': now.isoformat()}))
            with self.assertRaises(ValueError): due(control)
            body = encode(payload('together'))
            row = dict(provider='together', request_body=body, request_sha256=digest(body), attempt=0)
            for state, cap, paused in [('pause', 1, True), ('running', .01, False)]:
                control.write_text(json.dumps({'state': state, 'stop_at':
                    (now+timedelta(hours=1)).isoformat()}))
                ledger = SpendingLedger(root/(state+'.sqlite'), cap)
                try:
                    with patch.dict('os.environ', TOGETHER_API_KEY='test-only'), \
                         patch('preflight.repeats.fetch') as fetch:
                        with self.assertRaises(Paused if paused else RuntimeError):
                            run([row], root/(state+'.jsonl'), 1, 2, 1, ledger, control=control)
                        fetch.assert_not_called()
                    self.assertEqual(ledger.summary()['charged_or_reserved_usd'], 0)
                    self.assertEqual(Path(str(root/(state+'.jsonl'))+'.pause.json').exists(), paused)
                finally:
                    ledger.close()

    def test_pause_does_not_mask_invalid_response_or_settlement_failure(self):
        from preflight.scheduled_pause import Paused, run
        for failure in ('model', 'settlement'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); control = root/'control.json'; output = root/'run.jsonl'
                config = {'state': 'running', 'stop_at':
                          (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
                control.write_text(json.dumps(config))
                body = encode(payload('together'))
                rows = [dict(provider='together', request_body=body, request_sha256=digest(body),
                             attempt=0) for _ in range(3)]
                def fetch(row, key):
                    control.write_text(json.dumps({**config, 'state': 'pause'}))
                    time.sleep(.05)
                    data = {'model': 'wrong' if failure == 'model' else MODELS['together'],
                            'usage': {'prompt_tokens': 1, 'completion_tokens': 1},
                            'choices': [{'finish_reason': 'stop', 'message':
                                {'content': encode({'noul': 'true', 'choice': 'X', 'score': '2'})}}]}
                    return {**row, 'status': 200, 'response_body_b64':
                            base64.b64encode(encode(data).encode()).decode()}
                ledger = SpendingLedger(root/'budget.sqlite', 10)
                if failure == 'settlement':
                    def fail(record): raise ValueError('simulated settlement failure')
                    ledger.settle = fail
                try:
                    with patch.dict('os.environ', TOGETHER_API_KEY='test-only'), \
                         patch('preflight.repeats.fetch', side_effect=fetch):
                        with self.assertRaises((ValueError, RuntimeError)) as raised:
                            run(rows, output, 3, 200, 2, ledger, control=control)
                        self.assertNotIsInstance(raised.exception, Paused)
                    self.assertEqual(len(read_jsonl(output)), 1)
                    self.assertFalse(Path(str(output)+'.pause.json').exists())
                finally:
                    ledger.close()


if __name__ == '__main__': unittest.main()
