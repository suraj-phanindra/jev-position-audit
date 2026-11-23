"""Exact-condition reference comparisons; task bootstrap includes both arms together."""
import argparse
from collections import Counter,defaultdict
import json
import statistics

from analysis.pilot import paired,paired_values,summarize
from analysis.reference import report
from harness.audit import encode,read_jsonl,validate_manifest


def compare(jev,reference,manifest,provider,samples=20,draws=9999):
    validate_manifest(manifest)
    result=report(reference,manifest,provider,samples,canonical_schema=True)
    selected={encode([r['request_sha256'],r['meta']]) for r in manifest if not r['meta'].get('extension')}
    matched=[r for r in jev if encode([r['request_sha256'],r['meta']]) in selected and r['status']==200]
    expected=Counter((k,rep) for k in selected for rep in (0,1))
    actual=Counter((encode([r['request_sha256'],r['meta']]),r['replicate']) for r in matched)
    if actual!=expected:raise ValueError('Matched Jev subset must contain exactly two outcome replicates')
    refs=[]
    for cell in result['cells']:
        if cell['meta'].get('extension'):continue
        if cell['counts'].get('INVALID',0):
            return {'status':'invalid reference draws prevent complete scalar comparison','reference_report':result}
        value=cell.get('target_frequency',cell.get('expected_semantic_score'))
        if value is None:raise ValueError('Missing scalar reference outcome')
        refs.append({**cell,'value':value})
    def collapse(rows):
        groups=defaultdict(list)
        for r in rows:
            meta={k:v for k,v in r.items() if k not in ('delta','replicate')}
            groups[encode(meta)].append(r['delta'])
        return {k:statistics.mean(v) for k,v in groups.items()}
    a=collapse(paired(matched));b=collapse(paired_values(refs))
    if set(a)!=set(b):raise ValueError('Reference and Jev nuisance conditions differ')
    differences=[{**json.loads(k),'delta':a[k]-b[k]} for k in sorted(a)]
    def summary(rows):
        cells=summarize(rows,draws)
        for cell in cells:cell.pop('illustrative_tasks_for_mde_001',None)
        return cells
    return {'status':'matched descriptive comparison; no family-wide LLM claim',
            'provider':provider,'direction':'Jev contrast minus reference contrast',
            'cells':summary(differences),'jev_cells':summary(paired(matched)),
            'reference_cells':summary(paired_values(refs)),
            'reference_report':result,
            'uncertainty':'Whole-task bootstrap of paired arm differences; N=20 sampling noise is included in observed task variation. Sparse one-task cells have no interval. No ratio when reference effects approach zero.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest');p.add_argument('output')
    p.add_argument('--jev-runs',nargs='+',required=True);p.add_argument('--reference-runs',nargs='+',required=True)
    p.add_argument('--provider',choices=['anthropic','together'],required=True);args=p.parse_args()
    result=compare([r for path in args.jev_runs for r in read_jsonl(path)],
                   [r for path in args.reference_runs for r in read_jsonl(path)],read_jsonl(args.manifest),args.provider)
    with open(args.output,'x') as f:json.dump(result,f,indent=2)

if __name__=='__main__':main()
