# Statistical analysis candidate — 21 September 2026

**Registration candidate.** This consolidates implemented estimands and assumptions. No main
outcomes have been collected. The external statistical read remains required before
submission; a review before main collection would be preferable.

## Scientific effects

A1 is the signed, label/key-balanced state-order effect on exact copies, separately
for Noul, Choice, and comparative Score. A5 is the signed question-order effect for
each of four criteria. Source weights are 1/3, task weights equal within source,
and stimulus weights equal within task. Average nuisance conditions and replicates
within stimulus before averaging stimuli; repeated calls are not new tasks.

C-iii's three primary tests compare the Jev-like envelope with the neutral nested
envelope on nonidentity pairs, one per question type. Reverse the sign when content
y receives the envelope so positive means advantage for the formatted content.
Plain/simple, plain/neutral, plain/native, exact-copy, and direction-specific
results remain reported secondary contrasts. No effect identifies training-data
familiarity or a pure syntax mechanism. Source text and framing remain explicit.

The A family contains three A1, three A2, and four A5 tests, with Holm correction.
The C family contains three native-minus-neutral tests, with Holm correction.
Task-stratified bootstrap draws keep every variant of a sampled task together.
Centered bootstrap tests and descriptive confidence intervals must be distinguished;
a confidence interval on an unadjusted cell is not a family-adjusted significance
claim. `analysis/main.py` combines exact coverage checks, all thirteen tests, the operational
risk bounds, and descriptive extension summaries. `analysis/matched.py` compares
references on identical selected nuisance conditions.

## A2: gap dependence without squaring measurement noise

`analysis/gap.py` defines the source-specific and pooled gap trend. For each
nonidentity stimulus and independent outcome replicate, form the state-order
contrast and average label/answer-order nuisance settings. For Noul and Choice,
use logit-transformed returned probabilities, clipped at .005; repeat the analysis
at .001 and .01. These are transformations of returned scores, not recovery of
latent calibrated probabilities. For three-level comparative Score, restore the
semantic levels and use two log ratios: worse/equal and better/equal, flooring each
probability at the same clipping constant. Do not take a logit of an expected grade.

Let d1 and d2 be the independent, nuisance-balanced contrast vectors. Use
`mean_j(d1_j * d2_j)` as the magnitude observation. With independent replicates,
its expectation is the mean squared expected transformed contrast. Squaring a
single noisy contrast would instead add its measurement variance. The product
may be negative in a finite sample and is never truncated. Endpoint clipping and
independence are real assumptions; both receive sensitivity analyses.

Fit magnitude against the **observed annotation gap**, removing task intercepts.
Within each task, compute mean centered x*y and mean centered x*x; average these
contributions with equal task weights within source and equal source weights.
Their ratio is the pooled slope. Source slopes are also reported. Resample whole
tasks within source and re-estimate the ratio. Tasks lacking gap variation contribute
zero to both terms, and their number is reported. A negative slope is the primary
A2 alternative; its centered-bootstrap p-value enters the joint A-family Holm test.
This operational definition does not claim a known latent human-quality gap.

A negative trend does not establish monotonicity. Separately compare each adjacent
pair of bins among tasks represented in **both** bins. Report simultaneous upper
bounds for the nine comparisons (three transitions × three types). A stronger
monotone-decline statement requires every relevant bound to support that direction;
missing paired coverage or an inconclusive transition prevents that statement.
Human annotation noise and source-dependent scales remain limitations. A latent-gap
measurement-error sensitivity model is not yet implemented and must not be described
as completed correction. Reference arms have only one nonidentity pair per selected
task: their gap curves are descriptive, not the same within-task A2 test.

## Operational budgets: conditional finite-audit inference

The 1% overall and 5% contested budgets remain unchanged. Primary argmax compares
the two actual returned Choice masses; exact ties use the fixed content-ID hash.
Independent screening fixes contested membership. The two secondary policies are
symmetric routing at .2/.8 and one-sided action at .8. No confidence-field substitute
and no probability-mean TOST margin is adopted.

There are two different populations. Cluster intervals describe variability across
audit tasks under a task-sampling interpretation; they do not certify deployment
traffic. `analysis/risk.py` additionally bounds expected decision-change risk on
this **fixed finite audit matrix**, conditional on independent API call pairs and
fixed screening. This uses the same-replicate comparisons (two independent pairs
per mirrored condition). All four cross-replicate comparisons remain useful for
descriptive repeat-noise decomposition, but are dependent and do not become four
independent Bernoulli observations.

Assign each outcome its prespecified source/task/stimulus/condition/repeat weight.
For contested risk, select screened items and renormalize their original weights.
Do not rebalance sources or tasks after screening: that would define a different
conditional population. Copy-vs-copy actions are reported separately from decisions
between nonidentical responses. No result here transfers the budgets to an unknown
production traffic mix.

For independent Bernoulli outcomes Yi with nonnegative weights wi summing to one,
let r = sum(wi*Yi), mu = E[r], and wmax = max(wi). Convexity gives
`E[exp(-t*r)] <= exp((mu/wmax)*(exp(-t*wmax)-1))` for t > 0.
Optimizing the lower-tail Chernoff bound gives
`P_mu(r <= observed) <= exp(-(mu-r+r*log(r/mu))/wmax)` for r < mu.
Invert this inequality for a one-sided upper confidence bound. At r=0 the bound
is `min(1, wmax*log(1/alpha))`; zero observations do not yield zero uncertainty.
Apply the same construction to 1-Y for a lower bound. Bonferroni across both tails
and all reported policy/presentation cells gives simultaneous coverage under the
stated independence assumption. This derivation is implemented directly and tested
by exhaustive enumeration of a small heterogeneous Bernoulli example.

An upper bound below the budget supports stability on this finite audit matrix;
a lower bound above it supports failure of the budget. Otherwise report inconclusive.
A claim covering every policy/presentation requires every corresponding bound to
pass. Dependence, version drift, or incomplete screening invalidates that interpretation.
The conservative task-level concentration diagnostic is retained as a different,
stronger generalization sensitivity; it will often be inconclusive at 212 tasks.

## Planning evidence and limits

`analysis/main-power-candidate-v2.json` has 195 scenarios for A1, A5, and both legacy
and native-format effects, using pilot task SDs with 1x/2x/4x stress. At 1x, approximate
90%-power MDEs are .0132 for Choice A1 and .0047 for native-minus-neutral Choice.
These use an independent-normal-task approximation and are not equivalence margins.
The native estimates now use real pilot corpus items, not just synthetic examples.

`analysis/gap-power-candidate-v1.json` simulates the actual incomplete main gap ladder
under explicit transformed-noise models. Its 36 scenarios include flat nulls and
gated contrasts; null rejection ranged .002–.008 at the conservative .005 threshold.
Power depends strongly on repeat noise. For baseline contrast .15, scalar trend
power falls from 1.00 at balanced-repeat noise SD .1 to .18 at SD .3. Therefore the
study must not advertise uniform 90% power for arbitrary gap gating. This is a
sensitivity analysis, not empirical validation of the final bootstrap test.

`analysis/g2-temporal-20260921-v2.json` examines 200 chronological repeats for each
of 50 shapes. Pooled lag-one permutation p-values were .871 (Noul), .564 (Choice),
and .541 (Score). This does not reject exchangeability on that diagnostic; it
cannot establish independence or rule out later drift, cross-request dependence,
or other temporal effects. Repeat/order scheduling remains interleaved, and run
segment sensitivity must accompany main inference.
