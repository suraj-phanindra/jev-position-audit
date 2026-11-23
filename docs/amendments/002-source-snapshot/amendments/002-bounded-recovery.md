# Operational amendment 002: bounded transient recovery supervision

Date and pre-activation status counts: see the accompanying hash record
`002-bounded-recovery.json`. Original registration: https://osf.io/4nme3/.

This is a post-registration operational amendment. The original archive and
registered scientific source remain unchanged. Its local record precedes
activation; an OSF update remains to be made by the user. Do not represent the
later external timestamp as preceding supervised recovery.

## Trigger and information used

Repeated transient failures stop and drain the registered collectors. Manual
recoveries have repeatedly passed the same eligibility checks and restored
successful responses. At 20:12 UTC on 23 September, Jev had 2,009 successful
screening responses, 17 retained HTTP-529 overloads, and one transport failure.
All 17 earlier failed requests had subsequently succeeded on their next attempt;
the latest failure had not yet been retried. Reference collection also had
retained transient timeouts. No main effect estimates, hypothesis tests, or
scientific judgments informed this operational decision.

## Change

Permit a bounded local supervisor to invoke the existing checked recovery helper
after a terminal failure. It may make at most 100 recovery invocations over six
hours, shared across the three providers. A new supervision session requires an
explicit launch. Expiry ends recovery supervision and leaves live collectors
alone; it does not claim collection is complete.

The supervisor must first confirm that the prior process is gone and a terminal
failure record exists. It respects every existing `cooldown_until`. Otherwise it
waits at least 60 seconds after the failed collector drains, doubled to 120
seconds when a scheduled request has already failed twice (attempt index 1).
There is no third retry: attempt index 2 is the original third total attempt and
requires review. Backoff is tied to attempts on the same scheduled request;
unrelated failures on different requests do not automatically accumulate an
ever-longer pause. Existing manually imposed longer cooldowns remain binding.

Before each launch, the existing recovery helper rechecks the terminal summary,
retained segment, successful-response validity, model identity, narrow transient
allowlist including amendment 001, original hashes, and remaining attempt
eligibility. The original runner revalidates complete history and enforces the
shared $300 ledger and three-attempt cap. Any failed check disables supervised
recovery for that provider and records the reason. Other eligible providers may
continue. A supervisor/hash/inventory failure stops supervision for review.

Original stop-and-drain behavior stays in force. This is not retry-until-valid
sampling: invalid HTTP-200 judgments, model drift, nontransient errors, exhausted
attempts, missing terminal evidence, or budget stops cannot be bypassed.
Successful scheduled samples are never redrawn. Request bytes, sample allocation,
question types, model pins, pacing, worker counts, estimands, and analysis are
unchanged. Every attempt and recovery event remains archived.

## Implementation and disclosure

`preflight/supervise_recovery.py` is a separate launcher. A process-lifetime lock
prevents duplicate supervisors; the existing operator lock serializes launches.
The supervisor verifies this amendment's artifact hashes and writes timestamped
events, its PID/deadline, its amendment hash, and its final status under
`runs/main-v1/`. Recoveries identify amendment 002 as their initiator. No provider
credentials, scientific outcomes, or OSF view-only capabilities enter that log.

Record this change and the preceding manual pauses in the manuscript's operational
deviations. Unchanging model IDs cannot rule out serving drift across time or
load; the registered run-date/segment sensitivity remains necessary. This
amendment does not resolve the separately documented statistical-review issue.
