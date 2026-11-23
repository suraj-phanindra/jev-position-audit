"""Amendment 010 exploratory analyses 1 to 5 (descriptive only) and the descriptive reference-judge
comparison (registered analysis.matched.compare). Run once from the project root after run_main.py."""
import base64, glob, json, sqlite3, statistics, sys, time
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
assert Path.cwd().resolve() == ROOT
OUT = ROOT / 'results' / 'exploratory-results-amendment010.json'
assert not OUT.exists(), 'runs once'
sys.path.insert(0, str(ROOT))
from preflight import amendment009
t0 = time.time()
def log(m): print(f'[{time.time()-t0:6.0f}s] {m}', flush=True)
B, SEED = 9999, 20261116
SOURCES = ('MTBench', 'HANNA', 'SummEval')

def boot_ci(values, rng):
    v = np.asarray(values, float)
    if len(v) < 2: return [None, None]
    reps = v[rng.integers(0, len(v), (B, len(v)))].mean(axis=1)
    return np.quantile(reps, [.025, .975]).tolist()

def strat_boot(by_source, rng):
    """by_source: dict source -> array of task values. Equal source weights."""
    arrs = [np.asarray(by_source[s], float) for s in SOURCES if len(by_source.get(s, [])) > 0]
    est = float(np.mean([a.mean() for a in arrs]))
    reps = np.mean([a[rng.integers(0, len(a), (B, len(a)))].mean(axis=1) for a in arrs], axis=0)
    return est, np.quantile(reps, [.025, .975]).tolist()

main = json.load(open(ROOT / 'results/main-results-amendment010.json'))
log('loaded main results')
out = {'status': 'exploratory, descriptive only; no tests; amendment 010', 'bootstrap_draws': B, 'seed': SEED}

# ---- E1 per-source estimates and E2 direction ----
groups = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
for r in main['core_contrasts']:
    if r['probe'] == 'A' and r['axis'] == 'state_order' and r['gap_bin'] == 0 and r['kind'] != 'questions': name = 'A1_' + r['kind']
    elif r['probe'] == 'A' and r['axis'] == 'question_order': name = 'A5_' + r['question']
    elif r['probe'] == 'C-iii' and r['axis'] == 'format_family' and r['gap_bin'] > 0: name = 'Ciii_' + r['kind']
    else: continue
    groups[name][r['source']][r['seed_id']][r['stimulus_id']].append(r['delta'])
rng = np.random.default_rng(SEED)
e1, e2 = [], []
for name in sorted(groups):
    for s in SOURCES:
        tasks = groups[name][s]
        tm = [statistics.mean(statistics.mean(v) for v in st.values()) for _, st in sorted(tasks.items())]
        e1.append(dict(hypothesis=name, source=s, tasks=len(tm), estimate=float(np.mean(tm)), ci95=boot_ci(tm, rng)))
    if name.startswith('A1_'):
        stim = [statistics.mean(v) for s in SOURCES for st in groups[name][s].values() for v in st.values()]
        row = dict(kind=name[3:], stimuli=len(stim), share_primacy=float(np.mean([x > 0 for x in stim])),
                   share_recency=float(np.mean([x < 0 for x in stim])), share_zero=float(np.mean([x == 0 for x in stim])))
        for s in SOURCES:
            ss = [statistics.mean(v) for st in groups[name][s].values() for v in st.values()]
            row['share_primacy_' + s] = float(np.mean([x > 0 for x in ss]))
        e2.append(row)
out['E1_per_source'] = e1
out['E2_direction'] = dict(note='Positive A1 = primacy. For two-option Choice, first-slot mass exceeds one half exactly when the stimulus contrast is positive.',
                           rows=e2)
log('E1, E2 done')

# ---- E3 decision change by confidence (Choice, order axis, nonidentity) ----
with amendment009.installed():
    from harness.audit import read_jsonl
    conf = defaultdict(list)
    for p in sorted(glob.glob('runs/main-v1/typesafe/task-*/*.jsonl')):
        for row in read_jsonl(p):
            m = row.get('meta', {})
            if row['status'] != 200 or m.get('extension') or m.get('probe') != 'A' or m.get('kind') != 'choice' \
               or m.get('gap_bin', 0) == 0 or m.get('state_order') != 0: continue
            probs = json.loads(base64.b64decode(row['response_body_b64']))['answers']['preference']['probabilities']
            conf[m['stimulus_id']].append(max(float(x) for x in probs.values()))
