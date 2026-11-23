import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from harness.audit import digest,encode
from harness.billing import SpendingLedger
from preflight.live_check import payload
from preflight.repeats import run

class BillingChecks(unittest.TestCase):
    def row(self,provider='together'):
        body=encode(payload(provider))
        return {'provider':provider,'request_body':body,'request_sha256':digest(body)}

    def test_shared_reservations_crash_persistence_and_idempotent_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'budget.sqlite';a=SpendingLedger(path,.31);b=SpendingLedger(path,.31)
            row=self.row();reservation=a.reserve(row)
            self.assertIsNotNone(reservation);self.assertIsNone(b.reserve(row))
            a.close();a=SpendingLedger(path,.31)
            self.assertEqual(a.summary()['unsettled_attempts'],1)
            data={'usage':{'prompt_tokens':100,'completion_tokens':10}}
            record={**row,'status':200,'billing_reservation':reservation,
                    'response_body_b64':base64.b64encode(encode(data).encode()).decode()}
            a.settle(record);b.settle(record)
            self.assertAlmostEqual(a.summary()['charged_or_reserved_usd'],.0000168)
            second=b.reserve(row);self.assertIsNotNone(second)
            b.settle({**row,'status':None,'billing_reservation':second})
            self.assertAlmostEqual(a.summary()['charged_or_reserved_usd'],.3000168)
            self.assertIsNone(a.reserve(row))
            with self.assertRaises(ValueError):SpendingLedger(path,.50)
            with self.assertRaises(ValueError):a.settle({**record,'request_sha256':'wrong'})
            a.close();b.close()

    def test_budget_stops_before_sending(self):
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',TYPESAFE_API_KEY='local-test-key'),patch('preflight.repeats.fetch') as fetch:
            ledger=SpendingLedger(Path(d)/'budget.sqlite',.001)
            with self.assertRaises(RuntimeError):run([self.row('typesafe')],Path(d)/'run.jsonl',1,1,1,ledger)
            self.assertEqual(fetch.call_count,0)
            self.assertEqual(ledger.summary()['charged_or_reserved_usd'],0)
            ledger.close()

if __name__=='__main__':unittest.main()
