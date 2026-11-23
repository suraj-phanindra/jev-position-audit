"""Bounded recovery that preserves the prepared scheduled-pause entry point."""
import hashlib
import json
import os
from pathlib import Path

from preflight import recover as operator, supervise_recovery as bounded
from preflight.scheduled_pause import due

RECORD = Path('amendments/007-scheduled-recovery.json')
SUPERVISOR = '''import subprocess,sys,json
from pathlib import Path
from datetime import datetime,timezone
from preflight.supervise_scheduled import child_command
code=subprocess.call(child_command(sys.argv[2:]))
Path(sys.argv[1]).write_text(json.dumps({'exit_code':code,'finished_at':datetime.now(timezone.utc).isoformat()}))
sys.exit(code)
'''


def child_command(command):
    if (len(command) != 9 or command[1:3] != ['-u', '-m']
            or command[6] != '--provider' or command[8] != '--retry-transient'
            or command[7] not in ('typesafe', 'anthropic', 'together')):
        raise ValueError('Unexpected checked-recovery command')
    expected = 'preflight.amendment001' if command[7] == 'typesafe' else 'preflight.main_run'
    if command[3] != expected: raise ValueError('Unexpected collector entry point')
    return [*command[:3], 'preflight.scheduled_pause', *command[4:]]


def verify():
    data = RECORD.read_bytes()
    for name, expected in json.loads(data)['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError('Scheduled recovery artifact changed: '+name)
    return hashlib.sha256(data).hexdigest()


def recover(provider, initiator='operator'):
    verify()
    if due(): raise ValueError('Collection is held or its issuance deadline has passed')
    previous = operator.SUPERVISOR
    try:
        # The existing helper retains every eligibility, cooldown, hash and budget check.
        operator.SUPERVISOR = SUPERVISOR
        return operator.recover(provider, initiator='amendment 007 scheduled supervisor')
    finally:
        operator.SUPERVISOR = previous


def main():
    os.chdir(operator.ROOT)
    verify()
    if due(): raise ValueError('Collection is held or its issuance deadline has passed')
    previous_record, previous_recover = bounded.RECORD, bounded.recover
    try:
        bounded.RECORD, bounded.recover = RECORD, recover
        return bounded.main()  # Existing six-hour / 100-invocation bounds stay intact.
    finally:
        bounded.RECORD, bounded.recover = previous_record, previous_recover


if __name__ == '__main__': raise SystemExit(main())
