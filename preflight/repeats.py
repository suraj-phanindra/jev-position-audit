"""Paced, bounded repeat checks; raw records retained and no automatic retries."""
import argparse
import base64
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import time
import urllib.error
import urllib.request

from harness.audit import digest, encode, load_env, question, read_jsonl, validate_stimuli, validate_manifest
from preflight.live_check import KEYS, MODELS, URLS, NoRedirect, check_response, reference_payload


def schedule(stimuli, provider, repeats):
    validate_stimuli(stimuli)
    rows=[]
    for item in stimuli:
        stimulus={'state':{'task':item['prompt'],'candidates':[
            {'id':'X','text':item['x']},{'id':'Y','text':item['y']}]},
            'questions':{kind:question(kind,'X','Y',item.get('dimension','overall response quality'))
                         for kind in ('noul','choice','score')}}
        # Omit provider seeds: repetitions must not intentionally replay one draw.
        body=encode(reference_payload(provider,stimulus))
        for replicate in range(repeats):
            rows.append({'provider':provider,'replicate':replicate,'request_body':body,
                         'request_sha256':digest(body),'meta':{'stimulus_id':item['id'],
                         'seed_id':item['seed_id'],'source':item['source'],'gap_bin':item['gap_bin']}})
    random.Random(20260921).shuffle(rows)
    return rows


def manifest_schedule(manifest, provider, repeats, canonical_schema=False):
    validate_manifest(manifest)
    rows=[]
    for row in manifest:
        request=json.loads(row['request_body'])
        body=row['request_body'] if provider=='typesafe' else encode(reference_payload(provider,request,canonical_schema=canonical_schema))
        for sample in range(repeats):
            rows.append({**row,'provider':provider,'sample':sample,'request_body':body,
                         'jev_request_sha256':row['request_sha256'],'request_sha256':digest(body)})
    random.Random(20260922).shuffle(rows)
    return rows


def resume(rows, prior, retry_failed=False):
    def identity(row):
        return digest(json.dumps([row['provider'],row['request_sha256'],row['meta'],
                                  row['replicate'],row.get('sample')],sort_keys=True))
    wanted={identity(row):row for row in rows}
    if len(wanted)!=len(rows):raise ValueError('Duplicate schedule IDs')
    seen=defaultdict(list)
    for record in prior:
        sid=identity(record)
        if sid not in wanted:raise ValueError('Prior record not in this schedule')
        seen[sid].append(record)
    output=[]
    for row in rows:
        sid=identity(row);history=seen[sid]
        if any(r['status']==200 for r in history):continue
        if history and not retry_failed:continue
        output.append({**row,'schedule_id':sid,'attempt':len(history),
                       'replaces_failed_attempt':bool(history)})
    return output


def fetch(row,key):
    provider=row['provider']
    headers={'Content-Type':'application/json','User-Agent':'jev-taxonomy-preflight/0.1'}
    if provider=='anthropic':headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
    else:headers['Authorization']='Bearer '+key
    record={**row,'phase':row.get('phase','repeat_preflight'),'endpoint':URLS[provider],
            'started_at':datetime.now(timezone.utc).isoformat()}
    start=time.monotonic()
    try:
        opener=urllib.request.build_opener(NoRedirect())
        with opener.open(urllib.request.Request(URLS[provider],row['request_body'].encode(),headers),timeout=60) as response:
            raw,status=response.read(),response.status
    except urllib.error.HTTPError as error:raw,status=error.read(),error.code
    except (OSError,urllib.error.URLError) as error:
        raw,status=b'',None
        record['transport_error']=type(error).__name__
        reason=getattr(error,'reason',error)
        record['transport_reason_type']=type(reason).__name__
        record['transport_errno']=getattr(reason,'errno',None)
    record.update(status=status,elapsed_s=time.monotonic()-start,response_body_b64=base64.b64encode(raw).decode())
    return record


