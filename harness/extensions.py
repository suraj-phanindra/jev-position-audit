"""Probe A extensions: list rotations and pointwise descriptive rubric reversals."""
import argparse
from collections import Counter, defaultdict
import itertools
import json
import random
import re
import statistics

from harness.audit import digest, encode, read_jsonl, validate_stimuli, write_jsonl
from stimuli.prepare import gap_bin

CARDINALITIES = (2, 3, 5, 10, 25)
GRANULARITIES = (2, 3, 5, 7, 10)
IDENTITY_PREFIX_BYTES = 1200
# Authored ordinal anchors, not new human labels or equally spaced quality units.
ANCHORS = {
    'MTBench': (
        'Does not address the requested task at all.',
        'Mentions the task but supplies no usable part of an answer.',
        'Supplies an isolated relevant fragment; the requested result is absent.',
        'Attempts the central task, but errors prevent using its result.',
        'Completes a useful part of the task; most required work remains missing or incorrect.',
        'Completes most of the task, but a major required component is missing or incorrect.',
        'Completes the central task; a secondary requested component still needs substantial correction.',
        'Completes all requested components; a localized error still needs correction.',
        'Completes the task correctly; only a minor omission or unnecessary material remains.',
        'Completes every requested component correctly without material omissions or irrelevant material.'),
    'HANNA': (
        'No connected sequence of events can be recovered from the story.',
        'Individual events can be identified, but their order and participants cannot be reconciled.',
        'Some events connect, but contradictions prevent reconstructing the central sequence.',
        'The central sequence is recognizable, but major transitions have incompatible causes or outcomes.',
        'The central sequence is consistent, but multiple major transitions lack an intelligible connection.',
        'The central sequence is connected, but one major transition lacks an intelligible explanation.',
        'Major events connect consistently; several secondary transitions or references remain unclear.',
        'Major events and most secondary events connect; one localized transition or reference is unclear.',
        'Events, causes, and references are consistent; a minor transition is abrupt but understandable.',
        'Events, causes, and references form a consistent and clearly connected narrative throughout.'),
    'SummEval': (
        'The summary conveys no source-supported factual content.',
        'Only an isolated detail is supported; the central account contradicts or invents the source.',
        'Some details are supported, but multiple central claims contradict or invent the source.',
        'Most details are supported, but a central claim contradicts the source.',
        'Central claims avoid direct contradiction, but the main account relies on unsupported assertions.',
        'The central account is supported, but multiple secondary claims contradict or invent the source.',
        'The central account is supported, but one secondary claim contradicts the source.',
        'Explicit claims avoid contradiction, but an unsupported secondary assertion remains.',
        'All factual claims are supported, but wording invites a misleading implication about the source.',
        'All factual claims and their implications are supported by the source article.')}
DIMENSIONS = {'MTBench': 'task fulfillment', 'HANNA': 'story coherence',
              'SummEval': 'factual consistency with the source article'}


