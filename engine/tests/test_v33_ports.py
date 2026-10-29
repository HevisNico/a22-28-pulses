"""v3.3: per-port parameter symbols (fix P) and recovery/group resolution (fix R)."""
from pathlib import Path
import unittest, sys, os
from decimal import Decimal as D
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'affine'))
os.environ.setdefault('A22_ARTIFACT_DIR', str(ROOT / 'test_diagnostics'))
import engine, affine_iv as af, temporal, port_symbols, recovery_group
I = af.I; b = engine.b; ac = b.ac; dz = b.dz


def names(x):
    return set(x.d)


class PortSymbols(unittest.TestCase):
    def setUp(self):
        ns = 'test-v33/ports'
        temporal.begin_producer(ns); af.FRESH = ns + ':remainder'; af._COUNTER[0] = 0
        engine.settings_cell(ns)
        self.ns = ns

    def test_each_port_has_its_own_symbols(self):
        for j in range(3):
            for name, x in (('LM', b.LM_PORTS[j]), ('LE', b.LE_PORTS[j]), ('DM', b.DM_PORTS[j]),
                            ('DS', b.DS_PORTS[j]), ('DE', b.DE_PORTS[j])):
                own = {k for k in names(x) if k.startswith(self.ns + ':') and ':remainder' not in k}
                self.assertTrue(own, (name, j))
                self.assertTrue(all(k.endswith(f':{j}') for k in own), (name, j, own))
        for j in range(3):
            for k in range(3):
                if j != k:
                    self.assertFalse(names(b.DM_PORTS[j]) & names(b.DM_PORTS[k]))

    def test_plain_boxes_remain_for_shared_uses(self):
        for x in (b.C, b.LM, b.LS, b.LE, b.M, b.DM, b.DS, b.DE, b.D0, ac.LAM, dz.LAM):
            self.assertFalse(x.symbolic())

    def test_port_constants_cover_the_parameter_box(self):
        for j in range(3):
            self.assertTrue(b.LM_PORTS[j].lo <= b.LM.lo and b.LM.hi <= b.LM_PORTS[j].hi)
            self.assertTrue(b.LE_PORTS[j].lo <= b.LE.lo and b.LE.hi <= b.LE_PORTS[j].hi)

    def test_unit_and_coefficients_use_port_values(self):
        self.assertIn("DM_PORTS[j]", engine._src); self.assertIn("D0_PORTS[j]", engine._src)
        self.assertIn("DS_PORTS[j]", engine._src); self.assertIn("DE_PORTS[j]", engine._src)
        self.assertIn("LM_PORTS[j]", engine._coef); self.assertIn("LE_PORTS[j]", engine._coef)

    def _segment(self, port, full_start=True):
        origin = temporal.Time('clock', I(D('9.95')))
        return ac.Segment(port, origin, origin, full_start)

    def test_actuation_uses_the_segment_port_and_restores_globals(self):
        saved = (ac.LAM, ac.DM, ac.MU)
        for j in range(3):
            x = ac.charge(self._segment(j), temporal.Time('clock', I(D('9.96'))))
            own = {k for k in names(x) if ':LM:' in k}
            self.assertEqual(own, {f'{self.ns}:LM:{j}'})
            self.assertIs(ac.LAM, saved[0]); self.assertIs(ac.DM, saved[1]); self.assertIs(ac.MU, saved[2])

    def test_raw_dose_matches_kernel_for_single_port_history(self):
        fire = temporal.Time('clock', I(10))
        for j in range(3):
            h = ac.History(I('.38'), 0, (), fire, (self._segment(j),), False)
            t = temporal.Time('clock', I(D('11.4')))
            new = ac.raw_dose(h, t)
            saved = (ac.LAM, ac.DM, ac.MU)
            ac.LAM, ac.DM, ac.MU = ac.PORT_LAM[j], ac.PORT_DM[j], ac.PORT_MU[j]
            try:
                ref = port_symbols.ORIGINAL['raw_dose'](h, t)
            finally:
                ac.LAM, ac.DM, ac.MU = saved
            self.assertEqual(new.fingerprint(), ref.fingerprint())

    def test_deposit_history_uses_its_port(self):
        for j in range(3):
            origin = temporal.Time('clock', I(5))
            seg = ac.Segment(j, origin, origin, True)
            h = dz.History(I(0), 0, (), seg, False, ())
            x = dz.offered(h, temporal.Time('clock', I(D('5.1'))))
            self.assertEqual({k for k in names(x) if ':LE:' in k}, {f'{self.ns}:LE:{j}'})
            self.assertFalse(dz.LAM.symbolic())


class RecoveryGroup(unittest.TestCase):
    def test_declines_outside_slow_recovery(self):
        for p in (0, 1):
            self.assertIsNone(recovery_group.resolve(b, dict(p=p), [], 0, 'c', 0))

    def test_declines_when_resolver_refuses(self):
        import cycle_local_A20
        saved = cycle_local_A20.pending_window
        def refuse(*a): raise b.v.Ambiguous('test')
        cycle_local_A20.pending_window = refuse
        try:
            self.assertIsNone(recovery_group.resolve(b, dict(p=2), [], 0, 'c', 0))
        finally:
            cycle_local_A20.pending_window = saved

    def test_declines_forest_with_emission(self):
        import cycle_local_A20
        from types import SimpleNamespace
        saved = cycle_local_A20.pending_window
        forest = SimpleNamespace(branches=(SimpleNamespace(emissions=('fire',), state=dict(p=1)),))
        cycle_local_A20.pending_window = lambda *a: (forest, 3, [1, 2])
        try:
            self.assertIsNone(recovery_group.resolve(b, dict(p=2), [], 0, 'c', 0))
        finally:
            cycle_local_A20.pending_window = saved

    def test_hooked_only_in_the_group_path(self):
        self.assertEqual(engine._src.count('RECOVERY_GROUP('), 1)


if __name__ == '__main__':
    unittest.main()
