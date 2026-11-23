"""Disclosed post-registration amendment 001: explicit Jev overload recovery only."""
import base64
import hashlib
import json
from pathlib import Path
import sys

from preflight import main_run

ORIGINAL_HISTORY=main_run.valid_history
ORIGINAL_SCHEDULE=main_run.manifest_schedule
RECORD=Path('amendments/001-overload-529.json')


def valid_history(records,provider):
    regular=[]
    for row in records:
        if row['status']==529 and provider=='typesafe':
            data=json.loads(base64.b64decode(row['response_body_b64'],validate=True))
            if data.get('detail',{}).get('error_type')!='system_overloaded':
                raise ValueError('Amendment 001 only covers explicit Jev system_overloaded responses')
        else:regular.append(row)
    ORIGINAL_HISTORY(regular,provider)


def main():
    a=sys.argv[1:]
    if '--provider' not in a or a[a.index('--provider')+1]!='typesafe' or '--retry-transient' not in a:
        raise ValueError('Amendment 001 only permits explicit Jev transient-retry invocation')
    amendment=json.loads(RECORD.read_text())
    for name,expected in amendment['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Amendment artifact changed: '+name)
    digest=hashlib.sha256(RECORD.read_bytes()).hexdigest()
    def schedule(*args,**kwargs):
        return [{**r,'operational_amendment':'001-overload-529','operational_amendment_sha256':digest}
                for r in ORIGINAL_SCHEDULE(*args,**kwargs)]
    # Keep all original request/response validation, manifests, caps, and stopping rules.
    main_run.valid_history=valid_history
    main_run.manifest_schedule=schedule
    main_run.main()

if __name__=='__main__':main()
