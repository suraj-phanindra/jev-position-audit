"""Audit complete reference schedules and retain invalid draws as their own outcome."""
import argparse
import base64
from collections import Counter,defaultdict
import json
import math
from pathlib import Path

from harness.audit import encode,read_jsonl,score_value
from preflight.live_check import check_response,MODELS,verdict_options
from preflight.repeats import manifest_schedule
from analysis.binary_metrics import summarize as binary_metrics


def identity(row):
    return encode([row['request_sha256'],row['meta'],row['replicate'],row['sample']])


def report(records,manifest,provider,samples=20,canonical_schema=False):
    expected=manifest_schedule(manifest,provider,samples,canonical_schema=canonical_schema)
    by_id=defaultdict(list)
    for row in records:by_id[identity(row)].append(row)
    if set(by_id)!=set(identity(r) for r in expected):raise ValueError('Reference schedule incomplete or contaminated')
    cells=defaultdict(list);usage=Counter();transport_failures=0
    for row in expected:
        attempts=by_id[identity(row)]
        successful=[r for r in attempts if r['status']==200]
        transport_failures+=len(attempts)-len(successful)
        if len(successful)!=1:raise ValueError('A scheduled sample must have exactly one HTTP 200 result')
        data=json.loads(base64.b64decode(successful[0]['response_body_b64']))
        usage.update({k:v for k,v in data.get('usage',{}).items() if isinstance(v,int)})
        if data.get('model')!=MODELS[provider]:raise ValueError('Reference model changed')
        try:
            summary=check_response(provider,data,json.loads(row['request_body']))
            verdict=summary.get('verdicts',{}) if summary['valid_answers'] else {}
        except (ValueError,KeyError,TypeError):verdict={}
        request=json.loads(row['request_body'])
        questions=json.loads(request['messages'][-1]['content'])['questions']
        for name,q in questions.items():
            cells[encode([row['meta'],row['replicate'],name,q])].append(verdict.get(name,'INVALID'))
    output=[]
    for key,values in cells.items():
        if len(values)!=samples:raise ValueError('Incorrect number of draws')
        meta,replicate,name,q=json.loads(key);counts=Counter(values)
        entry={'meta':meta,'replicate':replicate,'question':name,'counts':dict(counts),'samples':samples}
        if not counts['INVALID']:
            options=verdict_options({name:q})[name]
            frequencies={v:counts[v]/samples for v in options}
            entry['frequencies']=frequencies
            if q['type']=='score':
                target=meta['target'];other='Y' if target=='X' else 'X'
                canonical=meta.get('canonical_levels',[f'{other} is better than {target}.','The candidates are equally good.',
                           f'{target} is better than {other}.'])
                entry['expected_semantic_score']=float(score_value(frequencies,q['criteria'],canonical))
                output.append(entry)
                continue
            p=frequencies['true' if q['type']=='noul' else meta['target']]
            z=1.959963984540054;den=1+z*z/samples
            center=(p+z*z/(2*samples))/den
            half=z*math.sqrt(p*(1-p)/samples+z*z/(4*samples*samples))/den
            entry.update(target_frequency=p,wilson95=[max(0,center-half),min(1,center+half)])
        output.append(entry)
    try:metrics=binary_metrics([r for r in records if r['status']==200],provider)
    except ValueError as error:metrics={'status':'unavailable','reason':str(error)}
    return {'binary_metrics':metrics,'provider':provider,'status':'complete reference schedule; registration status established separately',
            'conditions':len(manifest),'question_cells':len(output),'samples_per_condition':samples,'usage':dict(usage),
            'retained_failed_attempts':transport_failures,'cells':output,
            'warning':'Frequency estimates describe constrained verdict sampling, not calibrated correctness; no naive argmax flip test.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest');p.add_argument('output')
    p.add_argument('--runs',nargs='+',required=True);p.add_argument('--provider',choices=['anthropic','together'],required=True)
    p.add_argument('--canonical-schema',action='store_true')
    args=p.parse_args();rows=[r for path in args.runs for r in read_jsonl(path)]
    result=report(rows,read_jsonl(args.manifest),args.provider,canonical_schema=args.canonical_schema)
    with open(args.output,'x') as f:json.dump(result,f,indent=2)
    print(encode({k:v for k,v in result.items() if k!='cells'}))

if __name__=='__main__':main()
