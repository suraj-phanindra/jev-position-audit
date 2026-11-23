"""Operational pause adapter; registered scheduling and response handling stay intact.

Returning no issuance reservation reuses the registered runner's existing drain
path. Its legacy summary calls this `budget_exhausted`; the separate pause receipt
identifies the actual reason. The shared budget and reservations are not changed.
Not active until the dated operational amendment is recorded and this entry point
is explicitly launched. Already running collectors do not acquire this behavior.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from harness.audit import read_jsonl
from preflight.amendment001 import valid_history
from preflight.repeats import run as registered_run

CONTROL = Path('runs/main-v1/collection-control.json')
RECORD = Path('amendments/004-scheduled-pause.json')
AMENDMENT_SHA = None


class Paused(RuntimeError):
    """All issued calls are retained and settled; collection may remain stopped."""


def due(control=CONTROL, now=None):
    config = json.loads(Path(control).read_text())
    if config.get('state') not in ('running', 'pause'):
        raise ValueError('Invalid collection control state')
    deadline = datetime.fromisoformat(config['stop_at'])
    if deadline.tzinfo is None: raise ValueError('Pause deadline must include timezone')
    return config['state'] == 'pause' or (now or datetime.now(timezone.utc)) >= deadline


class PauseLedger:
    def __init__(self, ledger, control):
        self.ledger = ledger
        self.control = control
        self.paused_at = None
        self.issued = set()
        self.settled = set()
        self.settlement_failed = False

    def reserve(self, row):
        if due(self.control):
            self.paused_at = datetime.now(timezone.utc).isoformat()
            return None
        reservation = self.ledger.reserve(row)
        if reservation is not None: self.issued.add(reservation)
        return reservation

    def settle(self, record):
        try:
            self.ledger.settle(record)
            self.settled.add(record['billing_reservation'])
        except Exception:
            self.settlement_failed = True
            raise

    def summary(self):
        return self.ledger.summary()


def run(rows, output, max_calls, rate, workers, budget=None, *, control=CONTROL):
    if budget is None: raise ValueError('Scheduled pause requires the original shared ledger')
    adapter = PauseLedger(budget, control)
    if AMENDMENT_SHA:
        rows = [{**r, 'pause_amendment_sha256': AMENDMENT_SHA} for r in rows]
    try:
        registered_run(rows, output, max_calls, rate, workers, adapter)
    except RuntimeError:
        if adapter.paused_at is None or adapter.settlement_failed: raise
    else:
        if not due(control): return
        adapter.paused_at = datetime.now(timezone.utc).isoformat()
    records = read_jsonl(output)
    valid_history(records, rows[0]['provider'])
    receipts = [r['billing_reservation'] for r in records]
    if (len(receipts) != len(set(receipts)) or set(receipts) != adapter.issued
            or adapter.settled != adapter.issued or adapter.settlement_failed):
        raise RuntimeError('Pause could not reconcile all issued requests')
    receipt = dict(status='paused_and_drained', provider=rows[0]['provider'],
                   requested_at=adapter.paused_at, finished_at=datetime.now(timezone.utc).isoformat(),
                   completed=len(records), output=str(output),
                   output_sha256=hashlib.sha256(Path(output).read_bytes()).hexdigest(),
                   amendment_sha256=AMENDMENT_SHA,
                   note='Issuance stopped for operator/deadline pause; legacy budget_exhausted is not a changed spending cap.')
    with Path(str(output)+'.pause.json').open('x') as stream:
        json.dump(receipt, stream, indent=2); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(receipt), flush=True)
    raise Paused('Scheduled or operator pause; all issued requests drained')


def main():
    global AMENDMENT_SHA
    data = RECORD.read_bytes()
    for name, expected in json.loads(data)['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError('Operational amendment artifact changed: '+name)
    AMENDMENT_SHA = hashlib.sha256(data).hexdigest()
    due()  # Validate control before loading keys or initiating collection.
    from preflight import main_run, amendment001
    main_run.run = run
    args = sys.argv[1:]
    provider = args[args.index('--provider')+1]
    try:
        (amendment001.main if provider == 'typesafe' else main_run.main)()
    except Paused:
        return 75
    return 0


if __name__ == '__main__': raise SystemExit(main())
