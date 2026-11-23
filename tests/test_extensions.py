import base64
import copy
import json
import unittest
from decimal import Decimal

from harness.audit import digest,encode,target_value,validate_manifest,validate_response
from harness.extensions import generate_extensions,rubric,IDENTITY_PREFIX_BYTES
from preflight.repeats import manifest_schedule
from analysis.reference import report
from analysis.extensions import observations,summarize

class ExtensionChecks(unittest.TestCase):
    def test_identity_prefix_is_utf8_safe_and_constant_across_cardinalities(self):
        item=self.fixture();item['x']='\U0001f642'*700
        rows=generate_extensions([item],[item]);texts=set()
        for row in rows:
            m=row['meta']
            if m['extension']=='listwise' and m['variant']=='identity':
                texts.update(c['text'] for c in m['candidates'])
                self.assertTrue(m['copy_truncated'])
                self.assertEqual(m['copy_source_sha256'],digest(item['x']))
        self.assertEqual(len(texts),1)
        text=texts.pop()
        self.assertLessEqual(len(text.encode('utf-8')),IDENTITY_PREFIX_BYTES)
        self.assertTrue(item['x'].startswith(text))

    def fixture(self):
        return dict(id='one',seed_id='task',source='HANNA',gap_bin=1,gap_basis='fixture',
                    prompt='Tell a story',x='One event followed another.',y='Another story.',split='pilot',
                    annotation={'story_ids':['a','b'],'ratings_x':[4,4,4],'ratings_y':[3,3,3]})

    def test_rotations_semantics_and_g5(self):
        item=self.fixture();rows=generate_extensions([item],[item])
        self.assertEqual(len(rows),174)  # 80 rubric, 90 identical-list, four two-story list.
        validate_manifest(rows)
        self.assertEqual(rows,generate_extensions([item],[item]))
        for size in (2,3,5,7,10):self.assertEqual(len(rubric('HANNA',size)),size)
        for extension in ('rubric','listwise'):
            corrupt=copy.deepcopy(rows)
            r=next(r for r in corrupt if r['meta']['extension']==extension)
            request=json.loads(r['request_body']);request['state']['task']+=' '
            r['request_body']=encode(request);r['request_sha256']=digest(r['request_body'])
            with self.assertRaisesRegex(ValueError,'incidental'):validate_manifest(corrupt)
        with self.assertRaises(ValueError):validate_manifest(rows[:-1])
        with self.assertRaises(ValueError):validate_manifest(rows+[rows[0]])
        for r in rows:
            request=json.loads(r['request_body']);q=request['questions']['preference']
            if r['meta']['extension']=='rubric':
                levels=r['meta']['canonical_levels'];i=q['criteria'].index(levels[-1])
                a=dict(type='score',score=i,confidence=1,legend={str(j):l for j,l in enumerate(q['criteria'])},
                       probabilities={str(j):int(j==i) for j in range(len(levels))})
                self.assertEqual(target_value(a,q,r['meta']['target'],levels),Decimal(1))
            else:
                a=dict(type='choice',choice='C00',confidence=1,
                       probabilities={key:int(key=='C00') for key in q['criteria']})
            validate_response({'model':'jev-1.13.0','answers':{'preference':a}},request)

    def test_reference_supports_extensions(self):
        item=self.fixture();manifest=generate_extensions([item],[item]);records=[]
        for row in manifest_schedule(manifest,'anthropic',2,canonical_schema=True):
            request=json.loads(row['request_body']);q=json.loads(request['messages'][-1]['content'])['questions']['preference']
            verdict='C00' if q['type']=='choice' else str(q['criteria'].index(row['meta']['canonical_levels'][-1]))
            data={'model':'claude-haiku-4-5-20251001','stop_reason':'end_turn',
                  'content':[{'type':'text','text':encode({'preference':verdict})}]}
            records.append({**row,'status':200,'response_body_b64':base64.b64encode(encode(data).encode()).decode()})
        result=report(records,manifest,'anthropic',2,canonical_schema=True)
        self.assertTrue(all(c.get('expected_semantic_score',c.get('target_frequency'))==1 for c in result['cells']))

    def test_planted_effects_survive_identity_and_semantic_mapping(self):
        item=self.fixture();manifest=generate_extensions([item],[item]);records=[]
        for row in manifest:
            request=json.loads(row['request_body']);q=request['questions']['preference']
            if q['type']=='choice':
                first=request['state']['candidates'][0]['id'];k=len(q['criteria'])
                answer=dict(type='choice',choice=first,confidence=.8,
                            probabilities={key:.6 if key==first else .4/(k-1) for key in q['criteria']})
            else:
                # Always raw score zero; semantic effect is -1 under reversal.
                answer=dict(type='score',score=0,confidence=1,
                            legend={str(i):level for i,level in enumerate(q['criteria'])},
                            probabilities={str(i):int(i==0) for i in range(len(q['criteria']))})
            data={'model':'jev-1.13.0','answers':{'preference':answer}}
            records.append({**row,'status':200,'response_body_b64':base64.b64encode(encode(data).encode()).decode()})
        result=summarize(observations(records,manifest))
        for row in result['listwise']:
            self.assertAlmostEqual(row['primacy_minus_recency'],.6-.4/(row['cardinality']-1))
            self.assertTrue(all(abs(d)<1e-12 for d in row['forward_minus_reverse_key_probability_by_stable_id']))
        for row in result['rubric_contrasts']:
            self.assertEqual(row['delta'],-1 if row['axis']=='rubric_order' else 0)
        with self.assertRaises(ValueError):observations(records[:-1],manifest)

if __name__=='__main__':unittest.main()
