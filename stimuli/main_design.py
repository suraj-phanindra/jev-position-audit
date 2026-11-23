"""Deterministic held-out task allocation; builds no live requests and sends nothing."""
import argparse
from collections import Counter,defaultdict
import json
import random
from pathlib import Path

from harness.audit import digest,encode,generate,read_jsonl,validate_manifest,validate_stimuli,write_jsonl


def screening(stimuli,model):
    rows=[]
    for item in stimuli:
        if item['gap_bin']==0:continue
        for row in generate([item],model):
            if row['meta']['probe']=='A' and row['meta']['kind']=='choice':
                rows.append({**row,'meta':{**row['meta'],'collection_role':'screening'}})
    random.Random(20260923).shuffle(rows)
    validate_manifest(rows)
    return rows


def select(rows):
    tasks=defaultdict(list)
    for item in rows:
        if item['split']=='main':tasks[item['seed_id']].append(item)
    selected=[]
    for task,items in sorted(tasks.items()):
        for gap in range(1,5):
            available=[r for r in items if r['gap_bin']==gap]
            if available:selected.append(min(available,key=lambda r:digest('main-pair-v1:'+r['id'])))
        seed=min(items,key=lambda r:digest('main-identity-v1:'+r['id']))
        selected.append({**seed,'id':seed['id']+'-identity','y':seed['x'],'gap_bin':0,
                         'signed_gap':0,'gap_basis':'exact copy; no inferred human equality'})
    validate_stimuli(selected)
    # Fixed sample of tasks per corpus, chosen without main model outcomes.
    reference=[]
    for source,count in [('MTBench',12),('HANNA',14),('SummEval',14)]:
        clusters=sorted({r['seed_id'] for r in selected if r['source']==source},
                        key=lambda t:digest('main-reference-task-v1:'+t))[:count]
        for i,task in enumerate(clusters):
            pairs=[r for r in selected if r['seed_id']==task]
            reference.append(next(r for r in pairs if r['gap_bin']==0))
            desired=1+i%4
            reference.append(min([r for r in pairs if r['gap_bin']>0],
                                 key=lambda r:(abs(r['gap_bin']-desired),digest('main-reference-pair-v1:'+r['id']))))
    return selected,reference


def reference_manifest(main,reference,pairs):
    """Fixed ~4,000-condition reference budget; whole contrast groups only."""
    from harness.extensions import generate_extensions
    nuisance={};anchors=[]
    for source in ('MTBench','HANNA','SummEval'):
        tasks=sorted({r['seed_id'] for r in reference if r['source']==source},
                     key=lambda t:digest('reference-nuisance-v1:'+t))
        for i,task in enumerate(tasks):nuisance[task]=(i%2,'x' if (i//2)%2==0 else 'y')
        options=[r for r in reference if r['source']==source and r['gap_bin']>0]
        anchors.append(min(options,key=lambda r:digest('reference-extension-v1:'+r['id'])))
    output=[]
    for row in generate(reference,'jev-1.13.0',format_controls=True):
        m=row['meta'];labels,content=nuisance[m['seed_id']]
        if m['probe']=='A' or (m['gap_bin']>0 and m['labels_swapped']==labels and m['formatted_content']==content):
            output.append(row)
    anchor_ids={r['id'] for r in anchors};anchor_tasks={r['seed_id'] for r in anchors}
    # Use all selected main pairs within each task so list-copy seed selection is
    # identical to the full Jev design, not accidentally a different comparison.
    for row in generate_extensions([r for r in main if r['seed_id'] in anchor_tasks],pairs):
        m=row['meta'];labels,content=nuisance[m['seed_id']]
        if m['extension']=='listwise' or (m['stimulus_id'] in anchor_ids and
                m['labels_swapped']==labels and m['graded_content']==content):
            output.append(row)
    output.sort(key=lambda r:encode(r['meta']))
    random.Random(20260925).shuffle(output)
    validate_manifest(output)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('corpus');p.add_argument('output')
    p.add_argument('--screening-manifest',action='store_true')
    args=p.parse_args();directory=Path(args.output)
    if directory.exists():raise ValueError('Refuse existing allocation directory')
    rows=read_jsonl(args.corpus);selected,reference=select(rows)
    pilot_tasks={r['seed_id'] for r in rows if r['split']=='pilot'}
    assert not pilot_tasks & {r['seed_id'] for r in selected}
    write_jsonl(directory/'stimuli.jsonl',selected);write_jsonl(directory/'reference-stimuli.jsonl',reference)
    if args.screening_manifest:
        write_jsonl(directory/'screening.jsonl',screening(selected,'jev-1.13.0'))
    summary={}
    for source in ('MTBench','HANNA','SummEval'):
        subset=[r for r in selected if r['source']==source]
        ref=[r for r in reference if r['source']==source]
        summary[source]={'tasks':len({r['seed_id'] for r in subset}),'stimuli':len(subset),
                         'by_gap':dict(Counter(r['gap_bin'] for r in subset)),
                         'reference_tasks':len({r['seed_id'] for r in ref}),
                         'reference_by_gap':dict(Counter(r['gap_bin'] for r in ref))}
    summary['core_calls']={'jev':len(selected)*76*2,
                           'independent_jev_screening':sum(r['gap_bin']>0 for r in selected)*8,
                           'per_reference_judge':len(reference)*76*20}
    summary['status']='allocation candidate; no main collection; extensions not yet included in these counts'
    summary['hashes']={name:digest((directory/name).read_text()) for name in ('stimuli.jsonl','reference-stimuli.jsonl')}
    (directory/'allocation.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
