import base64
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness.audit import encode, read_jsonl, generate, question
from analysis.pilot import paired
from analysis.reference import report as reference_report
from preflight.repeats import run,schedule,manifest_schedule,resume
from stimuli.prepare import mtbench,hanna,split,summeval

class CorpusChecks(unittest.TestCase):
    def test_orientation_deduplication_and_rating_scale(self):
        a=[{'role':'user','content':'task'},{'role':'assistant','content':'aaa'}]
        b=[{'role':'user','content':'task'},{'role':'assistant','content':'bbb'}]
        r=dict(question_id=1,turn=1,conversation_a=a,conversation_b=b,winner='model_a',judge='one')
        reversed_row={**r,'conversation_a':b,'conversation_b':a,'winner':'model_b','judge':'two'}
        rows,dups=mtbench([r,r,reversed_row])
        self.assertEqual((len(rows),dups,rows[0]['signed_gap'],rows[0]['annotation']['raters']),(1,1,1,2))
        self.assertEqual(rows[0]['split'],split(rows[0]['seed_id']))
        hn=hanna([{'Story ID':s,'Worker ID':str(i),'Prompt':'p','Story':s,'Coherence':v}
                  for s,v in [('a','5'),('b','1')] for i in range(3)])
        self.assertEqual(hn[0]['signed_gap'],1)
        self.assertEqual(hn[0]['dimension'],'story coherence')

    def test_article_join_and_reference_manifest(self):
        article={'id':'abc','article':'Original evidence.'}
        rows=[dict(id='dm-test-abc',model_id=model,decoded=text,
                   expert_annotations=[{'consistency':score}]*3)
              for model,text,score in [('M1','faithful',5),('M2','invented',1)]]
        pairs=summeval(rows,{'abc':article})
        self.assertIn(article['article'],pairs[0]['prompt'])
        self.assertEqual(pairs[0]['signed_gap'],1)
        with self.assertRaises(ValueError):summeval(rows,{})
        manifest=generate(read_jsonl('stimuli/example.jsonl'),'jev-1.13.0')
        references=manifest_schedule(manifest,'anthropic',20)
        self.assertEqual(len(references),len(manifest)*20)
        self.assertEqual(len({r['jev_request_sha256'] for r in references}),len({r['request_sha256'] for r in manifest}))
        for r in references[:5]:
            source=next(x for x in manifest if x['request_sha256']==r['jev_request_sha256'])
            original=json.loads(source['request_body'])
            mirrored=json.loads(json.loads(r['request_body'])['messages'][-1]['content'])
            self.assertEqual(mirrored, {k:original[k] for k in ('state','questions')})

    def test_reference_frequency_retains_invalid_draws(self):
        manifest=[r for r in generate(read_jsonl('stimuli/example.jsonl')[:1],'jev-1.13.0') if r['meta']['kind']=='choice']
        scheduled=manifest_schedule(manifest,'anthropic',2)
        records=[]
        for r in scheduled:
            content='bad JSON' if r['sample']==1 else encode({'preference':r['meta']['target']})
            data={'model':'claude-haiku-4-5-20251001','stop_reason':'end_turn',
                  'content':[{'type':'text','text':content}]}
            records.append({**r,'status':200,'response_body_b64':base64.b64encode(encode(data).encode()).decode()})
        result=reference_report(records,manifest,'anthropic',2)
        self.assertEqual(result['conditions'],24)
        self.assertTrue(all(c['counts']['INVALID']==1 and 'target_frequency' not in c for c in result['cells']))
        with self.assertRaises(ValueError):reference_report(records[:-1],manifest,'anthropic',2)

    def test_reference_all_types_and_reversed_score_semantics(self):
        manifest=generate(read_jsonl('stimuli/example.jsonl')[:1],'jev-1.13.0')
        records=[]
        for r in manifest_schedule(manifest,'anthropic',2,canonical_schema=True):
            request=json.loads(r['request_body']);q=json.loads(request['messages'][-1]['content'])['questions']
            verdicts={}
            for name,question in q.items():
                target=r['meta']['target'];other='Y' if target=='X' else 'X'
                verdicts[name]=('true' if question['type']=='noul' else target if question['type']=='choice'
                                else str(question['criteria'].index(f'{target} is better than {other}.')))
            data={'model':'claude-haiku-4-5-20251001','stop_reason':'end_turn',
                  'content':[{'type':'text','text':encode(verdicts)}]}
            records.append({**r,'status':200,'response_body_b64':base64.b64encode(encode(data).encode()).decode()})
        result=reference_report(records,manifest,'anthropic',2,canonical_schema=True)
        self.assertEqual((result['conditions'],result['question_cells']),(76,100))
        self.assertTrue(all(c.get('target_frequency',c.get('expected_semantic_score'))==1 for c in result['cells']))
        with self.assertRaises(ValueError):reference_report(records,manifest,'anthropic',2)

    def test_paired_axes_do_not_mix_nuisance_conditions(self):
        rows=[]
        for state in (0,1):
            for keys in (0,1):
                q=question('choice','X','Y')
                if keys:q['criteria']=dict(reversed(list(q['criteria'].items())))
                p=.6+state*.1+keys*.02
                response={'model':'jev-1.13.0','answers':{'preference':{
                    'type':'choice','choice':'X','probabilities':{'X':p,'Y':1-p},'confidence':.5}}}
                rows.append({'status':200,'request_body':encode({'model':'jev-1.13.0','questions':{'preference':q}}),
                             'response_body_b64':base64.b64encode(encode(response).encode()).decode(),
                             'replicate':0,'meta':{'probe':'A','kind':'choice','target':'X',
                             'state_order':state,'choice_order':keys}})
        contrasts=paired(rows)
        self.assertEqual(len(contrasts),4)
        for c in contrasts:self.assertAlmostEqual(c['delta'],-.1 if c['axis']=='state_order' else -.02)
        with self.assertRaises(ValueError):paired(rows[:-1])

    def test_sampling_and_fail_fast_raw_retention(self):
        stimuli=read_jsonl('stimuli/example.jsonl')
        rows=schedule(stimuli,'together',20)
        self.assertEqual(len(rows),40)
        self.assertTrue(all('seed' not in json.loads(r['request_body']) for r in rows))
        self.assertEqual(len({r['request_sha256'] for r in rows}),2)
        prior=[{**rows[0],'status':200},{**rows[1],'status':None}]
        remaining=resume(rows,prior,retry_failed=True)
        self.assertEqual(len(remaining),39)
        self.assertEqual(sum(r['replaces_failed_attempt'] for r in remaining),1)
        self.assertEqual(len(resume(rows,prior)),38)
        def failed(row,key):return {**row,'status':429,'response_body_b64':base64.b64encode(b'limited').decode()}
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,TOGETHER_API_KEY='not-real'),patch('preflight.repeats.fetch',side_effect=failed) as fetch:
            output=Path(directory)/'run.jsonl'
            with self.assertRaises(RuntimeError):run(rows,output,40,100,1)
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(len(read_jsonl(output)),1)
            self.assertNotIn('not-real',output.read_text())
