"""F01 local regressions: analytic inclusions, no saved network history.

Run: python3 -B test_ready_general_A22.py
The decimal reference evaluates the closed solution at 300 digits; the
coverage argument itself is stated separately in NOTE_F01_READY_A22.md.
"""
from pathlib import Path
from decimal import Decimal, localcontext
import json
import campagne_A22  # Paths and time-arithmetic safety installation only.
import validation_A15 as b
import cycle_local_A20 as cyc
import dependances_A17 as dep
import actuations_A19 as ac
import depot_A19 as dz
import intervalles_decimaux as iv
import garde_relative_A22 as guards
import ready_general_A22 as general
import histoires_A21 as histories
import ordonnanceur_A22 as scheduler
import groupe_pret_feu_A22 as ready_cluster
from intervalles_decimaux import I, D

ROOT = Path(__file__).resolve().parent


def check(condition, label):
    if not condition:
        raise RuntimeError(label)


def contains(interval, point, label):
    check(interval.lo <= point <= interval.hi,
          f'{label}: {point} excluded from {interval.pair()}')


def state(q, current_gain=None, start=None):
    t = dep.Time('F01:start', I(0)) if start is None else start
    z = [I('.3').ln(), I('1.2').ln(), I('.3').ln()]
    raw = [None]*3
    if current_gain is not None:
        z[0] = I(current_gain).ln()
        raw[0] = t
    out = dict(t=t, q=q, z=z, b=I('.07999', '.08001'), p=0,
               raw=raw, aux=[0]*3, mark=[None]*3, err=[None]*3,
               caps=[False]*3, bstop=False, fire=None)
    out['actuation'] = (ac.History(out['b']),)
    out['depot'] = tuple((dz.History(v),) for v in z)
    out['memory'] = b.new_memory(out)
    return out


def exact_no_current(q0, elapsed):
    with localcontext() as ctx:
        ctx.prec = 300
        return D('.1') + (D(q0)-D('.1')) * (-D('.5')*D(elapsed)).exp()


def exact_current(q0, gain, elapsed):
    with localcontext() as ctx:
        ctx.prec = 300
        a, k, u = D(4).ln(), D('.5'), D(elapsed)
        return (D('.1') + (D(q0)-D('.1'))*(-k*u).exp()
                + D(gain)*a/(a-k)*((-k*u).exp()-(-a*u).exp()))


def current_root(q0, gain, horizon):
    with localcontext() as ctx:
        ctx.prec = 300
        lo, hi = D(0), D(horizon)
        check(exact_current(q0, gain, hi)>1, 'analytic root endpoint')
        # On this test's [0,.3], h is increasing; this brackets its first root.
        for _ in range(800):
            mid = (lo+hi)/2
            if exact_current(q0, gain, mid)<1:
                lo=mid
            else:
                hi=mid
        return (lo+hi)/2


def check_guard_outcomes(out, label):
    quiet = [x for x in out if not x.emissions]
    fired = [x for x in out if len(x.emissions)==1]
    check(len(quiet)==len(fired)==1, label+': retain zero and one fire')
    contains(quiet[0].state['q'], exact_current('.09', '2', '.3'), label+': quiet solution')
    root = current_root('.95', '2', '.3')
    contains(fired[0].emissions[0].box(), root, label+': first root')
    with localcontext() as ctx:
        ctx.prec=300
        qend=(-D(4).ln()*(D('.3')-root)).exp()
    contains(fired[0].state['q'], qend, label+': reset and fast solution')
    return dict(zero_or_one_emission=True, analytic_first_root=str(root),
                root_box=fired[0].emissions[0].box().pair())


iv.configure(160)
b.settings('1e-5', '1e-4')
b.PROFILE=None
installed=general.install()
check(cyc._ready_to is general.ready_to, 'A20 runtime helper installed')
check(cyc._scalar_root is general.scalar_root, 'A20 scalar root installed')
rows=[]

# Audit Annex A: this is a subset of the actual initial slab enclosure.
s=state(b.R+I('-1e-5', '1e-5')*(-b.K*b.U0).exp(),
        start=dep.Time('F01:initial_slab', b.U0))
