"""Find worked-example candidates (MT-Bench, Choice, legacy format) from main-run outputs.
Read-only. Writes worked-example-candidates.json next to this script's working dir."""
import json, base64, glob, statistics, sys
from collections import defaultdict

stim = {json.loads(l)['id']: json.loads(l) for l in open('stimuli/prepared-main-v1/stimuli.jsonl')}
cells = defaultdict(lambda: defaultdict(list))   # sid -> state_order -> list of P(first-slot candidate)
tgt = defaultdict(lambda: defaultdict(list))     # sid -> state_order -> P(target)
question = {}
for f in sorted(glob.glob('runs/main-v1/typesafe/task-*/*.jsonl')):
    for line in open(f):
        r = json.loads(line)
        m = r['meta']
        if r.get('status') != 200 or m.get('probe') != 'A' or m.get('kind') != 'choice' or m.get('source') != 'MTBench':
            continue
        if m.get('extension') or 'structured' in m or 'format_family' in m:
            continue
        d = json.loads(base64.b64decode(r['response_body_b64']))
        p = float(d['answers']['preference']['probabilities'][m['target']])
        so = m['state_order']
        tgt[m['stimulus_id']][so].append(p)
        cells[m['stimulus_id']][so].append(p if so == 0 else 1 - p)
        if m['stimulus_id'] not in question:
            req = json.loads(r['request_body'])
            question[m['stimulus_id']] = req['questions']['preference']
out = []
for sid, c in cells.items():
    if set(c) != {0, 1}:
        continue
    s = stim[sid]
    pt0, pt1 = statistics.mean(tgt[sid][0]), statistics.mean(tgt[sid][1])
    dec0 = 'target' if pt0 > .5 else 'other'
    dec1 = 'target' if pt1 > .5 else 'other'
    out.append(dict(id=sid, gap_bin=s['gap_bin'], signed_gap=s.get('signed_gap'),
                    p_target_when_first=round(pt0, 4), p_target_when_second=round(pt1, 4),
                    p_first_slot_mean=round(statistics.mean(c[0] + c[1]), 4),
                    decision_flips=dec0 != dec1, n=len(c[0]) + len(c[1]),
                    len_x=len(s['x']), len_y=len(s['y']), len_prompt=len(s['prompt']),
                    prompt=s['prompt'], x=s['x'], y=s['y'], question=question[sid]))
json.dump(out, open('worked-example-candidates.json', 'w'), indent=1)
by = defaultdict(int)
for o in out: by[(o['gap_bin'], o['decision_flips'])] += 1
print(len(out), dict(by))
