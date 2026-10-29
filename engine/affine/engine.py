"""A22 research engine with independent-port physical parameter boxes.
The installed adapter replaces the legacy shared-parameter settings below.
State/time enclosures remain affine. A strict subthreshold time-cover fallback
is installed after the parameter adapter. Experimental, not a qualified kernel.
"""
import sys, os, json, time, inspect, textwrap
K = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kernel')
for p in ('R_continuation_A22_2026-10-18', 'R_histoires_A21_2026-10-18', 'R_cycle_local_A20_2026-10-18', 'native'):
    sys.path.insert(0, K + '/' + p)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import intervalles_decimaux as iv
iv.configure(160)
import affine_iv
affine_iv.install()
from affine_iv import I
from decimal import Decimal as D
from experiment_parameters import PHYSICAL_EPSILON
import dependances_A17 as dep
import temporal
temporal.install(dep)
import validation_A15 as b
v = b.v; dep = b.dep
import cycle_local_A20, ready_general_A22
ready_general_A22.install()
# v3.3+C7, lemma C7 (with C6 as second resort): when the READY peak-time
# logarithm has no certified positive argument, bound the charge with the
# kernel's peak_upper, else with the piecewise pulse-memory cover.
_flow = textwrap.dedent(inspect.getsource(b.flowing))
_peak_old = ("            bb=J/(A-K);aa=q-R+bb;pk=(A*bb/(K*aa)).ln()/(A-K)\n"
             "            x=I(min(H,max(D(0),pk.lo)),min(H,max(D(0),pk.hi)))\n"
             "            assert v.ready(q,J,x).hi<1,'internal crossing inside uncertain external cluster'\n")
_peak_new = ("            bb=J/(A-K);aa=q-R+bb\n"
             "            ratio=A*bb/(K*aa) if aa.lo>0 else I(0)\n"
             "            if ratio.lo>0:\n"
             "                pk=ratio.ln()/(A-K)\n"
             "                x=I(min(H,max(D(0),pk.lo)),min(H,max(D(0),pk.hi)))\n"
             "                peak=v.ready(q,J,x).hi\n"
             "            else:peak=READY_CLUSTER_PEAK(s,tt)\n"
             "            assert peak<1 or READY_MEMORY_COVER(s,tt),'internal crossing inside uncertain external cluster'\n")
assert _flow.count(_peak_old) == 1, 'unexpected flowing() source'
b.READY_CLUSTER_PEAK = ready_general_A22.peak_upper
import cluster_memory_cover
b.READY_MEMORY_COVER = lambda s, tt: cluster_memory_cover.certify(b, s, tt)
exec(compile(_flow.replace(_peak_old, _peak_new), b.__file__, 'exec'), b.__dict__)
import avance_causale_A22 as causal
assert b.I is I and dep.I is I and v.I is I, 'affine class not installed everywhere'

# ---------------- affine roots (mean-value / interval Newton) ----------
from collections import Counter
_ROOT_HINTS = {}
ROOT_STATS = Counter()

def _piecewise_slope(deriv, l, h, pieces=(1, 8, 32)):
    """Enclosure of the derivative over [l, h]: the hull of its enclosures on
    a partition of [l, h]. Tried whole first, then on 8 and 32 equal pieces;
    a positive lower bound on every piece is a positive lower bound on the
    union. Same predicate as before, established on a finer partition."""
    l = D(l); h = D(h)
    best = deriv(I(l, h))
    if best.lo > 0 or h <= l:
        return best
    for n in pieces[1:]:
        cuts = [l] + [iv.NEAR.add(l, iv.NEAR.divide(iv.NEAR.multiply(iv.NEAR.subtract(h, l), D(k)), D(n))) for k in range(1, n)] + [h]
        cuts = sorted(set(c for c in cuts if l <= c <= h))
        parts = [deriv(I(a, b)) for a, b in zip(cuts, cuts[1:])]
        low = min(p.lo for p in parts); high = max(p.hi for p in parts)
        best = I(low, high)
        if low > 0:
            ROOT_STATS['piecewise_slopes'] += 1
            return best
    return best

