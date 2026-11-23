# Main-study design candidate — 21 September 2026

**Not frozen; no main calls authorized by this file and none collected.** This
candidate preserves Probe A and C-iii, both reference judges, existing labels only,
and the user's 1% overall / 5% contested decision-change budgets. It resolves the
mean-margin identification problem without inventing a favorable numerical margin.
The executed pilot remains separate. Main cases are selected from untouched tasks.

The latest allocation/cost candidate is [BUDGET.md](BUDGET.md), using 4,090 matched
reference conditions at N=20. [ANALYSIS_PLAN.md](ANALYSIS_PLAN.md) consolidates the
implemented gap estimand, finite-audit risk bounds, and current power evidence.
Those two files supersede the earlier all-conditions reference budget below.

## Allocation and weighting

`stimuli/main_design.py` selects one nonidentity pair per available human-gap bin
per held-out task, then one exact-copy control per task. Selection uses fixed hashes
and existing annotations only. No main judge outputs exist. The generated candidate
is in `stimuli/prepared-main-v1/`, with hashes in its `allocation.json`.

| Corpus | Held-out tasks | Nonidentity pairs | Identity controls | Total stimuli |
| --- | ---: | ---: | ---: | ---: |
| MTBench | 64 | 185 | 64 | 249 |
| HANNA | 75 | 267 | 75 | 342 |
| SummEval | 73 | 208 | 73 | 281 |
| Total | 212 | 660 | 212 | 872 |

Each source receives weight 1/3; each task equal weight within source; available
nonidentity gap bins equal weight within task. This defines an **audit population**,
not an inferred production traffic mix. Identity controls have their own estimand.
Missing gap bins are reported, never filled by duplicating observations.

Two independent Jev replicates per condition provide 132,544 calls under the
legacy 76-condition A/C-iii template. The implemented three-envelope format controls
increase this to 172 conditions per stimulus, or 299,968 calls for this allocation.
These are candidate counts, not a finalized main budget. A separate single-call screening pass over
the eight Choice A presentations of each nonidentity pair adds 5,280 calls. These
screening responses determine contested membership and are excluded from outcome
contrasts. Membership is fixed before the independent outcome pass.

The candidate reference subset selects 12/14/14 held-out tasks by source, then an
identity control and one annotation-stratified nonidentity pair per task: 80 stimuli
from 40 tasks. Both judges see these same stimuli and full core conditions, at
20 draws per condition: 121,600 legacy calls, or 275,200 with the format controls,
per reference judge. Exact budgets, token
estimates, extensions, and the adequacy of this subset remain to be finalized
before freeze. This replaces ambiguous earlier uses of “4,000 stimuli” versus
“4,000 conditions”; do not claim 4,000 independent reference tasks.

## Decision rules and tie handling

The primary rule selects the higher of the **two returned Jev Choice probabilities**,
aligned to stable content x/y. For a normalized binary vector this has boundary .5;
the implementation also handles rounded vectors whose masses do not sum exactly
to one by comparing the two masses directly. Equality selects x iff the first
64 bits of SHA256(`tie-v1:<stimulus_id>`) are even; otherwise y. This tie rule is
independent of displayed labels, key order, and position. Copies have stable copy
identities; choosing a different copy is not a quality error.

Secondary rules are symmetric routing (x at p >= .8, y at p <= .2, review otherwise)
and one-sided action (act at p >= .8, otherwise no action). Confidence is never
substituted for preference probability. Exact ties and invalid outcomes are
reported. Noul strict superiority and ordinal Score do not inherit Choice's .5 rule.

A nonidentity pair is contested if **any of the eight independent screening
responses** has p in [.4,.6]. This operational, noisy screening procedure is the
estimand; it does not reveal a latent “true contested” population. Its fixed rule
avoids selecting a subgroup using the very outcome fluctuations whose flips are
being measured. References use the same Jev-screened subset for matched diagnostics;
their own noisy 20-draw frequency is not treated as known subgroup membership.