out=guards.ready_to(cyc.Branch(s), s['t'].plus('.5'), 'F01:annex-A')
check(len(out)==1 and not out[0].emissions, 'Annex A no pulse')
with localcontext() as ctx:
    ctx.prec=300
    truth=D('.1')-D('1e-5')*(-D('.5')*(b.U0.lo+D('.5'))).exp()
contains(out[0].state['q'], truth, 'Annex A analytic witness')
check(out[0].state['q'].lo < b.R.lo and truth < b.R.lo, 'Annex A genuinely below r')
rows.append(dict(case='audit_annex_A', q=out[0].state['q'].pair(), witness=str(truth)))

for name,q in [('strictly_below_r', I('.08','.09')),
               ('straddles_r', I('.09999','.10001')),
               ('exact_return_r', I('.1'))]:
    s=state(q)
    for memory in (True,False):
        if not memory:s['memory']=None
        out=guards.ready_to(cyc.Branch(s), s['t'].plus('.5'), f'F01:{name}:{memory}')
        check(len(out)==1 and not out[0].emissions, name+': only no-fire')
        for initial in (q.lo, q.mid(), q.hi):
            contains(out[0].state['q'], exact_no_current(initial,'.5'), name)
        rows.append(dict(case=name, memory=memory, q=out[0].state['q'].pair(),
                         analytic_endpoint_and_midpoint_included=True))

# Very weak positive current used to make the old logarithmic peak
# denominator nonpositive.  Keep the actual below-r solution instead.
s=state(I('.08','.09'), current_gain='.000001')
out=guards.ready_to(cyc.Branch(s), s['t'].plus('.5'), 'F01:weak-current')
check(len(out)==1 and not out[0].emissions, 'weak current no guard')
for q0 in ('.08','.085','.09'):
    contains(out[0].state['q'], exact_current(q0,'.000001','.5'), 'weak current analytic')
rows.append(dict(case='weak_positive_current', q=out[0].state['q'].pair(), analytic_inclusions=True))

# A mixed READY box includes both a quiet trajectory and a firing one.
s=state(I('.09','.95'), current_gain='2')
tt=s['t'].plus('.3')
out=guards.ready_to(cyc.Branch(s), tt, 'F01:mixed-guard')
rows.append(dict(case='direct_conditional_guard', **check_guard_outcomes(out,'direct')))
out=cyc._ready_to(cyc.Branch(s), tt, 'F01:A20-adapter')
rows.append(dict(case='A20_runtime_adapter', **check_guard_outcomes(out,'A20')))

# Use a local observation boundary, with no hidden global event history.
# The actual incoming pulse continues until age 1, outside this window.
pending=((tt,(('end',-1,None),)),)
suffix=[tt.box().lo,D('Infinity')]
for label,step in [('A21_dynamic_helper',histories.step),('A22_scheduler',scheduler.step)]:
    hs=step(histories.History(cyc.Branch(s)), pending, suffix, 'F01:'+label)
    check(all(x.index==1 for x in hs), label+': observation consumed')
    rows.append(dict(case=label, **check_guard_outcomes([x.branch for x in hs],label)))

# A specialized shortcut may retain its narrower q>=r contract, provided
# it refuses the input instead of trimming away the sub-r part of a box.
under=state(I('.08','.09'))
try:
    ready_cluster.resolve(histories.History(cyc.Branch(under)),pending,suffix,'F01:narrow-shortcut')
except b.v.Ambiguous as error:
    check('charge at least r' in str(error),'narrow shortcut refusal reason')
    rows.append(dict(case='specialized_cluster_under_r_rejected',explicit_refusal=True))
else:
    raise RuntimeError('Specialized cluster silently accepted unsupported sub-r input')

# Phase label is a checked precondition; a protected state is not accepted.
bad={**s,'p':2}
try:
    guards.ready_to(cyc.Branch(bad),tt,'F01:wrong-mode')
except b.v.Ambiguous:
    rows.append(dict(case='non_READY_rejected', explicit_refusal=True))
else:
    raise RuntimeError('Non-READY state accepted')

report=dict(status='pass',scope='local F01 analytic regressions only; no campaign or saved prefix',
            installed=installed,cases=rows)
(ROOT/'test_ready_general_A22.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status=report['status'],cases=len(rows),analytic_annex_A_included=True,
                     below_r_and_straddling_and_equal_r=True,zero_and_one_fire_preserved=True)))
