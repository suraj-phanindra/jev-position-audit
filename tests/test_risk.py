import itertools
import math
import unittest
from analysis.risk import upper_bound,audit_bounds

class RiskChecks(unittest.TestCase):
    def test_weighted_bound_coverage_by_exhaustive_enumeration(self):
        probabilities=[.01,.1,.2,.5,.8,.99];weights=[.05,.1,.15,.2,.2,.3]
        truth=sum(p*w for p,w in zip(probabilities,weights));alpha=.1;miss=0
        for outcomes in itertools.product((0,1),repeat=6):
            chance=math.prod(p if y else 1-p for p,y in zip(probabilities,outcomes))
            if upper_bound(outcomes,weights,alpha)<truth:miss+=chance
        self.assertLessEqual(miss,alpha)
        self.assertAlmostEqual(upper_bound([0]*100,[.01]*100),.01*math.log(20))
        with self.assertRaises(ValueError):upper_bound([0],[.5])

    def test_contested_weights_condition_original_audit_population(self):
        rows=[]
        for source in ('MTBench','HANNA','SummEval'):
            for task,nitems in ((0,2),(1,1)):
                for item in range(nitems):
                    rows.append(dict(probe='A',axis='state_order',rule='argmax',gap_bin=1,
                                     source=source,seed_id=source+str(task),stimulus_id=source+str(task)+str(item),
                                     contested=source=='MTBench' and task==0 and item==0,
                                     paired_disagreements=[task,task]))
        result=audit_bounds(rows);all_rows=next(r for r in result if r['population']=='all')
        contested=next(r for r in result if r['population']=='contested')
        self.assertAlmostEqual(all_rows['observed_disagreement'],.5)
        self.assertAlmostEqual(contested['screened_audit_mass'],1/12)
        self.assertEqual(contested['observed_disagreement'],0)
        self.assertFalse(contested['below_budget'])

if __name__=='__main__':unittest.main()