## Why there is no policy-derived mean TOST margin

Consider two comparisons: .49 -> .51 and .51 -> .49. The signed mean shift is zero,
but argmax changes in both. Thus **no positive margin on the signed mean alone can
guarantee either flip budget**. The old density inversion requires assumptions on
individual perturbations that a mean-equivalence test does not establish.

The observed .01 grid adds a separate issue: at .50, the next action-changing
returned probability is a full grid step away under the specified tie rule.
A continuous boundary-mass bound can be conservative or discontinuous here. Neither
that bound nor an assumed density supplies the missing implication from mean to
individual changes. We retain boundary-mass sensitivity as descriptive analysis.

The operational null for each rule and population is therefore directly
`H0: decision-change probability >= budget`, against `< budget`. A one-sided upper
confidence bound below .01 or .05 supports the corresponding stability statement.
This is an upper-bound/noninferiority-style test, not a two-sided mean TOST.
A claim that all policies meet the budgets requires **all six** conditions to pass;
it cannot be rescued by a looser routing threshold. Individual statements require
prespecified multiplicity handling. No mean-effect TOST margin is adopted merely
to retain the original label “TOST”. Probability effects still receive signed
estimates, uncertainty intervals, and tests of the scientific bias hypotheses.

## Separate presentation effects from API randomness

For independent calls to presentations a and b, define
`F_cross = P(g(p_a) != g(p_b))`. This measures operational instability and includes
sampling/runtime noise. Estimate it by all cross-replicate action comparisons.
For each presentation, use distinct repeat pairs to estimate repeat disagreement;
let their average be `F_same`.

If action probabilities are vectors pi_a and pi_b and repetitions are independent,
`F_cross - F_same = 0.5 * ||pi_a - pi_b||^2`. This separates a distributional
presentation effect from the repeat-noise baseline. Its unbiased finite-sample
estimate may be negative and will not be truncated. Neither quantity establishes
a counterfactual coupling of a model's internal random state. Two repeats permit
aggregate estimation, not precise per-item characterization. Test temporal/run
segment sensitivity and inspect the G2 repeat sequence before assuming independence.

Pilot diagnostics implementing the policies are in `analysis/pilot-decisions-20260921.json`.
They are explicitly **not certification**: the pilot has one scheduled outcome
replicate per cell and a post-outcome contested subgroup. Main screening and
repeated outcomes resolve those design defects prospectively.

Reference probabilities are verdict frequencies, not calibrated probabilities of
correctness. A majority decision from 20 draws has its own sampling uncertainty.
Do not claim latent reference argmax flips from raw noisy point estimates, or mix
reference single-draw decisions with Jev probability-argmax decisions without
labeling the different operational protocols. Decision-level certification is
primary for Jev; reference decision results are uncertainty-aware diagnostics.

## Scientific estimands and multiplicity

- A1: source-weighted, label/key-balanced mean state-order shift on exact copies,
  separately for Noul, Choice, and semantic expected Score.
- A2: nonidentity quality-gap dependence, modeled within source. Signed effects,
  noise-corrected magnitude, and saturation sensitivity are distinct. A negative
  fitted slope is insufficient to claim a monotone curve. Ordered-bin comparisons
  and their simultaneous uncertainty must also support that stronger claim.
- A5: question-order effects for each of helpfulness, accuracy, safety, and style,
  with state order and labels counterbalanced. These are procedural controls,
  not claims that the rating corpora annotate those four criteria.
- C-iii: presentation effects separately by question type, with both formatted
  content directions retained. The native-vs-neutral schema contrast below is
  needed for schema-specific claims.

