"""Validated regenerative suffix for ONE joint history, with live plasticity.

This is a proof-based reachability step, not gain freezing. Every remaining
input is read from the pending physical queue. Protection excludes useful
gain actuations; recovery actuation stays active and is bounded uniformly.
All future threshold equations bind the SAME per-history gain parameters.
"""
from dataclasses import replace
import intervalles_decimaux as iv
from translation_tetes_A22 import translated_head
_ROOT_CACHE={}
from fractions import Fraction
import histoires_A21 as h
import validation_A15 as b
import dependances_A17 as dep
import actuations_A19 as ac
from intervalles_decimaux import I,D
import temps_valides_A22 as checked_times
checked_times.require_certifier_assertions()
checked_times.install()

def hpos(age,derivative=False):
    if age.hi>=1:raise b.v.Ambiguous('Regenerative head extends past first pulse end')
    if age.hi<=0:return I(0)
    z=I(max(D(0),age.lo),age.hi)
    value=dep.dh(z) if derivative else dep.h(z)
    return I(0,value.hi) if derivative and age.lo<=0 else value

def partition(pending,index):
    remaining=pending[index:]
    arrivals=[(tt,j,origin,k) for k,(tt,actions) in enumerate(remaining) for a,j,origin in actions if a=='raw_on']
    if not arrivals or arrivals[0][3]!=0:raise b.v.Ambiguous('Unaccounted prefix or no suffix arrival')
    groups=[]
    for event in arrivals:
        if not groups or all(event[0].minus(old[0]).lo>D('1.3') for old in groups[-1]):groups.append([event])
        else:groups[-1].append(event)
    cohorts=[];ports=None
    for k,group in enumerate(groups):
        current={j for _,j,_,_ in group}
        if len(current)!=len(group):raise b.v.Ambiguous('Repeated port in a regenerative cohort')
        if ports is None:ports=current
        if ports!=current:raise b.v.Ambiguous('Active port set changes inside suffix')
        start=min(pos for _,_,_,pos in group)
        end=min(pos for _,_,_,pos in groups[k+1]) if k+1<len(groups) else len(remaining)
        records={j:{} for j in ports}
        for tt,actions in remaining[start:end]:
            for action,j,origin in actions:
                if action=='end':continue
                if j not in records or action in records[j]:raise b.v.Ambiguous('Repeated or unmatched suffix section')
                records[j][action]=(tt,origin)
        required={'raw_on','raw_off','mark_on','mark_off','error_on','error_off'}
        if any(set(d)!=required for d in records.values()):raise b.v.Ambiguous('Incomplete auxiliary cycle in suffix')
        for d in records.values():
            for left,right in [('raw_on','raw_off'),('mark_on','mark_off'),('error_on','error_off')]:
                if d[left][1].token()!=d[right][1].token():raise b.v.Ambiguous('Unmatched section origin')
        cohorts.append(records)
    return cohorts

