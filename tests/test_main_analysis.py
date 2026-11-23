import base64
import json
import math
import unittest
from unittest.mock import patch
from analysis.matched import compare
from harness.audit import target_value
from analysis.main import analyze,holm
from harness.audit import generate,encode

class MainAnalysisChecks(unittest.TestCase):
    def test_holm_is_monotone_and_family_specific(self):
        r=holm([{'family':'A','p':.03},{'family':'A','p':.01},{'family':'C','p':.03}])
        self.assertEqual([x['holm_p'] for x in r],[.03,.02,.03])

    def test_complete_pipeline_recovers_planted_effects_and_rejects_missing_data(self):
        stimuli=[]
        for source in ('MTBench','HANNA','SummEval'):
            for task in range(2):
                for gap in (0,.2,.8):
                    stimuli.append(dict(id=f'{source}-{task}-{gap}',seed_id=f'{source}-{task}',source=source,
                                         gap_bin=0 if gap==0 else 2 if gap==.2 else 4,signed_gap=gap,gap_basis='fixture',
                                         prompt='task',x='one',y='one' if gap==0 else 'two'))
        manifest=generate(stimuli,'jev-1.13.0',repeats=2,format_controls=True);records=[]
        gaps={s['id']:s['signed_gap'] for s in stimuli}
        for row in manifest:
            request=json.loads(row['request_body']);m=row['meta'];g=gaps[m['stimulus_id']]
            d=.2*(1-g)*(1 if m['state_order']==0 else -1)
            if m['probe']=='C-iii':
                d=.1*(1 if m['formatted_content']=='x' else -1) if m.get('format_family')=='native' and m['structured'] else 0
            if m['kind']=='questions':d+=.1 if m['question_order']==0 else -.1
            p=.5+d;answers={};target=m['target'];other='Y' if target=='X' else 'X'
            for name,q in request['questions'].items():
                if q['type']=='noul':a={'type':'noul','noul':p}
                elif q['type']=='choice':a={'type':'choice','choice':target if p>=.5 else other,'confidence':.8,'probabilities':{target:p,other:1-p}}
                else:
                    canonical=[f'{other} is better than {target}.','The candidates are equally good.',f'{target} is better than {other}.']
                    masses=[.3-d/2,.4,.3+d/2]
                    probs={str(i):masses[canonical.index(v)] for i,v in enumerate(q['criteria'])}
                    a={'type':'score','probabilities':probs,'confidence':.8,'score':sum(int(i)*v for i,v in probs.items()),
                       'legend':{str(i):v for i,v in enumerate(q['criteria'])}}
                answers[name]=a
            response={'model':'jev-1.13.0','answers':answers}
            records.append({**row,'status':200,'response_body_b64':base64.b64encode(encode(response).encode()).decode()})
        cells=[]
        for r in records:
            if r['replicate']:continue
            request=json.loads(r['request_body']);response=json.loads(base64.b64decode(r['response_body_b64']))
            for name,q in request['questions'].items():
                cells.append({'meta':r['meta'],'replicate':0,'question':name,'counts':{},
                              'target_frequency':float(target_value(response['answers'][name],q,r['meta']['target']))})
        with patch('analysis.matched.report',return_value={'cells':cells}):
            matched=compare(records,[],[r for r in manifest if r['replicate']==0],'anthropic',draws=10)
            self.assertTrue(all(r['mean']==0 for r in matched['cells']))
            with self.assertRaises(ValueError):compare(records[:-1],[],[r for r in manifest if r['replicate']==0],'anthropic',draws=10)
        screened={s['id']:True for s in stimuli if s['gap_bin']>0}
        result=analyze(records,manifest,stimuli,screened,draws=999)
        self.assertEqual(len(result['primary_tests']),13)
        self.assertTrue(all(r['PC']==0 and r['PF_binary']==-1 and r['RS']==1 for r in result['binary_metrics']['cells']))
        self.assertTrue(all(r['reject'] for r in result['primary_tests']))
        risk=next(r for r in result['operational_risk'] if r['probe']=='A' and r['axis']=='state_order' and r['rule']=='argmax' and r['population']=='all')
        self.assertEqual(risk['observed_disagreement'],1)
        self.assertTrue(risk['above_budget'])
        self.assertTrue(all(r['status'].startswith('insufficient') for r in result['gap_adjacent_bins']))
        with self.assertRaises(ValueError):analyze(records[:-1],manifest,stimuli,screened,draws=10)
        with self.assertRaises(ValueError):analyze(records,manifest,stimuli,{},draws=10)

if __name__=='__main__':unittest.main()
