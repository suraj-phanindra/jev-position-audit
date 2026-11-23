import base64
from collections import Counter
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from preflight.recover import eligible, recover


class OperatorRecoveryChecks(unittest.TestCase):
    def test_cooldown_prevents_launch(self):
        previous = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory); runs = root/'runs/main-v1'; runs.mkdir(parents=True)
                (runs/'active-processes.json').write_text(json.dumps([
                    {'provider': 'typesafe', 'cooldown_until': '2999-01-01T00:00:00+00:00'}]))
                with patch('preflight.recover.ROOT', root), patch('preflight.recover.subprocess.Popen') as launch:
                    with self.assertRaisesRegex(ValueError, 'cooldown'): recover('typesafe')
                    launch.assert_not_called()
        finally: os.chdir(previous)

    def test_only_eligible_retained_failure_segments(self):
        def summary(rows):
            return dict(stopped_on_failure=True, budget_exhausted=False, billing_errors=[],
                        completed=len(rows), statuses=dict(Counter(str(r['status']) for r in rows)))
        row = dict(provider='typesafe', status=529, attempt=0,
                   response_body_b64=base64.b64encode(json.dumps(
                       {'detail': {'error_type': 'system_overloaded'}}).encode()).decode())
        self.assertEqual(eligible([row], summary([row]), 'typesafe')[0]['attempt'], 0)
        for change in ({'attempt': 2}, {'status': 401}, {'provider': 'together'},
                       {'response_body_b64': base64.b64encode(b'{}').decode()}):
            bad = {**row, **change}
            with self.assertRaises(ValueError): eligible([bad], summary([bad]), 'typesafe')
        for change in ({'stopped_on_failure': False}, {'budget_exhausted': True},
                       {'billing_errors': ['ValueError']}, {'completed': 2}, {'statuses': {}}):
            with self.assertRaises(ValueError): eligible([row], {**summary([row]), **change}, 'typesafe')
        timeout = dict(provider='together', status=None, attempt=1, transport_error='TimeoutError')
        self.assertEqual(len(eligible([timeout], summary([timeout]), 'together')), 1)
        bad_success = dict(provider='typesafe', status=200, attempt=0, request_body='{}',
                           response_body_b64=base64.b64encode(b'{}').decode())
        with patch('preflight.main_run.check_response', return_value={'model_match': False, 'valid_answers': True}):
            with self.assertRaises(ValueError):
                eligible([row, bad_success], summary([row, bad_success]), 'typesafe')


if __name__ == '__main__': unittest.main()
