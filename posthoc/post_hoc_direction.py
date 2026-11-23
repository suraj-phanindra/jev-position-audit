"""POST HOC analysis, added 18 Nov 2026 after the main results were opened.

Not in the registration (23 Sep 2026) or amendment 010 (14 Nov 2026).
Descriptive only: estimates and task-stratified bootstrap intervals, no tests.

Question: on non-identical pairs, does the order effect point to the first slot?
Estimator: the registered A1 contrast (target value with target first minus
target value with target second, state_order axis, probe A), applied to every
gap bin 0 to 4 instead of bin 0 only. Positive means the first slot gains,
whichever candidate is better. Bin 0 must reproduce the registered A1 estimates.

Input: the existing main-results JSON (core_contrasts). No new API calls.
"""
import hashlib, json, statistics, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

SOURCES = ('MTBench', 'HANNA', 'SummEval')
KINDS = ('choice', 'noul', 'score')
DRAWS = 9999
SEED = 20261118


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main(results_path, out_path):
    data = json.load(open(results_path))
    registered = {t['hypothesis']: t['estimate'] for t in data['primary_tests']}
    # groups[kind][bin][source][task][stimulus] -> deltas (same nesting as mean_tests)
    groups = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))))
    for r in data['core_contrasts']:
        if r['probe'] != 'A' or r['axis'] != 'state_order' or r['kind'] not in KINDS:
            continue
        groups[r['kind']][r['gap_bin']][r['source']][r['seed_id']][r['stimulus_id']].append(r['delta'])
    del data
    rng = np.random.default_rng(SEED)
    rows = []
    for kind in KINDS:
        for b in sorted(groups[kind]):
            src = groups[kind][b]
            if set(src) != set(SOURCES):
                raise ValueError(f'missing source for {kind} bin {b}')
            task_means, stim_means = {}, []
            for s in SOURCES:
                tm = []
                for _, stims in sorted(src[s].items()):
                    per = [statistics.mean(v) for v in stims.values()]
                    stim_means += [(s, x) for x in per]
                    tm.append(statistics.mean(per))
                task_means[s] = np.array(tm)
            est = float(np.mean([v.mean() for v in task_means.values()]))
            boot = np.mean([v[rng.integers(0, len(v), (DRAWS, len(v)))].mean(axis=1)
                            for v in task_means.values()], axis=0)
            row = dict(kind=kind, gap_bin=b, estimate=est, ci95=np.quantile(boot, [.025, .975]).tolist(),
                       tasks={s: int(len(v)) for s, v in task_means.items()},
                       stimuli=len(stim_means),
                       share_first_favoured=float(np.mean([x > 0 for _, x in stim_means])),
                       share_second_favoured=float(np.mean([x < 0 for _, x in stim_means])),
                       per_source={})
            for s in SOURCES:
                v = task_means[s]
                bs = v[rng.integers(0, len(v), (DRAWS, len(v)))].mean(axis=1)
                xs = [x for t, x in stim_means if t == s]
                row['per_source'][s] = dict(estimate=float(v.mean()), ci95=np.quantile(bs, [.025, .975]).tolist(),
                                            share_first_favoured=float(np.mean([x > 0 for x in xs])))
            rows.append(row)
    # validation: bin 0 must equal the registered A1 estimates
    checks = {}
    for kind in KINDS:
        b0 = next(r for r in rows if r['kind'] == kind and r['gap_bin'] == 0)['estimate']
        reg = registered['A1_' + kind]
        checks['A1_' + kind] = dict(bin0=b0, registered=reg, match=abs(b0 - reg) < 1e-12)
    if not all(c['match'] for c in checks.values()):
        raise ValueError(f'bin 0 does not reproduce A1: {checks}')
    out = dict(status='POST HOC, descriptive, added 2026-11-18 after main results were opened; '
                      'not in registration or amendment 010; no tests',
               estimator='registered A1 state-order contrast applied to gap bins 0 to 4; positive = first slot gains',
               input_file=str(results_path), input_sha256=sha256(results_path),
               script_sha256=sha256(__file__), bootstrap_draws=DRAWS, seed=SEED,
               a1_reproduction_check=checks, rows=rows)
    with open(out_path, 'x') as f:
        json.dump(out, f, indent=1)
    print(json.dumps({'written': out_path, 'checks': checks}, indent=1))


if __name__ == '__main__':
    main(Path(sys.argv[1]), sys.argv[2])
