import base64
import json
import math
import unittest

from analysis.gap import transformed,magnitudes,trends,adjacent_bins
from analysis.gap_power import plan
from harness.audit import generate,encode,question

class GapChecks(unittest.TestCase):
    def test_power_sensitivity_accounts_for_noise(self):
        items=[dict(source=s,seed_id=s+str(t),gap_bin=i+1,signed_gap=g)
               for s in ('MTBench','HANNA','SummEval') for t in range(10)
               for i,g in enumerate((.1,.2,.5,.9))]
        result=plan(items,simulations=200)
        self.assertEqual(len(result['rows']),36)
        rows=[r for r in result['rows'] if r['gated'] and r['baseline_contrast']==.3 and r['transformed_dimensions']==1]
        rates={r['balanced_repeat_noise_sd']:r['rejection_probability'] for r in rows}
        self.assertGreater(rates[.1],rates[1.])
        self.assertTrue(all(abs(r['true_population_projection'])<1e-12 for r in result['rows'] if not r['gated']))

    def test_score_coordinates_and_repeat_correction(self):
        q=question('score','X','Y');a={'probabilities':{'0':.2,'1':.3,'2':.5}}
        v=transformed(a,q,'X')
        rev={**q,'criteria':q['criteria'][::-1]}
        self.assertEqual(v,transformed({'probabilities':{'0':.5,'1':.3,'2':.2}},rev,'X'))
        item=dict(id='pair',seed_id='task',source='MTBench',gap_bin=2,gap_basis='fixture',signed_gap=.2,
                  prompt='task',x='one',y='two')
        manifest=[r for r in generate([item],'jev-1.13.0',repeats=2)
                  if r['meta']['probe']=='A' and r['meta']['kind']=='noul']
        records=[]
        for r in manifest:
            # Independent-repeat contrasts +1 and -1 => unbiased product -1,
            # which must not be truncated to zero or replaced by noisy squares.
            d=1 if r['replicate']==0 else -1
            p=1/(1+math.exp(-d)) if r['meta']['state_order']==0 else .5
            data={'model':'jev-1.13.0','answers':{'preference':{'type':'noul','noul':p}}}
            records.append({**r,'status':200,'response_body_b64':base64.b64encode(encode(data).encode()).decode()})
        result=magnitudes(records,[item])
        self.assertEqual(len(result),1);self.assertAlmostEqual(result[0]['magnitude'],-1)
        with self.assertRaises(ValueError):magnitudes([r for r in records if r['replicate']==0],[item])

    def test_gap_slopes_ignore_task_intercepts_and_detect_nonmonotonicity(self):
        rows=[]
        for source in ('MTBench','HANNA','SummEval'):
            for task in range(8):
                for kind in ('noul','choice','score'):
                    for gap in range(1,5):
                        rows.append(dict(source=source,seed_id=source+str(task),kind=kind,
                                         gap_bin=gap,gap=gap/4,magnitude=task*10+2-gap/4))
        result=trends(rows,draws=100)
        self.assertTrue(all(abs(r['slope']+1)<1e-12 for r in result))
        self.assertTrue(all(r['simultaneous_upper']<0 for r in adjacent_bins(rows,draws=100)))
        # A negative overall slope is not proof of monotonic decline.
        for r in rows:r['magnitude']+=.8 if r['gap_bin']==3 else 0
        result=trends(rows,draws=100)
        self.assertTrue(all(r['slope']<0 for r in result))
        self.assertTrue(any(r.get('simultaneous_upper',0)>0 for r in adjacent_bins(rows,draws=100)))

if __name__=='__main__':unittest.main()
