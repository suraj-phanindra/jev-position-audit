# Jev judge bias: position and structured-format affinity

**Registration candidate v1, 21 September 2026. Not externally registered.**
No main-study calls have been made. Main collection starts only after the exact
package receives an external timestamp and its registered copy is verified.
Prior pilots informed this design and are excluded from confirmatory analysis.

## Questions and scope

This study tests presentation sensitivity in a typed, non-generative judge:
**Probe A (position and order)** and **Probe C-iii (structured-format affinity)**.
Position effects lead; structured-format effects are the secondary contribution.
Verbosity, sycophancy, source-family affinity, provenance cues, agent traces, and
position × verbosity are outside this study. No new human raters are recruited.

The primary questions are whether order changes judgments, whether that effect
varies with externally annotated quality gap, and whether a Jev-like envelope
changes judgments relative to a neutral envelope. Two specified generative judges
provide matched comparisons. Observed differences cannot isolate architecture,
training objective, training corpus, or a universal effect of generation.

## Models and elicitation

| Arm | Pinned model | Route | Outcome calls per condition |
| --- | --- | --- | ---: |
| Jev | `jev-1.13.0` | TypeSafe direct | 2 |
| Haiku | `claude-haiku-4-5-20251001` | Anthropic Messages | 20 |
| DeepSeek | `deepseek-ai/DeepSeek-V4-Flash-0731` | Together Chat | 20 |

The refreshed Together catalogue contains no dated V4.1 Flash snapshot; 0731 is
retained. A dated ID is not proof of immutable serving internals. Every returned
model ID, request, response, timestamp, and usage record is retained. Model-ID
drift stops collection. No metered OpenAI API arm is used.

References use temperature 1, maximum 128 output tokens, no supplied seed, and
constrained verdicts without requested reasoning. Output schema keys and enums are
canonicalized independently of prompt ordering. State text and question semantics
match Jev. The reference Noul proxy is a true/false verdict. Frequency estimates
measure the constrained sampler's distribution, not calibrated correctness.
Together logprobs were accepted as a request field but absent in live responses;
they are not required or used as a primary outcome. Invalid draws are retained.

## Corpus, splitting, and allocation

Pinned MTBench, HANNA, and SummEval sources are recorded in `stimuli/sources.json`.
`stimuli/CORPUS.md` documents import, annotation provenance, and limitations.
Splits are assigned by `SHA256("split-v1:" + task_id) modulo 5`; residue zero is
pilot. All candidates, variants, and annotations from one task share a split.

Main selection is outcome-independent: one pair per available nonidentity gap bin
within task, plus one exact-copy pair. Hash tie-breaking and all request bytes are
specified by the enclosed code and manifests. There are **872 stimuli / 212 tasks**:
64 MTBench, 75 HANNA, and 73 SummEval tasks. Unequal bin availability is retained;
no model score supplies or repairs a quality label.

MTBench gaps are absolute preference margins, counting tied votes as half a win.
Most pairs have only 1–3 votes. HANNA coherence and SummEval consistency gaps are
absolute differences in mean existing human ratings divided by four; they are
**not preference margins**. Nonidentity bins are ≤.10, (.10,.30], (.30,.60], and
>.60. Exact identity is its own bin. Gap trends concern these noisy observed
annotations; no latent-gap measurement-error correction is claimed.

Reference selection contains 80 stimuli / 40 tasks, with 12/14/14 tasks by source.
Each contributes an identity and a nonidentity pair. The precise nuisance-condition
allocation is in `BUDGET.md`; comparisons use the exact same Jev conditions.

## Manipulations and outcomes

A core request uses stable candidate identities and crosses state order with label
assignment. Choice crosses answer-key order; comparative Score crosses rubric
direction; the four-question call crosses helpfulness/accuracy/safety/style order.
Noul asks strict superiority. Choice asks forced preference with stipulated equal
probability for equally good candidates. Comparative Score has worse/equal/better
levels, remapped to canonical semantics before computing its normalized mean.
A Score mean is not a preference probability. On exact copies, Noul's true answer
is false; the Score equality level and Choice symmetry are distinct diagnostics.

C-iii uses three lossless presentations: a simple `answer` wrapper, a neutral
nested `records/response/kind/selected` wrapper, and a Jev-like
`answers/response/type/choice` wrapper. Decoding preserves the original text exactly.
Each is crossed with state order, label assignment, which content is formatted,
and plain versus structured presentation. **Native minus neutral**, on nonidentity
pairs, is primary. The other contrasts are secondary. Added syntax changes token
count and readability; effects do not identify pure syntax or self-preference.
Format × position and format × observed gap are descriptive secondary analyses.

