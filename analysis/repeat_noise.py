"""Temporal sensitivity of G2 repeated requests; exchangeability is tested, not assumed."""
import argparse
import base64
from collections import defaultdict
import json

import numpy as np
from harness.audit import read_jsonl,target_value,validate_response


def report(records,draws=2000):
    groups=defaultdict(list)
    for r in records:
        if r['status']!=200:continue
        request=json.loads(r['request_body']);data=json.loads(base64.b64decode(r['response_body_b64']))
        validate_response(data,request)
        for name,q in request['questions'].items():
            value=float(target_value(data['answers'][name],q,'X'))
            groups[(q['type'],r['request_sha256'],name)].append((r['started_at'],value))
    rng=np.random.default_rng(20260928);out=[]
    for kind in ('noul','choice','score'):
        series=[];constant=0;drifts=[]
        for (k,request_hash,name),observations in groups.items():
            if k!=kind:continue
            values=np.array([v for _,v in sorted(observations)])
            if len(values)!=200:raise ValueError('G2 must have 200 successful observations per shape')
            drifts.append(float(values[100:].mean()-values[:100].mean()))
            if np.ptp(values)==0:constant+=1
            else:series.append((values-values.mean())/values.std())
        if not series:raise ValueError('No varying series')
        a=np.array(series)
        def statistic(z):return float(np.mean(z[:,:-1]*z[:,1:]))
        observed=statistic(a);permuted=[]
        for _ in range(draws):
            permuted.append(statistic(np.take_along_axis(a,np.argsort(rng.random(a.shape),axis=1),axis=1)))
        null=np.array(permuted);center=null.mean()
        p=(1+int(np.sum(abs(null-center)>=abs(observed-center))))/(draws+1)
        out.append(dict(kind=kind,varying_shapes=len(series),constant_shapes=constant,
                        pooled_standardized_lag1_product=observed,permutation_p_two_sided=p,
                        permutation_null_interval95=np.quantile(null,[.025,.975]).tolist(),
                        mean_late_minus_early=float(np.mean(drifts)),max_absolute_late_minus_early=float(max(abs(x) for x in drifts))))
    return {'status':'G2 temporal diagnostic only; no proof of independence', 'seed':20260928,
            'permutations':draws,'rows':out,
            'limits':['Chronological adjacency is within request shape, not consecutive global requests.',
                      'Permutation tests exchangeability under the fixed empirical values.',
                      'Apply multiplicity correction across three types before interpreting p-values.',
                      'A null cannot rule out higher-order, cross-request, or later-run dependence.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');p.add_argument('--runs',nargs='+',required=True)
    args=p.parse_args();records=[r for path in args.runs for r in read_jsonl(path)]
    result=report(records);result['run_files']=args.runs
    with open(args.output,'x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result['rows']))

if __name__=='__main__':main()
