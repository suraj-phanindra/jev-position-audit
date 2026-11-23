"""Cluster-level planning simulations; assumptions and variance stress cases are explicit."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
from statistics import NormalDist
import numpy as np

from harness.audit import read_jsonl
from analysis.pilot import paired


def plan(records,allocation,simulations=20000):
    source_n={s:allocation[s]['tasks'] for s in ('MTBench','HANNA','SummEval')}
    groups=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    for row in paired(records):
        if row['probe']=='A' and row['axis']=='state_order' and row['gap_bin']==0 and row['kind']!='questions':
            family='A1'
        elif row['probe']=='A' and row['axis']=='question_order':
            family='A5'
        elif row['probe']=='C-iii' and row['axis']=='format_family' and row['gap_bin']>0:
            family='Ciii_native_neutral'
        elif row['probe']=='C-iii' and row['gap_bin']>0 and not row.get('format_family'):
            family='Ciii_legacy_wrapper'
        else:continue
        dimension=row['question'] if family=='A5' else row['kind']
        groups[(family,dimension)][row['source']][row['seed_id']].append(row['delta'])
    rng=np.random.default_rng(20260922);out=[]
    for (family,kind),sources in sorted(groups.items()):
        sd={s:statistics.stdev(statistics.mean(v) for v in sources[s].values()) for s in source_n}
        tests=10 if family in ('A1','A5') else 3
        cutoff=NormalDist().inv_cdf(1-.05/(2*tests))
        se=(sum(sd[s]**2/source_n[s] for s in source_n)/9)**.5
        for scale in (1,2,4):
            noise=sum(rng.normal(0,scale*sd[s]/source_n[s]**.5,simulations) for s in source_n)/3
            for effect in (0,.005,.01,.02,.05):
                if se==0:raise ValueError('Zero pilot variance cannot identify planning power')
                rate=float(np.mean(np.abs((noise+effect)/(se*scale))>cutoff))
                out.append({'family':family,'kind':kind,'assumed_common_effect':effect,
                            'sd_multiplier':scale,'rejection_probability':rate,
                            'monte_carlo_se':float((rate*(1-rate)/simulations)**.5),
                            'pilot_task_sd':sd,'target_tasks':source_n,
                            'bonferroni_tests':tests,'normal_mde90':(cutoff+NormalDist().inv_cdf(.9))*se*scale})
    return {'status':'planning sensitivity, not final power certification',
            'simulations':simulations,'seed':20260922,
            'assumptions':['Independent task-level normal residuals within each source.',
                           'Equal source weights and equal task weights within source.',
                           'Pilot SD treated as known; 2x and 4x stress cases expose that uncertainty.',
                           'No precision credit for the second main replicate.',
                           'No claim of power for source-by-bin cells, interactions, gap trends, or operational equivalence.'],
            'rows':out}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('allocation');p.add_argument('output')
    p.add_argument('--runs',nargs='+',required=True);args=p.parse_args()
    records=[r for path in args.runs for r in read_jsonl(path) if r['status']==200]
    result=plan(records,json.loads(Path(args.allocation).read_text()))
    null=[r['rejection_probability'] for r in result['rows'] if r['assumed_common_effect']==0]
    assert all(0<=p<=.04 for p in null),null
    with open(args.output,'x') as f:json.dump(result,f,indent=2)
    print(f"Simulated {len(result['rows'])} planning scenarios; null size sanity check passed")

if __name__=='__main__':main()