def _plain_root(fun, deriv, lo, hi, guess):
    """Try a useful bracket first; every acceptance still checks both signs
    and a strictly positive slope. The original search remains the fallback.
    Hints are proposals only, cleared before every cell.
    """
    lo = D(lo); hi = D(hi); g = D(str(guess))
    assert hi > lo
    ROOT_STATS['roots'] += 1
    tag = (getattr(fun,'__code__',type(fun)),getattr(deriv,'__code__',type(deriv)))
    rad = _ROOT_HINTS.get(tag,D('1e-4'))
    def check(rad):
        ROOT_STATS['bracket_trials'] += 1
        l=max(lo,iv.DOWN.subtract(g,rad)); h=min(hi,iv.UP.add(g,rad))
        fl = fun(I(l)); fh = fun(I(h)); slope = _piecewise_slope(deriv, l, h)
        return l,h,fl.hi<=0 and fh.lo>=0 and slope.lo>0,slope.lo>0
    for _ in range(4):
        l,h,accepted,increasing=check(rad)
        if accepted:
            ROOT_STATS['hint_accepts'] += 1
            break
        if not increasing: break
        rad=iv.UP.multiply(rad,D(4))
    else:
        accepted=False
    if not accepted:
        ROOT_STATS['legacy_fallbacks'] += 1
        rad=D('1e-10')
        for _ in range(80):
            l,h,accepted,_=check(rad)
            if accepted: break
            rad=iv.UP.multiply(rad,D(4))
        else: raise v.Ambiguous(f'root bracket failed: {lo},{hi}')
    _ROOT_HINTS[tag]=rad
    x = I(l, h)
    for _ in range(18):
        m = x.mid(); slope = _piecewise_slope(deriv, x.lo, x.hi)
        assert slope.lo > 0
        y = x.intersect((I(m) - fun(I(m)) / slope).plain())
        y = y.plain()
        if y.width() >= iv.NEAR.divide(x.width(), D(2)): x = y; break
        x = y
    return x

def affine_refine(fun, deriv, T, steps=3):
    """t*(eps) = m - f(m,eps)/f'(xi,eps), xi in plain T, for every eps."""
    best = T
    for _ in range(steps):
        T = T.plain()
        m = T.mid(); S = deriv(T)
        if not S.lo > 0: return best
        N = I(m) - fun(I(m)) / S
        # Prefer the correlated form unless it is clearly wider.
        if N.symbolic() and N.width() <= iv.UP.multiply(T.width(), D('1.1')): best = N
        elif N.width() < best.width(): best = N
        R = I(max(N.lo, T.lo), min(N.hi, T.hi))
        if R.width() >= T.width(): break
        T = R
    return best

def root(fun, deriv, lo, hi, guess):
    T = _plain_root(fun, deriv, lo, hi, guess)
    return affine_refine(fun, deriv, T)
v.root = root

_orig_ready_root = b.ready_root
def ready_root(q, J, hi):
    T = _orig_ready_root(q, J, hi).plain()
    bb = J / (b.A - b.K)
    f = lambda u: v.ready(q, J, u) - 1
    df = lambda u: -b.K * (q - b.R + bb) * (-b.K * u).exp() + b.A * bb * (-b.A * u).exp()
    return affine_refine(f, df, T)
b.ready_root = ready_root

# ---------------- smooth monotone responses evaluated on affine arguments
_orig_h, _orig_dh = dep.h, dep.dh
def h(u):
    assert 0 <= u.lo <= u.hi <= 1
    if not u.symbolic(): return _orig_h(u)
    return dep.hp(u)
def dh(u):
    assert 0 <= u.lo <= u.hi <= 1
    if not u.symbolic(): return _orig_dh(u)
    return dep.dp(u)
dep.h = h; dep.dh = dh
ac = b.ac
_orig_primitive = ac.primitive
def primitive(age, finished=False):
    if finished or not (age.symbolic() or ac.LAM.symbolic()): return _orig_primitive(age, finished)
    if age.lo < 0: return _orig_primitive(age, finished)
    lam = ac.LAM; x = age; threshold = I('1.25').ln(); lx = lam * x
    if lx.hi <= threshold.lo: val = ac.EB * (x - (1 - (-lam * x).exp()) / lam)
    elif lx.lo >= threshold.hi: val = ac.STEP * (x - (1 - 4 * threshold) / lam)
    else: return _orig_primitive(age, finished)
    return val if val.lo >= 0 else _orig_primitive(age, finished)
