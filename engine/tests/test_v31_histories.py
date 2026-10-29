"""Fix H (v3.1): exact folding of completed history terms, sound merge."""
from pathlib import Path
import unittest, sys, os, random
from fractions import Fraction as F
from decimal import Decimal as D
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'affine'))
os.environ.setdefault('A22_ARTIFACT_DIR', str(ROOT / 'test_diagnostics'))
import engine, affine_iv as af, temporal
I = af.I
ac = engine.b.ac; dz = engine.b.dz


def range_at(x, eps):
    lin = sum(F.from_float(v) * eps.get(k, F(0)) for k, v in x.d.items())
    r = F.from_float(x.e)
    return F(x.clo) + lin - r, F(x.chi) + lin + r


class HistoryFoldTests(unittest.TestCase):
    def setUp(self):
        af.FRESH = None
        temporal.begin_producer('test-v31')
        engine.settings_cell('test-v31')
        base = temporal.Time('t', I(100) + I.symbol('tt', '0.001'))
        self.t = base
        o1 = engine.dep.shift(base, I('0.02') + I.symbol('d1', '0.0001'), 'o1')
        s1 = engine.dep.shift(o1, I('0.003') + I.symbol('d2', '0.0001'), 's1')
        e1 = engine.dep.shift(s1, I('0.01') + I.symbol('d3', '0.0001'), 'e1')
        self.seg_partial = ac.Segment(0, o1, s1, False, e1, True)
        self.seg_full = ac.Segment(1, o1, o1, True, e1, True)
        self.later = engine.dep.shift(e1, I('2'), 'later')

    def test_actuation_fold_is_exact(self):
        h = ac.History(I('0.08') + I.symbol('b0', '1e-5'), 2, (self.seg_partial,))
        f = engine._fold(h)
        self.assertEqual((f.full, f.partial), (0, ()))
        self.assertEqual(ac.baseline(h).fingerprint(), ac.baseline(f).fingerprint())

    def test_deposit_fold_is_exact(self):
        h = dz.History(I('-1.2') + I.symbol('z', '5e-5'), 1, (self.seg_partial,), None, False, ({'kind': 'label'},))
        f = engine._fold(h)
        self.assertEqual((f.full, f.partial, f.conditions), (0, (), ()))
        self.assertEqual(dz.offered(h, self.later).fingerprint(), dz.offered(f, self.later).fingerprint())

    def test_merge_encloses_every_member(self):
        rng = random.Random(3)
        hs = [ac.History(I(D(str(rng.uniform(.08, .09)))) + I.symbol('b0', '1e-5') + I.symbol(f'x{i}', '1e-4'), i % 3, (self.seg_partial,) * (i % 2))
              for i in range(40)]
        out = engine.unique_histories(hs)
        self.assertLess(len(out), len(hs))
        for h in hs:
            v = ac.baseline(h)
            for _ in range(10):
                eps = {k: F(rng.randint(-100, 100), 100) for k in ['b0', 'tt', 'd1', 'd2', 'd3'] + [f'x{i}' for i in range(40)]}
                lo, hi = range_at(v, eps)
                self.assertTrue(any(range_at(ac.baseline(m), eps)[0] <= lo and hi <= range_at(ac.baseline(m), eps)[1] for m in out))

    def test_below_soft_threshold_unchanged(self):
        hs = [ac.History(I(D('0.08') + D(i) / D(10**6)), 1, (self.seg_partial,)) for i in range(10)]
        out = engine.unique_histories(hs)
        self.assertEqual(len(out), 10)
        self.assertTrue(all(a is b for a, b in zip(out, hs)))

    def test_budget_no_longer_exceeded_by_offsets(self):
        hs = [ac.History(I(D('0.08') + D(i) / D(10**7)), i % 5, ()) for i in range(200)]
        out = engine.unique_histories(hs)
        self.assertEqual(len(out), 1)
        lo = min(ac.baseline(h).lo for h in hs); hi = max(ac.baseline(h).hi for h in hs)
        m = ac.baseline(out[0])
        self.assertTrue(m.lo <= lo and hi <= m.hi)

    def test_structurally_distinct_histories_are_not_merged(self):
        hs = [ac.History(I('0.08'), 0, (), self.t, (self.seg_full,) if i % 2 else (self.seg_partial,)) for i in range(2)]
        hs = hs * 1 + [ac.History(I(D('0.08') + D(i) / D(10**6)), 0, (), self.t, (self.seg_full,)) for i in range(40)]
        out = engine.unique_histories(hs)
        marks = {engine.history_key(h.marks) for h in out}
        self.assertEqual(len(marks), 2)


if __name__ == '__main__':
    unittest.main()
