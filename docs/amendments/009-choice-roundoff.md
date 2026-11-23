# Amendment 009: numerical residue at the existing choice-validation boundary

Recorded 27 September 2026 after the 12:02:48 UTC collection stop, before resumed
issuance and before main effect analysis. The last response in
`runs/main-v1/typesafe/task-165/20260927T120143066709Z.jsonl` selected C06 with
probability 0.27999999999999997 while the maximum was C04 at 0.29. The existing
0.01 choice consistency tolerance was exceeded by 0.00000000000000003.
The collector correctly stopped under its implemented rule; the recovery
supervisor then stopped because this HTTP-200 response was not a transient error.

The correction adds an absolute arithmetic allowance of 1e-15 to that specific
choice consistency comparison. It does not change the scientific tolerance of
0.01 at the measurement precision of interest. It is applied to every choice
response, not an item allowlist. All other schema, model, mass, range, score,
confidence, and question-identity validation remains intact. The original frozen
source is preserved and an explicit adapter supplies the correction.

This is a post-registration validation correction informed by inspection of one
operationally rejected response, not a new pristine preregistration. The original
selected label and all original probabilities remain stored and used; the adapter
uses a temporary validation copy only after checking the narrow boundary. No
rounding, renormalization, relabeling, deletion, new draw, or retry of this HTTP-200
response is permitted. The draw is retained once and skipped on resume. Its
schedule ID is `9073c163b5db07bc8dac47ac2bf98b2437b06242be2d8da6398a7bb0a83a17f5`.

The same adapter must be installed before importing analysis modules that bind
`target_value`, and remain installed for analysis. Downstream analysis and export
receipts must identify amendment 009. Main inference remains held for complete
collection and the external statistics review. No main effect estimates were
examined to diagnose this incident. Report the count of affected validation
records and retain the unmodified-validator failure in the audit trail.

Before restart, validate the retained segment under both validators and reconcile
the ledger and request identities. Resume only unissued draws. Subsequent
nontransient failures still stop; the three-attempt limit, six-hour recovery
sessions, rate, worker count, model, request texts, sample allocation and $300 cap
are unchanged. Monday 28 September issuance stops at 07:25 PDT, with drain targeted
before the user's 07:30 PDT transport deadline. Local activation and external OSF
disclosure receive their actual timestamps separately.