ac.primitive = primitive

_orig_capped = ac.capped_dose
def capped_dose(h, t, live=False):
    """For nondecreasing raw rate r capped at B, the capped dose over [0,X] is
    min_y R(y) + B(X-y), attained at the contact time.  At a point y0 of the
    certified contact bracket [lower,upper] the value exceeds the dose by at
    most (upper-lower)*max(|r(lower)-B|,|r(upper)-B|)."""
    section = h.fire.plus(1); duration = t.minus(section).nonnegative()
    if h.saturated or ac.raw_rate(h, section).lo >= ac.BMAX.hi: return ac.BMAX * duration
    uncapped = ac.raw_dose(h, t, live)
    if ac.raw_rate(h, t, live).hi <= ac.BMAX.lo: return uncapped
    lower, upper, certain = ac.contact(h, section, duration.hi)
    if not (certain and duration.lo >= upper and upper > lower):
        return _orig_capped(h, t, live)
    y0 = I(lower, upper).mid()
    rl = ac.raw_rate(h, section.plus(lower)) - ac.BMAX; ru = ac.raw_rate(h, section.plus(upper)) - ac.BMAX
    dev = max(rl.lo.copy_abs(), rl.hi.copy_abs(), ru.lo.copy_abs(), ru.hi.copy_abs())
    err = iv.UP.multiply(iv.UP.subtract(upper, lower), dev)
    value = ac.raw_dose(h, section.plus(y0)) + ac.BMAX * (duration - I(y0)) - I(0, err)
    return value.intersect(I(0, (ac.BMAX * duration).hi)).intersect(I(0, uncapped.hi))
ac.capped_dose = capped_dose

# ---------------- per-cell symbolic device and initial state ------------
_src = textwrap.dedent(inspect.getsource(b.unit))
_old = "s=dict(t=v.T('initial_slab',U0),q=R+I(-DELTA.hi,DELTA.hi)*(-K*U0).exp()+I(0,(3*C*A*U0).hi),\n        z=[I(g).ln()+I(-DELTA.hi,(9*DELTA).hi) for g in ('.3','1.2','.3')],b=I('.08')+I(-DELTA.hi,DELTA.hi),"
assert _old in _src
_src = _src.replace(_old, "s=dict(t=v.T('initial_slab',U0),q=R+INIT['q']*(-K*U0).exp()+I(0,(3*C*A*U0).hi),\n        z=[I(g).ln()+INIT['z'][i] for i,g in enumerate(('.3','1.2','.3'))],b=I('.08')+INIT['b'],")
_src = _src.replace('D1 if k==0 else D0','D1_PORTS[j] if k==0 else D0_PORTS[j]')
# Fix P (v3.3): auxiliary event durations of port j use port j's constants.
_old_aux = "off=shift(mon,DM,f'{cell}:mo:{j}:{k}');err=shift(off,DS,f'{cell}:e:{j}:{k}');end=shift(err,DE,f'{cell}:eo:{j}:{k}')"
assert _src.count(_old_aux) == 1
_src = _src.replace(_old_aux, "off=shift(mon,DM_PORTS[j],f'{cell}:mo:{j}:{k}');err=shift(off,DS_PORTS[j],f'{cell}:e:{j}:{k}');end=shift(err,DE_PORTS[j],f'{cell}:eo:{j}:{k}')")
# Retain the terminal affine state and all histories in every cell artifact.
_src = _src.replace('return out,dict(q=', 'return out,dict(terminal_affine=s,q=')
# Fix E (v3): a refused READY order between the fire and pure arrivals is
# resolved by enclosing both orders (affine/commutation.py).  The original
# refusal is re-raised unchanged whenever the commutation preconditions fail.
import commutation
_hook_group_old = "            s,kind=advance(s,L,cell,count);count+=1\n"
_hook_group_new = ("            try:s,kind=advance(s,L,cell,count)\n"
                   "            except v.Ambiguous:\n"
                   "                _c=COMMUTE(s,pending,idx,stopidx,suffix,cell,count)\n"
                   "                if _c is None:\n"
                   "                    _r=RECOVERY_GROUP(s,pending,idx,cell,count)\n"
                   "                    if _r is None:raise\n"
                   "                    s,_k,_n,_m=_r;idx=_k;count+=_n;clusters+=1;branches+=_m\n"
                   "                    continue\n"
                   "                s,_f,_n,_k=_c;out.append(_f);count+=_k-idx+1;idx=_k;clusters+=1;branches+=_n\n"
                   "                continue\n"
                   "            count+=1\n")
