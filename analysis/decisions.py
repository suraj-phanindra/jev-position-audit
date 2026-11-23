"""Direct decision-risk diagnostics. Probability-mean equivalence does not bound flips."""
import argparse
import base64
from collections import Counter,defaultdict
import json
import math
from pathlib import Path
import statistics

from harness.audit import digest,encode,read_jsonl,validate_manifest,validate_response

RULES=('argmax','symmetric','one_sided')


def action(p,rule,stimulus_id,other=None):
    if not math.isfinite(p) or not 0<=p<=1:raise ValueError('Invalid probability')
    if rule=='argmax':
        other=1-p if other is None else other
        if not math.isfinite(other) or not 0<=other<=1:raise ValueError('Invalid opposite probability')
        if p==other:return 'x' if int(digest('tie-v1:'+stimulus_id)[:16],16)%2==0 else 'y'
        return 'x' if p>other else 'y'
    if rule=='symmetric':return 'x' if p>=.8 else 'y' if p<=.2 else 'review'
    if rule=='one_sided':return 'act' if p>=.8 else 'no_action'
    raise ValueError('Unknown policy')


def disagreement(a,b):
    if not a or not b:raise ValueError('Empty sample')
    ca,cb=Counter(a),Counter(b)
    return 1-sum(ca[k]*cb[k] for k in ca)/(len(a)*len(b))


def repeat_disagreement(values):
    if len(values)<2:return None
    counts=Counter(values);n=len(values)
    return 1-sum(v*(v-1) for v in counts.values())/(n*(n-1))


def screening_membership(records,manifest):
    """Freeze membership from a complete, separate screening schedule only."""
    validate_manifest(manifest)
    def key(row):return (row['request_sha256'],encode(row['meta']),row['replicate'])
    for row in manifest:
        m=row['meta']
        if (m.get('collection_role')!='screening' or m['probe']!='A' or
                m['kind']!='choice' or m['gap_bin']==0 or row['replicate']!=0):
            raise ValueError('Not a nonidentity Choice screening manifest')
    if sorted(map(key,records))!=sorted(map(key,manifest)):
        raise ValueError('Screening coverage incomplete or duplicated')
    membership={}
    for row in records:
        if row['status']!=200:raise ValueError('Screening contains unsuccessful outcomes')
        if digest(row['request_body'])!=row['request_sha256']:raise ValueError('Request hash mismatch')
        request=json.loads(row['request_body']);data=json.loads(base64.b64decode(row['response_body_b64']))
        validate_response(data,request)
        m=row['meta'];p=float(data['answers']['preference']['probabilities'][m['target']])
        membership[m['stimulus_id']]=membership.get(m['stimulus_id'],False) or .4<=p<=.6
    return membership


