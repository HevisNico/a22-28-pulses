"""Strict no-fire cover for an already admitted READY pulse memory.

Only used when the legacy q/current peak bound fails. No new input is
admitted within this flow; dep.evaluate preserves the correlations between
the current charge and the ages/amplitudes of admitted pulses. All closed
time pieces must have charge upper bound strictly below one. Otherwise the
original refusal is preserved. Experimental: new campaign identity required.
"""
STATS = {'attempts': 0, 'resolved': 0, 'refused': 0, 'pieces': 0}

def certify(b, s, tt, max_depth=8):
    STATS['attempts'] += 1
    if s['p'] != 0 or s.get('memory') is None:
        STATS['refused'] += 1
        return False
    I, D = b.I, b.D
    H = tt.minus(s['t']).nonnegative().hi
    stack = [(D(0), H, 0)]
    import intervalles_decimaux as iv
    while stack:
        lo, hi, depth = stack.pop()
        probe = b.shift(s['t'], I(lo, hi), 'READY-memory-cover')
        charge = b.dep.evaluate(s['memory'], probe)
        STATS['pieces'] += 1
        if charge.hi < 1:
            continue
        if depth >= max_depth:
            STATS['refused'] += 1
            return False
        mid = iv.NEAR.divide(iv.NEAR.add(lo, hi), D(2))
        if not lo < mid < hi:
            STATS['refused'] += 1
            return False
        stack.append((mid, hi, depth + 1))
        stack.append((lo, mid, depth + 1))
    STATS['resolved'] += 1
    return True
