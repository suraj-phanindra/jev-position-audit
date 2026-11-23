import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class ScheduledRecoveryChecks(unittest.TestCase):
    def test_supervisor_routes_every_provider_to_pause_adapter_and_records_exit(self):
        self.assertIsNotNone(importlib.util.find_spec('preflight.supervise_scheduled'))
        from preflight.supervise_scheduled import SUPERVISOR, child_command
        for provider, code in [('typesafe', 75), ('anthropic', 1), ('together', 0)]:
            module = 'preflight.amendment001' if provider == 'typesafe' else 'preflight.main_run'
            command = [sys.executable, '-u', '-m', module, 'package', 'receipt',
                       '--provider', provider, '--retry-transient']
            expected = command.copy(); expected[3] = 'preflight.scheduled_pause'
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as directory:
                terminal = Path(directory)/'exit.json'
                with patch('sys.argv', ['supervisor', str(terminal), *command]), \
                     patch('subprocess.call', return_value=code) as call:
                    with self.assertRaises(SystemExit) as raised: exec(SUPERVISOR, {})
                    self.assertEqual(raised.exception.code, code)
                    call.assert_called_once_with(expected)
                self.assertEqual(json.loads(terminal.read_text())['exit_code'], code)
                if code == 75:
                    from datetime import datetime, timezone
                    from preflight.supervise_recovery import state
                    with patch('preflight.supervise_recovery.process_running', return_value=False):
                        with self.assertRaisesRegex(ValueError, 'Unexpected collector exit code'):
                            state(dict(supervisor_pid=123, exit_record=str(terminal)),
                                  datetime.now(timezone.utc))
        with self.assertRaises(ValueError): child_command(['python', '-m', 'other'])

    def test_hold_refuses_recovery_and_checked_helper_is_preserved(self):
        self.assertIsNotNone(importlib.util.find_spec('preflight.supervise_scheduled'))
        from preflight import supervise_scheduled as scheduled, recover as operator
        original = operator.SUPERVISOR
        with patch.object(scheduled, 'verify'), patch.object(scheduled, 'due', return_value=True), \
             patch.object(operator, 'recover') as recover:
            with self.assertRaises(ValueError): scheduled.recover('together')
            recover.assert_not_called()
        def checked(provider, initiator):
            self.assertEqual(operator.SUPERVISOR, scheduled.SUPERVISOR)
            self.assertEqual(provider, 'together')
            self.assertIn('007', initiator)
            raise ValueError('existing eligibility guard refused recovery')
        with patch.object(scheduled, 'verify'), patch.object(scheduled, 'due', return_value=False), \
             patch.object(operator, 'recover', side_effect=checked):
            with self.assertRaisesRegex(ValueError, 'eligibility guard'):
                scheduled.recover('together')
        self.assertEqual(operator.SUPERVISOR, original)


if __name__ == '__main__': unittest.main()
