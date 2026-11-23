"""Secondary binary Choice metrics; sampled verdicts and returned-score argmax stay distinct."""
import base64
from collections import Counter,defaultdict
import json
import statistics

from analysis.decisions import action
from harness.audit import encode,validate_response
from preflight.live_check import check_response


def summarize(records,provider='typesafe'):
    cells=defaultdict(dict)
    for row in records:
        m=row['meta']
        if m.get('extension') or m['probe']!='A' or m['kind']!='choice':continue
        if row['status']!=200:raise ValueError('Binary metrics require successful scheduled draws')
        request=json.loads(row['request_body']);data=json.loads(base64.b64decode(row['response_body_b64']))
        if provider=='typesafe':
            validate_response(data,request)
            probs=data['answers']['preference']['probabilities'];target=m['target']
            verdict=action(probs[target],'argmax',m['stimulus_id'],probs['Y' if target=='X' else 'X'])
        else:
            checked=check_response(provider,data,request)
            if not checked['model_match'] or not checked['valid_answers']:
                raise ValueError('Invalid reference verdict: binary metrics unavailable, retain invalid counts separately')
            verdict='x' if checked['verdicts']['preference']==m['target'] else 'y'
        key=encode(m);draw=(row['replicate'],row.get('sample',0))
        if draw in cells[key]:raise ValueError('Duplicate binary draw')
        cells[key][draw]=verdict
    mirrors=defaultdict(dict)
    for key,draws in cells.items():
        m=json.loads(key);side=m.pop('state_order');mirrors[encode(m)][side]=draws
    groups=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    for key,sides in mirrors.items():
        if set(sides)!={0,1} or set(sides[0])!=set(sides[1]):raise ValueError('Incomplete binary state mirrors')
        m=json.loads(key);a,b=sides[0],sides[1];n=len(a)
        # State 0 starts with content x; state 1 starts with content y.
        pc=sum(a[k]==b[k] for k in a)/n
        primacy=sum(a[k]=='x' and b[k]=='y' for k in a)/n
        recency=sum(a[k]=='y' and b[k]=='x' for k in a)/n
        rs=statistics.mean(max(Counter(v.values()).values())/n for v in (a,b))
        groups[(m['source'],m['gap_bin'])][m['seed_id']][m['stimulus_id']].append(
            {'PC':pc,'PF_binary':recency-primacy,'primacy_rate':primacy,'recency_rate':recency,'RS':rs,'draws_per_request':n})
    output=[]
    for (source,gap),tasks in sorted(groups.items()):
        metrics=('PC','PF_binary','primacy_rate','recency_rate','RS')
        # Equal task then equal stimulus weights, matching the within-source estimand.
        values={metric:statistics.mean(statistics.mean(statistics.mean(r[metric] for r in rows)
                for rows in items.values()) for items in tasks.values()) for metric in metrics}
        output.append(dict(source=source,gap_bin=gap,tasks=len(tasks),**values,
            draws_per_request=sorted({r['draws_per_request'] for items in tasks.values() for rows in items.values() for r in rows})))
    return {'cells':output,'outcome':'returned-score argmax' if provider=='typesafe' else 'individual sampled verdict',
            'notes':['Descriptive same-index paired draws; PC includes stochastic disagreement.',
                     'PF_binary = recency rate - primacy rate. For exhaustive binary judgments this is the paper raw PF scaled by theoretical extrema plus/minus number of pairs.',
                     'RS is observed modal-verdict fraction, sensitive to repeat count; no determinism claim.',
                     'Reference metrics use individual draws, never argmax of the 20-draw frequency.'],
            'definition_source':'https://arxiv.org/html/2406.07791v6#S2.SS1'}