def rubric(source, size):
    if size not in GRANULARITIES or source not in ANCHORS:
        raise ValueError('Unknown rubric source or granularity')
    groups = [[] for _ in range(size)]
    for i, description in enumerate(ANCHORS[source]):
        groups[i*size//10].append(description)
    return ['One of the following descriptions applies: ' + ' OR '.join(g) for g in groups]


def pools(pairs):
    """Recover distinct annotated candidates; deduplicate identical text explicitly."""
    tasks = {}
    for row in pairs:
        if row['source'] not in ('HANNA', 'SummEval'):
            continue  # Pairwise MTBench votes are not cardinal candidate ratings.
        task = tasks.setdefault(row['seed_id'], {'seed': row, 'candidates': {}})
        if any(row[k] != task['seed'][k] for k in ('prompt', 'source', 'split')):
            raise ValueError('Task metadata conflict')
        ids = row['annotation'].get('story_ids') or row['id'].rsplit('-', 2)[-2:]
        for i, content in enumerate(('x', 'y')):
            candidate = {'source_id': ids[i], 'text': row[content],
                         'ratings': row['annotation']['ratings_'+content]}
            old = task['candidates'].setdefault(ids[i], candidate)
            if old != candidate:
                raise ValueError('Inconsistent candidate annotations across pairs')
    for task in tasks.values():
        unique = {}
        for c in sorted(task['candidates'].values(), key=lambda c: digest('list-dedup-v1:'+c['source_id'])):
            unique.setdefault(c['text'], c)
        task['duplicate_texts_removed'] = len(task['candidates'])-len(unique)
        task['candidates'] = sorted(unique.values(), key=lambda c: digest('list-pool-v1:'+c['source_id']))
    return tasks


def append(rows, meta, request, repeats):
    body = encode(request)
    for replicate in range(repeats):
        rows.append({'meta': meta, 'replicate': replicate, 'request_body': body,
                     'request_sha256': digest(body)})


def generate_extensions(stimuli, pairs, model='jev-1.13.0', repeats=1):
    validate_stimuli(stimuli)
    if repeats<1 or not re.fullmatch(r'jev-\d+\.\d+\.\d+', model):
        raise ValueError('Invalid repeats or unpinned model')
    rows = []
    for item, size, content, labels, state_order, direction in itertools.product(
            stimuli, GRANULARITIES, ('x','y'), (0,1), (0,1), (0,1)):
        ids = {'x':'Y' if labels else 'X', 'y':'X' if labels else 'Y'}
        levels = rubric(item['source'],size)
        state = {'task':item['prompt'], 'candidates':[{'id':ids[c],'text':item[c]} for c in ('x','y')]}
        if state_order: state['candidates'].reverse()
        q = {'type':'score','instructions':f"Rate candidate {ids[content]} on {DIMENSIONS[item['source']]} "
             'against the task, independently of the other candidate. Select the closest descriptive level.',
             'criteria':levels[::-1] if direction else levels}
        meta = {k:item[k] for k in ('seed_id','source','gap_bin','gap_basis')}
        meta.update(probe='A',extension='rubric',kind='score',stimulus_id=item['id'],
                    stimulus_sha256=digest(encode(item)),granularity=size,graded_content=content,
                    labels_swapped=labels,target=ids[content],state_order=state_order,
                    rubric_order=direction,canonical_levels=levels)
        append(rows,meta,{'state':state,'model':model,'questions':{'preference':q}},repeats)
    # One content copy and one nested annotated candidate pool per selected task.
    seeds = {}
    for item in sorted(stimuli,key=lambda r:digest('list-seed-v1:'+r['id'])):
        seeds.setdefault(item['seed_id'],item)
    annotated = pools([r for r in pairs if r['seed_id'] in seeds])
    for task, item in sorted(seeds.items()):
        identity_text=item['x'].encode('utf-8')[:IDENTITY_PREFIX_BYTES].decode('utf-8',errors='ignore')
        for size in CARDINALITIES:
            variants = [('identity',[{'text':identity_text} for _ in range(size)],0,0)]
            pool = annotated.get(task,{}).get('candidates',[])
            if len(pool)>=size:
                selected = pool[:size]
                means = sorted((statistics.mean(c['ratings']) for c in selected),reverse=True)
                gap = (means[0]-means[1])/4
                variants.append(('annotated',selected,gap_bin(gap),gap))
            for variant, candidates, bin_id, gap in variants:
                stable = [{'id':f'C{i:02d}','text':c['text']} for i,c in enumerate(candidates)]
                for rotation, key_order in itertools.product(range(size),(0,1)):
                    criteria = {c['id']:f"Prefer candidate {c['id']}." for c in stable}
                    if key_order: criteria = dict(reversed(list(criteria.items())))
                    q = {'type':'choice','instructions':f"Evaluate candidates against the task on {item.get('dimension','overall response quality')}. "
                         'Select the best candidate. Assign equal preference probability among equally good candidates.',
                         'criteria':criteria}
                    meta = dict(probe='A',extension='listwise',kind='choice',seed_id=task,source=item['source'],
                                stimulus_id=task+'-list-'+variant+'-'+str(size),cardinality=size,
                                gap_bin=bin_id,gap_basis='exact copies' if variant=='identity' else 'top two mean human ratings divided by four',
                                list_gap=gap,variant=variant,rotation=rotation,choice_order=key_order,
                                target='C00',candidate_sha256=digest(encode(candidates)),
                                candidates=candidates,duplicate_texts_removed=annotated.get(task,{}).get('duplicate_texts_removed',0))
                    if variant=='identity':
                        meta.update(copy_source_sha256=digest(item['x']),copy_seed_pair_id=item['id'],
                                    copy_prefix_utf8_limit=IDENTITY_PREFIX_BYTES,copy_truncated=identity_text!=item['x'])
                    state = {'task':item['prompt'],'candidates':stable[rotation:]+stable[:rotation]}
                    append(rows,meta,{'state':state,'model':model,'questions':{'preference':q}},repeats)
    random.Random(20260924).shuffle(rows)
    validate_extensions(rows)
    return rows


def validate_extensions(rows):
    groups = {}; cells = defaultdict(Counter)
    for row in rows:
        m = row['meta'];body = row['request_body'];request = json.loads(body)
        if digest(body)!=row['request_sha256'] or encode(request)!=body:
            raise ValueError('Extension request bytes/hash mismatch')
        if not re.fullmatch(r'jev-\d+\.\d+\.\d+',request['model']):
            raise ValueError('Unpinned extension model')
        if m['extension']=='listwise':
            size=m['cardinality'];rotation=m['rotation'];order=m['choice_order']
            if size not in CARDINALITIES or rotation not in range(size) or order not in (0,1):
                raise ValueError('Invalid listwise treatment')
            stable=[{'id':f'C{i:02d}','text':c['text']} for i,c in enumerate(m['candidates'])]
            if len(stable)!=size or digest(encode(m['candidates']))!=m['candidate_sha256']:
                raise ValueError('Listwise candidate identity mismatch')
            if m['variant']=='identity':
                if len({c['text'] for c in stable})!=1 or m['gap_bin']!=0:
                    raise ValueError('Identity list must contain exact copies')
            elif m['variant']=='annotated':
                if len({c['text'] for c in stable})!=size:raise ValueError('Annotated list must contain distinct texts')
                means=sorted((statistics.mean(c['ratings']) for c in m['candidates']),reverse=True)
                if m['list_gap']!=(means[0]-means[1])/4 or m['gap_bin']!=gap_bin(m['list_gap']):
                    raise ValueError('Listwise annotation gap mismatch')
            else:raise ValueError('Unknown list variant')
            expected=stable[rotation:]+stable[:rotation]
            if request['state']['candidates']!=expected:
                raise ValueError('Listwise rotation changed content or identity')
            request['state']['candidates']=stable
            q=request['questions']['preference']
            criteria={c['id']:f"Prefer candidate {c['id']}." for c in stable}
            if q['type']!='choice' or q['criteria']!=(dict(reversed(list(criteria.items()))) if order else criteria):
                raise ValueError('Listwise criteria mismatch')
            if list(q['criteria'])!=list(criteria)[::(-1 if order else 1)]:
                raise ValueError('Listwise criteria order mismatch')
            q['criteria']=criteria
            key=(m['extension'],m['stimulus_id'],row['replicate'])
            cell=(rotation,order);expected_cells=set(itertools.product(range(size),(0,1)))
        elif m['extension']=='rubric':
            levels=rubric(m['source'],m['granularity'])
            if m['canonical_levels']!=levels:raise ValueError('Rubric anchors changed')
            q=request['questions']['preference']
            if q['type']!='score' or q['criteria']!=(levels[::-1] if m['rubric_order'] else levels):
                raise ValueError('Rubric reversal changed semantics')
            q['criteria']=levels
            if m['state_order']: request['state']['candidates'].reverse()
            key=(m['extension'],m['stimulus_id'],m['granularity'],m['graded_content'],m['labels_swapped'],row['replicate'])
            cell=(m['state_order'],m['rubric_order']);expected_cells=set(itertools.product((0,1),repeat=2))
        else:raise ValueError('Unknown extension')
        canonical=encode(request)
        if key in groups and groups[key][0]!=canonical:
            raise ValueError('G5 extension incidental difference')
        groups[key]=(canonical,expected_cells);cells[key][cell]+=1
    for key,observed in cells.items():
        if set(observed)!=groups[key][1] or any(n!=1 for n in observed.values()):
            raise ValueError('Incomplete or duplicated extension factorial')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stimuli');p.add_argument('pairs');p.add_argument('output')
    p.add_argument('--repeats',type=int,default=1)
    args=p.parse_args()
    rows=generate_extensions(read_jsonl(args.stimuli),read_jsonl(args.pairs),repeats=args.repeats)
    write_jsonl(args.output,rows)
    print(encode({'calls':len(rows),'by_extension':dict(Counter(r['meta']['extension'] for r in rows))}))

if __name__=='__main__':main()
