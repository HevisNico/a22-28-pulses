# Lemma E: outward rounding of the fire-time widening

Lemma E encloses a READY fire whose order against a group of events is undecided by
F̂ = t0 + (r0 + [−δ, 0]), where δ = κ·w is computed with upward rounding at 160 digits. The engine
first built the lower end as `I(-delta, D(0))`. In Python, unary minus on a `Decimal` rounds to the
ambient 28-digit context, so the lower end could move **inward** by up to one unit in the 28th digit.

In the original 28-pulse campaign (kernel `886d1c5c…`) this happened once in a way that shrank the
enclosure: cell (18,4), batch 89, κ ≈ 0.91718, δ ≈ 0.25178 with 160 digits, rounding loss
6.215·10⁻³⁰. The correction is one line ([`commutation_fix.diff`](commutation_fix.diff)):
`I(delta.copy_negate(), D(0))`, which is exact.

The campaign of this repository (kernel `b49dca10…`) was run with the corrected engine. Its terminal
enclosures, its terminal domain and its future certificates are identical to those of the original
campaign; only the identity hashes differ.

## How to audit

`engine/tests/test_commutation_rounding.py` evaluates the expression actually present in
`engine/affine/commutation.py` with the archived δ of cell (18,4) and requires the lower end to be at
most r0.lo − δ exactly (400-digit check). The recorded outputs:

| File | Engine | Result |
|---|---|---|
| [`regression_test_unfixed_engine.txt`](regression_test_unfixed_engine.txt) | original line `I(-delta, D(0))` | FAIL: lower end 0.2482228588982200685780834315 > required 0.24822285889822006857808343149378… |
| [`regression_test_fixed_engine.txt`](regression_test_fixed_engine.txt) | corrected line | OK |

Lemma E in `proof/lean/CommutationE.lean` covers the mathematics, not the rounding of the code.
