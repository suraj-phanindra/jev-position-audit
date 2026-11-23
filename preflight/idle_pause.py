"""Stop an uninstrumented collector only at a verified zero-request checkpoint."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time

from preflight.recover import process_running


def group(pid):
    result = subprocess.run(['ps', '-axo', 'pid=,ppid=,pgid=,stat='],
                            capture_output=True, text=True, check=True, timeout=5)
    rows = []
    for line in result.stdout.splitlines():
        p, parent, pg, state = line.split()
        if int(pg) == pid:
            rows.append(dict(pid=int(p), ppid=int(parent), pgid=int(pg), stat=state))
    return rows


def verified_group(job):
    pid = job['supervisor_pid']
    if type(pid) is not int or pid <= 1: raise ValueError('Invalid collector process group')
    members = group(pid)
    if len(members) != 2 or not any(r['pid'] == pid for r in members):
        raise ValueError('Expected one supervisor and one collector; inspect terminal state')
    worker = next(r for r in members if r['pid'] != pid)
    if worker['ppid'] != pid or any(r['stat'].startswith(('T', 'Z')) for r in members):
        raise ValueError('Unexpected collector ancestry or process state')
    command = subprocess.check_output(['ps', '-p', str(worker['pid']), '-o', 'command='], text=True).strip()
    module = 'preflight.amendment001' if job['provider'] == 'typesafe' else 'preflight.main_run'
    expected = (' -u -m '+module+' preflight/generated/registration-v1 '
                'REGISTRATION_RECEIPT.json --provider '+job['provider']+' --retry-transient')
    if not command.endswith(expected): raise ValueError('Unexpected collector command')
    parent = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True)
    if 'code=subprocess.call(sys.argv[2:])' not in parent or job['exit_record'] not in parent:
        raise ValueError('Unexpected supervisor command')
    return members


def pending(root, provider):
    db = sqlite3.connect((root/'spending.sqlite').resolve().as_uri()+'?mode=ro', uri=True, timeout=5)
    try:
        return db.execute('SELECT count(*) FROM attempts WHERE provider=? AND charged IS NULL',
                          (provider,)).fetchone()[0]
    finally:
        db.close()


def write_record(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2); stream.flush(); os.fsync(stream.fileno())


def attempt(provider, root=Path('runs/main-v1')):
    root = Path(root)
    with (root/'operator-launch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        watcher = root/'recovery-supervisor-active.json'
        if watcher.exists() and process_running(json.loads(watcher.read_text())['pid']):
            raise ValueError('Stop automatic recovery before attempting an idle checkpoint')
        job = next(j for j in json.loads((root/'active-processes.json').read_text())
                   if j['provider'] == provider)
        if pending(root, provider): return None
        members = verified_group(job); pid = job['supervisor_pid']
        worker = next(r['pid'] for r in members if r['pid'] != pid)
        frozen = False
        event = dict(provider=provider, supervisor_pid=pid,
                     started_at=datetime.now(timezone.utc).isoformat(), outcome='verification_error')
        try:
            os.killpg(pid, signal.SIGSTOP); frozen = True
            deadline = time.monotonic()+2
            while True:
                current = group(pid)
                if {r['pid'] for r in current} != {r['pid'] for r in members}:
                    raise ValueError('Process group changed while suspending')
                if all(r['stat'].startswith('T') for r in current): break
                if time.monotonic() >= deadline: raise RuntimeError('Could not verify suspension')
                time.sleep(.01)
            # Reserve commits before HTTP submission; response fsync precedes settlement.
            # An uncommitted new reservation cannot have submitted a request yet.
            if pending(root, provider):
                event['outcome'] = 'continued_with_outstanding_request'
                return None
            now = datetime.now(timezone.utc)
            prefix = root/(provider+'-idle-stop-'+now.strftime('%Y%m%dT%H%M%S%fZ'))
            intent = dict(provider=provider, requested_at=now.isoformat(),
                          supervisor_pid=pid, worker_pid=worker, frozen_group=current,
                          outstanding_requests=0, previous_job=job,
                          reason='User-requested transport pause; no outstanding issued requests after whole-group suspension.')
            write_record(Path(str(prefix)+'-intent.json'), intent)
            os.kill(worker, signal.SIGKILL)
            event['outcome'] = 'worker_stopped_at_verified_idle'
        finally:
            if frozen:
                try: os.killpg(pid, signal.SIGCONT)
                except ProcessLookupError: pass
                event['finished_at'] = datetime.now(timezone.utc).isoformat()
                with (root/'idle-pause-attempts.jsonl').open('a') as stream:
                    stream.write(json.dumps(event)+'\n'); stream.flush(); os.fsync(stream.fileno())
        deadline = time.monotonic()+10
        terminal = Path(job['exit_record'])
        while time.monotonic() < deadline:
            if not any(not r['stat'].startswith('Z') for r in group(pid)) and terminal.exists(): break
            time.sleep(.05)
        else: raise RuntimeError('Worker stopped at idle; supervisor termination still requires verification')
        exit_record = json.loads(terminal.read_text())
        if exit_record['exit_code'] != -signal.SIGKILL or pending(root, provider):
            raise RuntimeError('Unexpected terminal state after idle checkpoint')
        result = dict(intent, status='stopped_at_verified_idle_checkpoint',
                      finished_at=datetime.now(timezone.utc).isoformat(), exit_record=exit_record)
        write_record(Path(str(prefix)+'.json'), result)
        return result
