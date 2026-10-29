"""v3: common-generator union (fix C) and fire/arrival commutation (fix E)."""
from pathlib import Path
import unittest, sys, os, random
from fractions import Fraction as F
from decimal import Decimal as D
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'affine'))
os.environ.setdefault('A22_ARTIFACT_DIR', str(ROOT / 'test_diagnostics'))
import engine, affine_iv as af, temporal, port_symbols
I = af.I


def value_bounds(x, eps):
    """Exact rational [lo,hi] of the affine form at the parameter point eps."""
    lin = sum((F.from_float(v) * eps.get(k, F(0)) for k, v in x.d.items()), F(0))
    e = F.from_float(x.e)
    return F(x.clo) + lin - e, F(x.chi) + lin + e


def random_form(rng, names, base):
    d = {}
    for k in names:
        if rng.random() < .8:
            c = base.get(k, rng.uniform(-1, 1)) * (1 + rng.choice([0, 0, 1e-16, -3e-15, 1e-9, rng.uniform(-.5, .5)]))
            if rng.random() < .1: c = -c
            d[k] = c
    c = D(str(rng.uniform(-1, 1))); w = D(str(abs(rng.gauss(0, 1e-3))))
    return I.make(c, c + w if rng.random() < .5 else c, d, abs(rng.gauss(0, 1e-6)) if rng.random() < .5 else 0.0)


class CommonGeneratorUnion(unittest.TestCase):
    def setUp(self): af.FRESH = None; temporal.begin_producer('test-v3')

    def test_pointwise_enclosure_exact(self):
        rng = random.Random(20261021)
        for trial in range(400):
            names = [f's{i}' for i in range(rng.randint(1, 12))]
            base = {k: rng.uniform(-1, 1) * 10 ** rng.randint(-8, 0) for k in names}
            xs = [random_form(rng, names, base) for _ in range(rng.randint(2, 5))]
            h = af.hull(xs)
            for _ in range(12):
                eps = {k: F(rng.choice([-1, 1, 0, rng.uniform(-1, 1)])) for k in names}
                hl, hh = value_bounds(h, eps)
                for x in xs:
                    lo, hi = value_bounds(x, eps)
                    self.assertLessEqual(hl, lo); self.assertGreaterEqual(hh, hi)

    def test_audit_witness_no_manufactured_dependence(self):
        x = I.symbol('x', 1); h = af.hull([x, -x]); z = h - x
        self.assertLessEqual(F(z.lo), -2 * F.from_float(x.d['x']))
        self.assertGreaterEqual(F(z.hi), 0)

    def test_last_bit_differences_keep_correlation(self):
        x = I.symbol('x', '1e-3'); y = I.symbol('y', '1e-3')
        a = x * I('1.000000000000001') + y
        b = x + y * I('0.999999999999999')
        old = af.hull_identical([a, b]) - x - y
        new = af.hull([a, b]) - x - y
        self.assertGreater(old.width(), D('3.9e-3'))
        self.assertLess(new.width(), D('1e-12'))

    def test_truncation_above_kmax_stays_outward(self):
        self.assertEqual(af.KMAX, 256)
        d = {str(i): 2.0 ** (-(i % 70)) for i in range(400)}
        x = I.make(D(0), D(0), d, 0.)
        self.assertEqual(len(x.d), 256)
        self.assertGreaterEqual(F(x.hi), sum(map(F.from_float, d.values()), F(0)))

    def test_native_truncation_equals_reference(self):
        import rounding, importlib
        ref = importlib.util.spec_from_file_location('rounding_ref', rounding.__file__)
        os.environ['A22_AFFINE_NATIVE'] = '0'
        try:
            mod = importlib.util.module_from_spec(ref); ref.loader.exec_module(mod)
        finally:
            del os.environ['A22_AFFINE_NATIVE']
        self.assertIsNot(mod.truncate_coeff, rounding.truncate_coeff)
        rng = random.Random(96)
        for _ in range(300):
            n = rng.randint(1, 600); k = rng.randint(1, 300)
            pool = [rng.uniform(-1, 1) * 2.0 ** rng.randint(-60, 2) for _ in range(rng.randint(1, 40))]
            d = {f's{i}': rng.choice(pool) for i in range(n)}
            a, ea = mod.truncate_coeff(d, k); b, eb = rounding.truncate_coeff(d, k)
            self.assertEqual(list(a.items()), list(b.items())); self.assertEqual(ea, eb)
            self.assertEqual(len(a), min(n, k))
            kept = sorted(d.items(), key=lambda kv: -abs(kv[1]))[:k]
            self.assertEqual(set(a), {x for x, _ in kept})
            self.assertGreaterEqual(F.from_float(ea), sum((F.from_float(abs(v)) for x, v in d.items() if x not in a), F(0)))

    def test_identical_and_plain_reproduce_v2(self):
        rng = random.Random(7)
        for _ in range(200):
            c = [D(str(rng.uniform(-1, 1))) for _ in range(3)]
            xs = [I(min(c[i], c[i] + D('.01')), c[i] + D('.01')) for i in range(3)]
            self.assertEqual(af.hull(xs).fingerprint(), af.hull_identical(xs).fingerprint())
        x = I.symbol('x', 1) + I('.3')
        self.assertIs(af.hull([x, x]), x)


