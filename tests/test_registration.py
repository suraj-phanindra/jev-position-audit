import json
from pathlib import Path
import tempfile
import unittest
from preflight.freeze import compressed,sha
from preflight.main_run import verify,valid_history
from harness.audit import read_jsonl

class RegistrationChecks(unittest.TestCase):
    def test_compressed_schedule_and_registered_hash_gate(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);rows=[{'text':'α and newline\n'}]
            compressed(p/'rows.jsonl.gz',rows)
            self.assertEqual(read_jsonl(p/'rows.jsonl.gz'),rows)
            with self.assertRaises(FileExistsError):compressed(p/'rows.jsonl.gz',rows)
            (p/'DESIGN.json').write_text('{"tasks":212}')
            (p/'INDEX.json').write_text(json.dumps({'files':{n:sha(p/n) for n in ('DESIGN.json','rows.jsonl.gz')}}))
            receipt={'registration_url':'https://osf.io/test-fixture','registered_at':'2020-01-01T00:00:00Z',
                     'index_sha256':sha(p/'INDEX.json'),'verified_external_copy':True}
            (p/'receipt.json').write_text(json.dumps(receipt))
            self.assertEqual(verify(p,p/'receipt.json')['tasks'],212)
            receipt['verified_external_copy']=False;(p/'receipt.json').write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):verify(p,p/'receipt.json')
            receipt['verified_external_copy']=True;(p/'receipt.json').write_text(json.dumps(receipt))
            (p/'DESIGN.json').write_text('{"tasks":213}')
            with self.assertRaises(ValueError):verify(p,p/'receipt.json')
        valid_history([{'status':429},{'status':None}],'typesafe')
        with self.assertRaises(ValueError):valid_history([{'status':401}],'typesafe')

if __name__=='__main__':unittest.main()
