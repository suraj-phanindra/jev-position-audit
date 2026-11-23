"""Explicit operator recovery; launches the unchanged registered runner once."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from harness.audit import read_jsonl
from preflight.amendment001 import valid_history
from preflight.main_run import verify

ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR = '''import subprocess,sys,json
from pathlib import Path
from datetime import datetime,timezone
code=subprocess.call(sys.argv[2:])
Path(sys.argv[1]).write_text(json.dumps({'exit_code':code,'finished_at':datetime.now(timezone.utc).isoformat()}))
sys.exit(code)
'''


def eligible(records, summary, provider):
    if (summary.get('stopped_on_failure') is not True or
            summary.get('budget_exhausted') is not False or summary.get('billing_errors') != []):
        raise ValueError('Not a cleanly drained transient-failure stop')
    if (len(records) != summary['completed'] or
            dict(Counter(str(r['status']) for r in records)) != summary['statuses'] or
            any(r['provider'] != provider for r in records)):
        raise ValueError('Failure summary and retained segment disagree')
    valid_history(records, provider)  # Reject invalid HTTP-200s, drift, and nontransient failures.
    failures = [r for r in records if r['status'] != 200]
    if not failures or any(r['attempt'] >= 2 for r in failures):
        raise ValueError('No retryable failures or three-attempt limit reached')
    return [{'status': r['status'], 'attempt': r['attempt'],
             'transport_error': r.get('transport_error')} for r in failures]


def process_running(pid):
    if type(pid) is not int or pid <= 0: raise ValueError('Invalid supervisor PID')
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'stat='],
                            capture_output=True, text=True, timeout=5)
    if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
        return False
    if result.returncode != 0 or not result.stdout.strip():
        raise ValueError('Could not verify supervisor process state')
    if result.stdout.strip().startswith('Z'):
        try: os.waitpid(pid, os.WNOHANG)
        except ChildProcessError: pass
        return False
    return True


def recover(provider, initiator='operator'):
    os.chdir(ROOT)
    root = Path('runs/main-v1')
    # Serialize only operator launches; provider workers remain independent.
    with (root/'operator-launch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = json.loads((root/'active-processes.json').read_text())
        old = next(j for j in active if j['provider'] == provider)
        if old.get('cooldown_until') and datetime.now(timezone.utc) < datetime.fromisoformat(old['cooldown_until']):
            raise ValueError('Provider cooldown remains active until '+old['cooldown_until'])
        terminal = json.loads(Path(old['exit_record']).read_text())
        if terminal['exit_code'] != 1: raise ValueError('Previous runner did not terminate with failure')
        if process_running(old['supervisor_pid']):
            raise ValueError('Previous supervisor is still live; refusing duplicate launch')
        summaries = []
        for line in Path(old['console']).read_text().splitlines():
            try: row = json.loads(line)
            except json.JSONDecodeError: continue
            if isinstance(row, dict) and 'stopped_on_failure' in row: summaries.append(row)
        if not summaries: raise ValueError('No terminal collection summary')
        segment = max((root/provider).rglob('*.jsonl'), key=lambda p: p.name)
        failures = eligible(read_jsonl(segment), summaries[-1], provider)
        verify('preflight/generated/registration-v1', 'REGISTRATION_RECEIPT.json')
        numbers = [int(re.search(r'-resume(\d+)-', p.name)[1])
                   for p in root.glob(provider+'-resume*-*.json')]
        number = max(numbers, default=0) + 1
        date = datetime.now(timezone.utc).strftime('%Y%m%d')
        console = root/f'{provider}-console-resume{number}-{date}.log'
        exit_path = root/f'{provider}-exit-resume{number}-{date}.json'
        metadata = root/f'{provider}-resume{number}-{date}.json'
        if exit_path.exists() or metadata.exists(): raise ValueError('Recovery record already exists')
        module = 'preflight.amendment001' if provider == 'typesafe' else 'preflight.main_run'
        command = [sys.executable, '-u', '-m', module,
                   'preflight/generated/registration-v1', 'REGISTRATION_RECEIPT.json',
                   '--provider', provider, '--retry-transient']
        with console.open('xb') as stream:
            process = subprocess.Popen([sys.executable, '-u', '-c', SUPERVISOR, str(exit_path), *command],
                                       stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        job = dict(provider=provider, supervisor_pid=process.pid, keep_awake_pid=None,
                   console=str(console), exit_record=str(exit_path),
                   resumed_at=datetime.now(timezone.utc).isoformat(),
                   reason=f'Recovery initiated by {initiator} after retained-segment validation; scientific settings and caps unchanged.',
                   inspected_segment=str(segment), inspected_failures=failures)
        def record():
            metadata.write_text(json.dumps(job, indent=2)+'\n')
            (root/'active-processes.json').write_text(json.dumps(
                [job if j['provider'] == provider else j for j in active], indent=2)+'\n')
        record()  # Preserve the live handle even if the keep-awake helper fails.
        awake = subprocess.Popen(['/usr/bin/caffeinate', '-i', '-w', str(process.pid)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
        job['keep_awake_pid'] = awake.pid
        record()
        print(json.dumps(job), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('provider', choices=['typesafe', 'anthropic', 'together'])
    recover(p.parse_args().provider)