# Fix R (v3.3): a protected slow-recovery return (p=2) that overlaps an
# exterior event GROUP is routed to the kernel's own certified local-cycle
# resolver (cycle_local_A20.pending_window), exactly as unit() already does
# for a single exterior event.  The resolver enumerates every admissible
# order of the return and the events; only a forest whose branches all end
# READY with no emission is joined (same rule as the single-event path).
# Anything else re-raises the original refusal.
import recovery_group
b.RECOVERY_GROUP = lambda s, pending, idx, cell, count: recovery_group.resolve(b, s, pending, idx, cell, count)
_hook_single_old = ("            try:s,kind=advance(s,tt,cell,count)\n"
                    "            except v.Ambiguous:\n"
                    "                if s['p']!=2:raise\n")
_hook_single_new = ("            try:s,kind=advance(s,tt,cell,count)\n"
                    "            except v.Ambiguous:\n"
                    "                _c=COMMUTE(s,pending,idx,stopidx,suffix,cell,count)\n"
                    "                if _c is not None:\n"
                    "                    s,_f,_n,_k=_c;out.append(_f);count+=_k-idx+1;idx=_k;clusters+=1;branches+=_n\n"
                    "                    continue\n"
                    "                if s['p']!=2:raise\n")
# Same situation inside an exterior cluster: the guard-free order enumeration
# asserts 'internal crossing inside uncertain external cluster'.  Only that
# assertion is intercepted, and only for a READY state with pure arrivals.
_hook_cluster_old = ("            U=v.T(f'{cell}:U:{count}',I(upper));poss=[]\n"
                     "            for order in admissible_orders(s,group):\n"
                     "                ss=s\n"
                     "                for tt,actions in order:ss=act(flowing(ss,tt,True),actions)\n"
                     "                ss=flowing(ss,U,True);poss.append(ss)\n")
_hook_cluster_new = ("            U=v.T(f'{cell}:U:{count}',I(upper));poss=[]\n"
                     "            try:\n"
                     "                for order in admissible_orders(s,group):\n"
                     "                    ss=s\n"
                     "                    for tt,actions in order:ss=act(flowing(ss,tt,True),actions)\n"
                     "                    ss=flowing(ss,U,True);poss.append(ss)\n"
                     "            except AssertionError as _refusal:\n"
                     "                if str(_refusal)!='internal crossing inside uncertain external cluster':raise\n"
                     "                _c=COMMUTE(s,pending,idx,stopidx,suffix,cell,count)\n"
                     "                if _c is None:raise\n"
                     "                s,_f,_n,_k=_c;out.append(_f);count+=_k-idx;idx=_k;clusters+=1;branches+=_n\n"
                     "                continue\n")
assert (_src.count(_hook_group_old) == 1 and _src.count(_hook_single_old) == 1
        and _src.count(_hook_cluster_old) == 1), 'unexpected unit() source'
_src = (_src.replace(_hook_group_old, _hook_group_new).replace(_hook_single_old, _hook_single_new)
        .replace(_hook_cluster_old, _hook_cluster_new))
b.COMMUTE = lambda s, pending, idx, stop, suffix, cell, count: commutation.resolve(b, s, pending, idx, stop, suffix, cell, count)
exec(compile(_src, b.__file__, 'exec'), b.__dict__)
# Fix P (v3.3): the mark current and the error-deposit current of port j
# decay with port j's own LM_j and LE_j.
_coef = textwrap.dedent(inspect.getsource(b.coefficients))
for _o, _n in (("(-LE*t.minus(s['err'][j]))", "(-LE_PORTS[j]*t.minus(s['err'][j]))"),
               ("(-LM*t.minus(s['mark'][j]))", "(-LM_PORTS[j]*t.minus(s['mark'][j]))")):
    assert _coef.count(_o) == 1, 'unexpected coefficients() source'
    _coef = _coef.replace(_o, _n)
exec(compile(_coef, b.__file__, 'exec'), b.__dict__)

