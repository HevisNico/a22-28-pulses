"""Regression: the lemma-E widening must enlarge the fire enclosure outward, exactly.

v4.4 to v4.6 computed the widened fire enclosure as r0 + I(-delta, 0). Python's unary minus
rounds to the ambient 28-digit Decimal context, while delta is a 160-digit upward-rounded
value, so the lower end could move INWARD. In the 28-pulse campaign of v4.6, cell (18,4),
batch 89, this shrank the enclosure by about 6.215e-30. The fix uses delta.copy_negate(),
which is exact. This test evaluates the expression actually present in affine/commutation.py
with that archived delta.
"""
import os
import re
import sys
import unittest
from decimal import Decimal as D, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'affine'))
os.environ.setdefault('A22_ARTIFACT_DIR', str(ROOT / 'test_diagnostics'))
import engine  # installs the kernel paths, as the other tests do
from affine_iv import I

# Archived widening of cell (18,4), batch 89 (v4.6, 28 pulses, T = 230), 160 digits.
DELTA_18_4 = D('0.25177714110177993142191656850621528358634133168474469658771808186725357513329841486757'
               '78400756949989416196030342044573555756977095445243585445832879587013621239')
ROUNDING_LOSS_18_4 = D('6.215283586341331684744696588E-30')


def widening_expression():
    source = (ROOT / 'affine' / 'commutation.py').read_text()
    lines = [line.strip() for line in source.splitlines() if re.match(r'\s*rho = r0 \+ I\(', line)]
    assert len(lines) == 1, lines
    return lines[0][len('rho = '):]


class CommutationRounding(unittest.TestCase):
    def test_archived_delta_is_the_reported_case(self):
        self.assertEqual(len(DELTA_18_4.as_tuple().digits), 160)
        self.assertEqual(DELTA_18_4 - (-(-DELTA_18_4)), ROUNDING_LOSS_18_4)

    def test_widening_is_outward_and_exact(self):
        expression = widening_expression()
        r0 = I(D('0.5'), D('0.75'))
        rho = eval(expression, {'I': I, 'D': D}, {'r0': r0, 'delta': DELTA_18_4})
        with localcontext() as ctx:
            ctx.prec = 400
            required = D('0.5') - DELTA_18_4
        self.assertLessEqual(rho.lo, required)
        self.assertGreaterEqual(rho.hi, D('0.75'))
        self.assertNotIn('I(-delta', expression)

    def test_old_expression_was_inward(self):
        r0 = I(D('0.5'), D('0.75'))
        old = eval('r0 + I(-delta, D(0)) if delta > 0 else r0', {'I': I, 'D': D}, {'r0': r0, 'delta': DELTA_18_4})
        with localcontext() as ctx:
            ctx.prec = 400
            required = D('0.5') - DELTA_18_4
        self.assertGreater(old.lo, required)


if __name__ == '__main__':
    unittest.main()