def certify(history,pending,cell='10,2'):
    x=history.branch;s=x.state
    if s['p']!=0 or s['q'].lo!=b.R.lo or s['q'].hi!=b.R.hi:return None
    if s['raw']!=[None]*3 or s['aux']!=[0]*3:return None
    memory=s.get('memory')
    if memory is None or memory.get('pulses') or memory['q'].lo!=b.R.lo or memory['q'].hi!=b.R.hi:return None
    if any(v.active is not None for hs in s['depot'] for v in hs):return None
    if any(v.fire is not None or v.marks for v in s['actuation']):return None
    G=[b.C if s['caps'][j] else s['z'][j].exp() for j in range(3)]
    if any(g.lo<=0 or g.hi>b.C.hi for g in G):return None
    B=s['b']
    if B.lo<=0 or B.hi>D('1.1'):return None
    tau_min=1+I('2.5').ln()/I('1.1');tau_max=1+I('2.5').ln()/I(B.lo)
    try:cohorts=partition(pending,history.index)
    except b.v.Ambiguous:return None
    target=pending[-1][0]
    if any(a!='end' for a,_,_ in pending[-1][1]) or target.box().pair()!=I(1116).pair():return None
    proofs=[];emissions=[];previous=s['t'];last_records=None;root_cache={};cache_hits=0;translations={};translation_hits=0
    try:
        for k,records in enumerate(cohorts):
            active=sorted(records)
            starts=[records[j]['raw_on'][0] for j in active]
            # Use common time expressions, including correlated parent dates.
            anchor=min(starts,key=lambda t:t.box().lo)
            low=min(t.minus(anchor).lo for t in starts)
            origin=anchor.plus(low);offsets=[t.minus(origin) for t in starts]
            if min(t.minus(previous).lo for t in starts)<=0:raise b.v.Ambiguous('Suffix cohort is not strictly after preceding return bound')
            H=D('.999999');roots=[]
            function_key=(iv.PREC,tuple(b.A.pair()),tuple(b.K.pair()),tuple(b.R.pair()),tuple((g.lo,g.hi,a.lo,a.hi) for g,a in zip([G[j] for j in active],offsets)))
            if function_key in _ROOT_CACHE:
                roots=_ROOT_CACHE[function_key];root_cache[function_key]=roots;cache_hits+=1
            else:
                for high in (True,False):
                    gg=[I(G[j].hi if high else G[j].lo) for j in active]
                    aa=[I(a.lo if high else a.hi) for a in offsets]
                    f=lambda u:b.R+sum((g*hpos(u-a) for g,a in zip(gg,aa)),I(0))-1
                    df=lambda u:sum((g*hpos(u-a,True) for g,a in zip(gg,aa)),I(0))
                    if f(I(0)).hi>=0 or f(I(H)).lo<=0:raise b.v.Ambiguous('Regenerative head not bracketed')
                    root=b.v.root(f,df,D(0),H,b.v.guessroot(f,H));roots.append(root)
                root_cache[function_key]=roots;_ROOT_CACHE[function_key]=roots
            interval=I(roots[0].lo,roots[1].hi)
            pattern,fire,translation_proof=translated_head(active,starts,anchor,translations)
            if fire is not None:translation_hits+=1
            else:fire=dep.shift(origin,interval,f'{cell}:regenerative:{history.index}:{k}')
            if pattern not in translations:translations[pattern]=(anchor,fire,k)
            # The earliest protected return uses the largest physically
            # allowed b; the latest uses monotonic b >= its current lower.
            earliest=fire.plus(tau_min.lo);latest=fire.plus(tau_max.hi)
            tail=min(earliest.minus(records[j]['raw_off'][0]).lo for j in active)
            gate=D('Infinity')
            for j in active:
                if not s['caps'][j]:
                    gate=min(gate,records[j]['error_on'][0].minus(fire).lo,earliest.minus(records[j]['error_off'][0]).lo)
            next_times=[cohorts[k+1][j]['raw_on'][0] for j in sorted(cohorts[k+1])] if k+1<len(cohorts) else [target]
            recovery=min(t.minus(latest).lo for t in next_times)
            if min(tail,gate,recovery)<=0:raise b.v.Ambiguous('Live suffix gate/tail/recovery margin failed')
            # All auxiliary sections must finish before the next input too.
            if any(t.minus(records[j]['error_off'][0]).lo<=0 for t in next_times for j in active):raise b.v.Ambiguous('Unfinished auxiliary cycle')
            proofs.append(dict(inputs=tuple(starts),head=fire,translation_proof=translation_proof,root_from_upper=roots[0],root_from_lower=roots[1],
                tail_margin=str(tail),gain_gate_margin=str(gate),recovery_margin=str(recovery),
                equation='r + sum_j g_j*h_positive(t-arrival_j) = 1',
                gain_binding='The same initial per-history g[0:3] for every head and the terminal state'))
            emissions.append(fire);previous=latest;last_records=records
    except (b.v.Ambiguous,AssertionError,ValueError):return None
    out=s.copy();out.update(t=target,q=b.R,p=0,raw=[None]*3,aux=[0]*3,fire=emissions[-1],
        b=I(B.lo,'1.1'),bstop=B.lo==D('1.1'),memory=dep.start(target,b.R,[]),
        mark=[last_records[j]['mark_on'][1] if j in last_records else s['mark'][j] for j in range(3)],err=[last_records[j]['error_on'][1] if j in last_records else s['err'][j] for j in range(3)])
    # The completed old ledger is retained in the proof below. At the quiet
    # terminal section, only the present rate enters future physical flow.
    # This conservative per-history projection does not join distinct gains
    # or output histories. It is justified uniformly for every b in B..1.1.
    out['actuation']=(ac.History(out['b'],saturated=out['bstop']),)
    certificate=dict(kind='certified_regenerative_suffix',starting_state=s,
        gain_parameters=tuple(G),per_port_deposits=s['depot'],heads=tuple(proofs),
        principal_minimum_protection=tau_min,principal_maximum_protection=tau_max,
        recovery_actuation='Still active; monotonic rate bounded between starting lower and 1.1',
        gain_actuation='Still active; excluded by certified protection gates or reached caps',
        terminal_auxiliary_charge_on_active_ports=b.RM,active_ports=tuple(sorted(last_records)),
        inactive_auxiliaries='No arrivals: original initial-slab exponential rest enclosure remains in force',terminal_resource_interval=(50,100),
        all_pending_incoming_auxiliary_and_main_currents_completed=True,
        head_root_cache_hits=cache_hits,distinct_scalar_head_functions=len(root_cache),exact_time_translation_hits=translation_hits,
        scope='One joint history. No state/output hull and no transfer of narrow mixing coefficient.')
    y=replace(x,state=out,emissions=x.emissions+tuple(emissions),conditions=x.conditions+(certificate,),trace=x.trace+(certificate,))
    return h.History(y,len(pending),history.count+len(pending)-history.index,history.lineage)