class FireArrivalCommutation(unittest.TestCase):
    """Synthetic layer-18 situation: a neighbour arrival 2e-3 after the fire
    of the cell, with +/-5e-3 of extra (artificial) uncertainty on its date."""
    SEP = D('2e-3'); RHO = D('5e-3')

    def run_cell(self, arrival, tag, point=False):
        orig = I.symbol
        if point:
            I.symbol = staticmethod(lambda name, radius: orig(name, '0'))
            port_symbols.COVER_CHECK = False   # exact-parameter sampling (v3.3)
        try:
            ns = f'test-v3/{tag}'
            temporal.begin_producer(ns); af.FRESH = ns + ':remainder'; af._COUNTER[0] = 0
            engine.settings_cell(ns)
            own = tuple(temporal.Time('clock', I(0)).plus(8 * k) for k in range(3))
            right = () if arrival is None else (temporal.Time('arrival', arrival),)
            return engine.b.unit(((), own, right), f'T,{tag}')
        finally:
            I.symbol = orig; port_symbols.COVER_CHECK = True

    def setUp(self):
        out, _ = self.run_cell(None, 'nominal')
        self.tau = out[0].box().mid() + self.SEP

    def test_v2_refuses_v3_encloses_every_order(self):
        arrival = I(self.tau) + I.symbol('X', self.RHO)
        saved = engine.b.COMMUTE
        engine.b.COMMUTE = lambda *a: None
        try:
            with self.assertRaises(engine.b.v.Ambiguous):
                self.run_cell(arrival, 'v2')
        finally:
            engine.b.COMMUTE = saved
        out, st = self.run_cell(arrival, 'v3')
        proofs = [p for p in st['width_profile']['relative_order_proofs'] if p.get('guard') == 'fire_arrival_commutation']
        self.assertEqual(len(proofs), 1)
        self.assertLess(D(proofs[0]['kappa']), 1)
        fire = out[0].box()
        # Exact-parameter runs, arrival placed before, at and after the fire.
        for k in (-10, -7, -4, -2, 0, 5, 10):
            o, _ = self.run_cell(I(self.tau + self.RHO * k / 10), f'point{k}', point=True)
            self.assertTrue(fire.lo <= o[0].box().mid() <= fire.hi, k)

    def test_two_arrivals_around_the_fire(self):
        """Left and right arrivals both uncertain around the fire (exterior
        cluster path): every order and fire position is enclosed."""
        def run(la, ra, tag, point=False):
            orig = I.symbol
            if point:
                I.symbol = staticmethod(lambda name, radius: orig(name, '0')); port_symbols.COVER_CHECK = False
            try:
                ns = f'test-v3g/{tag}'
                temporal.begin_producer(ns); af.FRESH = ns + ':remainder'; af._COUNTER[0] = 0
                engine.settings_cell(ns)
                own = tuple(temporal.Time('clock', I(0)).plus(8 * k) for k in range(3))
                return engine.b.unit(((temporal.Time('L', la),), own, (temporal.Time('R', ra),)), f'G,{tag}')
            finally:
                I.symbol = orig; port_symbols.COVER_CHECK = True
        left = self.tau - D('1e-3')
        out, st = run(I(left) + I.symbol('Y', self.RHO), I(self.tau) + I.symbol('X', self.RHO), 'sym')
        self.assertTrue(any(p.get('guard') == 'fire_arrival_commutation' and p['arrivals'] == 2
                            for p in st['width_profile']['relative_order_proofs']))
        fire = out[0].box()
        for x, y in ((-5, -5), (-5, 0), (0, -2), (5, -5), (5, 5)):
            o, _ = run(I(left + D(y) / 1000), I(self.tau + D(x) / 1000), f'p{x}{y}', True)
            self.assertTrue(fire.lo <= o[0].box().mid() <= fire.hi, (x, y))

    def test_non_arrival_events_are_not_commuted(self):
        b = engine.b
        s = dict(p=0, memory={'pulses': {}}, raw=[None] * 3)
        pending = [(temporal.Time('x', I(1)), [('end', -1, None)])]
        import commutation
        self.assertIsNone(commutation.resolve(b, s, pending, 0, 1, [D(1), D('Infinity')], 'c', 0))


if __name__ == '__main__':
    unittest.main()
