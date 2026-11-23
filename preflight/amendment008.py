"""Dated, bounded recovery for the observed TypeSafe HTTP-520 error pattern."""
import base64
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys

from preflight import amendment001, main_run, recover as operator
from preflight import scheduled_pause, supervise_recovery as bounded, supervise_scheduled
from preflight.live_check import URLS

RECORD = Path('amendments/008-http-520.json')
ORIGINAL_HISTORY = amendment001.ORIGINAL_HISTORY
SUPERVISOR = supervise_scheduled.SUPERVISOR.replace(
    'from preflight.supervise_scheduled import child_command',
    'from preflight.amendment008 import child_command')


def valid_history(records, provider):
    regular = []
    for row in records:
        if row['status'] == 520:
            if (provider != 'typesafe' or row.get('provider') != provider
                    or row.get('endpoint') != URLS['typesafe']
                    or base64.b64decode(row['response_body_b64'], validate=True) != b'error code: 520\n'):
                raise ValueError('HTTP 520 does not match amendment 008')
        else:
            regular.append(row)
    ORIGINAL_HISTORY(regular, provider)


def verify():
    supervise_scheduled.verify()
    data = RECORD.read_bytes()
    for name, expected in json.loads(data)['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError('Amendment 008 artifact changed: ' + name)
    return hashlib.sha256(data).hexdigest()


@contextmanager
def installed():
    previous = amendment001.ORIGINAL_HISTORY
    amendment001.ORIGINAL_HISTORY = valid_history
    try:
        yield
    finally:
        amendment001.ORIGINAL_HISTORY = previous


def child_command(command):
    command = supervise_scheduled.child_command(command)
    command[3] = 'preflight.amendment008'
    return command


def recover(provider, initiator='operator'):
    verify()
    if scheduled_pause.due():
        raise ValueError('Collection is held or its issuance deadline has passed')
    previous = operator.SUPERVISOR
    try:
        operator.SUPERVISOR = SUPERVISOR
        with installed():
            return operator.recover(provider, initiator='amendment 008 bounded HTTP-520 recovery')
    finally:
        operator.SUPERVISOR = previous


def main():
    verify()
    if sys.argv[1:] == ['--supervise']:
        if scheduled_pause.due():
            raise ValueError('Collection is held or its issuance deadline has passed')
        previous = bounded.RECORD, bounded.recover
        try:
            bounded.RECORD, bounded.recover = RECORD, recover
            return bounded.main()
        finally:
            bounded.RECORD, bounded.recover = previous
    with installed():
        return scheduled_pause.main()


if __name__ == '__main__':
    raise SystemExit(main())
