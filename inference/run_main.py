"""Single main analysis run under amendment 010 (posted on OSF 14 Nov 2026).

Runs the registered analysis.main.analyze unchanged, inside the amendment 009 adapter, then adds the
amendment 010 sign-flip p-values, the max-p decision rule, Holm, and the sparse-contrast flag.
Run once from the project root:  .venv/bin/python inference/run_main.py
"""
import glob, hashlib, json, os, resource, statistics, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if Path.cwd().resolve() != ROOT:
    raise SystemExit('Run from the project root')
OUT = ROOT / 'results' / 'main-results-amendment010.json'
if OUT.exists():
    raise SystemExit('Results already exist; the analysis runs once')
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'inference'))

import numpy as np
from signflip import signflip_p
from preflight import amendment009

t0 = time.time()
def log(msg): print(f'[{time.time()-t0:7.0f}s] {msg}', flush=True)

amendment009_record = amendment009.verify()
with amendment009.installed():
    import analysis.main as M
    from harness.audit import read_jsonl
    from analysis.decisions import screening_membership
    from analysis.gap import SOURCES

    manifests = sorted(glob.glob('preflight/generated/registration-v1/manifests/task-*.jsonl.gz'))
    runs = sorted(glob.glob('runs/main-v1/typesafe/task-*/*.jsonl'))
    screen_manifest = 'preflight/generated/registration-v1/manifests/screening.jsonl.gz'
    screen_runs = sorted(glob.glob('runs/main-v1/typesafe/screening/*.jsonl'))
    stimuli_path = 'preflight/generated/registration-v1/stimuli.jsonl.gz'
    log(f'{len(manifests)} manifests, {len(runs)} run files, {len(screen_runs)} screening files')

    attempts = []
    for i, p in enumerate(runs):
        attempts.extend(read_jsonl(p))
        if i % 40 == 0: log(f'loaded {i+1}/{len(runs)} run files, {len(attempts)} attempts, '
                            f'maxrss {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e9:.1f} GB')
    screen_attempts = [r for p in screen_runs for r in read_jsonl(p)]
    screened = screening_membership([r for r in screen_attempts if r['status'] == 200], read_jsonl(screen_manifest))
    manifest = [r for p in manifests for r in read_jsonl(p)]
    stimuli = read_jsonl(stimuli_path)
    successes = [r for r in attempts if r['status'] == 200]
    log(f'{len(successes)} successes, {len(attempts)-len(successes)} failed attempts retained; analysing')

    result = M.analyze(successes, manifest, stimuli, screened)
    log('registered analysis complete')

    # ---- amendment 010 additions ----
    groups = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    for r in result['core_contrasts']:  # identical grouping to analysis.main.mean_tests
        if r['probe'] == 'A' and r['axis'] == 'state_order' and r['gap_bin'] == 0 and r['kind'] != 'questions':
            name = 'A1_' + r['kind']
        elif r['probe'] == 'A' and r['axis'] == 'question_order': name = 'A5_' + r['question']
        elif r['probe'] == 'C-iii' and r['axis'] == 'format_family' and r['gap_bin'] > 0: name = 'Ciii_' + r['kind']
        else: continue
        groups[name][r['source']][r['seed_id']][r['stimulus_id']].append(r['delta'])
    flip = {}
    for name, sources in groups.items():
        means = [np.array([statistics.mean(statistics.mean(v) for v in items.values())
                           for _, items in sorted(sources[s].items())]) for s in SOURCES]
        flip[name] = dict(p_signflip=signflip_p(means, 9999),
                          nonzero_tasks=int(sum(int(np.sum(m != 0)) for m in means)),
                          tasks=int(sum(len(m) for m in means)))
    registered = result['primary_tests']
    decided = []
    for t in registered:
        d = {k: v for k, v in t.items() if k not in ('holm_p', 'reject')}
        d['p_registered'] = t['p']
        if t['hypothesis'] in flip:
            d.update(flip[t['hypothesis']])
            d['p'] = max(t['p'], d['p_signflip'])
            d['approximate_interval'] = d['nonzero_tasks'] < 20
        decided.append(d)
    result['primary_tests_registered_holm'] = registered
    result['primary_tests'] = M.holm(decided)
    result.update(amendment='010 (OSF update 14 Nov 2026)', amendment009_record_sha256=amendment009_record,
                  failed_attempts_retained=sum(r['status'] != 200 for r in attempts),
                  screening_failed_attempts_retained=sum(r['status'] != 200 for r in screen_attempts),
                  run_files=len(runs), screening_files=len(screen_runs),
                  peak_rss_gb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9,
                  runtime_seconds=round(time.time() - t0))
    with open(OUT, 'x') as f:
        json.dump(result, f, indent=1, default=float)
    log('wrote ' + str(OUT) + ' sha256 ' + hashlib.sha256(OUT.read_bytes()).hexdigest())
