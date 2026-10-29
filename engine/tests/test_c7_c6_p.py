"""v3.3 + C7: targeted tests of lemma C7 (peak bound without the peak
logarithm), lemma C6 (piecewise pulse-memory cover) and remark P (root
bracket slope on a partition). Each accepting path must keep refusing when
its bound is insufficient."""
from pathlib import Path
import unittest, sys, os, math, random
from decimal import Decimal as D
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'affine'))
os.environ.setdefault('A22_ARTIFACT_DIR', str(ROOT / 'test_diagnostics'))
import engine, affine_iv as af, temporal, cluster_memory_cover
import ready_general_A22
I = af.I
b = engine.b


class RemarkP(unittest.TestCase):
    """_piecewise_slope and its use in _plain_root."""

    def setUp(self):
        af.FRESH = None
        engine._ROOT_HINTS.clear(); engine.ROOT_STATS.clear()

    def test_partition_covers_bracket_exactly(self):
        seen = []
        def deriv(x):
            seen.append((x.lo, x.hi)); return I(-1) if x.width() > D('.2') else I(1)
        l, h = D('0.1'), D('0.9')
        s = engine._piecewise_slope(deriv, l, h)
        self.assertGreater(s.lo, 0)
        pieces = seen[1:]                       # seen[0] is the whole interval
        self.assertEqual(pieces[0][0], l); self.assertEqual(pieces[-1][1], h)
        for (a0, a1), (b0, b1) in zip(pieces, pieces[1:]):
            self.assertEqual(a1, b0)            # contiguous, no gap or overlap
        self.assertTrue(all(a0 < a1 for a0, a1 in pieces))

    def test_hull_of_pieces_is_returned(self):
        def deriv(x):
            return I(2) if x.hi <= D('.5') else (I('0.5') if x.lo >= D('.5') else I(-1, 3))
        s = engine._piecewise_slope(deriv, D(0), D(1))
        self.assertEqual((s.lo, s.hi), (D('0.5'), D(2)))

    def test_wide_root_accepted_through_pieces(self):
        # Root spread over [0.3, 0.7]; the slope is provable only on short pieces.
        fun = lambda x: x - I('.5') + I('-.2', '.2')
        deriv = lambda x: I(1) if x.width() <= D('.15') else I(-1, 1)
        r = engine._plain_root(fun, deriv, D(0), D(1), .5)
        self.assertLessEqual(r.lo, D('.3')); self.assertGreaterEqual(r.hi, D('.7'))
        self.assertGreater(engine.ROOT_STATS['piecewise_slopes'], 0)

    def test_tangency_still_refused(self):
        # Every partition has a piece containing 0.5, where the slope may vanish.
        fun = lambda x: x - I('.5') + I('-.2', '.2')
        deriv = lambda x: I(0, 1) if x.lo <= D('.5') <= x.hi else I(1)
        with self.assertRaises(b.v.Ambiguous):
            engine._plain_root(fun, deriv, D(0), D(1), .5)

    def test_near_zero_slope(self):
        fun = lambda x: x - I('.5')
        r = engine._plain_root(fun, lambda x: I('1e-30', 1), D(0), D(1), .5)
        self.assertLessEqual(r.lo, D('.5')); self.assertGreaterEqual(r.hi, D('.5'))
        engine._ROOT_HINTS.clear()
        with self.assertRaises(b.v.Ambiguous):
            engine._plain_root(fun, lambda x: I(0, 1), D(0), D(1), .5)

    def test_signs_still_required(self):
        with self.assertRaises(b.v.Ambiguous):
            engine._plain_root(lambda x: x + I(1), lambda x: I(1), D(0), D(1), .5)


class _Probe:
    def __init__(self, lo, hi): self.lo, self.hi = lo, hi
class _Gap:
    def __init__(self, h): self.h = h
    def nonnegative(self): return I(0, self.h)
class _Clock:
    def __init__(self, h): self.h = h
    def minus(self, other): return _Gap(self.h)
class _Stub:
    """Minimal b for cluster_memory_cover: charge(u) is a monotone formula
    evaluated exactly at the ends of each time piece."""
    I = I; D = D
    def __init__(self, charge):
        self.charge = charge
        self.dep = self
    def shift(self, t, u, key): return _Probe(u.lo, u.hi)
    def evaluate(self, memory, probe):
        # Like an interval evaluation: exact extremes plus an overestimate
        # proportional to the width of the time piece.
        values = [self.charge(probe.lo), self.charge(probe.hi)]
        if probe.lo < D('.5') < probe.hi: values.append(self.charge(D('.5')))
        slack = (probe.hi - probe.lo) * D('1e-3')
        return I(min(values) - slack, max(values) + slack)


