"""Repeat-corrected presentation magnitude and task-clustered gap trends."""
import base64
from collections import defaultdict
import json
import math
import statistics

import numpy as np

from harness.audit import encode,validate_response

SOURCES=('MTBench','HANNA','SummEval')


def transformed(answer,question,target,clip=.005):
    if not 0<clip<.5:raise ValueError('Invalid clipping sensitivity')
    if question['type'] in ('noul','choice'):
        p=float(answer['noul'] if question['type']=='noul' else answer['probabilities'][target])
        p=min(1-clip,max(clip,p))
        return (math.log(p/(1-p)),)
    other='Y' if target=='X' else 'X'
    levels=[f'{other} is better than {target}.','The candidates are equally good.',f'{target} is better than {other}.']
    if set(question['criteria'])!=set(levels):raise ValueError('Comparative three-level score required')
    p=[float(answer['probabilities'][str(question['criteria'].index(level))]) for level in levels]
    # Additive log ratios preserve the ordinal distribution; the denominator is
    # the equality level, not an arbitrary logit of an expected grade.
    return tuple(math.log(max(clip,p[i])/max(clip,p[1])) for i in (0,2))


def magnitudes(records,stimuli,clip=.005):
    items={r['id']:r for r in stimuli};pairs=defaultdict(dict)
    for row in records:
        m=row['meta']
        if m.get('extension') or m['probe']!='A' or m['kind'] not in ('noul','choice','score'):continue
        if row['status']!=200:raise ValueError('Unsuccessful outcome cannot enter gap analysis')
        request=json.loads(row['request_body']);data=json.loads(base64.b64decode(row['response_body_b64']))
        validate_response(data,request)
        nuisance={k:v for k,v in m.items() if k!='state_order'}
        key=(encode(nuisance),row['replicate'])
        if m['state_order'] in pairs[key]:raise ValueError('Duplicate state-order outcome')
        pairs[key][m['state_order']]=transformed(data['answers']['preference'],request['questions']['preference'],m['target'],clip)
    repetitions=defaultdict(lambda:defaultdict(list))
    for (encoded,replicate),sides in pairs.items():
        if set(sides)!={0,1}:raise ValueError('Missing state-order mirror')
        m=json.loads(encoded)
        d=tuple(a-b for a,b in zip(sides[0],sides[1]))
        repetitions[(m['stimulus_id'],m['kind'])][replicate].append(d)
    output=[]
    for (sid,kind),repeats in repetitions.items():
        if set(repeats)!={0,1}:raise ValueError('A2 requires exactly two independent replicate schedules')
        if len(repeats[0])!=len(repeats[1]):raise ValueError('Replicate nuisance coverage differs')
        means=[tuple(statistics.mean(v[j] for v in repeats[r]) for j in range(len(repeats[r][0]))) for r in (0,1)]
        item=items[sid]
        output.append(dict(stimulus_id=sid,seed_id=item['seed_id'],source=item['source'],kind=kind,
                           gap_bin=item['gap_bin'],gap=abs(item['signed_gap']),
                           magnitude=sum(a*b for a,b in zip(*means))/len(means[0]),
                           replicate_contrasts=means))
    return output


def trends(rows,draws=5000,seed=20260926):
    """Within-task slopes; negative means less squared order effect at larger gaps."""
    rng=np.random.default_rng(seed);out=[]
    for kind in ('noul','choice','score'):
        grouped=defaultdict(lambda:defaultdict(list))
        for r in rows:
            if r['kind']==kind and r['gap_bin']>0:grouped[r['source']][r['seed_id']].append(r)
        contributions={};counts={}
        for source in SOURCES:
            tasks=grouped[source];values=[]
            for task,items in sorted(tasks.items()):
                x=np.array([r['gap'] for r in items]);y=np.array([r['magnitude'] for r in items])
                x=x-x.mean();y=y-y.mean()
                values.append((float(np.mean(x*y)),float(np.mean(x*x))))
            if not values:raise ValueError('Missing source in gap trend')
            contributions[source]=np.array(values)
            counts[source]={'tasks':len(values),'tasks_with_gap_variation':sum(v[1]>0 for v in values)}
        samples={}
        for source,a in contributions.items():
            means=a.mean(axis=0)
            if means[1]<=0:raise ValueError('No within-task gap variation in source')
            boot=a[rng.integers(0,len(a),(draws,len(a)))].mean(axis=1)
            samples[source]=boot
            estimates=np.divide(boot[:,0],boot[:,1],out=np.full(draws,np.nan),where=boot[:,1]>0)
            valid=estimates[np.isfinite(estimates)]
            out.append(dict(kind=kind,source=source,slope=means[0]/means[1],
                            ci95=np.quantile(valid,[.025,.975]).tolist() if len(valid)>=.99*draws else None,
                            degenerate_bootstrap_draws=draws-len(valid),**counts[source]))
        pooled=np.mean([a.mean(axis=0) for a in contributions.values()],axis=0)
        boot=np.mean(list(samples.values()),axis=0)
        estimates=boot[:,0]/boot[:,1]
        # Conservative threshold for the ten-test A family; primary alternative is negative.
        slope=float(pooled[0]/pooled[1]);errors=estimates-slope
        upper=float(slope-np.quantile(errors,.005))
        out.append(dict(kind=kind,source='equal-source pooled',slope=slope,
                        ci95=np.quantile(estimates,[.025,.975]).tolist(),
                        basic_upper99_5=upper,
                        centered_bootstrap_p_negative=(1+int(np.sum(errors<=slope)))/(draws+1),
                        multiplicity_note='Apply Holm jointly with the three A1 and four A5 tests; no standalone verdict.',
                        tasks=sum(v['tasks'] for v in counts.values())))
    return out


def adjacent_bins(rows,draws=5000,seed=20260927):
    """Paired-task higher-gap minus lower-gap differences, not composition shifts."""
    rng=np.random.default_rng(seed);out=[]
    for kind in ('noul','choice','score'):
        for low in (1,2,3):
            sources={}
            for source in SOURCES:
                tasks=defaultdict(lambda:defaultdict(list))
                for r in rows:
                    if r['kind']==kind and r['source']==source and r['gap_bin'] in (low,low+1):
                        tasks[r['seed_id']][r['gap_bin']].append(r['magnitude'])
                sources[source]=np.array([statistics.mean(v[low+1])-statistics.mean(v[low])
                                         for v in tasks.values() if low in v and low+1 in v])
            entry=dict(kind=kind,lower_bin=low,higher_bin=low+1,paired_tasks={s:len(v) for s,v in sources.items()})
            if any(len(v)<2 for v in sources.values()):
                entry['status']='insufficient paired tasks in at least one source'
            else:
                estimates=np.mean([v[rng.integers(0,len(v),(draws,len(v)))].mean(axis=1) for v in sources.values()],axis=0)
                mean=float(np.mean([v.mean() for v in sources.values()]))
                entry.update(status='descriptive monotonicity check',mean=mean,
                             # Nine simultaneous upper bounds: 3 kinds x 3 adjacent comparisons.
                             simultaneous_upper=float(2*mean-np.quantile(estimates,.05/9)))
            out.append(entry)
    return out
