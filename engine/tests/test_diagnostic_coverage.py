"""Lightweight diagnostic regressions; no kernel import or simulation."""
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace
import importlib.util, unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
h=load('verif_h1h2');summary=load('bilan_campagne')

class Box:
    def __init__(self,lo,hi=None):self.lo,self.hi=D(str(lo)),D(str(lo if hi is None else hi))
    def pair(self):return [str(self.lo),str(self.hi)]
class Time:
    def minus(self,other):return Box(1)

class CoverageRegression(unittest.TestCase):
    def audit(self,covered,peak=False):
        profile=SimpleNamespace(relative_order_proofs=[])
        def advance(s,boundary,cell,count):
            if covered:profile.relative_order_proofs.append(dict(guard='no_fire_cover'))
            return s,'external'
        def evaluate(mem,t,derivative=False):
            if peak and t.lo<=D('.5')<=t.hi:return Box('1.01')
            return Box('.9')
        b=SimpleNamespace(PROFILE=profile,advance=advance,dep=SimpleNamespace(evaluate=evaluate),shift=lambda t,u,key:u)
        audit=h.DecisionAudit(b,Box);audit.install_ready_checks()
        b.advance(dict(p=0,memory={'fixture':True},t=Time()),Time(),'fixture',1)
        return audit
    def test_outer_fallback_decision_is_counted_and_rechecked(self):
        audit=self.audit(True)
        self.assertEqual(dict(audit.counts),{'H2_no_fire_cover':1})
        self.assertEqual(dict(audit.stats),{'H2_no_fire_cover: proved':1})
    def test_standard_decision_has_separate_count(self):
        self.assertEqual(dict(self.audit(False).counts),{'H2_standard':1})
    def test_safe_endpoints_do_not_hide_an_interior_threshold(self):
        audit=self.audit(True,peak=True)
        self.assertEqual(len(audit.bad),1)
        self.assertEqual(audit.bad[0]['verdict'],'inconclusive')
    def test_incomplete_replay_never_reports_success(self):
        self.assertEqual(h.outcome(False,[]),2)
        self.assertEqual(h.outcome(True,[{'unproved':True}]),1)
        self.assertEqual(h.outcome(True,[]),0)
    def test_summary_distinguishes_recorded_covers_from_rechecks(self):
        result=summary.cover_summary([{'guard':'no_fire_cover','cover':[['0','.5','.9'],['.5','1','.99']]}])
        self.assertEqual(result['recorded_no_fire_cover_decisions'],1)
        self.assertEqual(result['recorded_no_fire_cover_leaves'],2)
        self.assertEqual(result['recorded_no_fire_cover_minimum_margin_exact'],'1/100')
        self.assertFalse(result['no_fire_covers_reverified'])

if __name__=='__main__':unittest.main()
