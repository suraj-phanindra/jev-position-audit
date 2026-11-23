"""Shared, crash-conservative spending ledger. Frozen list rates; no cache discounts."""
import base64
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import uuid

# Nanodollars per token; integer arithmetic avoids floating-point budget drift.
RATES={'typesafe':(42,0),'anthropic':(1000,5000),'together':(140,280)}
# Exceed full documented context input cost plus the 128-token reference output cap.
RESERVES={'typesafe':3_000_000,'anthropic':500_000_000,'together':300_000_000}
POLICY=json.dumps({'rates':RATES,'reserves':RESERVES},sort_keys=True)


class SpendingLedger:
    def __init__(self,path,limit_usd):
        amount=Decimal(str(limit_usd))*1_000_000_000
        if not amount.is_finite() or amount<=0 or amount!=amount.to_integral_value():
            raise ValueError('Invalid dollar limit')
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path,timeout=30,isolation_level='IMMEDIATE')
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY CHECK(id=1), cap INTEGER NOT NULL, used INTEGER NOT NULL, policy TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, provider TEXT NOT NULL, request_sha256 TEXT NOT NULL, reserved INTEGER NOT NULL, charged INTEGER, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO budget VALUES (1,?,0,?)',(int(amount),POLICY))
            saved=self.db.execute('SELECT cap,policy FROM budget WHERE id=1').fetchone()
            if saved!=(int(amount),POLICY):raise ValueError('Existing ledger cap/rate policy differs; do not reset it')

    def reserve(self,row):
        provider=row['provider'];request=json.loads(row['request_body'])
        from preflight.live_check import MODELS
        if request['model']!=MODELS[provider]:raise ValueError('Billing policy requires pinned model')
        if provider!='typesafe' and (request.get('max_tokens')!=128 or request.get('temperature')!=1):
            raise ValueError('Reference request differs from bounded sampling protocol')
        amount=RESERVES[provider];identity=str(uuid.uuid4())
        with self.db:
            changed=self.db.execute('UPDATE budget SET used=used+? WHERE id=1 AND used+?<=cap',(amount,amount)).rowcount
            if not changed:return None
            self.db.execute('INSERT INTO attempts(id,provider,request_sha256,reserved) VALUES (?,?,?,?)',
                            (identity,provider,row['request_sha256'],amount))
        return identity

    def settle(self,record):
        identity=record['billing_reservation'];provider=record['provider'];reserve=RESERVES[provider]
        cost=reserve;status='unknown_charged_at_reserve'
        if record['status']==200:
            try:
                data=json.loads(base64.b64decode(record['response_body_b64'],validate=True));usage=data['usage']
                incoming=usage.get('input_tokens',usage.get('prompt_tokens'))
                outgoing=usage.get('output_tokens',usage.get('completion_tokens'))
                cached=usage.get('cache_read_input_tokens',0);created=usage.get('cache_creation_input_tokens',0)
                if any(type(v) is not int or v<0 for v in (incoming,outgoing,cached,created)):raise ValueError('Invalid usage')
                a,b=RATES[provider];cost=(incoming+cached+2*created)*a+outgoing*b
                status='reported_usage_at_conservative_list_rate'
            except (ValueError,KeyError,TypeError):pass
        with self.db:
            changed=self.db.execute('UPDATE attempts SET charged=?,status=? WHERE id=? AND charged IS NULL',
                                    (cost,status,identity)).rowcount
            saved=self.db.execute('SELECT provider,request_sha256,reserved,charged FROM attempts WHERE id=?',(identity,)).fetchone()
            if saved!=(provider,record['request_sha256'],reserve,cost):raise ValueError('Reservation/receipt mismatch')
            if changed:self.db.execute('UPDATE budget SET used=used+? WHERE id=1',(cost-reserve,))
        if cost>reserve:raise RuntimeError('Reported usage exceeded reservation; stop and reconcile billing policy')

    def summary(self):
        cap,used=self.db.execute('SELECT cap,used FROM budget WHERE id=1').fetchone()
        pending=self.db.execute('SELECT count(*) FROM attempts WHERE charged IS NULL').fetchone()[0]
        return {'cap_usd':cap/1e9,'charged_or_reserved_usd':used/1e9,'unsettled_attempts':pending}

    def close(self):self.db.close()