Rubric extensions use 2/3/5/7/10 semantic levels, target both candidates, and cross
state/rubric direction. Coarsening changes descriptions; cross-granularity contrasts
are not pure cardinality effects. Listwise extensions use 2/3/5/10/25 candidates,
all cyclic rotations, and both key directions. Exact-copy lists use a UTF-8-safe
1,200-byte source prefix shared across cardinalities. Distinct annotated lists use
available HANNA/SummEval pools up to ten; no MTBench cardinal ratings are invented.
References cover these extensions on one task per source, descriptively.

Every manifest passes G5: undo only the declared transformation, then require
identical remaining request bytes and a complete factorial group. Structural
`wellposed` results and retained warnings are enclosed as `LINT.json`. Forced
Choice is intentionally exhaustive under its tie rule; independent single-question
calls isolate order surfaces. Structural lint does not establish scientific validity.

## Primary hypotheses and inference

`ANALYSIS_PLAN.md` supplies the mathematical specification; enclosed source fixes
its implementation. All primary tests and all secondary outcomes are reported,
including null, contrary, and inconclusive results.

- **A1:** signed state-order effect on exact copies, separately for Noul, Choice,
  and comparative Score (three two-sided tests).
- **A2:** decreasing squared expected transformed state-order contrast with
  observed nonidentity annotation gap (three one-sided negative-trend tests).
- **A5:** signed question-order effect for each of four criteria (four two-sided tests).
- **C-iii:** native-minus-neutral advantage for formatted content, separately for
  Noul, Choice, and comparative Score (three two-sided tests).

A1/A2/A5 form one ten-test Holm family; C-iii forms one three-test Holm family.
Source weights are one third, tasks are equal within source, and stimuli are equal
within task. Average nuisance settings and independent replicates within stimulus.
Use 9,999 task-stratified bootstrap draws with fixed code seeds. Descriptive 95%
intervals are not multiplicity-adjusted significance claims. No selection based on
pilot sign or main results changes the declared direction or family.

For A2, Noul/Choice use logits clipped at .005, with .001/.01 sensitivity. Score
uses two semantic log ratios, worse/equal and better/equal. Multiply independent
replicate contrasts rather than squaring one noisy observation, retaining negative
finite-sample products. Regress the resulting magnitude on observed gap after
within-task centering, as specified in `ANALYSIS_PLAN.md`. Negative slope alone
is not monotonicity: report adjacent-bin paired-task contrasts and simultaneous
bounds, including missing coverage. Reference gap curves are descriptive because
each selected task has only one nonidentity pair.

Signed contrasts use content-aligned outcomes. State-order positive means primacy;
format positive means advantage for the formatted content. `analysis/main.py`
requires complete main and independent screening coverage before primary inference.
`analysis/matched.py` verifies exact reference/Jev nuisance matching and reports
paired task-bootstrap differences, separately by reference. It does not divide by
near-zero reference effects or generalize two models to all LLM judges.

