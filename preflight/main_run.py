"""Run registered schedules with hash verification, retained failures, and one shared cap."""
import argparse
import base64
from datetime import datetime,timezone
import json
from pathlib import Path
from urllib.parse import urlparse

from harness.audit import load_env,read_jsonl
from harness.billing import SpendingLedger
from preflight.freeze import sha
from preflight.live_check import check_response
from preflight.repeats import manifest_schedule,resume,run


def verify(directory,receipt_path):
    directory=Path(directory);receipt=json.loads(Path(receipt_path).read_text())
    url=urlparse(receipt['registration_url'])
    if url.scheme!='https' or not (url.hostname=='osf.io' or (url.hostname or '').endswith('.osf.io')):
        raise ValueError('External OSF registration URL required')
    timestamp=datetime.fromisoformat(receipt['registered_at'].replace('Z','+00:00'))
    if timestamp.tzinfo is None or timestamp>datetime.now(timezone.utc):raise ValueError('Invalid registration timestamp')
    if receipt['index_sha256']!=sha(directory/'INDEX.json') or receipt.get('verified_external_copy') is not True:
        raise ValueError('Exact external registration package has not been verified')
    index=json.loads((directory/'INDEX.json').read_text())
    for name,expected in index['files'].items():
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe registration path')
        if sha(directory/relative)!=expected:raise ValueError('Registered artifact changed: '+name)
        if relative.parts[0]=='snapshot' and relative.suffix=='.py':
            if sha(Path(*relative.parts[1:]))!=expected:raise ValueError('Executable differs from registered source: '+name)
    return json.loads((directory/'DESIGN.json').read_text())


def valid_history(records,provider):
    # No retry-until-valid sampling; HTTP-200 semantic failures require a dated amendment.
    for row in records:
        if row['status']==200:
            d=json.loads(base64.b64decode(row['response_body_b64']))
            summary=check_response(provider,d,json.loads(row['request_body']))
            if not summary['model_match'] or not summary['valid_answers']:
                raise ValueError('Invalid prior HTTP-200 result; stop for protocol amendment')
        elif row['status'] not in (None,408,429,500,502,503,504):
            raise ValueError('Nontransient prior error; stop for protocol amendment')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('package');p.add_argument('registration_receipt')
    p.add_argument('--provider',choices=['typesafe','anthropic','together'],required=True)
    p.add_argument('--env-file',default='.env')
    p.add_argument('--retry-transient',action='store_true');args=p.parse_args()
    spec=verify(args.package,args.registration_receipt);load_env(args.env_file)
    root=Path('runs/main-v1');root.mkdir(parents=True,exist_ok=True)
    # All providers and resumes share this ledger; changing run-root mid-study is prohibited.
    ledger=SpendingLedger(root/'spending.sqlite',spec['main_spending_limit_usd'])
    roles=('screening','jev_outcomes') if args.provider=='typesafe' else ('reference',)
    try:
        for role in roles:
            for schedule in spec['schedules']:
                if schedule['role']!=role:continue
                manifest=read_jsonl(Path(args.package)/schedule['path'])
                repeats=spec['jev_samples'] if args.provider=='typesafe' else spec['reference_samples']
                rows=manifest_schedule(manifest,args.provider,repeats,canonical_schema=True)
                output=root/args.provider/Path(schedule['path']).name.removesuffix('.jsonl.gz')
                prior=[r for path in sorted(output.glob('*.jsonl')) for r in read_jsonl(path)]
                valid_history(prior,args.provider)
                for r in prior:ledger.settle(r)
                remaining=resume(rows,prior,args.retry_transient)
                if not args.retry_transient and any(r['status']!=200 for r in prior):
                    raise ValueError('Retained transient failures require explicit --retry-transient')
                if any(r['attempt']>=3 for r in remaining):raise ValueError('Three-attempt limit reached; amendment required')
                if not remaining:continue
                remaining=[{**r,'phase':'main_'+role,'registration_index_sha256':sha(Path(args.package)/'INDEX.json')} for r in remaining]
                stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                print(json.dumps({'provider':args.provider,'schedule':schedule['path'],'remaining':len(remaining)}),flush=True)
                # Conservative pilot-supported pacing; provider throttling stops and drains.
                run(remaining,output/(stamp+'.jsonl'),len(remaining),4 if args.provider=='typesafe' else 2,4,ledger)
    finally:ledger.close()

if __name__=='__main__':main()
