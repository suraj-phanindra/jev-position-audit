"""Amendments 002/003: bounded recovery of checked transient failures only."""
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

from harness.audit import read_jsonl
from preflight.recover import ROOT, recover, process_running

RECORD = Path('amendments/003-zombie-recovery.json')
MAX_RECOVERIES = 100
MAX_HOURS = 6


def verify_amendment():
    data = RECORD.read_bytes()
    for name, expected in json.loads(data)['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError('Amendment artifact changed: '+name)
    return hashlib.sha256(data).hexdigest()


def state(job, now):
    if process_running(job['supervisor_pid']): return 'live'
    terminal = json.loads(Path(job['exit_record']).read_text())
    if terminal['exit_code'] == 0: return 'complete'
    if terminal['exit_code'] != 1: raise ValueError('Unexpected collector exit code')
    earliest = datetime.fromisoformat(terminal['finished_at'])+timedelta(seconds=60)
    if job.get('cooldown_until'):
        earliest = max(earliest, datetime.fromisoformat(job['cooldown_until']))
    if now < earliest: return 'wait'
    segment = max((Path('runs/main-v1')/job['provider']).rglob('*.jsonl'), key=lambda p:p.name)
    attempts = [r['attempt'] for r in read_jsonl(segment) if r['status'] != 200]
    if not attempts or any(type(a) is not int or a < 0 or a >= 2 for a in attempts):
        raise ValueError('No remaining transient attempt eligibility')
    earliest = max(earliest, datetime.fromisoformat(terminal['finished_at'])+
                   timedelta(seconds=60 * 2**max(attempts)))
    return 'wait' if now < earliest else 'retry'


def main():
    os.chdir(ROOT)
    root = Path('runs/main-v1')
    with (root/'recovery-supervisor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        digest = verify_amendment()
        start = datetime.now(timezone.utc)
        deadline = start+timedelta(hours=MAX_HOURS)
        stamp = start.strftime('%Y%m%dT%H%M%SZ')
        prefix = root/('recovery-supervisor-'+stamp)
        events = Path(str(prefix)+'.jsonl')
        terminal = Path(str(prefix)+'-exit.json')
        metadata = dict(pid=os.getpid(), started_at=start.isoformat(), deadline=deadline.isoformat(),
                        max_recoveries=MAX_RECOVERIES, amendment_sha256=digest,
                        events=str(events), exit_record=str(terminal))
        with Path(str(prefix)+'.json').open('x') as stream: json.dump(metadata,stream,indent=2)
        print(json.dumps(metadata),flush=True)
        disabled = {}; completed = set(); recoveries = 0; result = 'supervision_limit'
        with events.open('x') as stream:
            def log(event, **fields):
                stream.write(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(),event=event,**fields))+'\n')
                stream.flush(); os.fsync(stream.fileno())
            try:
                while datetime.now(timezone.utc) < deadline and recoveries < MAX_RECOVERIES:
                    if verify_amendment() != digest: raise ValueError('Amendment record changed')
                    jobs = json.loads((root/'active-processes.json').read_text())
                    if sorted(j['provider'] for j in jobs) != ['anthropic','together','typesafe']:
                        raise ValueError('Provider inventory changed')
                    for job in jobs:
                        if recoveries >= MAX_RECOVERIES or datetime.now(timezone.utc) >= deadline: break
                        provider = job['provider']
                        if provider in disabled or provider in completed: continue
                        try:
                            status = state(job, datetime.now(timezone.utc))
                            if status == 'complete':
                                completed.add(provider); log('collector_complete',provider=provider)
                            elif status == 'retry':
                                log('recovery_requested',provider=provider,previous_exit=job['exit_record'])
                                recoveries += 1
                                # The shared helper rechecks the live handle, retained segment,
                                # validity, hashes, cooldown, attempt caps, and spending stop.
                                recover(provider, initiator='amendment 003 bounded supervisor')
                                log('recovery_launched',provider=provider,recoveries=recoveries)
                                if recoveries >= MAX_RECOVERIES: break
                        except Exception as error:
                            disabled[provider] = str(error)
                            log('provider_requires_review',provider=provider,error=type(error).__name__,reason=str(error))
                    if len(disabled)+len(completed) == 3:
                        result = 'complete' if not disabled else 'review_required'; break
                    if recoveries >= MAX_RECOVERIES:
                        if disabled: result = 'review_required'
                        break
                    time.sleep(5)
            except Exception as error:
                result = 'supervisor_error'
                log(result,error=type(error).__name__,reason=str(error))
            finally:
                final = dict(status=result,finished_at=datetime.now(timezone.utc).isoformat(),
                             recoveries=recoveries,completed=sorted(completed),disabled=disabled)
                with terminal.open('x') as output: json.dump(final,output,indent=2)
                log('supervision_ended',**final)
        # A supervision limit ends recovery monitoring, not live collection jobs.
        return 0 if result == 'complete' else 1


if __name__ == '__main__': raise SystemExit(main())
