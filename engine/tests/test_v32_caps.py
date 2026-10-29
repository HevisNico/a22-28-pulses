"""Fix S (v3.2): unions of capped quantities respect the physical cap."""
from pathlib import Path
import unittest, sys, os, random
from fractions import Fraction as F
from decimal import Decimal as D
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'affine'))
os.environ.setdefault('A22_ARTIFACT_DIR', str(ROOT / 'test_diagnostics'))
import engine, affine_iv as af, temporal
I = af.I


def range_at(x, eps):
    lin = sum(F.from_float(v) * eps.get(k, F(0)) for k, v in x.d.items())
    r = F.from_float(x.e)
    return F(x.clo) + lin - r, F(x.chi) + lin + r


class CapTests(unittest.TestCase):
    def setUp(self):
        af.FRESH = None; temporal.begin_producer('test-v32')

    def members(self):
        x = I('1.0899') + I.symbol('e1', '0.01')
        y = I('1.09') + I.symbol('e1', '0.005') + I.symbol('e2', '0.0049')
        return [x, y]

    def test_plain_hull_would_trip_the_invariant(self):
        m = self.members()
        self.assertTrue(all(v.hi <= D('1.1') for v in m))
        self.assertGreater(af.hull(m).hi, D('1.1'))          # the v3 situation

    def test_capped_union_respects_cap_and_contains_members(self):
        m = self.members()
        r = engine._capped_union(m, D('1.1'), 'rate')
        self.assertLessEqual(r.hi, D('1.1'))
        rng = random.Random(1)
        for _ in range(200):
            eps = {'e1': F(rng.randint(-100, 100), 100), 'e2': F(rng.randint(-100, 100), 100)}
            lo, hi = range_at(r, eps)
            for v in m:
                vlo, vhi = range_at(v, eps)
                self.assertTrue(lo <= vlo and vhi <= hi)

    def test_away_from_cap_union_is_unchanged(self):
        x = I('0.5') + I.symbol('e1', '0.01'); y = I('0.505') + I.symbol('e1', '0.011')
        self.assertEqual(engine._capped_union([x, y], D('1.1'), 'rate').fingerprint(), af.hull([x, y]).fingerprint())

    def test_installed(self):
        self.assertIs(engine.b.ac.bounds, engine.ac_bounds)
        self.assertIs(engine.b.dz.bounds, engine.dz_bounds)


if __name__ == '__main__':
    unittest.main()
