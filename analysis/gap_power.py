"""Gap-trend power sensitivity for the actual incomplete within-task gap ladder."""
import argparse
from collections import defaultdict
import json
from statistics import NormalDist

import numpy as np
from harness.audit import read_jsonl
from analysis.gap import SOURCES


def plan(stimuli,simulations=2000):
    grouped=defaultdict(lambda:defaultdict(list))
    for r in stimuli:
        if r['gap_bin']>0:grouped[r['source']][r['seed_id']].append(abs(r['signed_gap']))
    data={}
    for source in SOURCES:
        tasks=[np.array(v) for _,v in sorted(grouped[source].items())]
        counts=np.array([len(v) for v in tasks]);starts=np.r_[0,np.cumsum(counts)[:-1]]
        x=np.concatenate(tasks);center=np.concatenate([v-v.mean() for v in tasks])
        var=np.array([np.mean((v-v.mean())**2) for v in tasks])
        data[source]=(x,center,counts,starts,var)
    rng=np.random.default_rng(20260929);out=[]
    cutoff=NormalDist().inv_cdf(1-.05/10)
    for dimension in (1,2):
        for level in (.05,.15,.3):
            for sigma in (.1,.3,1.):
                for gated in (False,True):
                    pieces=[];truth=[]
                    for source,(x,center,counts,starts,var) in data.items():
                        task=rng.normal(0,.1,(simulations,len(counts)))
                        a=level*(1-x if gated else np.ones(len(x)))
                        # Task heterogeneity is shared by both independent repeats.
                        mean=a+np.repeat(task,counts,axis=1)
                        y=np.zeros_like(mean)
                        for _ in range(dimension):
                            d1=mean+rng.normal(0,sigma,mean.shape)
                            d2=mean+rng.normal(0,sigma,mean.shape)
                            y+=d1*d2/dimension
                        cov=np.add.reduceat(y*center,starts,axis=1)/counts
                        pieces.append((cov,var))
                        truth.append((np.mean(np.add.reduceat((a*a+.01)*center,starts)/counts),var.mean()))
                    denominator=np.mean([var.mean() for _,var in pieces])
                    beta=np.mean([cov.mean(axis=1) for cov,_ in pieces],axis=0)/denominator
                    variance=sum(np.var(cov-beta[:,None]*var,axis=1,ddof=1)/cov.shape[1]
                                 for cov,var in pieces)/(9*denominator**2)
                    rejected=beta/np.sqrt(variance)<-cutoff
                    rate=float(rejected.mean())
                    out.append(dict(transformed_dimensions=dimension,baseline_contrast=level,
                                    balanced_repeat_noise_sd=sigma,gated=gated,
                                    true_population_projection=float(np.mean([v[0] for v in truth])/denominator),
                                    rejection_probability=rate,monte_carlo_se=(rate*(1-rate)/simulations)**.5))
    return {'status':'assumption-based gap-trend planning; not empirical power certification',
            'simulations':simulations,'seed':20260929,'rows':out,
            'assumptions':['Uses all actual main nonidentity annotation gaps and task missingness.',
                           'Gaussian noise on nuisance-balanced transformed contrasts; independent repeats.',
                           'Task random intercept SD .1 on the transformed contrast, shared across repeats and items.',
                           'Scalar dimension represents Noul/Choice logits; dimension two represents Score log ratios.',
                           'Flat alternative: d(g)=baseline; gated alternative: d(g)=baseline*(1-g).',
                           'One-sided cluster-sandwich normal test at .05/10 approximates the planned bootstrap test.',
                           'Power for the stronger monotonicity claim is not inferred from trend power.',
                           'Does not model clipping, human measurement error, or cross-request dependence.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stimuli');p.add_argument('output');args=p.parse_args()
    result=plan(read_jsonl(args.stimuli))
    with open(args.output,'x') as f:json.dump(result,f,indent=2)
    null=[r['rejection_probability'] for r in result['rows'] if not r['gated']]
    print(json.dumps({'scenarios':len(result['rows']),'null_rejection_range':[min(null),max(null)]}))

if __name__=='__main__':main()
