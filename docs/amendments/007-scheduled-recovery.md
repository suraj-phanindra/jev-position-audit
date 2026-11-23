# Operational amendment 007: pause-aware bounded recovery

Recorded 24 September 2026 after registration and partial collection. The user
returned to work and explicitly requested resumption; no overnight run occurred.
The transport checkpoint was reverified: all 54 raw files and ledger rows are
unchanged, all processes are stopped, zero reservations are unsettled, and original
registered artifacts match. Spending remains $41.822786986 of $300.

The prepared `preflight.supervise_scheduled` adapter routes every eligible recovery
through amendment 004's pause-aware entry point, preserving the original six-hour
and 100-recovery session bounds, per-draw three-attempt limit, cooldowns, response
validation and spending checks. An operator/deadline pause is terminal, never an
automatic retry or a completed-study label. Its existing code and tests were
prepared on 23 September but not activated then.

Initial resumption from the intentional transport pause is an explicit operator
launch after checkpoint validation, not a transient-failure recovery. Original
exit records (-9 for Jev and 1 for the references) remain intact. Only the exact
amendment-006 reservation barrier is removed. All collectors use the same ledger,
registration, manifest schedules and saved histories, skipping successful draws.

The obsolete 24 September 07:25 PDT deadline is archived and replaced by a new
recorded work-session control. Default collection window: six hours from launch,
then stop issuance and drain; the user may request an earlier pause or explicitly
extend the deadline. The actual control and launch times are recorded separately.
The former home-readiness requirement is superseded by the user's work-resume
instruction. No model, request, allocation, analysis, pacing, sample count, cap,
or failed-attempt history changes. No aggregate main-study effect estimates or
hypothesis tests informed this amendment; statistics review remains pending.

Validation: 55 local tests passed on 24 September, including scheduled routing,
held/deadline recovery refusal, existing eligibility checks, pause/drain accounting,
and reservation-barrier removal. These tests make no live API calls. Record the
actual subsequent activation and OSF disclosure timestamps separately.
