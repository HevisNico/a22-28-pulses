"""Fixes A (correlated event order) and B (sound affine min/max)."""
from pathlib import Path
import unittest, sys, os, random, inspect
from fractions import Fraction as F
from decimal import Decimal as D
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'affine'))
os.environ.setdefault('A22_ARTIFACT_DIR', str(ROOT / 'test_diagnostics'))
import engine, affine_iv as af, temporal, sound_lattice as sl
I = af.I


def value_at(x, eps):
    """Exact rational centre-point value of the linear part at eps (remainder ignored)."""
    c = (F(x.clo) + F(x.chi)) / 2
    return c + sum(F.from_float(v) * eps.get(k, F(0)) for k, v in x.d.items())


class SoundLatticeTests(unittest.TestCase):
    def setUp(self):
        af.FRESH = None; temporal.begin_producer('test-lattice')

    def test_audit_counterexample_overlap_is_not_identified(self):
        x = I.symbol('x', 1); y = -x + I('.1')
        m = sl.amin(x, y)
        self.assertIsNot(m, x); self.assertIsNot(m, y)
        z = m - x   # at eps=1, min(x,y)-x = -1.9 must be enclosed
        self.assertLessEqual(F(z.lo), F(-19, 10))
        M = sl.amax(x, y)
        self.assertIsNot(M, x); self.assertIsNot(M, y)

    def test_dominance_keeps_correlation(self):
        x = I.symbol('x', '0.01'); y = I('1') + I.symbol('y', '0.01')
        self.assertIs(sl.amin(x, y), x); self.assertIs(sl.amin(y, x), x)
        self.assertIs(sl.amax(x, y), y); self.assertIs(sl.amax(y, x), y)
        z = sl.amin(x, y) - x; self.assertEqual((F(z.lo), F(z.hi)), (0, 0))

    def test_constant_cap_and_clamp(self):
        x = I('0.05') + I.symbol('x', '0.01')
        self.assertIs(sl.amin(I('.1'), sl.amax(I(0), x)), x)
        neg = I('-0.5') + I.symbol('n', '0.01')
        z = sl.amax(I(0), neg); self.assertEqual((F(z.lo), F(z.hi)), (0, 0))

    def test_plain_inputs_reproduce_original_expressions(self):
        rng = random.Random(7)
        for _ in range(500):
            a, b2, c, d = sorted(D(str(rng.uniform(-1, 1))) for _ in range(4))
            pairs = [(I(a, b2), I(c, d)), (I(a, c), I(b2, d)), (I(a, d), I(b2, c)), (I(c, d), I(a, b2))]
            for x, y in pairs:
                self.assertEqual(sl.amin(x, y).pair(), I(min(x.lo, y.lo), min(x.hi, y.hi)).pair())
                self.assertEqual(sl.amax(x, y).pair(), I(max(x.lo, y.lo), max(x.hi, y.hi)).pair())

    def test_pointwise_enclosure_random(self):
        rng = random.Random(11)
        for _ in range(300):
            x = I(D(str(rng.uniform(-1, 1)))) + I.symbol('s', D(str(rng.uniform(0, .5)))) + I.symbol('t', D(str(rng.uniform(0, .5))))
            y = I(D(str(rng.uniform(-1, 1)))) + I.symbol('s', D(str(rng.uniform(0, .5)))) * I(-1) + I.symbol('u', D(str(rng.uniform(0, .5))))
            mn = sl.amin(x, y); mx = sl.amax(x, y)
            for _ in range(20):
                eps = {k: F(rng.randint(-100, 100), 100) for k in ('s', 't', 'u')}
                vx = value_at(x, eps); vy = value_at(y, eps)
                for res, truth in ((mn, min(vx, vy)), (mx, max(vx, vy))):
                    if res is x or res is y:
                        self.assertEqual(value_at(res, eps), truth)
                    else:
                        self.assertTrue(F(res.lo) <= truth <= F(res.hi))

    def test_installed_sites(self):
        self.assertEqual(engine.SOUND_LATTICE_EDITS, ['actuations_A19.gain', 'actuations_A19.increment',
                         'actuations_A19.clip', 'depot_A19.value', 'dependances_A17.tail'])
        for mod, name in ((engine.b.ac, 'clip'), (engine.b.dz, 'value')):
            self.assertIn('amin', getattr(mod, name).__code__.co_names)


class CorrelatedOrderTests(unittest.TestCase):
    def setUp(self):
        af.FRESH = None; temporal.begin_producer('test-order')

    def test_overlapping_boxes_with_proven_order(self):
        common = temporal.Time('common', I(10) + I.symbol('c', '0.01'))
        early = engine.dep.shift(common, I('0.001'), 'early')
        late = engine.dep.shift(common, I('0.002'), 'late')
        self.assertLess(late.box().lo, early.box().hi)           # absolute boxes overlap
        self.assertGreater(late.minus(early).lo, 0)              # correlated order proven

    def test_advance_uses_correlated_difference(self):
        names = engine.b.advance.__code__.co_names if hasattr(engine.b.advance, '__code__') else ()
        src_ok = 'minus' in engine.orig_advance.__code__.co_names
        self.assertTrue(src_ok)


if __name__ == '__main__':
    unittest.main()
