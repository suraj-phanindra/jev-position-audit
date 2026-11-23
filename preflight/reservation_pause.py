"""Reversible operator issuance barrier; existing collectors drain normally."""
from pathlib import Path
import sqlite3

from harness.billing import POLICY

NAME = 'operator_transport_pause'
SQL = ("CREATE TRIGGER operator_transport_pause BEFORE INSERT ON attempts "
       "BEGIN SELECT RAISE(ABORT, 'operator transport pause'); END")


def install(path):
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=rw', uri=True, timeout=5)
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT policy FROM budget WHERE id=1').fetchone() != (POLICY,):
                raise ValueError('Unexpected spending policy')
            db.execute(SQL)  # Refuse an existing barrier; never silently replace it.
    finally:
        db.close()


def remove(path):
    """Only after checkpoint validation and explicit authorization to resume."""
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=rw', uri=True, timeout=5)
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT sql FROM sqlite_master WHERE type=? AND name=?',
                          ('trigger', NAME)).fetchone() != (SQL,):
                raise ValueError('Missing or changed operator barrier')
            db.execute('DROP TRIGGER operator_transport_pause')
    finally:
        db.close()
