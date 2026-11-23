# Operational amendment 003: distinguish exited zombies from live collectors

Date and pre-activation counts are recorded in `003-zombie-recovery.json`.
Original registration: https://osf.io/4nme3/. This local operational amendment
requires later disclosure through the user's OSF update; that external timestamp
must not be represented as preceding activation.

## Observed defect

Together's collector supervisor PID 59834 exited with code 1 at
2026-09-23T20:47:31.270544Z after retaining one transport failure and draining its
in-flight requests. Its parent was recovery supervisor PID 59145. The child
remained a zombie: `ps` showed state `Z` and the terminal exit record existed.
Both recovery liveness checks used `os.kill(pid, 0)`, which also succeeds for an
exited zombie. Consequently, the supervisor incorrectly reported it as live and
never reached the existing terminal-summary and retry-eligibility checks.

At 20:50:17 UTC, only recovery supervisor 59145 was stopped with SIGTERM. The
operator stop receipt is retained separately because SIGTERM did not execute the
supervisor's Python finalizer. Live provider collectors were not stopped.
The files committed by amendment 002 were first copied byte-for-byte into
`amendments/002-source-snapshot/`, preserving their original relative paths and
verified hashes. The original amendment record and registration remain intact.

## Correction

The automatic and manual recovery paths now share one process-state check. It
queries the operating system's `ps` state, treats a zombie as terminated, and
reaps it when it is a child of the checking process. A missing PID is also
terminated; every other reported process state remains live. Invalid PIDs,
inspection errors, and timeouts fail closed. This change does not itself permit
a launch: the terminal record, drained summary, retained response validation,
retry eligibility, hashes, cooldown, and budget checks must still pass.

The corrected recovery supervisor is explicitly relaunched as a new bounded
session, with the unchanged per-session limits of six hours and 100 recovery
invocations. The earlier session made one recovery invocation; both sessions'
events remain retained and must be counted in the operational report. This is
not a reset of per-request attempts or spend. The original three-total-attempt
limit, shared $300 accounting cap, and existing Jev cooldown remain binding.

The supervisor now verifies amendment 003's hashes and identifies this amendment
as the initiator of recoveries. Registered scientific code, request bytes, model
pins, allocation, samples, rate limits, estimands, and analysis are unchanged.
No main effect estimates or hypothesis tests informed this fix.

## Validation

A regression test created a real exited child and confirmed its zombie state.
Before the fix, the actual supervisor state function returned `live` instead of
the expected terminal state. After the fix, it recognizes the terminal record.
Checks also cover live-process protection, absent/non-child zombie handling,
inspection failures, cooldowns, backoff, attempt limits, and recovery refusal.
The hash record identifies the final test log and original registration check.

Successful live collection after restart is reported separately; passing the
regression test does not establish recovery from provider overload or timeouts.
