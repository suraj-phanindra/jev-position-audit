# Operational amendment 001: Jev overload response

Date recorded: 2026-09-23T18:52:45.838599+00:00
Original registration: https://osf.io/4nme3/
Original index SHA-256: `6f91554686e9e81fd18e47c22eb282dac9ac4a7d736faa793d0fb8f803bb8df0`.

**Post-registration amendment, not part of the original archived ZIP.** The
original package and all its source files remain unchanged. This local amendment
must be disclosed in the manuscript and added to the OSF registration's update
history; an external update has not yet been submitted.

## Trigger and decision

On 23 September 2026, during independent Jev screening, the provider returned
HTTP 529 with `detail.error_type = system_overloaded`. The response stated that
high traffic prevented processing. The registered runner stopped and drained
in-flight calls. The registered transient-status list included 408, 429, 500,
502, 503, and 504, but omitted 529. This was an operational omission, not a
response-validity failure or a scientific result.

Permit an explicit retry of **Jev HTTP 529 only when the raw JSON identifies
`system_overloaded`**. Keep every failed attempt. The existing limit of three
total attempts per scheduled draw, shared $300 ledger, pacing, model pins,
request bodies, sample allocation, all response checks, and stopping rules
continue to apply. Other 529 bodies and other providers remain outside this
amendment. No HTTP-200 invalid judgment may be redrawn until valid.

The implementation is a separate entry point, `preflight/amendment001.py`. It
verifies the original registered package through the existing runner, checks
this amendment's artifact hashes, narrowly extends the historical-error check,
and labels every subsequent request record with the amendment ID and hash. It
does not rewrite prior logs or replace the archived source. The executable
wrapper and its focused check are included in the amendment's hash record.

## Information available at the decision

Jev had 483 successful **screening** responses, one retained connection
disconnect, and one retained HTTP-529 overload response. No Jev main outcome
requests had begun. Reference collection had already begun; the billing ledger
contained 980 successful Haiku usage receipts and
658 successful DeepSeek usage receipts at this record time.
Only collection status, model identity, usage, and failure diagnostics were
reviewed for this decision; no main effect estimates or hypothesis tests were
computed. Disclosed pilot analyses predate registration.

All original scientific estimands, hypotheses, analysis methods, and decision
budgets remain in force. This amendment changes recovery from one explicit
provider overload response and must not be described as originally preregistered.

## OSF update

Use the existing registration's Updates → Update action. Explain that a
provider overload code was omitted from the retry allowlist and append the
amendment description and hashes to the Summary. OSF preserves the update
history; the original uploaded ZIP should remain unchanged.
