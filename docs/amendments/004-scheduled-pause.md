# Operational amendment 004: operator and scheduled pauses

Prepared 23 September 2026 after registration and during collection, in response
to the user's need to transport the laptop and pause again by 07:30 America/Los_Angeles
on 24 September. This is an operational change, not a statistical amendment.
No main effect estimates or hypothesis tests informed it. Local preparation does
not constitute an external OSF timestamp or activation of a new collector.

## Change

`preflight.scheduled_pause` is a separate entry point around the registered runner.
Before each issuance reservation, it reads `runs/main-v1/collection-control.json`.
The control requires a `state` of `running` or `pause`, and an explicit timezone
on `stop_at`. Missing or malformed control fails closed. An operator pause or
elapsed deadline refuses further reservations without modifying the shared cap.

This refusal reuses the original runner's drain path. Its original summary labels
the refusal `budget_exhausted: true`; a separate, fsynced `.pause.json` receipt
identifies an operator/deadline pause rather than actual spending exhaustion.
No fabricated HTTP error, request, response, or billing reservation is inserted.
All already-issued calls are saved and settled through the original path.

Before reporting a pause, the adapter revalidates returned model identities and
typed answers, checks that issued reservations exactly match retained receipts
and successful settlements, and hashes the closed output segment. Model or
billing failures remain failures, never successful pause receipts. A clean pause
exits with code 75, distinguishable from collection completion (0) or failure (1).
Jev still uses amendment 001's narrowly permitted overload-history handling.

The original request bytes, manifests, shuffled order, model IDs, concurrency,
pacing, sample counts, retry limits, analysis, and shared $300 cap remain unchanged.
The wrapper adds only an operational amendment hash to retained row metadata.
It does not change already running processes. First activation and every new
launch must be recorded with the entry point, control, and amendment hashes.

## Overnight operation

The planned issuance deadline is **2026-09-24 07:25 PDT / 14:25 UTC**, allowing a
five-minute drain buffer before the user's **07:30 PDT** departure. Existing
network timeouts remain unchanged. This is not a guarantee that every network
operation finishes within five minutes; the actual terminal state and ledger must
be verified before declaring the laptop safe to close.

The overnight control is initially held in `pause` state. Collection must not
restart until the user confirms they are set up at home. This morning deadline
does not replace the currently requested afternoon pause.

The amendment-003 automatic recovery supervisor must remain off: its launcher
uses the old entry points and does not preserve this deadline. Any supervised
recovery used overnight must explicitly launch the new entry point, respect the
same control and attempt/cooldown limits, and never restart a code-75 pause.
Do not interpret code 75 as completed collection or bypass existing recovery
guards. Before a later resume, verify the pause receipt, closed segment hash,
original ledger, all retained history, absence of live collectors, and remaining
attempt eligibility. Record the interruption and new resume time.

## Validation

Local tests exercise two simultaneous in-flight calls, durable response capture,
settlement of all issued reservations, skipping completed draws on resume,
deadline comparison, rejection of malformed controls, genuine budget exhaustion,
and model-validation/billing failures coinciding with a pause. They send no API
requests. This is not yet evidence of a live overnight pause or completed study.
