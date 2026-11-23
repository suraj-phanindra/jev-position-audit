"""Dated correction of float serialization residue at the choice tolerance boundary."""
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

from harness import audit
from preflight import amendment008, recover as operator, supervise_recovery as bounded
from preflight import scheduled_pause

RECORD = Path('amendments/009-choice-roundoff.json')
ORIGINAL_TARGET = audit.target_value
EPSILON = Decimal('0.000000000000001')
SUPERVISOR = amendment008.SUPERVISOR.replace(
    'from preflight.amendment008 import child_command',
    'from preflight.amendment009 import child_command')


def target_value(answer, request_question, target, canonical_levels=None):
    try:
        return ORIGINAL_TARGET(answer, request_question, target, canonical_levels)
    except ValueError as error:
        if (str(error) != 'Returned choice contradicts its probability distribution'
                or request_question['type'] != 'choice'):
            raise
        probs = {k: audit.probability(v) for k, v in answer['probabilities'].items()}
        gap = max(probs.values()) - probs[answer['choice']]
        if not Decimal('0.01') < gap <= Decimal('0.01') + EPSILON:
            raise
        # Validation copy only: retain the original label and every probability in raw data.
        checked = {**answer, 'choice': max(probs, key=probs.get)}
        return ORIGINAL_TARGET(checked, request_question, target, canonical_levels)


@contextmanager
def installed():
    previous = audit.target_value
    audit.target_value = target_value
    try:
        with amendment008.installed():
            yield
    finally:
        audit.target_value = previous


def verify():
    amendment008.verify()
    data = RECORD.read_bytes()
    for name, expected in json.loads(data)['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError('Amendment 009 artifact changed: ' + name)
    return hashlib.sha256(data).hexdigest()


def child_command(command):
    command = amendment008.child_command(command)
    command[3] = 'preflight.amendment009'
    return command


def recover(provider, initiator='operator'):
    verify()
    if scheduled_pause.due():
        raise ValueError('Collection is held or its issuance deadline has passed')
    previous = operator.SUPERVISOR
    try:
        operator.SUPERVISOR = SUPERVISOR
        with installed():
            return operator.recover(provider, initiator='amendment 009 choice roundoff correction')
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