def paired_choices(records,screened=None):
    cells=defaultdict(lambda:{0:{},1:{}});contested=defaultdict(bool)
    for row in records:
        m=row['meta']
        if m.get('collection_role')=='screening':raise ValueError('Screening cannot enter outcome contrasts')
        if m.get('extension'):raise ValueError('Pairwise policies do not apply to extension outcomes')
        if m['kind']!='choice':continue
        if row['status']!=200:raise ValueError('Do not silently omit failed outcomes')
        request=json.loads(row['request_body']);data=json.loads(base64.b64decode(row['response_body_b64']))
        validate_response(data,request)
        p=float(data['answers']['preference']['probabilities'][m['target']])
        other=float(data['answers']['preference']['probabilities']['Y' if m['target']=='X' else 'X'])
        if screened is not None:
            if m['gap_bin']!=0 and m['stimulus_id'] not in screened:raise ValueError('Missing screening membership')
            contested[m['stimulus_id']]=screened.get(m['stimulus_id'],False)
        elif m['probe']=='A':contested[m['stimulus_id']] |= .4<=p<=.6
        axes=['state_order','choice_order'] if m['probe']=='A' else ['structured']
        manipulations=[(axis,m[axis]) for axis in axes]
        if m.get('structured')==1 and m.get('format_family') in ('neutral','native'):
            manipulations.append(('format_family',int(m['format_family']=='native')))
        for axis,side in manipulations:
            nuisance={k:v for k,v in m.items() if k!=axis}
            key=(axis,encode(nuisance))
            rep=row['replicate']
            if rep in cells[key][side]:raise ValueError('Duplicate outcome')
            cells[key][side][rep]=(p,other)
    out=[]
    for (axis,encoded),sides in cells.items():
        if set(sides[0])!=set(sides[1]) or not sides[0]:raise ValueError('Unmatched repeats')
        m=json.loads(encoded)
        for rule in RULES:
            a=[action(p,rule,m['stimulus_id'],other) for _,(p,other) in sorted(sides[0].items())]
            b=[action(p,rule,m['stimulus_id'],other) for _,(p,other) in sorted(sides[1].items())]
            cross=disagreement(a,b);sa=repeat_disagreement(a);sb=repeat_disagreement(b)
            same=None if sa is None or sb is None else (sa+sb)/2
            out.append({**m,'axis':axis,'rule':rule,'cross_disagreement':cross,
                        'same_disagreement':same,'excess_disagreement':None if same is None else cross-same,
                        'paired_disagreements':[int(x!=y) for x,y in zip(a,b)],
                        'contested':contested[m['stimulus_id']],
                        'ties':sum(p==other for side in sides.values() for p,other in side.values()),
                        'draws':len(a)+len(b)})
    return out


def summarize(rows):
    cells=defaultdict(lambda:defaultdict(list))
    for row in rows:
        for group in ['identity'] if row['gap_bin']==0 else ['all']+(['contested'] if row['contested'] else []):
            key=(row['probe'],row['axis'],row['source'],row['rule'],group,row.get('formatted_content'),row.get('format_family','legacy'))
            cells[key][row['seed_id']].append(row)
    result=[]
    for key,tasks in sorted(cells.items()):
        rates=[statistics.mean(r['cross_disagreement'] for r in values) for values in tasks.values()]
        entry=dict(zip(('probe','axis','source','rule','population','formatted_content','format_family'),key))
        # This is a conservative sensitivity bound, not a claim that these pilot
        # tasks were independent random samples from a deployment population.
        radius=math.sqrt(math.log(1/.05)/(2*len(rates)))
        mean=statistics.mean(rates)
        entry.update(tasks=len(rates),mean_cross_disagreement=mean,
                     hoeffding_one_sided95_sensitivity=[max(0,mean-radius),min(1,mean+radius)],
                     ties=sum(r['ties'] for values in tasks.values() for r in values),
                     draws=sum(r['draws'] for values in tasks.values() for r in values))
        same=[statistics.mean(r['same_disagreement'] for r in values)
              for values in tasks.values() if all(r['same_disagreement'] is not None for r in values)]
        if len(same)==len(rates):
            entry.update(mean_same_disagreement=statistics.mean(same),
                         mean_excess_disagreement=mean-statistics.mean(same))
        result.append(entry)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output');p.add_argument('--runs',nargs='+',required=True)
    args=p.parse_args();attempts=[r for path in args.runs for r in read_jsonl(path)]
    rows=paired_choices([r for r in attempts if r['status']==200])
    out={'status':'pilot diagnostics; not operational equivalence certification',
         'run_files':args.runs,'failed_attempts_retained':sum(r['status']!=200 for r in attempts),
         'contested_note':'Post-outcome pilot stratum; independent screening is specified for main collection.',
         'policy':'Single returned Jev probability; hash tie breaker fixed across presentation.',
         'noise_note':'Cross-condition risk includes API randomness. Same-condition control needs >=2 repeats.',
         'cells':summarize(rows)}
    with open(args.output,'x') as f:json.dump(out,f,indent=2)
    print(f"Saved {len(out['cells'])} decision-risk diagnostic cells")

if __name__=='__main__':main()
