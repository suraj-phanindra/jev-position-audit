"""Conditional finite-audit risk bounds; independent call pairs, fixed screening weights."""
from collections import defaultdict
import math


def upper_bound(outcomes,weights,alpha=.05):
    if not outcomes or len(outcomes)!=len(weights) or not 0<alpha<1:
        raise ValueError('Invalid risk observations or error rate')
    if any(y not in (0,1) for y in outcomes) or any(not math.isfinite(w) or w<=0 for w in weights):
        raise ValueError('Require Bernoulli outcomes and positive finite weights')
    if not math.isclose(sum(weights),1,rel_tol=0,abs_tol=1e-10):raise ValueError('Weights must sum to one')
    observed=sum(y*w for y,w in zip(outcomes,weights));c=max(weights)*math.log(1/alpha)
    if observed==0:return min(1,c)
    def divergence(mu):return mu-observed+observed*math.log(observed/mu)
    if divergence(1)<=c:return 1.
    low,high=observed,1.
    for _ in range(80):
        mid=(low+high)/2
        if divergence(mid)<c:low=mid
        else:high=mid
    return high


def audit_bounds(contrasts):
    groups=defaultdict(list)
    for r in contrasts:
        if r['gap_bin']==0:continue # Copy selections are not quality decisions.
        key=(r['probe'],r['axis'],r.get('format_family','legacy'),r['rule'])
        groups[key].append(r)
    prepared=[]
    for key,rows in sorted(groups.items()):
        source_tasks=defaultdict(set);task_items=defaultdict(set);item_cells=defaultdict(int)
        for r in rows:
            source_tasks[r['source']].add(r['seed_id']);task_items[r['seed_id']].add(r['stimulus_id'])
            item_cells[r['stimulus_id']]+=1
        if set(source_tasks)!={'MTBench','HANNA','SummEval'}:
            raise ValueError('All three sources required for equal-source audit weighting')
        for population in ('all','contested'):
            values=[];weights=[];task_ids=set()
            for r in rows:
                if population=='contested' and not r['contested']:continue
                ys=r['paired_disagreements']
                if len(ys)!=2:raise ValueError('Risk certification requires two paired replicates')
                w=1/(3*len(source_tasks[r['source']])*len(task_items[r['seed_id']])*item_cells[r['stimulus_id']]*len(ys))
                values.extend(ys);weights.extend([w]*len(ys));task_ids.add(r['seed_id'])
            entry=dict(zip(('probe','axis','format_family','rule'),key))
            entry.update(population=population,budget=.01 if population=='all' else .05,tasks=len(task_ids))
            if not weights:
                entry.update(status='empty screened subgroup; no equivalence claim')
                prepared.append((entry,None,None));continue
            mass=sum(weights);weights=[w/mass for w in weights]
            entry.update(screened_audit_mass=mass,independent_pairs=len(values),
                         effective_pairs=1/sum(w*w for w in weights),maximum_weight=max(weights),
                         observed_disagreement=sum(y*w for y,w in zip(values,weights)))
            prepared.append((entry,values,weights))
    # Simultaneous two-sided coverage across all reported policy/presentation cells.
    alpha=.05/(2*max(1,sum(v is not None for _,v,_ in prepared)))
    output=[]
    for entry,values,weights in prepared:
        if values is not None:
            lower=1-upper_bound([1-y for y in values],weights,alpha)
            upper=upper_bound(values,weights,alpha)
            entry.update(status='conditional on independent call pairs and fixed audit/screening',
                         lower=lower,upper=upper,per_tail_alpha=alpha,
                         below_budget=upper<entry['budget'],above_budget=lower>entry['budget'])
        output.append(entry)
    return output
