import base64
from collections import Counter
import sys
import unittest
from unittest.mock import patch

from preflight import amendment008 as adapter, amendment001, recover as operator
from preflight.live_check import URLS


class Http520Checks(unittest.TestCase):
    def test_exact_error_pattern_keeps_existing_guards(self):
        row = dict(provider='typesafe', endpoint=URLS['typesafe'], status=520,
                   attempt=0, response_body_b64=base64.b64encode(b'error code: 520\n').decode())
        def summary(rows):
            return dict(stopped_on_failure=True, budget_exhausted=False, billing_errors=[],
                        completed=len(rows), statuses=dict(Counter(str(r['status']) for r in rows)))
        before = amendment001.ORIGINAL_HISTORY
        with adapter.installed():
            self.assertEqual(operator.eligible([row], summary([row]), 'typesafe')[0]['status'], 520)
            for change in ({'attempt': 2}, {'status': 401}, {'endpoint': 'https://example.com'},
                           {'response_body_b64': base64.b64encode(b'other error').decode()},
                           {'provider': 'together'}):
                bad = {**row, **change}
                with self.assertRaises(ValueError):
                    operator.eligible([bad], summary([bad]), 'typesafe')
            with self.assertRaises(ValueError):
                adapter.valid_history([{**row, 'provider': 'together'}], 'together')
            with self.assertRaises(ValueError):
                operator.eligible([row], {**summary([row]), 'billing_errors': ['failure']}, 'typesafe')
            good = {**row, 'status': 200, 'request_body': '{}',
                    'response_body_b64': base64.b64encode(b'{}').decode()}
            with patch('preflight.main_run.check_response', return_value={'model_match': False, 'valid_answers': True}):
                with self.assertRaises(ValueError):
                    operator.eligible([row, good], summary([row, good]), 'typesafe')
        self.assertIs(amendment001.ORIGINAL_HISTORY, before)

    def test_pause_routing_and_no_launch_while_held(self):
        cmd = [sys.executable, '-u', '-m', 'preflight.amendment001', 'package',
               'receipt', '--provider', 'typesafe', '--retry-transient']
        self.assertEqual(adapter.child_command(cmd)[3], 'preflight.amendment008')
        with patch.object(adapter, 'verify'), patch.object(adapter.scheduled_pause, 'due', return_value=True), \
             patch.object(operator, 'recover') as launch:
            with self.assertRaises(ValueError): adapter.recover('typesafe')
            launch.assert_not_called()
        with patch.object(adapter, 'verify'), patch.object(adapter.scheduled_pause, 'main', return_value=75) as run, \
             patch.object(sys, 'argv', ['adapter', *cmd[4:]]):
            self.assertEqual(adapter.main(), 75)
            run.assert_called_once()


if __name__ == '__main__': unittest.main()
