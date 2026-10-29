"""Fix E (v3): a READY fire and pure input arrivals need no order decision.

Situation refused by v2: in READY mode the first threshold crossing f0 of the
current trajectory and an input arrival a (raw_on only) have overlapping
enclosures of their difference, so advance() cannot prove which is first.

Instead of deciding the order we enclose BOTH orders and join them, exactly as
the kernel already does for uncertain orders of exterior events.

Notation (READY, memory present).  Q0(t) = dep.evaluate(memory,t) is the
charge without the new arrivals; f0 is its first crossing of 1, obtained
with the kernel's own candidate construction (same guard functions, same
peak bound, same certified root).  An arrival of port j at a_j adds the
nonnegative term g_j*h(t-a_j) (dep.add / dep.evaluate are additive), so the
actual charge Q satisfies Q = Q0 before the first arrival and Q >= Q0 after.

Lemma 1 (no order needed).  The actual fire date F satisfies, for every
parameter point,  min(a_min,f0) <= F <= f0.
  F <= f0 because Q(f0) >= Q0(f0) = 1; F >= min(a_min,f0) because Q = Q0 < 1
  on [t0, min(a_min,f0)).
Lemma 2 (tightening).  Let sigma <= Q0' on the elapsed window
[min(a_i)-t0, f0-t0] and G >= sum_j g_j.  On [0,1], h(0)=0 and h' <= A
(h''<0 on [0, 2 ln(A/K)/(A-K)], checked below), so h(u) <= A u.  For t in
[a_min,f0]:  Q(t) <= 1 - sigma (f0-t) + G A (t-a_min)  < 1  while
t < (sigma f0 + G A a_min)/(sigma + G A).  Hence
        F >= f0 - kappa (f0-a_min)^+,   kappa = G A/(sigma + G A) in (0,1].
With sigma unavailable kappa = 1 (Lemma 1).

The emitted date is Fhat = t0 + (r0 + [-kappa*w, 0]), w >= (f0-a_min)^+,
which encloses F in every branch.  Each admissible order of the arrivals and
each position k of the fire among them is computed with the UNCHANGED
kernel maps (flowing, act, fire_reset) and all branches are joined at a
common clock U after every event of the group and before the next pending
event and before the end of the fast section.  Post-fire states differ only
through the fire date (the arrival's pulse is discarded by the reset, admission
is closed after the fire, raw/aux/mark flags are identical); join_states
retains every actuation/deposit history.

Any failed precondition returns None and the caller re-raises the ORIGINAL
refusal: this path can only replace a refusal, never a v2 decision.
"""
import intervalles_decimaux as iv
from decimal import Decimal as D
from affine_iv import I

STATS = {'attempts': 0, 'resolved': 0, 'declined': {}}


def _no(reason):
    STATS['declined'][reason] = STATS['declined'].get(reason, 0) + 1
    return None


def _check_pulse_slope(b):
    # h''<0 on [0,1] <=> 1 < 2 ln(A/K)/(A-K); then h(u) <= h'(0) u = A u on [0,1].
    assert (2 * (b.A / b.K).ln() / (b.A - b.K)).lo > 1


def _fire_root(b, s, H, cell, count):
    """validation_A15.advance READY fire candidate, with horizon H (plain)."""
    v, dep = b.v, b.dep
    A, K, R = b.A, b.K, b.R
    q = s['q']; J, _, _ = b.coefficients(s)
    memory = s.get('memory')
    if memory is None or not J.hi > 0 or not H > 0:
        return None
    bb = J / (A - K); aa = q - R + bb; pk = (A * bb / (K * aa)).ln() / (A - K)
    peak = I(max(D(0), pk.lo), max(D(0), pk.hi)); x = I(min(H, peak.lo), min(H, peak.hi))
    legacy_max = v.ready(q, J, x)
    probe = lambda u: b.shift(s['t'], u, f'{cell}:{count}:commute-probe')
    f = lambda u: dep.evaluate(memory, probe(u)) - 1
    df = lambda u: dep.evaluate(memory, probe(u), True)
    memory_max = dep.evaluate(memory, probe(I(0, H)))
    if not min(legacy_max.hi, memory_max.hi) >= 1:
        return None
    hi = min(H, peak.lo)
    if not hi > 0 or f(I(hi)).lo < 0:
        return None
    try:
        return v.root(f, df, D(0), hi, v.guessroot(f, hi)), df
    except (v.Ambiguous, ValueError, AssertionError):
        STATS['cover_roots'] = STATS.get('cover_roots', 0) + 1
        root = _first_crossing_cover(f, hi)
        return (root, df) if root is not None else None