# ---------------- fix A: event order from the correlated time difference --
# x(eps)-tt(eps) >= 0 for every eps proves tt first even when the absolute
# date boxes overlap; this is pointwise and therefore sound.
_adv = textwrap.dedent(inspect.getsource(b.advance))
# Lemma C7 in advance(): same fallback before the peak logarithm.
_advance_peak_old = "            bb=J/(A-K);aa=q-R+bb;pk=(A*bb/(K*aa)).ln()/(A-K)\n"
_advance_peak_new = ("            bb=J/(A-K);aa=q-R+bb\n"
                     "            ratio=A*bb/(K*aa) if aa.lo>0 else I(0)\n"
                     "            if ratio.lo<=0:\n"
                     "                if READY_CLUSTER_PEAK(s,boundary)<1:return flowing(s,boundary),'external'\n"
                     "                raise v.Ambiguous('ready guard still overlaps external boundary or possible tangency')\n"
                     "            pk=ratio.ln()/(A-K)\n")
assert _adv.count(_advance_peak_old) == 1, 'unexpected advance() peak source'
_adv = _adv.replace(_advance_peak_old, _advance_peak_new)
_old_order = "if not all(tt.box().hi<=x.box().lo for x,_,_ in candidates[1:]):"
assert _adv.count(_old_order) == 1
_adv = _adv.replace(_old_order, "if not all(x.minus(tt).lo>=0 for x,_,_ in candidates[1:]):")
exec(compile(_adv, b.__file__, 'exec'), b.__dict__)

# ---------------- fix B: sound affine min/max in clip/cap/clamp sites -----
import sound_lattice
SOUND_LATTICE_EDITS = sound_lattice.install({'actuations_A19': b.ac, 'depot_A19': b.dz, 'dependances_A17': dep})

def settings_cell(cell):
    """validation_A15.settings with each +/-EPS box replaced by a named symbol."""
    v.constants(); b.A = v.A; b.K = v.K; b.R = v.R; b.RM = v.RM
    b.DELTA = I('1e-5'); b.EPS = I(PHYSICAL_EPSILON)
    A, K, R, RM, DELTA = b.A, b.K, b.R, b.RM, b.DELTA
    dep.configure(A, K, R)
    sym = lambda name: 1 + I.symbol(f'{cell}:{name}', PHYSICAL_EPSILON)
    b.C = 4 * sym('C'); b.Z = b.C.ln()
    b.LM = v.LM * sym('LM'); b.LS = v.LS * sym('LS'); b.LE = v.LE * sym('LE'); b.M = v.M * sym('M')
    M, LE, LM, LS = b.M, b.LE, b.LM, b.LS
    def hh(u): return A / (A - K) * ((-K * u).exp() - (-A * u).exp())
    def dh(u): return A / (A - K) * (A * (-A * u).exp() - K * (-K * u).exp())
    b.U0 = I((2 * DELTA / (LE * RM)).hi); U0 = b.U0
    init = I(-DELTA.hi, DELTA.hi)
    fn = lambda u: RM + M * hh(u) - 1
    b.D0 = v.root(fn, lambda u: M * dh(u), D(0), D('.1'), .02)
    fn = lambda u: RM + init * (-K * u).exp() + M * hh(u) - 1
    df = lambda u: -K * init * (-K * u).exp() + M * dh(u)
    fast = v.root(fn, df, D(0), D('.1'), .02)
    att = (-A * U0).exp()
    fn = lambda u: RM + init * (-K * u).exp() + M * att * hh(u) - 1
    df = lambda u: -K * init * (-K * u).exp() + M * att * dh(u)
    slow = v.root(fn, df, D(0), D('.1'), .02)
    D1 = I(fast.lo, (U0 + slow).hi); m1 = D1.mid()
    r1 = max(iv.UP.subtract(D1.hi, m1), iv.UP.subtract(m1, D1.lo))
    b.D1 = D1.plain()
    b.D1_PORTS = tuple(I(m1)+I.symbol(f'{cell}:D1:{j}',r1) for j in range(3))
    b.DM = I('1.25').ln() / LM; b.DS = I(8).ln() / LS; b.DE = I(4).ln() / LE
    b.ac.configure(LM); b.dz.configure(LE, b.Z)
    assert (b.D1+b.DM+b.DS+b.DE).hi<D('1.3') and U0.hi<b.D1.lo and b.D1.hi<D('.1')
    assert (b.D0+b.DM+b.DS+b.DE).lo>1 and (b.D1+b.DM+b.DS+b.DE).lo>1
    assert (b.D0+b.DM+b.DS).lo>1 and (b.D1+b.DM+b.DS).lo>1
    assert (R+DELTA+3*b.C*A*U0).hi<D('.2') and (RM+DELTA+M*A*U0).hi<1
    assert LM.lo>(I('.8')*LS).hi and LM.lo>(I('.1')*LE).hi
    work=(3*b.C+3*M+1)*A+I('1.1')+I('4.5')*LM+I('2.4')*LE
    assert work.hi<270 and work.hi<500 and b.C.lo>D('3.9') and M.hi<40
    b.D0_PORTS = (b.D0,) * 3; b.DM_PORTS = (b.DM,) * 3; b.DS_PORTS = (b.DS,) * 3; b.DE_PORTS = (b.DE,) * 3
    b.LM_PORTS = (b.LM,) * 3; b.LE_PORTS = (b.LE,) * 3
    b.INIT = dict(q=I.symbol(f'{cell}:q0', '1e-5'),
                  z=[I('4e-5') + I.symbol(f'{cell}:z{j}', '5e-5') for j in range(3)],
                  b=I.symbol(f'{cell}:b0', '1e-5'))

