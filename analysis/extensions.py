"""Descriptive Probe A extension estimates, preserving complete factorial coverage."""
import argparse
import base64
from collections import defaultdict
import json
import statistics

from harness.audit import digest,encode,read_jsonl,target_value,validate_manifest,validate_response


def observations(records,manifest):
    validate_manifest(manifest)
    def key(row):return row['request_sha256'],encode(row['meta']),row['replicate']
    if sorted(map(key,records))!=sorted(map(key,manifest)):
        raise ValueError('Extension outcome coverage differs from manifest')
    out=[]
    for row in records:
        if row['status']!=200:raise ValueError('Unsuccessful extension outcome')
        if digest(row['request_body'])!=row['request_sha256']:raise ValueError('Request hash mismatch')
        request=json.loads(row['request_body']);data=json.loads(base64.b64decode(row['response_body_b64']))
        validate_response(data,request)
        m=row['meta'];a=data['answers']['preference'];q=request['questions']['preference']
        out.append({'meta':m,'replicate':row['replicate'],'probabilities':a['probabilities'],
                    'value':float(target_value(a,q,m['target'],m.get('canonical_levels')))})
    return out


def summarize(rows):
    lists=defaultdict(dict);rubrics=defaultdict(dict)
    for row in rows:
        m=row['meta']
        if m['extension']=='listwise':
            key=(m['stimulus_id'],row['replicate'])
            cell=(m['rotation'],m['choice_order'])
            if cell in lists[key]:raise ValueError('Duplicate listwise outcome')
            lists[key][cell]=row
        elif m['extension']=='rubric':
            for axis in ('state_order','rubric_order'):
                nuisance={k:v for k,v in m.items() if k!=axis}
                key=(axis,encode(nuisance),row['replicate'])
                if m[axis] in rubrics[key]:raise ValueError('Duplicate rubric outcome')
                rubrics[key][m[axis]]=row['value']
        else:raise ValueError('Unknown extension')
    listwise=[];rubric=[]
    for (_,replicate),cells in lists.items():
        m=next(iter(cells.values()))['meta'];k=m['cardinality']
        if set(cells)!={(r,o) for r in range(k) for o in (0,1)}:
            raise ValueError('Incomplete listwise rotations/key orders')
        position=[statistics.mean(float(cells[(rotation,order)]['probabilities'][f'C{(rotation+pos)%k:02d}'])
                                 for rotation in range(k) for order in (0,1)) for pos in range(k)]
        key_deltas=[statistics.mean(float(cells[(r,0)]['probabilities'][f'C{i:02d}'])-
                                    float(cells[(r,1)]['probabilities'][f'C{i:02d}']) for r in range(k))
                    for i in range(k)]
        listwise.append({k:m[k] for k in ('stimulus_id','seed_id','source','variant','gap_bin','list_gap','cardinality')})
        listwise[-1].update(replicate=replicate,mean_probability_by_state_position=position,
                            primacy_minus_recency=position[0]-position[-1],
                            forward_minus_reverse_key_probability_by_stable_id=key_deltas)
    for (axis,encoded,replicate),values in rubrics.items():
        if set(values)!={0,1}:raise ValueError('Incomplete rubric mirror')
        m=json.loads(encoded)
        rubric.append({**m,'axis':axis,'replicate':replicate,'delta':values[0]-values[1]})
    # Task means, not replicated API calls, are the descriptive sampling units.
    groups=defaultdict(lambda:defaultdict(list))
    for r in rubric:
        groups[(r['source'],r['granularity'],r['axis'])][r['seed_id']].append(r['delta'])
    summaries=[]
    for (source,size,axis),tasks in sorted(groups.items()):
        means=[statistics.mean(v) for v in tasks.values()]
        summaries.append(dict(source=source,granularity=size,axis=axis,tasks=len(means),
                              mean=statistics.mean(means),task_sd=statistics.stdev(means) if len(means)>1 else None))
    return {'listwise':listwise,'rubric_contrasts':rubric,'rubric_task_summaries':summaries}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest');p.add_argument('output');p.add_argument('--runs',nargs='+',required=True)
    args=p.parse_args();attempts=[r for path in args.runs for r in read_jsonl(path)]
    result=summarize(observations([r for r in attempts if r['status']==200],read_jsonl(args.manifest)))
    result.update(status='extension pilot only; no confirmatory conclusions',attempt_files=args.runs,
                  failed_attempts=sum(r['status']!=200 for r in attempts))
    with open(args.output,'x') as f:json.dump(result,f,indent=2)
    print(encode({'listwise_sets':len(result['listwise']),'rubric_contrasts':len(result['rubric_contrasts'])}))

if __name__=='__main__':main()