def _first_crossing_cover(f, hi, depth=12):
    """Enclosure of F = inf{u in [0,hi] : Q(t0+u) >= 1} without any slope
    assumption (same idea as garde_relative_A22.cover).  Requires Q(t0) < 1
    and Q(t0+hi) >= 1 for every parameter point.  Left-to-right bisection:
      - a piece with f.hi < 0 contains no point with Q >= 1  -> F is later;
      - the first piece with f.lo >= 0 bounds F from above by its left end;
    so F lies in [left end of the first undecided piece, upper].  Plain
    (uncorrelated) result: sound, possibly wide."""
    if not f(I(0)).hi < 0:
        return None
    lower = None; upper = hi
    stack = [(D(0), hi, 0)]
    while stack:
        a, z, n = stack.pop()
        if lower is not None and a >= upper:
            continue
        val = f(I(a, z))
        if val.hi < 0:
            continue                      # Q < 1 on [a,z]
        if val.lo >= 0:
            upper = min(upper, a)         # Q >= 1 on [a,z]
            if lower is None: lower = a
            continue
        if n >= depth or a == z:
            if lower is None: lower = a     # leftmost undecided piece
            continue
        m = iv.NEAR.divide(iv.NEAR.add(a, z), D(2))
        stack.append((m, z, n + 1)); stack.append((a, m, n + 1))   # left first
    if lower is None or lower > upper:
        return None
    return I(lower, upper)


AUXILIARY = ('mark_on', 'mark_off', 'error_on', 'error_off')
MAX_EVENTS = 8


class _Extend(Exception):
    """The fire may reach the next pending event: widen the window."""


def resolve(b, s, pending, idx, stop, suffix, cell, count):
    """Return (joined state at U, fire date, branch count, next index) or None.

    The window starts with the refused overlap group pending[idx:stop]; it is
    extended (overlap-closed, as the kernel does) while the fire enclosure can
    reach the next pending event, within one fast section and MAX_EVENTS."""
    STATS['attempts'] += 1
    while True:
        try:
            out = _resolve(b, s, pending[idx:stop], suffix[stop], cell, count)
        except _Extend as why:
            if stop >= len(pending) or stop - idx >= MAX_EVENTS:
                return _no(f'window limit reached ({why})')
            upper = max(t.box().hi for t, _ in pending[idx:stop + 1])
            stop += 1
            while stop < len(pending) and upper > suffix[stop]:
                upper = max(upper, pending[stop][0].box().hi); stop += 1
            continue
        except (b.v.Ambiguous, AssertionError, ArithmeticError, ValueError, ZeroDivisionError) as e:
            return _no(f'{type(e).__name__}: {str(e)[:120]}')
        if out is None:
            return None
        STATS['resolved'] += 1
        return out + (stop,)