def run(rows,output,max_calls,rate,workers,budget=None):
    if not rows or len(rows)>max_calls or rate<=0 or not 1<=workers<=32:raise ValueError('Invalid budget/rate/workers')
    if len({r['provider'] for r in rows})!=1:raise ValueError('One provider per run')
    provider=rows[0]['provider']
    key=os.environ.get(KEYS[provider])
    if not key:raise ValueError('Missing '+KEYS[provider])
    for row in rows:
        if digest(row['request_body'])!=row['request_sha256']:raise ValueError('Request hash mismatch')
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    counts=Counter(); completed=0; failed=False; exhausted=False; next_start=0; index=0; billing_errors=[]
    with open(output,'x') as stream, ThreadPoolExecutor(max_workers=workers) as pool:
        pending=set()
        while pending or (index<len(rows) and not failed):
            if index<len(rows) and not failed and len(pending)<workers and time.monotonic()>=next_start:
                row={**rows[index],'run_settings':{'rate_rps':rate,'workers':workers}}
                if budget is not None:
                    try:reservation=budget.reserve(row)
                    except Exception as error:
                        failed=True;billing_errors.append(type(error).__name__)
                        continue
                    if reservation is None:
                        failed=True;exhausted=True
                        continue
                    row['billing_reservation']=reservation
                pending.add(pool.submit(fetch,row,key));index+=1
                next_start=time.monotonic()+1/rate
            if not pending:
                time.sleep(max(0,min(1,next_start-time.monotonic())))
                continue
            timeout=max(0,next_start-time.monotonic()) if len(pending)<workers and index<len(rows) and not failed else 1
            done,pending=wait(pending,timeout=min(timeout,1),return_when=FIRST_COMPLETED)
            for future in done:
                record=future.result()
                # Save original bytes before parsing; drain in-flight calls after any failure.
                stream.write(encode(record)+'\n');stream.flush();os.fsync(stream.fileno())
                if budget is not None:
                    try:budget.settle(record)
                    except Exception as error:
                        failed=True;billing_errors.append(type(error).__name__)
                completed+=1;counts[str(record['status'])]+=1
                if record['status']!=200:failed=True
                else:
                    try:
                        summary=check_response(provider,json.loads(base64.b64decode(record['response_body_b64'])),json.loads(record['request_body']))
                        if not summary['model_match'] or not summary['valid_answers']:failed=True
                    except (ValueError,KeyError,TypeError):failed=True
                if completed%100==0:print(encode({'completed':completed,'scheduled':len(rows),'statuses':dict(counts)}),flush=True)
        print(encode({'completed':completed,'scheduled':len(rows),'statuses':dict(counts),'stopped_on_failure':failed,
                      'budget_exhausted':exhausted,'billing_errors':billing_errors,
                      'budget':budget.summary() if budget is not None else None}),flush=True)
    if failed:raise RuntimeError('Failure retained; scheduling stopped and in-flight responses drained')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stimuli');p.add_argument('output');p.add_argument('--provider',choices=list(MODELS),required=True)
    p.add_argument('--repeats',type=int,required=True);p.add_argument('--max-calls',type=int,required=True)
    p.add_argument('--rate',type=float,default=2);p.add_argument('--workers',type=int,default=4)
    p.add_argument('--env-file',default='.env')
    p.add_argument('--canonical-schema',action='store_true',help='Hold reference output grammar order fixed across prompt manipulations')
    p.add_argument('--resume-from',nargs='*',default=[])
    p.add_argument('--retry-failed',action='store_true')
    p.add_argument('--manifest',action='store_true',help='Input is a complete G5 manifest instead of a stimulus corpus')
    p.add_argument('--budget-db',help='Shared persistent ledger; reuse across all main batches and resumes')
    p.add_argument('--budget-limit-usd',type=float)
    args=p.parse_args()
    if args.repeats<1:p.error('repeats must be positive')
    if bool(args.budget_db)!=(args.budget_limit_usd is not None):p.error('Supply both budget options')
    load_env(args.env_file)
    builder=manifest_schedule if args.manifest else schedule
    rows=(builder(read_jsonl(args.stimuli),args.provider,args.repeats,canonical_schema=args.canonical_schema)
          if args.manifest else builder(read_jsonl(args.stimuli),args.provider,args.repeats))
    if args.resume_from:
        rows=resume(rows,[r for path in args.resume_from for r in read_jsonl(path)],args.retry_failed)
    if args.budget_db:
        from harness.billing import SpendingLedger
        ledger=SpendingLedger(args.budget_db,args.budget_limit_usd)
        try:run(rows,args.output,args.max_calls,args.rate,args.workers,ledger)
        finally:ledger.close()
    else:run(rows,args.output,args.max_calls,args.rate,args.workers)

if __name__=='__main__':main()
