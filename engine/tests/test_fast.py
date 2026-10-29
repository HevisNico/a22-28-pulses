"""Root proposals must never bypass enclosure checks."""
import unittest, sys, os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'affine'))
import engine as e, affine_iv as af
from decimal import Decimal as D
from fractions import Fraction

class FastTests(unittest.TestCase):
    def setUp(self):
        af.FRESH=None
        e._ROOT_HINTS.clear();e.ROOT_STATS.clear()

    def test_hint_still_checks_endpoint_signs(self):
        root=e._plain_root(lambda x:x-af.I('.731'),lambda x:af.I(1),D(0),D(1),.7305)
        self.assertLessEqual(root.lo,D('.731'))
        self.assertGreaterEqual(root.hi,D('.731'))
        self.assertGreater(e.ROOT_STATS['bracket_trials'],1)

    def test_wide_hint_derivative_falls_back(self):
        def deriv(x):
            return af.I(1) if x.width()<D('1e-6') else af.I(-1,1)
        root=e._plain_root(lambda x:x-af.I('.5'),deriv,D(0),D(1),.5)
        self.assertLessEqual(root.lo,D('.5'))
        self.assertGreaterEqual(root.hi,D('.5'))
        self.assertEqual(e.ROOT_STATS['legacy_fallbacks'],1)

    def test_missing_sign_change_refused(self):
        with self.assertRaises(e.v.Ambiguous):
            e._plain_root(lambda x:x+af.I(1),lambda x:af.I(1),D(0),D(1),.5)

    def test_nonpositive_derivative_refused(self):
        with self.assertRaises(e.v.Ambiguous):
            e._plain_root(lambda x:x-af.I('.5'),lambda x:af.I(-1,1),D(0),D(1),.5)

    def test_root_at_narrow_boundary(self):
        truth=D('0.000000000003')
        root=e._plain_root(lambda x:x-af.I(truth),lambda x:af.I(1),D(0),D('.001'),float(truth))
        self.assertLessEqual(root.lo,truth);self.assertGreaterEqual(root.hi,truth)

    def test_underflow_is_outward(self):
        self.assertGreaterEqual(Fraction(af.fup(D('1e-1000'))),Fraction(D('1e-1000')))
        self.assertEqual(af.fup(D(0)),0.)

    def test_native_allocation_copies_coefficients_and_preserves_values(self):
        d={'z':-0.0,'a':.25};x=af.I.make(D('1.00'),D('1.10'),d,.001)
        d['a']=99.
        self.assertEqual(x._d['a'],.25)
        self.assertEqual(x._d['z'].hex(),(-0.).hex())
        self.assertEqual(str(x.clo),'1.00')
        self.assertEqual(list(x.d),['z','a'])
        with self.assertRaises(AttributeError):x.e=4.
        self.assertLessEqual(x.lo,D('.75'))
        self.assertGreaterEqual(x.hi,D('1.35'))

if __name__=='__main__':unittest.main()