def _resolve(b, s, group, next_lo, cell, count):
    if s['p'] != 0 or s.get('memory') is None or not group:
        return _no('state is not READY with a pulse memory')
    arrivals = []          # raw_on dates: they add a pulse (Lemmas 1-2)
    added = set()
    for tt, actions in group:
        for action, j, origin in actions:
            if action == 'raw_on':
                arrivals.append(tt); added.add((j, origin.token()))
            elif action == 'raw_off':
                # Lemma 0: the memory term of this input already stops its
                # admission at origin+1 (dep.pulse / dep.tail), so in READY
                # the raw_off event leaves Q(t) unchanged; act() only clears
                # the flag.  Require exactly that term and that exact date.
                key = (j, origin.token())
                if key not in s['memory']['pulses'] and key not in added:
                    return _no('raw_off input absent from memory')
                if tt.token() != origin.plus(1).token():
                    return _no('raw_off date is not origin+1')
            elif action in AUXILIARY:
                # Lemma 0': in READY, act() changes only flags, actuation and
                # deposit histories; Q = dep.evaluate(memory) is untouched
                # (pulse amplitudes are fixed at admission).  The histories of
                # every order are computed explicitly and all are retained.
                pass
            else:
                return _no(f'non-commuting action {action}')
    _check_pulse_slope(b)
    t0 = s['t']
    if any(tt.minus(t0).hi < 0 for tt, _ in group):
        return _no('_resolve: event precedes the state')
    da = [a.minus(t0) for a in arrivals]
    # Horizon strictly before the next pending event.
    H = iv.DOWN.subtract(D(next_lo), t0.box().hi) if D(next_lo).is_finite() else D(1)
    H = iv.DOWN.multiply(min(H, D(1)), D('0.999999999'))
    found = _fire_root(b, s, H, cell, count)
    if found is None:
        if D(next_lo).is_finite(): raise _Extend('no certified crossing before the next event')
        return _no('no certified crossing')
    r0, df = found
    # w >= (f0 - a_min)^+ for every parameter point.
    w = max([(r0 - x).hi for x in da] + [D(0)])
    if not w < 1:
        return _no('arrival window >= 1')
    # Pass 1: every admissible arrival order and every fire position k.
    orders = list(b.admissible_orders(s, group))
    if not orders:
        return _no('no admissible order')
    prefixes = []
    gains = D(0)
    for order in orders:
        ss = s
        prefixes.append((order, 0, ss))
        for k, (tt, actions) in enumerate(order, 1):
            ss = b.act(b.flowing(ss, tt, False), actions)
            prefixes.append((order, k, ss))
        added = D(0)
        for _, actions in order:
            for action, j, origin in actions:
                if action != 'raw_on':
                    continue
                # The exact amplitude stored by act() -> dep.add for this pulse.
                g = ss['memory']['pulses'][(j, origin.token())]['g']
                added = iv.UP.add(added, g.hi)
        gains = max(gains, added)
    # Lemma 2 when a positive slope bound exists on the window, else kappa=1.
    kappa = D(1)
    if w > 0:
        lo = max(D(0), min(x.lo for x in da))
        sigma = df(I(lo, max(lo, r0.hi))).lo
        if sigma > 0:
            ga = iv.UP.multiply(gains, b.A.hi)
            kappa = min(D(1), iv.UP.divide(ga, iv.DOWN.add(sigma, ga)))
    delta = iv.UP.multiply(kappa, w)
    rho = r0 + I(delta.copy_negate(), D(0)) if delta > 0 else r0
    fire = b.shift(t0, rho, f'{cell}:{count}:commuted-fire')
    upper = max([fire.box().hi] + [tt.box().hi for tt, _ in group])
    if not upper < D(next_lo):
        raise _Extend('fire may reach the next event')
    if not upper < fire.plus(1).box().lo:
        return _no('window reaches the end of the fast section')
    U = b.v.T(f'{cell}:commute-U:{count}', I(upper))
    # Pass 2: fire at the common enclosure, remaining arrivals after it.
    poss = []
    for order, k, ss in prefixes:
        ss = b.fire_reset(b.flowing(ss, fire, False))
        for tt, actions in order[k:]:
            ss = b.act(b.flowing(ss, tt, True), actions)
        poss.append(b.flowing(ss, U, True))
    first = poss[0]
    assert all(x['p'] == 1 and x['aux'] == first['aux'] and x['fire'] is fire and
               [(t.token() if t else None) for t in x['raw']] == [(t.token() if t else None) for t in first['raw']]
               for x in poss)
    joined = b.join_states(poss, dict(cell=cell, batch=count, orders=len(poss), kind='fire_arrival_commutation'))
    joined['fire'] = fire
    if b.PROFILE is not None:
        b.PROFILE.guard('fire', fire)
        b.PROFILE.relative_order_proofs.append(dict(cell=cell, batch=count, guard='fire_arrival_commutation',
            arrivals=len(group), branches=len(poss), kappa=str(kappa), widening=str(delta),
            fire=fire.box().pair(), join_time=U.box().pair(),
            events=[[a for a, _, _ in acts] for _, acts in group],
            predicate='min(a_min,f0) <= F <= f0 and F >= f0-kappa*(f0-a_min)^+ ; Q unchanged by raw_off/auxiliary actions; post-fire states of every order joined'))
    return joined, fire, len(poss)