# ---------------- import-safe physical entry point ----------------------
orig_advance=b.advance
b.advance=lambda s,bd,cell,count:causal.advance(s,bd,cell,count,orig_advance)

def compute_cell(layer,lane,trains,namespace):
    """Fresh calculation only. The external runner stores/reloads each result."""
    import resource
    _ROOT_HINTS.clear();ROOT_STATS.clear()
    temporal.begin_producer(namespace)
    affine_iv.FRESH=namespace+':remainder'
    affine_iv._COUNTER[0]=0
    started=time.perf_counter();cpu=time.process_time()
    settings_cell(namespace)
    inputs=tuple(trains[j] for j in ((lane-1)%12,lane,(lane+1)%12))
    outputs,state=b.unit(inputs,f'{layer},{lane}:aff')
    boxes=[t.box() for t in outputs]
    return {'outputs':tuple(outputs),'state':state,'metrics':{
        'layer':layer,'lane':lane,'pulses':len(outputs),'clusters':state['clusters'],
        'orders':state['orders_enclosed'],'max_width':str(max((x.width() for x in boxes),default=D(0))),
        'elapsed_seconds':time.perf_counter()-started,'cpu_seconds':time.process_time()-cpu,
        'root_search':dict(ROOT_STATS),
        'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}}

# Repr of marginal intervals is not an identity for a correlated history.
from dataclasses import is_dataclass,fields

def history_key(x):
    if isinstance(x,I):return ('affine',x.fingerprint())
    if isinstance(x,temporal.Time):return ('time',x.key,x.base.fingerprint(),x.offset,tuple((k,n,v.fingerprint()) for k,n,v in x.terms))
    if is_dataclass(x):return (type(x).__module__,type(x).__name__,tuple(history_key(getattr(x,f.name)) for f in fields(x)))
    if isinstance(x,(tuple,list)):return (type(x).__name__,tuple(history_key(v) for v in x))
    return x

# ---------------- fix H (v3.1): exact folding + sound merge of histories --
# A completed contribution enters the physics only through a sum:
#   actuation  baseline(h) = initial + STEP*full + sum transfer(partial)
#   deposit    offered(h)  = initial + .6*full   + sum transfer(partial) + active
# (actuations_A19.baseline, depot_A19.offered; finish/close_gate only extend
# full/partial).  Folding those terms into `initial` is therefore an exact
# identity.  Histories whose remaining structure (fire, marks, saturation /
# active segment, clamp) is identical then differ only by `initial`, which
# enters additively: replacing the group by one history whose initial is the
# affine union (hull) of theirs encloses every member pointwise.  Depot
# `conditions` are branch labels never read numerically.  Applied only above
# SOFT histories, so ordinary cells compute exactly as in v3.
SOFT_HISTORIES = 32
HISTORY_STATS = {'compressions': 0, 'merged_away': 0}

def _fold(h):
    ac, dz = b.ac, b.dz
    if isinstance(h, ac.History):
        if h.saturated or (h.full == 0 and not h.partial):return h
        return ac.History(ac.baseline(h), 0, (), h.fire, h.marks, False)
    if isinstance(h, dz.History):
        if h.clamped or (h.full == 0 and not h.partial and not h.conditions):return h
        initial = h.initial + I('.6') * h.full + sum((dz.transfer(seg, dz.LAM, '.1', '.025', 8) for seg in h.partial), I(0))
        return dz.History(initial, 0, (), h.active, False, ())
    return h

def _structure(h):
    if isinstance(h, b.ac.History):
        return ('actuation', h.saturated, history_key(h.fire), history_key(h.marks), h.full, len(h.partial))
    if isinstance(h, b.dz.History):
        return ('deposit', h.clamped, history_key(h.active), h.full, len(h.partial), len(h.conditions))
    return ('other', history_key(h))

def _compress(hs):
    from dataclasses import replace
    groups = {}
    for h in map(_fold, hs):
        groups.setdefault(_structure(h), []).append(h)
    out = []
    for key, members in groups.items():
        if len(members) == 1 or key[0] == 'other' or key[1]:   # saturated/clamped: exact copies only
            out.extend(members);continue
        merged = replace(members[0], initial=affine_iv.hull([m.initial for m in members]))
        HISTORY_STATS['merged_away'] += len(members) - 1
        out.append(merged)
    HISTORY_STATS['compressions'] += 1
    return out

def unique_histories(histories,limit=128):
    seen={}
    for h in histories:
        k=history_key(h)
        if k not in seen:seen[k]=h
    if len(seen)>SOFT_HISTORIES:
        compressed={}
        for h in _compress(list(seen.values())):
            k=history_key(h)
            if k not in compressed:compressed[k]=h
        seen=compressed
    if len(seen)>limit:raise RuntimeError(f'disjunction budget exceeded: {len(seen)}>{limit}')
    return tuple(seen.values())
b.ac.unique=unique_histories
b.dz.unique=unique_histories

# ---------------- fix S (v3.2): physical caps of history unions -------------
# Each recovery rate is capped (actuations_A19.rate = clip at BMAX) and each
# log-gain is capped (depot_A19.value = min(., TARGET)), pointwise.  The union
# over histories is therefore also <= the cap pointwise, but the common-
# generator hull (v3) may enclose it in a form whose range slightly exceeds
# the cap, which trips the kernel invariants 'recovery saturation invariant'
# (b.hi <= 1.1) and 'gain saturation invariant' (z.hi <= Z.hi) although no
# physical value does.  Only in that case the union is intersected with the
# plain envelope of the members [min lo_i, max hi_i]; every member, hence the
# truth, lies in both enclosures, so the intersection is sound.  Away from
# saturation nothing changes.
CAP_STATS = {'rate': 0, 'gain': 0}
_orig_ac_bounds = b.ac.bounds
_orig_dz_bounds = b.dz.bounds

def _capped_union(values, cap_hi, kind):
    res = affine_iv.hull(values)
    if res.hi > cap_hi:
        plain = I(min(v.lo for v in values), max(v.hi for v in values))
        res = res.intersect(plain)
        CAP_STATS[kind] += 1
    return res

def ac_bounds(histories, t, quantity='rate', live=True):
    if quantity == 'ell':
        return _orig_ac_bounds(histories, t, quantity, live)
    return _capped_union([b.ac.rate(h, t, live) for h in histories], b.ac.BMAX.hi, 'rate')

def dz_bounds(histories, t):
    return _capped_union([b.dz.value(h, t) for h in histories], b.dz.TARGET.hi, 'gain')

b.ac.bounds = ac_bounds
b.dz.bounds = dz_bounds

# Independent physical-port parameter scope: conservative box adapter.
import port_box_adapter as _port_box_candidate
_port_box_candidate.install(sys.modules[__name__])

# Fix P (v3.3): one symbol per physical port, used only for that port.
import port_symbols as _port_symbols
PORT_SYMBOLS = _port_symbols.install(sys.modules[__name__])

# Strict subthreshold time-cover fallback; no physical or parameter change.
import nofire_cover as _nofire_cover
_nofire_cover.install(sys.modules[__name__])
