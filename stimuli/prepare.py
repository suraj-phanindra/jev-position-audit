"""Import pinned human annotations; keep source task clusters and rating scales."""
import csv
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from harness.audit import digest, encode, validate_stimuli, write_jsonl


def split(cluster):
    return 'pilot' if int(digest('split-v1:' + cluster)[:8], 16) % 5 == 0 else 'main'


def gap_bin(gap):
    return 1 if gap <= .10 else 2 if gap <= .30 else 3 if gap <= .60 else 4


def mtbench(rows):
    groups = defaultdict(dict)
    duplicates = 0
    for row in rows:
        if row['turn'] != 1:
            continue  # Second-turn conversations can have different preceding contexts.
        a, b = row['conversation_a'], row['conversation_b']
        if a[0]['role'] != 'user' or b[0] != a[0] or a[1]['role'] != 'assistant' or b[1]['role'] != 'assistant':
            raise ValueError('Unmatched first-turn contexts')
        x, y = sorted((a[1]['content'], b[1]['content']))
        if x == y:
            continue
        winner = row['winner']
        if winner not in ('model_a', 'model_b', 'tie'):
            raise ValueError('Unknown human vote')
        won = None if winner == 'tie' else (a if winner == 'model_a' else b)[1]['content']
        vote = .5 if won is None else float(won == x)
        key = (row['question_id'], a[0]['content'], x, y)
        judge = str(row['judge'])
        if judge in groups[key]:
            if groups[key][judge] != vote:
                raise ValueError('Conflicting repeated human vote')
            duplicates += 1
        groups[key][judge] = vote
    out = []
    for (qid, prompt, x, y), votes in sorted(groups.items()):
        margin = 2 * sum(votes.values()) / len(votes) - 1
        cluster = f'mtbench:{qid}'
        out.append(dict(id='mt-' + digest(encode([qid,x,y]))[:20], seed_id=cluster,
                        source='MTBench', gap_basis='first-turn human preference margin',
                        gap_bin=gap_bin(abs(margin)), signed_gap=margin, prompt=prompt, x=x,y=y,
                        dimension='overall response quality', split=split(cluster),
                        annotation={'votes_x':list(votes.values()),'raters':len(votes),
                                    'judge_ids_sha256':[digest(v) for v in votes]}))
    return out, duplicates


def hanna(rows):
    stories, prompts = defaultdict(list), defaultdict(list)
    for row in rows:
        stories[row['Story ID']].append(row)
    for sid, labels in sorted(stories.items()):
        first = labels[0]
        if len({r['Worker ID'] for r in labels}) != len(labels):
            raise ValueError('Duplicate HANNA story/rater')
        if any((r['Prompt'],r['Story']) != (first['Prompt'],first['Story']) for r in labels):
            raise ValueError('HANNA story identity mismatch')
        ratings = [int(r['Coherence']) for r in labels]
        if any(v not in range(1,6) for v in ratings):
            raise ValueError('Invalid HANNA rating')
        prompts[first['Prompt']].append((sid,first['Story'],ratings))
    out=[]
    for prompt, entries in sorted(prompts.items()):
        cluster='hanna:' + digest(prompt)[:20]
        for a,b in itertools.combinations(entries,2):
            if a[1] == b[1]:
                continue
            margin=(sum(a[2])/len(a[2])-sum(b[2])/len(b[2]))/4
            out.append(dict(id=f'hanna-{a[0]}-{b[0]}-coherence',seed_id=cluster,source='HANNA',
                            gap_basis='difference in mean human coherence rating divided by four',
                            gap_bin=gap_bin(abs(margin)),signed_gap=margin,
                            prompt='Write a coherent story for this prompt: '+prompt,x=a[1],y=b[1],
                            dimension='story coherence',split=split(cluster),
                            annotation={'story_ids':[a[0],b[0]],'ratings_x':a[2],'ratings_y':b[2]}))
    return out


