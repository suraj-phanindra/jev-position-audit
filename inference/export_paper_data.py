"""Compact, outcome-derived aggregates for figures and tables (no raw text)."""
import json, statistics
from collections import defaultdict
import numpy as np
m = json.load(open('results/main-results-amendment010.json')); x = json.load(open('results/exploratory-results-amendment010.json'))
SOURCES = ('MTBench', 'HANNA', 'SummEval')
rng = np.random.default_rng(20261117)
def strat(by):
    arrs = [np.asarray(by[s]) for s in SOURCES if by.get(s)]
    est = float(np.mean([a.mean() for a in arrs]))
    reps = np.mean([a[rng.integers(0, len(a), (9999, len(a)))].mean(axis=1) for a in arrs], axis=0)
    return est, np.quantile(reps, [.025, .975]).tolist()
gap = []
cells = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
for r in m['gap_observations']:
    cells[(r['kind'], r['gap_bin'])][r['source']][r['seed_id']].append(r['magnitude'])
for (kind, b), by in sorted(cells.items()):
    tm = {s: [statistics.mean(v) for v in by[s].values()] for s in SOURCES if by[s]}
    est, ci = strat(tm)
    gap.append(dict(kind=kind, gap_bin=b, estimate=est, ci95=ci, tasks=sum(len(v) for v in tm.values()),
                    by_source={s: float(np.mean(v)) for s, v in tm.items()}))
out = dict(primary=m['primary_tests'], primary_registered=m['primary_tests_registered_holm'],
           gap_trends=m['gap_trends'], gap_by_bin=gap, gap_adjacent=m['gap_adjacent_bins'],
           operational_risk=[r for r in m['operational_risk']], binary_metrics=m['binary_metrics'],
           E1=x['E1_per_source'], E2=x['E2_direction'], E3=x['E3_flips_by_confidence'], E4=x['E4_listwise_identity'],
           E5=x['E5_cost'],
           reference={p: dict(jev=r['jev_cells'], ref=r['reference_cells'], diff=r['cells'], status=r['status'],
                              uncertainty=r['uncertainty']) for p, r in x['reference'].items()},
           rubric=x.get('rubric') if 'rubric' in x else None,
           extensions_rubric=m['extensions'].get('rubric_task_summaries'))
json.dump(out, open('results/paper-data-amendment010.json', 'w'), indent=1, default=float)
print('ok')