stim_conf = {k: statistics.mean(v) for k, v in conf.items()}
flips = defaultdict(lambda: {'cross': [], 'same': []})
src_of, task_of = {}, {}
for r in main['decision_contrasts']:
    if r['axis'] != 'state_order' or r['rule'] != 'argmax' or r['gap_bin'] == 0: continue
    flips[r['stimulus_id']]['cross'].append(r['cross_disagreement'])
    if r['same_disagreement'] is not None: flips[r['stimulus_id']]['same'].append(r['same_disagreement'])
    src_of[r['stimulus_id']] = r['source']; task_of[r['stimulus_id']] = r['seed_id']
bins = [('below 0.6', 0, .6), ('0.6 to 0.9', .6, .9), ('0.9 or above', .9, 1.01)]
e3 = []
for label, lo, hi in bins:
    for metric in ('cross', 'same'):
        bys = defaultdict(lambda: defaultdict(list))
        for sid, f in flips.items():
            c = stim_conf.get(sid)
            if c is None or not (lo <= c < hi) or not f[metric]: continue
            bys[src_of[sid]][task_of[sid]].append(statistics.mean(f[metric]))
        by_source = {s: [statistics.mean(v) for v in bys[s].values()] for s in SOURCES if bys[s]}
        n_stim = sum(len(v) for s in bys for v in bys[s].values())
        if not by_source: e3.append(dict(bin=label, metric=metric, stimuli=0)); continue
        est, ci = strat_boot(by_source, rng)
        e3.append(dict(bin=label, metric=metric, stimuli=n_stim, tasks=sum(len(v) for v in by_source.values()),
                       sources=sorted(by_source), rate=est, ci95=ci))
out['E3_flips_by_confidence'] = dict(note='Choice, Probe A nonidentity, argmax decision. cross = change under state-order reversal; same = change between repeats of the same order (noise floor). Confidence = mean top-option probability at state order 0. Sources with no stimuli in a bin are omitted from that bin.', rows=e3)
log('E3 done')

# ---- E4 listwise position mass by list size ----
lw = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
for r in main['extensions']['listwise']:
    if r['variant'] != 'identity': continue
    lw[r['cardinality']][r['source']][r['seed_id']].append(r['mean_probability_by_state_position'])
e4 = []
for k in sorted(lw):
    pos_by_source = {s: [np.mean(v, axis=0) for v in lw[k][s].values()] for s in SOURCES if lw[k][s]}
    row = dict(cardinality=k, uniform=1 / k, tasks=sum(len(v) for v in pos_by_source.values()))
    for label, idx in (('first', 0), ('last', -1)):
        est, ci = strat_boot({s: [t[idx] for t in v] for s, v in pos_by_source.items()}, rng)
        row[label + '_position_mass'] = est; row[label + '_ci95'] = ci
    row['mean_mass_by_position'] = np.mean([np.mean(v, axis=0) for v in pos_by_source.values()], axis=0).tolist()
    e4.append(row)
out['E4_listwise_identity'] = e4
log('E4 done')

# ---- E5 cost ----
con = sqlite3.connect(ROOT / 'runs/main-v1/completion-checkpoint-20260928.sqlite')
cost = {p: dict(attempts=n, usd=u / 1e9) for p, n, u in con.execute(
    'select provider,count(*),sum(coalesce(charged,reserved)) from attempts group by provider')}
succ = {'typesafe': 494768, 'anthropic': 81800, 'together': 81800}
for p in cost: cost[p]['usd_per_1000_successes'] = 1000 * cost[p]['usd'] / succ[p]
out['E5_cost'] = dict(note='Conservative ledger (list rates; failures at reserve). 1 unit = 1e-9 USD.', providers=cost,
                      total_usd=sum(c['usd'] for c in cost.values()),
                      jev_usd_per_primary_test=cost['typesafe']['usd'] / 13)
log('E5 done')

# ---- registered descriptive reference comparison ----
with amendment009.installed():
    from analysis.matched import compare
    from harness.audit import read_jsonl
    jev = [r for p in sorted(glob.glob('runs/main-v1/typesafe/task-*/*.jsonl')) for r in read_jsonl(p)]
    manifest = read_jsonl('preflight/generated/registration-v1/manifests/reference.jsonl.gz')
    out['reference'] = {}
    for prov in ('anthropic', 'together'):
        refs = [r for p in sorted(glob.glob(f'runs/main-v1/{prov}/reference/*.jsonl')) for r in read_jsonl(p)]
        res = compare(jev, refs, manifest, prov)
        res.pop('reference_report', None)
        out['reference'][prov] = res
        log(f'reference {prov} done')
with open(OUT, 'x') as f: json.dump(out, f, indent=1, default=float)
log('wrote ' + str(OUT))