Secondary binary Choice metrics report PC (same-index content-aligned verdict
agreement), primacy and recency rates, and `PF_binary = recency − primacy`. Under
exhaustive binary judgments, the literature's raw PF simplifies to recency count
minus primacy count; scaling by theoretical extrema ±number of pairs gives this
normalization. RS is the modal-verdict fraction per repeated request. These are
explicit descriptive metrics, not standalone hypothesis tests. Jev uses returned-
score argmax; references use individual sampled verdicts, never argmax of the noisy
20-draw frequency. PC includes sampling noise; RS depends on repeat count.
[Metric definitions](https://arxiv.org/html/2406.07791v6#S2.SS1)

## Decision stability and equivalence

The user's budgets remain **1% overall / 5% contested**. Primary argmax compares
both actual returned Choice masses; exact ties use the frozen content-identity
hash. Secondary policies route at .2/.8 or act above .8. Independent screening
uses eight Choice presentations per nonidentity pair; a pair is contested if any
screened target probability lies in [.4,.6]. Screening outcomes never enter effect
estimation. Copy cases are reported separately from substantive decisions.

**No signed-mean TOST margin is adopted.** Small average shifts can cancel while
many decisions change. Instead, prespecified weighted Bernoulli concentration
bounds test decision-change risk directly on the fixed audit matrix, conditional
on independent API calls and fixed screening. Bounds cover both tails and all
reported policy/presentation cells simultaneously. Preserve original population
weights when conditioning on contested membership. Upper below budget supports
stability; lower above budget supports failure; otherwise report inconclusive.
A claim covering all policies requires every corresponding bound to pass.

These are finite-audit results, not certification of unknown deployment traffic.
Report task-level sensitivity and same-condition stochastic disagreement alongside
cross-presentation disagreement. Cross-replicate combinations do not create extra
independent observations. A stable pilot does not prove determinism or independence.
Quantized means can detect some small returned-score effects, but deterministic
rounding bias need not average away; latent probabilities remain unidentified.
`confidence` is not a separate head or a substitute primary outcome.

## Pilot disclosure, power, and limitations

Excluded pre-main data include 10,000 Jev repeated requests, the 3,952-call initial
pilot, 3,840 native-format pilot successes, synthetic format checks, 590 extension
checks per arm, and the two N=20 reference integration pilots. Full counts and
retained failed attempts are in `preflight/READINESS.md` and pilot artifacts.
These observations were used to choose the final allocation, clipping sensitivity,
format controls, output grammar, pacing, and analytical estimands before main data.

Pilot-based task-noise simulations and the 36 gap-trend sensitivity scenarios are
summarized in `ANALYSIS_PLAN.md`. Power is not uniformly 90%: noisy transformed
contrasts can substantially weaken A2. Existing annotation noise, possible corpus
contamination, limited reference tasks, few ratings, sampling dependence, and
serving drift remain material limitations. There is no newly human-labelled fresh
holdout. Reference nulls do not establish a broken experiment; synthetic positive
controls test implementation independently of a model exhibiting expected bias.

## Collection, stopping, and budget

The frozen allocation is **494,768 Jev calls** including 5,280 screening calls,
and **81,800 per reference**. `BUDGET.md` gives request-based estimates of $131.29
at median observed ratios and $260.33 in the stress scenario, excluding prior work.
A shared persistent ledger caps conservatively accounted main API spend at **$300**,
including attempted retries. Unknown usage retains its full reservation. This is
a bound under the recorded provider list-rate policy, not a provider invoice cap
covering taxes or a future price change. No caching savings are assumed.

Use `preflight/main_run.py` with the verified registration receipt. All providers
and resumes share `runs/main-v1/spending.sqlite`; it must never be reset or bypassed.
Conservative starting rates are four Jev requests/s and two reference requests/s,
with four workers each. Therefore the Jev sweep takes at least about 34 hours at
that pacing; it is not the earlier three-hour estimate. Every call retains raw
response bytes before validation. Stop scheduling and drain in-flight calls after
an error. Resumes use new files, retain every attempt, and skip successful samples.

Only HTTP 408/429/500/502/503/504 or transport failures may receive explicit retries,
up to three total attempts per scheduled draw. No automatic retry-until-valid;
HTTP-200 invalid outputs, model drift, persistent errors, or context failures stop
for a dated amendment. Never silently change text, model, sample count, or cases.
Budget exhaustion is a stop, not permission to drop a cell. Incomplete confirmatory
coverage is reported; primary full-design claims wait for completion or an explicit
amendment. Outcome-driven early stopping is prohibited.

Task schedule order and within-task order are deterministic shuffled schedules.
All variants and repeats remain together for clustering. Report run dates and
segment sensitivity; a date-stamped model identifier cannot exclude backend drift.

## Registration and release

`DESIGN.json` enumerates compressed schedules and counts; `INDEX.json` hashes every
package artifact, including the source snapshot. The external upload contains source/specification files and the complete hash
index; dataset-bearing schedules remain local pending license review, bound by
that externally timestamped index. The external receipt records OSF URL,
registration time, index hash, and verification of the external copy. The
main entry point checks these and rejects changed executable source. Local hashes
alone are not an external preregistration. Any subsequent change gets a dated
amendment describing whether affected outcomes were already observed.

The user handles technical-only TypeSafe outreach. This work sends no study preview
or other messages. Auth keys and raw private environment files are excluded from
the package. Release corpus material only consistent with its source licenses;
source availability does not automatically permit relicensing news or stories.
The manuscript remains a solo preprint with an independent statistics read before
submission. Public posting and reviewer assessment are still future work.

Phase 2 mitigation/mechanism experiments are **not included in this registration
or budget**. Report main results completely before selecting follow-ups; register
their designs separately. Their results cannot become retroactively confirmatory
under this protocol. Position leads regardless of which secondary finding is larger.