class LemmaC6(unittest.TestCase):
    def certify(self, charge, H=D(1), s=None):
        s = s or dict(p=0, memory=object(), t=None)
        return cluster_memory_cover.certify(_Stub(charge), s, _Clock(H))

    def test_below_threshold_accepted(self):
        self.assertTrue(self.certify(lambda u: D('.9') - (u - D('.5')) ** 2))

    def test_threshold_reached_refused(self):
        self.assertFalse(self.certify(lambda u: D(1) - (u - D('.5')) ** 2))

    def test_near_threshold_needs_pieces_but_passes(self):
        # Peak 1 - 1e-4: the whole-window slack (1e-3) is too large, pieces of
        # width below 0.1 are enough.
        before = cluster_memory_cover.STATS['pieces']
        self.assertTrue(self.certify(lambda u: D(1) - D('1e-4') - D('1e-3') * abs(u - D('.5'))))
        self.assertGreater(cluster_memory_cover.STATS['pieces'] - before, 1)

    def test_depth_limit_refuses(self):
        # Peak 1 - 1e-30: pieces cannot get small enough within depth 8.
        self.assertFalse(self.certify(lambda u: D(1) - D('1e-30') - D('1e-3') * abs(u - D('.5'))))

    def test_non_ready_or_no_memory_refused(self):
        ok = lambda u: D('.5')
        self.assertFalse(self.certify(ok, s=dict(p=2, memory=object(), t=None)))
        self.assertFalse(self.certify(ok, s=dict(p=0, memory=None, t=None)))


def ready_state(q, g, arrival_age, t0='1'):
    """READY state at time t0 with one raw input on port 0 started
    arrival_age earlier, gain g on every port, charge interval q."""
    t = temporal.Time('c7-now', I(t0))
    x = temporal.Time('c7-arrival', I(t0) - I(arrival_age))
    return dict(t=t, q=q, raw=[x, None, None], caps=[False] * 3, z=[I(g).ln()] * 3,
                err=[None] * 3, mark=[None] * 3, p=0, aux=[0] * 3, bstop=False, b=I('.08'))


def exact_charge(q0, g, age, u):
    A, K, R = math.log(4), .5, .1
    J = g * A * math.exp(-A * age)
    return R + (q0 - R) * math.exp(-K * u) + J * (math.exp(-K * u) - math.exp(-A * u)) / (A - K)


class LemmaC7(unittest.TestCase):
    def setUp(self):
        ns = 'test-c7'
        temporal.begin_producer(ns); af.FRESH = None; af._COUNTER[0] = 0
        engine.settings_cell(ns)

    def check_bound(self, qlo, qhi, glo, ghi, age, H):
        s = ready_state(I(qlo, qhi), I(glo, ghi), age)
        tt = temporal.Time('c7-end', I('1') + I(H))
        bound = ready_general_A22.peak_upper(s, tt)
        rng = random.Random(7)
        worst = -1.0
        for _ in range(200):
            q0 = rng.uniform(float(qlo), float(qhi)); g = rng.uniform(float(glo), float(ghi))
            for k in range(101):
                worst = max(worst, exact_charge(q0, g, float(age), float(H) * k / 100))
        self.assertGreaterEqual(float(bound), worst - 1e-12)
        return bound

    def test_bound_with_interior_peak(self):
        self.check_bound(D('.1'), D('.12'), D('.3'), D('.31'), D('.05'), D('.9'))

    def test_bound_when_logarithm_has_no_positive_argument(self):
        # aa = q0 - R + J/(A-K) <= 0: the case C7 handles.
        bound = self.check_bound(D('0'), D('.02'), D('.0001'), D('.0002'), D('.5'), D('.9'))
        self.assertLess(bound, 1)

    def test_near_threshold_bound_is_not_below_true_peak(self):
        self.check_bound(D('.95'), D('.99'), D('.3'), D('.3'), D('.0'), D('.5'))

    def test_advance_refuses_when_peak_bound_reaches_threshold(self):
        s = ready_state(I('0', '1.2'), I('.0001'), D('.5'))
        boundary = temporal.Time('c7-boundary', I('1.9'))
        with self.assertRaises(b.v.Ambiguous):
            b.advance(s, boundary, 'c7', 0)

    def test_advance_flows_when_peak_bound_is_below_threshold(self):
        s = ready_state(I('0', '.02'), I('.0001'), D('.5'))
        boundary = temporal.Time('c7-boundary2', I('1.9'))
        out, kind = b.advance(s, boundary, 'c7', 1)
        self.assertEqual(kind, 'external')
        self.assertLess(out['q'].hi, 1)


if __name__ == '__main__':
    unittest.main()
