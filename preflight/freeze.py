"""Build bounded-memory registration materials offline. This does not register or run them."""
import argparse
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import shutil

from harness.audit import encode,generate,read_jsonl,validate_manifest
from harness.extensions import generate_extensions
from stimuli.main_design import select,screening,reference_manifest


def sha(path):
    with open(path,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def compressed(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with open(path,'xb') as f,gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:
        for r in rows:z.write((encode(r)+'\n').encode())


def build(corpus,directory):
    directory=Path(directory)
    if directory.exists():raise ValueError('Refuse existing registration candidate')
    pairs=read_jsonl(corpus);stimuli,reference=select(pairs)
    pilot={r['seed_id'] for r in pairs if r['split']=='pilot'}
    if pilot & {r['seed_id'] for r in stimuli}:raise ValueError('Pilot/main task leakage')
    compressed(directory/'stimuli.jsonl.gz',stimuli)
    compressed(directory/'reference-stimuli.jsonl.gz',reference)
    tasks=defaultdict(list)
    for r in stimuli:tasks[r['seed_id']].append(r)
    schedules=[]
    def save(name,rows,role):
        validate_manifest(rows);path=directory/name;compressed(path,rows)
        schedules.append(dict(path=name,sha256=sha(path),conditions=len(rows),role=role))
    for i,(task,items) in enumerate(sorted(tasks.items())):
        rows=generate(items,'jev-1.13.0',repeats=2,format_controls=True)
        rows+=generate_extensions(items,[p for p in pairs if p['seed_id']==task],repeats=2)
        # Interleave replicates/surfaces within task; execution uses the frozen task order below.
        import random
        random.Random(20260926+i).shuffle(rows)
        save(f'manifests/task-{i:03d}.jsonl.gz',rows,'jev_outcomes')
        if (i+1)%25==0:print(f'Built {i+1}/{len(tasks)} task schedules',flush=True)
    save('manifests/screening.jsonl.gz',screening(stimuli,'jev-1.13.0'),'screening')
    save('manifests/reference.jsonl.gz',reference_manifest(stimuli,reference,pairs),'reference')
    import random
    random.Random(20260927).shuffle(schedules)
    counts=Counter()
    for s in schedules:counts[s['role']]+=s['conditions']
    spec=dict(status='candidate; external registration required',corpus_sha256=sha(corpus),
              tasks=len(tasks),stimuli=len(stimuli),schedules=schedules,counts=dict(counts),
              main_spending_limit_usd=300,reference_samples=20,jev_samples=1,
              models={'typesafe':'jev-1.13.0','anthropic':'claude-haiku-4-5-20251001','together':'deepseek-ai/DeepSeek-V4-Flash-0731'})
    (directory/'DESIGN.json').write_text(json.dumps(spec,indent=2)+'\n')
    print(encode({'counts':dict(counts),'tasks':len(tasks),'stimuli':len(stimuli)}))


def seal(directory):
    directory=Path(directory)
    if (directory/'INDEX.json').exists():raise ValueError('Already sealed; create a new candidate for changes')
    paths=[Path(n) for n in ('PROTOCOL.md','ANALYSIS_PLAN.md','BUDGET.md','REGISTRATION.md','requirements.txt','stimuli/sources.json','stimuli/CORPUS.md','preflight/READINESS.md','analysis/main-power-candidate-v2.json','analysis/gap-power-candidate-v1.json','analysis/g2-temporal-20260921-v2.json')]
    for folder in ('harness','analysis','preflight','stimuli','tests'):paths+=sorted(Path(folder).glob('*.py'))
    paths+=sorted(Path('preflight').glob('*.mjs'))
    for path in paths:
        target=directory/'snapshot'/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    files={str(p.relative_to(directory)):sha(p) for p in sorted(directory.rglob('*')) if p.is_file()}
    (directory/'INDEX.json').write_text(json.dumps({'files':files},indent=2)+'\n')
    print(encode({'index_sha256':sha(directory/'INDEX.json'),'files':len(files)}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['build','seal']);p.add_argument('directory')
    p.add_argument('--corpus',default='stimuli/prepared-v2/pairs.jsonl');a=p.parse_args()
    build(a.corpus,a.directory) if a.operation=='build' else seal(a.directory)