def summeval(rows, articles):
    groups=defaultdict(list)
    for row in rows:
        aid=row['id'].rsplit('-',1)[-1]
        if aid not in articles:raise ValueError('Missing SummEval source article')
        groups[aid].append(row)
    out=[]
    for aid, summaries in sorted(groups.items()):
        if len({r['model_id'] for r in summaries})!=len(summaries):
            raise ValueError('Duplicate SummEval article/model')
        cluster='summeval:'+aid
        for a,b in itertools.combinations(sorted(summaries,key=lambda r:r['model_id']),2):
            if a['decoded']==b['decoded']:continue
            ax=[r['consistency'] for r in a['expert_annotations']]
            by=[r['consistency'] for r in b['expert_annotations']]
            if len(ax)!=3 or len(by)!=3 or any(v not in range(1,6) for v in ax+by):
                raise ValueError('Unexpected SummEval expert ratings')
            margin=(sum(ax)/3-sum(by)/3)/4
            out.append(dict(id=f"summeval-{aid}-{a['model_id']}-{b['model_id']}",
                            seed_id=cluster,source='SummEval',gap_basis='expert consistency mean difference divided by four',
                            gap_bin=gap_bin(abs(margin)),signed_gap=margin,split=split(cluster),
                            prompt='Summarize this article faithfully:\n'+articles[aid]['article'],
                            x=a['decoded'],y=b['decoded'],dimension='factual consistency with the source article',
                            annotation={'ratings_x':ax,'ratings_y':by,'article_id':aid,
                                        'article_sha256':digest(articles[aid]['article'])}))
    return out


def main():
    import argparse
    import pyarrow.parquet as pq
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",default="stimuli/prepared")
    output=Path(parser.parse_args().output)
    if output.exists():raise ValueError("Output already exists; use a new directory")
    for entry in json.loads(Path('stimuli/sources.json').read_text()):
        if hashlib.sha256(Path(entry['file']).read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Source checksum mismatch: '+entry['file'])
    mt, duplicates=mtbench(pq.read_table('stimuli/raw/mtbench.parquet').to_pylist())
    with open('stimuli/raw/hanna.csv',newline='') as f:
        hn=hanna(list(csv.DictReader(f)))
    articles={r['id']:r for r in pq.read_table('stimuli/raw/cnndm_test.parquet').to_pylist()}
    sv=summeval([json.loads(line) for line in Path('stimuli/raw/summeval.jsonl').read_text().splitlines()],articles)
    excluded_empty = sum(not r["x"].strip() or not r["y"].strip() for r in mt+hn+sv)
    mt = [r for r in mt if r["x"].strip() and r["y"].strip()]
    hn = [r for r in hn if r["x"].strip() and r["y"].strip()]
    sv = [r for r in sv if r["x"].strip() and r["y"].strip()]
    rows=mt+hn+sv
    validate_stimuli(rows)
    write_jsonl(output/'pairs.jsonl',rows)
    coverage={"excluded_empty_candidate_pairs": excluded_empty}
    for source in ('MTBench','HANNA','SummEval'):
        subset=[r for r in rows if r['source']==source]
        coverage[source]={'pairs':len(subset),'tasks':len({r['seed_id'] for r in subset}),
                          'bins':dict(Counter(r['gap_bin'] for r in subset)),
                          'pilot_tasks':len({r['seed_id'] for r in subset if r['split']=='pilot'}),
                          'main_tasks':len({r['seed_id'] for r in subset if r['split']=='main'})}
    coverage['MTBench']['deduplicated_votes']=duplicates
    coverage['MTBench']['votes_per_pair']=dict(Counter(r['annotation']['raters'] for r in mt))
    coverage['SummEval'].update(annotations=1600, matched_articles=100)
    # Preflight uses only pilot tasks: one pair per task, selected without judge outputs.
    selected=[]
    for source in ('MTBench','HANNA'):
        by_task=defaultdict(list)
        for row in rows:
            if row['source']==source and row['split']=='pilot':by_task[row['seed_id']].append(row)
        for cluster in sorted(by_task):
            selected.append(min(by_task[cluster],key=lambda r:digest('preflight:'+r['id'])))
    # Remaining shapes are exact-copy variants, not additional independent tasks.
    originals=list(selected)
    for row in originals:
        if len(selected)>=50:break
        selected.append({**row,'id':row['id']+'-identity','y':row['x'],'gap_bin':0,
                         'signed_gap':0,'gap_basis':'exact copy; no human equality claim'})
    if len(selected)<50:raise ValueError('Insufficient preflight shapes')
    selected=selected[:50]
    write_jsonl(output/'preflight50.jsonl',selected)
    coverage['preflight']={'shapes':len(selected),'tasks':len({r['seed_id'] for r in selected}),
                          'note':'50 stimuli, including copies; tasks are not all independent'}
    (output/'coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
    print(json.dumps(coverage,indent=2))

if __name__=='__main__':main()
