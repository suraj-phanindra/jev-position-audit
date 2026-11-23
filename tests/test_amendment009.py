import copy
from decimal import Decimal
import unittest
from unittest.mock import patch

from harness import audit
from preflight import amendment009 as adapter, recover as operator


class RoundoffChecks(unittest.TestCase):
    def test_boundary_only_and_no_mutation(self):
        q = {'type': 'choice', 'criteria': {'X': 'x', 'Y': 'y', 'Z': 'z'}}
        a = {'type': 'choice', 'choice': 'X', 'confidence': .2,
             'probabilities': {'X': .27999999999999997, 'Y': .29, 'Z': .43}}
        # Use an additional outcome to reproduce a valid distribution whose maximum is .29.
        q['criteria'].update(W='w')
        a['probabilities'].update(Z=.22, W=.21)
        original = copy.deepcopy(a)
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            audit.target_value(a, q, 'X')
        with adapter.installed():
            self.assertEqual(audit.target_value(a, q, 'X'), Decimal('0.27999999999999997'))
            self.assertEqual(a, original)
            for replacement in (.279999, .27):
                with self.assertRaisesRegex(ValueError, 'contradicts'):
                    audit.target_value({**a, 'probabilities': {**a['probabilities'], 'X': replacement}}, q, 'X')
            with self.assertRaises(ValueError):
                audit.target_value({**a, 'confidence': 2}, q, 'X')
            with self.assertRaises(ValueError):
                audit.target_value({**a, 'choice': 'unknown'}, q, 'X')
        self.assertIs(audit.target_value, adapter.ORIGINAL_TARGET)
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            audit.target_value(a, q, 'X')

    def test_routing_and_pause(self):
        self.assertEqual(adapter.child_command(['python', '-u', '-m', 'preflight.amendment001',
                                                'package', 'receipt', '--provider', 'typesafe', '--retry-transient'])[3],
                         'preflight.amendment009')
        with patch.object(adapter, 'verify'), patch.object(adapter.scheduled_pause, 'due', return_value=True), \
                patch.object(operator, 'recover') as launch:
            with self.assertRaises(ValueError): adapter.recover('typesafe')
            launch.assert_not_called()


if __name__ == '__main__': unittest.main()
