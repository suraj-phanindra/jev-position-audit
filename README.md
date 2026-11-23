# Same Answer, Different Verdict: a position-bias audit of the Jev decision model

Code, aggregate results and figures for a registered audit of order and format sensitivity in **Jev 1.13** (`jev-1.13.0`), a typed decision model that returns probabilities instead of text.

## What the audit measures

- **Identical copies.** The same answer is shown twice, in both orders. Any shift toward a slot is a pure order effect.
- **Quality-gap ladder.** Pairs from three human-annotated corpora are binned by human-rated quality gap (bins 1 to 4).
- **Presentations.** Candidate order (mirrored), question order, three format envelopes (Jev-style, neutral, simple), and same-order repeats as a noise floor.
- **Reference judges.** Claude Haiku 4.5 and DeepSeek V4 Flash on a matched 40-task subset (20 sampled verdicts per condition).

| Corpus | Tasks | Pairs | Human signal used for the gap |
|---|---:|---:|---|
| MT-Bench | 64 | 249 | first-turn human preference margin |
| HANNA | 75 | 342 | mean coherence rating difference |
| SummEval | 73 | 281 | mean expert consistency rating difference |

## Headline results

| Result | Status |
|---|---|
| Choice: first slot gains **+0.127** [0.118, 0.136] on identical copies, first slot favoured in **98.6%** of identical pairs | registered, confirmed |
| Order-effect size shrinks as the quality gap grows (negative slopes for all three question types) | registered, confirmed |
| No detectable pooled effect of question order or Jev-style format | registered, null |
| Order reversal changes **47.5%** of decisions below 0.6 confidence and **0.1%** at 0.9 or above | exploratory |
| On the closest non-identical pairs the order effect leans to the second slot, mostly on SummEval | post hoc |

## Repository layout

| Path | Contents |
|---|---|
| `harness/` | request construction, collection and audit trail |
| `stimuli/` | corpus import and stimulus design (`prepare.py`, `main_design.py`, `CORPUS.md`, pinned `sources.json`) |
| `preflight/` | registration-time checks and amendment adapters (amendment 009 must be installed before analysis) |
| `analysis/` | registered estimands: contrasts (`pilot.py`), gap trend (`gap.py`), decisions and budgets (`decisions.py`, `risk.py`), main analysis (`main.py`) |
| `inference/` | amendment 010 inference: `signflip.py`, synthetic `calibration.py` and its results, `run_main.py`, `run_exploratory.py`, `export_paper_data.py` |
| `posthoc/` | the post hoc direction check and its output (labelled post hoc) |
| `results/` | aggregate result files (`paper-data-amendment010.json`, `exploratory-results-amendment010.json`) |
| `tables/`, `figures/` | CSV tables, figure scripts and rendered figures |
| `docs/` | analysis plan, design, protocol and operational amendments |
| `tests/` | unit tests (all keys in tests are dummy values) |

## Not included

- **Raw API responses** (about 6.6 GB) and the 483 MB main results file. They contain corpus text that this repository does not redistribute.
- **Corpus text.** Rebuild stimuli from the pinned public sources with `stimuli/prepare.py` (see `stimuli/CORPUS.md`).
- **Credentials.** Collection reads API keys from a local `.env`, which is never committed.

## Reproducing

```sh
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover tests          # unit tests
.venv/bin/python figures/make_figures.py             # figures from results/paper-data-amendment010.json
.venv/bin/python posthoc/make_fig_tab.py             # post hoc figure and table
```

Re-running `inference/run_main.py` needs the raw run files, which are not distributed.

## Registration

Design registered on OSF on 23 September 2026 ([registration](https://osf.io/4nme3/)). Amendment 010 fixed the inference method before any outcome was opened. The post hoc analysis was recorded on OSF after the main results were opened.
