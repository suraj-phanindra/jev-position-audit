import unittest
from analysis.decisions import action,disagreement,repeat_disagreement,screening_membership,paired_choices
from preflight.live_check import reference_payload
from harness.audit import question,generate,format_candidate,unformat_candidate,validate_manifest,encode
import json
import base64
from stimuli.main_design import select,screening,reference_manifest
from harness.extensions import generate_extensions
from analysis.pilot import paired

class DecisionChecks(unittest.TestCase):
    def test_format_controls_and_independent_screening(self):
        item=dict(id='pair',seed_id='task',source='fixture',gap_bin=1,gap_basis='fixture',
                  prompt='task',x='Quoted "text"\n雪',y='Another answer')
        for family in ('simple','neutral','native'):
            self.assertEqual(unformat_candidate(format_candidate(item['x'],family),family),item['x'])
            with self.assertRaises(ValueError):unformat_candidate('{"answer":"changed","confidence":1}',family)
        rows=generate([item],'jev-1.13.0',format_controls=True)
        self.assertEqual(len(rows),172)
        validate_manifest(rows)
        def response(row,p):
            target=row['meta']['target'];other='Y' if target=='X' else 'X'
            data={'model':'jev-1.13.0','answers':{'preference':{'type':'choice',
                  'probabilities':{target:p,other:1-p},'choice':target if p>=.5 else other,'confidence':.8}}}
            return {**row,'status':200,'response_body_b64':base64.b64encode(encode(data).encode()).decode()}
        outcomes=[response(r,.6 if r['meta'].get('format_family')=='native' else .4)
                  for r in rows if r['meta']['kind']=='choice']
        contrasts=[r for r in paired(outcomes) if r['axis']=='format_family']
        self.assertEqual(len(contrasts),8)
        for r in contrasts:self.assertAlmostEqual(r['delta'],.2 if r['formatted_content']=='x' else -.2)
        screen=screening([item],'jev-1.13.0')
        self.assertEqual(len(screen),8)
        observed=[response(r,.9) for r in screen]
        self.assertEqual(screening_membership(observed,screen),{'pair':False})
        observed[0]=response(screen[0],.5)
        membership=screening_membership(observed,screen)
        self.assertEqual(membership,{'pair':True})
        with self.assertRaises(ValueError):screening_membership(observed[:-1],screen)
        with self.assertRaises(ValueError):paired_choices(observed)
        self.assertTrue(all(r['contested'] for r in paired_choices(outcomes,membership)))
        self.assertFalse(any(r['contested'] for r in paired_choices(outcomes,{'pair':False})))

    def test_ties_and_thresholds(self):
        self.assertEqual(action(.5,'argmax','one',.51),'y')
        self.assertEqual(action(.49,'argmax','one',.48),'x')
        self.assertEqual(action(.49,'argmax','one',.49),action(.5,'argmax','one',.5))
        for rule in ('argmax','symmetric','one_sided'):
            self.assertEqual(action(.5,rule,'one'),action(.5,rule,'one'))
        self.assertEqual(action(.2,'symmetric','one'),'y')
        self.assertEqual(action(.8,'symmetric','one'),'x')
        self.assertEqual(action(.799,'one_sided','one'),'no_action')
        self.assertEqual(action(.8,'one_sided','one'),'act')
        with self.assertRaises(ValueError):action(float('nan'),'argmax','one')

    def test_output_grammar_is_fixed_independently_of_prompt_order(self):
        q=question('choice','X','Y')
        a={'state':{},'questions':{'preference':q}}
        b={'state':{},'questions':{'preference':{**q,'criteria':dict(reversed(list(q['criteria'].items())))}}}
        for provider in ('anthropic','together'):
            pa=reference_payload(provider,a,canonical_schema=True)
            pb=reference_payload(provider,b,canonical_schema=True)
            key='output_config' if provider=='anthropic' else 'response_format'
            self.assertEqual(pa[key],pb[key])
            self.assertNotEqual(pa['messages'][-1]['content'],pb['messages'][-1]['content'])
        self.assertNotEqual(reference_payload('anthropic',a)['output_config'],reference_payload('anthropic',b)['output_config'])

    def test_main_allocation_excludes_pilot_tasks(self):
        rows=[]
        for source in ('MTBench','HANNA','SummEval'):
            for split in ('main','pilot'):
                for gap in (1,4):
                    rows.append(dict(id=f'{source}-{split}-{gap}',seed_id=f'{source}-{split}',
                                     source=source,split=split,gap_bin=gap,gap_basis='fixture',
                                     signed_gap=.1,prompt='task',x='one',y='two'))
        main,reference=select(rows)
        self.assertEqual(len(main),9)
        self.assertEqual(len(reference),6)
        self.assertTrue(all(r['split']=='main' for r in main+reference))
        self.assertEqual(sum(r['gap_bin']==0 for r in main),3)
        self.assertEqual((main,reference),select(list(reversed(rows))))

    def test_reference_subset_matches_main_requests(self):
        pairs=[]
        for source in ('MTBench','HANNA','SummEval'):
            pairs.append(dict(id=source+'-M0-M1',seed_id=source,source=source,split='main',
                              gap_bin=1,gap_basis='fixture',signed_gap=.1,prompt='task',x='one',y='two',
                              annotation={'story_ids':['M0','M1'],'ratings_x':[4,4,4],'ratings_y':[3,3,3]}))
        main,ref=select(pairs);subset=reference_manifest(main,ref,pairs)
        full=generate(main,'jev-1.13.0',format_controls=True)+generate_extensions(main,pairs)
        key=lambda r:(r['request_sha256'],encode(r['meta']),r['replicate'])
        self.assertTrue(set(map(key,subset))<=set(map(key,full)))
        self.assertEqual(subset,reference_manifest(list(reversed(main)),list(reversed(ref)),list(reversed(pairs))))

    def test_zero_mean_can_flip_every_decision(self):
        before=[.49,.51];after=[.51,.49]
        self.assertAlmostEqual(sum(b-a for a,b in zip(before,after)),0)
        self.assertTrue(all(action(a,'argmax',str(i))!=action(b,'argmax',str(i))
                            for i,(a,b) in enumerate(zip(before,after))))

    def test_noise_and_distribution_change_are_separate(self):
        self.assertEqual(disagreement(['x','y'],['x','y']),.5)
        self.assertIsNone(repeat_disagreement(['x']))
        self.assertEqual(repeat_disagreement(['x','x']),0)
        self.assertEqual(repeat_disagreement(['x','y']),1)
        # Finite-sample unbiased excess can be negative; never truncate it.
        self.assertLess(disagreement(['x','y'],['x','y'])-repeat_disagreement(['x','y']),0)
        self.assertEqual(disagreement(['x','x'],['y','y']),1)

if __name__=='__main__':unittest.main()
