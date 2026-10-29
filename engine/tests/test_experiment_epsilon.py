"""Physical-box sweeps keep port independence and initial uncertainty fixed."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = r'''
import json, sys
from decimal import Decimal as D
sys.path.insert(0, 'affine')
import engine, temporal, affine_iv, experiment_parameters
eps = D(experiment_parameters.PHYSICAL_EPSILON)
ns = 'epsilon-preflight'
temporal.begin_producer(ns)
affine_iv.FRESH = ns + ':remainder'
engine.settings_cell(ns)
b = engine.b
assert b.EPS.lo == b.EPS.hi == eps
assert b.DELTA.lo == b.DELTA.hi == D('1e-5')
for name in ('C', 'LM', 'LS', 'LE', 'M'):
    nominal = engine.I(4) if name == 'C' else getattr(engine.v, name)
    expected = nominal * (1 + engine.I(-eps, eps))
    actual = getattr(b, name)
    assert actual.lo <= expected.lo <= expected.hi <= actual.hi, name
for group in (b.LM_PORTS, b.LE_PORTS):
    for j, value in enumerate(group):
        assert any(k.endswith(':'+str(j)) for k in value.d)
        for k in range(j):
            assert not (set(value.d) & set(group[k].d))
for value in (b.INIT['q'], b.INIT['b']):
    assert D('-1e-5') - D('1e-18') < value.lo <= D('-1e-5')
    assert D('1e-5') <= value.hi < D('1e-5') + D('1e-18')
for value in b.INIT['z']:
    assert D('-1e-5') - D('1e-18') < value.lo <= D('-1e-5')
    assert D('9e-5') <= value.hi < D('9e-5') + D('1e-18')
print(json.dumps({'epsilon':str(eps),'delta':str(b.DELTA.lo)}))
'''


class EpsilonSweep(unittest.TestCase):
    def test_all_sweep_widths_cover_their_boxes_with_independent_ports(self):
        for eps in ('1e-4', '3e-4', '1e-3', '3e-3', '1e-2'):
            with self.subTest(epsilon=eps):
                env = dict(os.environ, A22_PHYSICAL_EPSILON=eps,
                           OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
                result = subprocess.run([sys.executable, '-B', '-c', CHECK],
                                        cwd=ROOT, env=env, text=True,
                                        capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['delta'], '0.00001')


if __name__ == '__main__':
    unittest.main()
