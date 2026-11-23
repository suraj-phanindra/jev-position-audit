import base64
import unittest
from analysis.budget import estimate,size
from analysis.repeat_noise import report
from harness.audit import encode,digest,generate,question

class PlanningChecks(unittest.TestCase):
    def test_budget_counts_and_stress(self):
        item=dict(id='pair',seed_id='task',source='MTBench',gap_bin=1,gap_basis='fixture',
                  signed_gap=.1,prompt='task',x='one',y='two')
        reference=generate([item],'jev-1.13.0',format_controls=True)
        calibration={(p,'MTBench',k):dict(median_tokens_per_utf8_byte=.2,max_observed_tokens_per_utf8_byte=.3,
                                        median_output=10,max_observed_output=20,n=10)
                     for p in ('typesafe','anthropic','together') for k in ('noul','choice','score','questions')}
        result=estimate([item],[],reference,calibration)
        self.assertEqual(result['providers']['typesafe']['calls'],692)
        for provider in ('anthropic','together'):
            self.assertEqual(result['providers'][provider]['calls'],3440)
        for r in result['providers'].values():self.assertGreater(r['stress_cost_usd'],r['median_cost_usd'])

    def test_temporal_diagnostic_detects_alternation_despite_zero_drift(self):
        questions={k:question(k,'X','Y') for k in ('noul','choice','score')}
        request={'model':'jev-1.13.0','state':{},'questions':questions};body=encode(request);rows=[]
        for i in range(200):
            p=.2 if i%2 else .8
            answers={'noul':{'type':'noul','noul':p},
                     'choice':{'type':'choice','choice':'X' if p>.5 else 'Y','confidence':.8,'probabilities':{'X':p,'Y':1-p}},
                     'score':{'type':'score','score':2*p,'confidence':.8,'probabilities':{'0':1-p,'1':0,'2':p},
                              'legend':{str(j):v for j,v in enumerate(questions['score']['criteria'])}}}
            response={'model':'jev-1.13.0','answers':answers}
            rows.append(dict(status=200,request_body=body,request_sha256=digest(body),started_at=f'{i:03d}',
                             response_body_b64=base64.b64encode(encode(response).encode()).decode()))
        result=report(rows,draws=99)
        for r in result['rows']:
            self.assertAlmostEqual(r['mean_late_minus_early'],0)
            self.assertLess(r['pooled_standardized_lag1_product'],-.99)
            self.assertLess(r['permutation_p_two_sided'],.02)
        with self.assertRaises(ValueError):report(rows[:-1],draws=10)

if __name__=='__main__':unittest.main()
