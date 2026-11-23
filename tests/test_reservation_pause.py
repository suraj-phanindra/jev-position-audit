import base64
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from harness.audit import digest, encode, read_jsonl
from harness.billing import SpendingLedger
from preflight.live_check import MODELS, payload
from preflight.repeats import run, resume


class ReservationPauseCheck(unittest.TestCase):
    def test_external_barrier_drains_calls_and_rolls_back_blocked_reservation(self):
        self.assertIsNotNone(importlib.util.find_spec('preflight.reservation_pause'))
        from preflight.reservation_pause import install, remove
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root/'budget.sqlite'; output = root/'calls.jsonl'
            ledger = SpendingLedger(path, 10)
            body = encode(payload('together'))
            rows = [dict(provider='together', request_body=body, request_sha256=digest(body),
                         meta={'id': i}, replicate=0, sample=0, attempt=0) for i in range(10)]
            calls = []; lock = threading.Lock()
            def fetch(row, key):
                with lock:
                    calls.append(row)
                    if len(calls) == 2: install(path)
                time.sleep(.08)
                data = {'model': MODELS['together'], 'usage': {'prompt_tokens': 100, 'completion_tokens': 10},
                        'choices': [{'finish_reason': 'stop', 'message':
                            {'content': encode({'noul': 'true', 'choice': 'X', 'score': '2'})}}]}
                return {**row, 'status': 200, 'response_body_b64':
                        base64.b64encode(encode(data).encode()).decode()}
            try:
                with patch.dict('os.environ', TOGETHER_API_KEY='test-only'), \
                     patch('preflight.repeats.fetch', side_effect=fetch):
                    with self.assertRaises(RuntimeError): run(rows, output, 10, 200, 3, ledger)
                saved = read_jsonl(output)
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(saved), 2)
                self.assertEqual(ledger.summary()['unsettled_attempts'], 0)
                self.assertAlmostEqual(ledger.summary()['charged_or_reserved_usd'], .0000336)
                self.assertEqual(ledger.db.execute('SELECT count(*) FROM attempts').fetchone()[0], 2)
                self.assertEqual(len(resume(rows, saved)), 8)
                with self.assertRaises(sqlite3.IntegrityError): ledger.reserve(rows[2])
                self.assertAlmostEqual(ledger.summary()['charged_or_reserved_usd'], .0000336)
                remove(path)
                reservation = ledger.reserve(rows[2])
                self.assertIsNotNone(reservation)
                ledger.settle({**rows[2], 'billing_reservation': reservation, 'status': None})
            finally:
                ledger.close()


if __name__ == '__main__': unittest.main()
