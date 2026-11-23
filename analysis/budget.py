"""Estimate full-list-rate costs from actual request sizes and observed token usage."""
import argparse
import base64
from collections import defaultdict
import json
from pathlib import Path
import statistics

from harness.audit import encode,generate,read_jsonl
from harness.extensions import generate_extensions
from preflight.live_check import reference_payload

PRICES={'typesafe':(.042,0),'anthropic':(1,5),'together':(.14,.28)}


def size(request,provider):
    if provider=='typesafe':stimulus={k:request[k] for k in ('state','questions')}
    else:stimulus=json.loads(request['messages'][-1]['content'])
    return len(encode(stimulus).encode('utf-8'))


def calibrate(records):
    ratios=defaultdict(list);outputs=defaultdict(list)
    for r in records:
        if r['status']!=200:continue
        provider=r.get('provider','typesafe');meta=r['meta']
        if meta.get('source') not in ('MTBench','HANNA','SummEval'):continue
        usage=json.loads(base64.b64decode(r['response_body_b64']))['usage']
        tokens=usage.get('input_tokens',usage.get('prompt_tokens'))
        tokens+=usage.get('cache_read_input_tokens',0)+usage.get('cache_creation_input_tokens',0)
        out=usage.get('output_tokens',usage.get('completion_tokens'))
        key=(provider,meta['source'],meta['kind'])
        ratios[key].append(tokens/size(json.loads(r['request_body']),provider))
        outputs[key].append(out)
    result={k:{'n':len(v),'median_tokens_per_utf8_byte':statistics.median(v),
               'max_observed_tokens_per_utf8_byte':max(v),'median_output':statistics.median(outputs[k]),
               'max_observed_output':max(outputs[k])} for k,v in ratios.items()}
    for provider in ('anthropic','together'):
        for source in ('MTBench','HANNA','SummEval'):
            key=(provider,source,'noul')
            if key not in result:
                result[key]={**result[(provider,source,'choice')],
                             'proxy':'same-source Choice; standalone Noul token calibration unavailable'}
    return result


def main_conditions(stimuli,pairs):
    tasks=defaultdict(list);pool=defaultdict(list)
    for s in stimuli:tasks[s['seed_id']].append(s)
    for s in pairs:pool[s['seed_id']].append(s)
    for task,items in sorted(tasks.items()):
        for item in items:yield from generate([item],'jev-1.13.0',format_controls=True)
        yield from generate_extensions(items,pool[task])


def estimate(stimuli,pairs,reference,calibration):
    totals=defaultdict(lambda:dict(calls=0,median_input_estimate=0,stress_input_estimate=0,
                                 median_output_estimate=0,stress_output_estimate=0))
    worst=[]
    def add(row,provider,repeats):
        m=row['meta'];request=json.loads(row['request_body'])
        wire=request if provider=='typesafe' else reference_payload(provider,request,canonical_schema=True)
        key=(provider,m['source'],m['kind'])
        if key not in calibration:raise ValueError('Missing token calibration: '+str(key))
        c=calibration[key];n=size(wire,provider);t=totals[provider]
        t['calls']+=repeats
        t['median_input_estimate']+=n*c['median_tokens_per_utf8_byte']*repeats
        # A scenario, not a guarantee: 1.5 times the largest observed ratio.
        t['stress_input_estimate']+=n*c['max_observed_tokens_per_utf8_byte']*1.5*repeats
        t['median_output_estimate']+=c['median_output']*repeats
        t['stress_output_estimate']+=(c['max_observed_output'] if provider=='typesafe' else 128)*repeats
        if provider=='typesafe':worst.append((n*c['max_observed_tokens_per_utf8_byte']*1.5,m['stimulus_id'],m.get('extension','core')))
    for row in main_conditions(stimuli,pairs):
        add(row,'typesafe',2)
        m=row['meta']
        if not m.get('extension') and m['probe']=='A' and m['kind']=='choice' and m['gap_bin']>0:
            add(row,'typesafe',1) # Separate contested screening.
    for row in reference:
        for provider in ('anthropic','together'):add(row,provider,20)
    for provider,t in totals.items():
        prices=PRICES[provider]
        for scenario in ('median','stress'):
            t[scenario+'_cost_usd']=(t[scenario+'_input_estimate']*prices[0]+t[scenario+'_output_estimate']*prices[1])/1e6
    return {'status':'planning estimates, not an invoice or hard spending ceiling',
            'prices_usd_per_million':PRICES,'providers':dict(totals),
            'calibration':[{**dict(zip(('provider','source','kind'),k)),**v} for k,v in sorted(calibration.items())],
            'largest_jev_stress_input_estimates':sorted(set(worst),reverse=True)[:10],
            'assumptions':['No caching or batch discounts credited.',
                           'Input estimate uses observed tokens/UTF8-byte ratios by provider, source and question type.',
                           'Stress uses 1.5 times the largest observed ratio and 128 output tokens per reference call.',
                           'Tokenization and hidden prompt overhead can differ; stress is not a proven bound.',
                           'All candidate main tasks and all A/C-iii manipulations retained for Jev.',
                           'Both reference judges receive the same 4,090-condition candidate at N=20.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');p.add_argument('--runs',nargs='+',required=True)
    args=p.parse_args()
    records=[r for path in args.runs for r in read_jsonl(path)]
    result=estimate(read_jsonl('stimuli/prepared-main-v1/stimuli.jsonl'),read_jsonl('stimuli/prepared-v2/pairs.jsonl'),
                    read_jsonl('preflight/generated/main-reference-candidate-v4.jsonl'),calibrate(records))
    result['calibration_files']=args.runs
    with open(args.output,'x') as f:json.dump(result,f,indent=2)
    print(encode(result['providers']))

if __name__=='__main__':main()
