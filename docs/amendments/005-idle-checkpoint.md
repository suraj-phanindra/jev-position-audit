# Operational amendment 005: verified idle checkpoint for transport

Recorded 23 September 2026 after registration and during main collection. The user
requested that collection stop cleanly within 90 minutes so the laptop can be
transported. The running collectors predate amendment 004's cooperative pause
adapter. Waiting for a natural failure cannot guarantee a timely stopping point.
No main effect estimates or hypothesis tests informed this procedure.

## Stop procedure

Automatic recovery is stopped and its process termination verified. The helper
`preflight.idle_pause.attempt` holds the existing operator-launch lock, verifies
the supervisor/collector process group, ancestry, and expected command lines, and
reads the original ledger without changing it. If a provider has any unsettled
reservation, it does not stop that provider.

At an apparent idle point, the helper suspends the entire two-process group and
verifies that both processes are stopped. It then reads the ledger again. If any
reservation is unsettled, it immediately continues the group without terminating
either process. A changed or unverified process inventory also prevents stopping.

Only after the suspended group has **zero unsettled reservations** does the helper
write an fsynced intent record and terminate the collector worker with SIGKILL.
The supervisor is continued and records the actual child exit code, **-9**. A
separate fsynced checkpoint receipt records the verified idle state and observed
termination. This is an intentional idle checkpoint, not a normal completion,
HTTP failure, or code-75 cooperative pause. No provider response is fabricated.

The ordering in the registered runner is essential: a reservation commits before
HTTP submission; every raw response is flushed and fsynced before settlement.
Consequently zero unsettled reservations after whole-group suspension excludes
an issued request whose response has not been retained and settled. If suspension
occurs inside an uncommitted new reservation, that request has not been submitted;
termination rolls back that transaction. An unsettled reservation is never cleared
to manufacture an idle point. A checkpoint with any uncertainty fails verification.

After all providers stop, verify retained response-to-reservation accounting,
request/response validity and model identities, all collector descendants, and
the original ledger before declaring the laptop safe to close. Preserve hashes
of all response files and use SQLite backup for a consistent ledger checkpoint.

## Resume and scope

An idle checkpoint must be verified as such; the existing transient-failure
recovery helper must not treat exit -9 as an ordinary eligible retry. A new
explicit launch can use the registered history/resume logic after checkpoint
validation and an activation record. The contemplated home run must use amendment
004's pause adapter and retain the original ledger, schedule, request bytes,
samples, model pins, attempt limits, pacing, and spending cap. Already saved
successful draws are not repeated.

This amendment changes operational stopping only. Each brief suspension, stop
intent, verified terminal receipt, and later restart is recorded. Local amendment
records are not external OSF timestamps; disclose the amendment separately in the
registration update history. Tests use only disposable local processes and a test
ledger, including an outstanding-request guard and the check/suspend race.