Candidate multiplicity families: ten A tests (three A1, three A2, four A5), and
three C-iii tests, using Holm within family. Source-specific and cross-judge
contrasts are secondary until exact allocation and family membership are frozen.
A2's repeat-product logit/log-ratio estimand and ordered-bin checks are implemented
in `analysis/gap.py`; see `ANALYSIS_PLAN.md` for their interpretation and limits.
The richer C-iii controls and their direct native-minus-neutral contrast now have
offline tests, a synthetic smoke check, and a completed 3,840-call real-corpus pilot
on 40 tasks. Its variance now informs the updated planning sensitivity analysis.

For Noul/Choice, logit sensitivity uses clipping at .005, with .001/.01 sensitivity
analyses. This is a transformation of returned scores, not reconstruction of
latent probabilities. Clipping does not remove every saturation issue. Do not
apply a probability logit to normalized expected Score; retain its ordinal
probability vector and semantic level mapping.

Resample tasks with every pair/condition/repeat intact, stratified by source.
Use source weights stated above and report effective task counts per contrast.
For operational certification, report a conservative bounded-task concentration
bound alongside descriptive cluster bootstrap intervals. Zero observed flips
must not produce a zero-width “proof of invariance”. With 212 tasks and these
strict budgets, some clean-looking outcomes will remain inconclusive. That is
an honest limitation, not permission to relax the budgets.

## Planning evidence

`analysis/main-power-candidate.json` contains 90 reproducible, 20,000-trial
planning scenarios. It assumes independent normal task-level residuals and uses
pilot task SDs, stressed at 1x/2x/4x. It grants no variance reduction for the second
Jev replicate. This is sensitivity analysis, not validated power for every cell.

At the uninflated pilot SDs, approximate 90%-power MDE for pooled Choice A1 is .0132;
for the legacy simple-JSON C-iii Choice contrast it is .0068. At 4x SD those become
about .0528 and .0272. These are detection planning quantities, **not equivalence
margins**. That first simulation did not cover A2/A5/new schema controls. The updated
`main-power-candidate-v2.json` adds A5 and real-corpus native-format controls;
`gap-power-candidate-v1.json` adds assumption-based A2 sensitivity. Neither supports
a claim that every cell, monotonicity statement, or equivalence test has 90% power.

## Complete the scoped manipulation families

The core pairwise protocol does not replace the rest of Probe A. Required extensions:

1. Listwise cardinalities 2/3/5/10/25, with stable option identities and balanced
   cyclic rotations, crossed with key order. Exact-copy lists identify positional
   preference without new labels. Nonidentity listwise quality gaps need explicit
   human-rating-based definitions; 25 distinct rated candidates per task are not
   available in the current corpora, so no such coverage may be claimed.
2. Rubric granularities 2/3/5/7/10, using anchored pointwise quality levels and
   semantic remapping under level permutations. This is a separately specified
   rubric experiment. Do not force an even-sized comparative scale to imply a
   nonexistent equality category or recycle pairwise tie semantics.
3. C-iii now retains the simple lossless wrapper baseline and adds a neutral nested
   envelope and a Jev-like nested envelope, preserving the exact candidate string.
   Example shapes: `records.response.{kind,selected}` versus
   `answers.response.{type,choice}`, with identical categorical type value. Add no
   provenance, confidence, correctness, or authority assertion. Differences still
   include key semantics; they do not prove familiarity with undisclosed training
   data. Native-vs-neutral isolates a narrower surface contrast than prose-vs-JSON.

The format extension has manifests, G5/linter checks, and a live Jev smoke check.
It still needs matched reference verification and power planning on real pilot tasks.
The listwise and rubric extensions are now implemented and have passed 590/590
Jev pilot calls plus 590/590 one-draw integration calls on each reference provider.
These reference integration checks do not replace the N=20 scientific protocol.
The remaining work is allocation, power, temporal-noise sensitivity, and freeze.

### Implemented extension definitions

