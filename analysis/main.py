"""Combined Jev analysis: exact coverage, thirteen primary tests, and screened risk."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import statistics

import numpy as np
from harness.audit import digest,encode,read_jsonl,validate_manifest
from analysis.pilot import paired
from analysis.binary_metrics import summarize as binary_metrics
from analysis.gap import magnitudes,trends,adjacent_bins,SOURCES
from analysis.decisions import paired_choices,screening_membership
from analysis.risk import audit_bounds
from analysis.extensions import observations,summarize as extension_summary


def coverage(records,manifest):
    validate_manifest(manifest)
    def identity(r):return r['request_sha256'],digest(encode(r['meta'])),r['replicate']
    expected=Counter(map(identity,manifest));observed=Counter(map(identity,records))
    if any(n!=1 for n in expected.values()) or observed!=expected:
        raise ValueError('Main outcome coverage is incomplete, duplicated, or contaminated')
    for r in records:
        if r['status']!=200 or digest(r['request_body'])!=r['request_sha256']:
            raise ValueError('Unsuccessful or changed main request')


def holm(tests):
    output=[dict(t) for t in tests]
    for family in sorted({t['family'] for t in output}):
        ordered=sorted((t for t in output if t['family']==family),key=lambda t:t['p'])
        previous=0
        for i,t in enumerate(ordered):
            if not 0<=t['p']<=1:raise ValueError('Invalid primary p-value')
            previous=max(previous,min(1,(len(ordered)-i)*t['p']))
            t.update(holm_p=previous,reject=previous<=.05)
    return output


def mean_tests(contrasts,draws=9999):
    groups=defaultdict(lambda:defaultdict(lambda:defaultdict(lambda:defaultdict(list))))
    for r in contrasts:
        if r['probe']=='A' and r['axis']=='state_order' and r['gap_bin']==0 and r['kind']!='questions':
            name='A1_'+r['kind']
        elif r['probe']=='A' and r['axis']=='question_order':name='A5_'+r['question']
        elif r['probe']=='C-iii' and r['axis']=='format_family' and r['gap_bin']>0:name='Ciii_'+r['kind']
        else:continue
        groups[name][r['source']][r['seed_id']][r['stimulus_id']].append(r['delta'])
    output=[];rng=np.random.default_rng(20260930)
    for name,sources in sorted(groups.items()):
        if set(sources)!=set(SOURCES):raise ValueError('Missing source in primary mean contrast')
        means={s:np.array([statistics.mean(statistics.mean(v) for v in items.values())
                          for _,items in sorted(sources[s].items())]) for s in SOURCES}
        if any(len(v)<2 for v in means.values()):raise ValueError('Need at least two tasks per source for bootstrap')
        estimate=float(np.mean([v.mean() for v in means.values()]))
        boot=np.mean([v[rng.integers(0,len(v),(draws,len(v)))].mean(axis=1) for v in means.values()],axis=0)
        errors=boot-estimate
        p=(1+int(np.sum(abs(errors)>=abs(estimate))))/(draws+1)
        output.append(dict(hypothesis=name,family='C' if name.startswith('C') else 'A',estimate=estimate,
                           ci95=np.quantile(boot,[.025,.975]).tolist(),p=p,alternative='two-sided',
                           task_counts={s:len(v) for s,v in means.items()}))
    return output


def analyze(records,manifest,stimuli,screened,draws=9999):
    coverage(records,manifest)
    core=[r for r in records if not r['meta'].get('extension')]
    if {r['id'] for r in stimuli}!={r['meta']['stimulus_id'] for r in core}:
        raise ValueError('Stimulus registry differs from core outcome population')
    if set(screened)!={r['id'] for r in stimuli if r['gap_bin']>0}:
        raise ValueError('Screening membership differs from nonidentity main population')
    contrasts=paired(core);tests=mean_tests(contrasts,draws)
    gap_rows=magnitudes(core,stimuli)
    gap_trends=trends(gap_rows,draws)
    for r in gap_trends:
        if r['source']=='equal-source pooled':
            tests.append(dict(hypothesis='A2_'+r['kind'],family='A',estimate=r['slope'],ci95=r['ci95'],
                              p=r['centered_bootstrap_p_negative'],alternative='negative',tasks=r['tasks']))
    expected={f'A1_{k}' for k in ('noul','choice','score')}|{f'A2_{k}' for k in ('noul','choice','score')}|{
        'A5_'+k for k in ('helpfulness','accuracy','safety','style')}|{'Ciii_'+k for k in ('noul','choice','score')}
    if {r['hypothesis'] for r in tests}!=expected or len(tests)!=13:
        raise ValueError('Primary hypothesis family is incomplete or duplicated')
    decisions=paired_choices(core,screened)
    result={'status':'analysis completed; interpretation depends on registration and design assumptions',
            'bootstrap_draws':draws,'primary_tests':holm(tests),
            'gap_trends':gap_trends,'gap_adjacent_bins':adjacent_bins(gap_rows,draws),
            'gap_clipping_sensitivity':{str(clip):trends(magnitudes(core,stimuli,clip),draws)
                                        for clip in (.001,.01)},
            'operational_risk':audit_bounds(decisions),'binary_metrics':binary_metrics(core),
            'repeat_noise_note':'Direct bounds use independent same-replicate pairs; cross-pair excess is descriptive.',
            'core_contrasts':contrasts,'gap_observations':gap_rows,'decision_contrasts':decisions}
    ext=[r for r in records if r['meta'].get('extension')]
    if ext:
        result['extensions']=extension_summary(observations(ext,[r for r in manifest if r['meta'].get('extension')]))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output')
    p.add_argument('--manifests',nargs='+',required=True);p.add_argument('--runs',nargs='+',required=True)
    p.add_argument('--stimuli',required=True);p.add_argument('--screening-manifest',required=True)
    p.add_argument('--screening-runs',nargs='+',required=True)
    args=p.parse_args()
    attempts=[r for path in args.runs for r in read_jsonl(path)]
    screen_attempts=[r for path in args.screening_runs for r in read_jsonl(path)]
    screened=screening_membership([r for r in screen_attempts if r['status']==200],read_jsonl(args.screening_manifest))
    result=analyze([r for r in attempts if r['status']==200],
                   [r for path in args.manifests for r in read_jsonl(path)],read_jsonl(args.stimuli),screened)
    result.update(failed_attempts_retained=sum(r['status']!=200 for r in attempts),
                  screening_failed_attempts_retained=sum(r['status']!=200 for r in screen_attempts),
                  run_files=args.runs,screening_files=args.screening_runs)
    with open(args.output,'x') as f:json.dump(result,f,indent=2)
    print(encode({'primary_tests':len(result['primary_tests']),'risk_cells':len(result['operational_risk'])}))

if __name__=='__main__':main()
