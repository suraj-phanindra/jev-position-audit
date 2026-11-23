# Operational amendment 006: reservation barrier for a clean transport pause

Recorded 23 September 2026 during main collection, before activation. The user
requested a clean pause for laptop transport. Amendment 005 stopped Jev at a
verified idle checkpoint, but the continuously busy reference collectors had not
reached an idle point. This procedure lets their original drain logic finish all
issued calls without terminating either process. No main inference informed it.

## Reversible issuance barrier

`preflight.reservation_pause.install` installs one named SQLite trigger in the
original spending database: `operator_transport_pause`, before insertion into
`attempts`. It raises `IntegrityError` with the literal message `operator transport
pause`. No rows, prices, budget cap, or scientific artifacts are changed.

The registered `SpendingLedger.reserve` updates the reserved budget and inserts
the attempt in one transaction before any HTTP call is submitted. The trigger
aborts insertion; the connection context rolls back the entire reservation,
including the budget increment. The registered runner catches that reservation
error, stops new scheduling, drains its existing futures, fsyncs all responses,
settles their existing reservations, writes its actual terminal summary, and exits.
The summary truthfully includes `billing_errors: ["IntegrityError"]`: this is an
operator-requested issuance stop, not a provider failure or spending-cap increase.
No unissued request is counted as an attempt, and no fake response is inserted.

The trigger affects new reservations only. It does not prevent settlement or
alter the handling of already-issued requests. It is retained during transport
as a guard against accidental collection. The original recovery supervisor is
off; its normal eligibility guard also refuses a stop with a billing error.

## Validation and resume

A local test uses the original runner and real SQLite ledger, installs the barrier
through a second connection while two simulated calls are in flight, verifies
both responses are retained and settled, and verifies that the blocked third
reservation leaves neither an attempt row nor a budget increment. Removing the
exact trigger restores reservation ability. No API requests are used in this test.

Before calling the live pause complete, verify every provider's process and
terminal evidence, zero unsettled reservations, exact response-to-reservation
coverage, unchanged request hashes, valid responses/model pins, and stable raw
files. Back up the ledger consistently through SQLite's backup API. Document the
actual stop mechanisms separately: Jev's verified idle termination under amendment
005 and the reference collectors' normal drain under this amendment.

Resume only when the user confirms they are set up again. After checkpoint
verification, remove only the exact recorded trigger, preserve the same ledger
and history, and explicitly launch the amendment-004 entry point for the planned
morning deadline. Retained successful draws must be skipped by the original resume
logic. No changes are made to sample sizes, request content, randomization, model
IDs, rate limits, retry caps, spending cap, or statistical analysis.

Local recording is not an external preregistration timestamp. The activation,
database trigger SQL, terminal evidence, and later removal/resumption must be
retained and disclosed in the OSF update history.
