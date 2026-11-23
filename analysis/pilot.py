"""Descriptive pilot contrasts; never a confirmatory test or frozen margin."""
import argparse
import base64
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import statistics

from harness.audit import encode,read_jsonl,target_value,validate_manifest,validate_response


def percentile(values,q):
    values=sorted(values)
    return values[min(len(values)-1,int(q*(len(values)-1)))]


def paired(records):
    observations=[]
    for row in records:
        if row['status']!=200:raise ValueError('Failed pilot request')
        request=json.loads(row['request_body'])
        response=json.loads(base64.b64decode(row['response_body_b64']))
        validate_response(response,request)
        for name,q in request['questions'].items():
            observations.append({'meta':row['meta'],'replicate':row['replicate'],'question':name,
                                 'value':float(target_value(response['answers'][name],q,row['meta']['target']))})
    return paired_values(observations)


def paired_values(observations):
    """One contrast definition shared by returned scores and reference frequencies."""
    cells=defaultdict(dict)
    for row in observations:
        meta=row['meta']
        if meta.get('extension'):raise ValueError('Use analysis.extensions for extension manifests')
        axes=['structured'] if meta['probe']=='C-iii' else ['state_order']+{
            'noul':[],'choice':['choice_order'],'score':['rubric_order'],'questions':['question_order']}[meta['kind']]
        manipulations=[(axis,meta[axis]) for axis in axes]
        if meta.get('structured')==1 and meta.get('format_family') in ('neutral','native'):
            manipulations.append(('format_family',int(meta['format_family']=='native')))
        for axis,level in manipulations:
            nuisance={k:v for k,v in meta.items() if k!=axis}
            key=(axis,row['question'],encode(nuisance),row['replicate'])
            if level in cells[key]:raise ValueError('Duplicate pilot cell')
            cells[key][level]=row['value']
    output=[]
    for (axis,name,encoded,replicate),values in cells.items():
        if set(values)!={0,1}:raise ValueError('Missing mirrored pilot cell')
        meta=json.loads(encoded)
        delta=values[0]-values[1]
        if axis in ('structured','format_family'):
            delta=values[1]-values[0]
            if meta['formatted_content']=='y':delta=-delta
        output.append({**meta,'axis':axis,'question':name,'replicate':replicate,'delta':delta})
    return output


def summarize(contrasts,draws=2000):
    cells=defaultdict(lambda:defaultdict(list))
    for row in contrasts:
        key=(row['probe'],row['axis'],row['kind'],row['question'],row['source'],row['gap_bin'],row.get('formatted_content'),row.get('format_family','legacy'))
        cells[key][row['seed_id']].append(row['delta'])
    rng=random.Random(20260921);out=[]
    for key,tasks in sorted(cells.items()):
        means=[statistics.mean(v) for v in tasks.values()]
        entry=dict(zip(('probe','axis','kind','question','source','gap_bin','formatted_content','format_family'),key))
        entry.update(tasks=len(means),mean=statistics.mean(means))
        if len(means)>1:
            bootstrap=[statistics.mean(rng.choices(means,k=len(means))) for _ in range(draws)]
            sd=statistics.stdev(means)
            entry.update(task_mean_sd=sd,ci95=[percentile(bootstrap,.025),percentile(bootstrap,.975)],
                         ci90=[percentile(bootstrap,.05),percentile(bootstrap,.95)],
                         illustrative_tasks_for_mde_001=max(2,math.ceil(10.51*sd**2/.01**2)) if sd>0 else None)
        else:entry['uncertainty']='not estimable from one task'
        out.append(entry)
    return out


def boundary_masses(records):
    probabilities=defaultdict(list);baseline={}
    for row in records:
        m=row['meta']
        if m['probe']!='A' or m['kind']!='choice' or m['gap_bin']==0:continue
        d=json.loads(base64.b64decode(row['response_body_b64']))
        p=float(d['answers']['preference']['probabilities'][m['target']])
        probabilities[m['stimulus_id']].append(p)
        if m['labels_swapped']==m['state_order']==m['choice_order']==0:baseline[m['stimulus_id']]=p
    out=[]
    for rule,bounds in [('argmax',[.5]),('symmetric',[.2,.8]),('one_sided',[.8])]:
        for subgroup,budget in [('all',.01),('contested',.05)]:
            ids=[i for i in baseline if subgroup=='all' or any(.4<=p<=.6 for p in probabilities[i])]
            values=[baseline[i] for i in ids]
            if not values:
                out.append(dict(rule=rule,subgroup=subgroup,n=0));continue
            grid=[]
            for m in [0,.001,.002,.004,.008,.01,.02]:
                count=sum(any(abs(p-b)<=m+1e-12 for b in bounds) for p in values)
                # Diagnostic only: task selection is stratified, not iid production draws.
                upper=min(1,count/len(values)+math.sqrt(math.log(6/.05)/(2*len(values))))
                grid.append(dict(shift=m,boundary_mass=count/len(values),hoeffding_upper_sensitivity=upper))
            out.append(dict(rule=rule,subgroup=subgroup,n=len(values),budget=budget,grid=grid))
    return {'status':'no margin adopted; equal pilot-task diagnostic only',
            'warning':'Sparse tasks and conditional subgroup uncertainty preclude production guarantees.',
            'cells':out}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run');p.add_argument('manifest');p.add_argument('output')
    p.add_argument('--additional-runs',nargs='*',default=[])
    args=p.parse_args();paths=[args.run]+args.additional_runs
    attempts=[r for path in paths for r in read_jsonl(path)]
    records=[r for r in attempts if r['status']==200]
    manifest=read_jsonl(args.manifest);validate_manifest(manifest)
    expected=sorted((r['request_sha256'],encode(r['meta']),r['replicate']) for r in manifest)
    observed=sorted((r['request_sha256'],encode(r['meta']),r['replicate']) for r in records)
    if observed!=expected:raise ValueError('Run does not exactly cover pilot manifest')
    out={'status':'pilot only; bootstrap intervals are unstable in sparse cells',
         'attempt_files':paths,'failed_attempts':len(attempts)-len(records),
         'calls':len(records),'task_clusters':len({r['meta']['seed_id'] for r in records}),
         'contrasts':summarize(paired(records)),
         'boundary_masses':boundary_masses(records)}
    with open(args.output,'x') as f:json.dump(out,f,indent=2)
    print(f"Saved {len(out['contrasts'])} descriptive cells; no hypothesis verdicts")

if __name__=='__main__':main()