`harness/extensions.py` authors ten descriptive pointwise anchors per source:
task fulfillment for MTBench, narrative coherence for HANNA, and factual consistency
for SummEval. For K=2/3/5/7/10, consecutive anchors are grouped by `floor(i*K/10)`;
each level explicitly lists its applicable descriptions. Rubric order reverses
the complete level strings. These are authored instruments, not newly validated
human scales. Changing K also changes category coarseness and wording structure;
cross-K differences cannot identify a pure cardinality mechanism. Within-K order
contrasts do preserve descriptions exactly. Both candidates are graded separately,
with labels, state order, and rubric direction crossed: 80 calls per pair/replicate.
Expected semantic coordinates are ordinal summaries, not probabilities of preference.

Listwise sets use every rotation crossed with forward/reversed Choice keys.
Candidate IDs remain fixed. Identity lists cover K=2/3/5/10/25 in every source.
For HANNA/SummEval, distinct candidates are recovered from the pinned annotations,
identical text is deduplicated by a fixed source-ID hash, and nested candidate sets
use a fixed hash order independent of judge results. The list gap is the difference
between the top two mean human ratings, divided by four. MTBench pairwise votes
do not supply cardinal candidate ratings, so its listwise nonidentity arm is absent.
Neither rating corpus supplies 25 distinct rated candidates per task. These coverage
limits are explicit; copies are never mislabeled as distinct human-rated responses.
Candidate annotation disagreements across pairs fail validation.

`analysis/extensions.py` averages probability at each state position over all
rotations and both key directions, retaining separate key-order contrasts for each
stable option identity. It reports first-minus-last probability and the full position
curve; this custom contrast is not renamed the literature's Preference Fairness.
Rubric contrasts restore semantic order before subtraction and retain whole tasks
as the descriptive sampling units. Planted judges test both estimators, including
a judge whose raw score is always zero while its meaning reverses.

Raw probability validation allows a mass discrepancy up to `max(.02,.005*K)` and
score/rounded-expectation discrepancy up to `max(.04,.005*(K*(K-1)/2+1))`.
These are explicit nearest-cent rounding envelopes, not a claim about the server's
rounding mechanism. No probability vector is silently renormalized. Record deviations
and analyze sensitivity to strict mass conservation before the freeze. The previous
fixed tolerance was only appropriate to the small preflight answer spaces.

The three-task extension pilot has one task per corpus and cannot establish
population effect sizes. It includes 240 rubric and 350 listwise calls. All pins,
legends, and verdict schemas matched across providers. The largest observed Jev
input was 10,181 tokens; this does not validate context fit for every held-out list.
[API Score semantics](https://docs.typesafe.ai/primitives/score) and
[Choice semantics](https://docs.typesafe.ai/primitives/choice) were checked on
21 September 2026. The former documents independent level evaluation and up to
ten descriptive levels; that claim is an API description, not independently
verified architecture evidence.

### Full candidate counts, before budget resolution

`preflight/generated/full-allocation-counts-v1.json` now includes the extensions.
At the current uncommitted allocation, Jev would make 494,768 calls (including
screening), and each reference would make 497,600 calls at N=20. This is materially
larger than the early reference cost sketch. No such main schedule has been run.
Resolve a power-aware stratified reference allocation and a token-based budget
before freeze; a scientific subsample need not execute every nuisance combination
on every reference task. Both judges must receive the same selected complete
contrast groups. Reducing N or choosing cells after seeing main results is not an
acceptable budget adjustment. Haiku's current official list price remains $1/M
input and $5/M output ([pricing](https://platform.claude.com/docs/en/about-claude/pricing));
the new smoke requests recorded no cache hits, so automatic near-total caching
must not be assumed.

## Freeze and publication

Before main collection: finish the above analysis and manipulation definitions,
validate implementation on pilot/synthetic data, resolve the reference allocation
and total budget, save source/code/manifest hashes, and obtain an external protocol
timestamp. Any changes after that point require explicit dated amendments.

The planned independent statistics read remains required before submission;
reviewing this design before main collection would also protect the study from
an expensive analytic mistake. The manuscript must distinguish preregistered main
results, disclosed pilot-informed design choices, and exploratory follow-ups.
