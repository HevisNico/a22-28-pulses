"""Validated regenerative suffix for ONE joint history, with live plasticity.

This is a proof-based reachability step, not gain freezing. Every remaining
input is read from the pending physical queue. Protection excludes useful
gain actuations; recovery actuation stays active and is bounded uniformly.
All future threshold equations bind the SAME per-history gain parameters.
"""
from dataclasses import replace
from fractions import Fraction
import histoires_A21 as h
import validation_A15 as b
import dependances_A17 as dep
import actuations_A19 as ac
from intervalles_decimaux import I,D

def hpos(age,derivative=False):
    if age.hi>=1:raise b.v.Ambiguous('Regenerative head extends past first pulse end')
    if age.hi<=0:return I(0)
    z=I(max(D(0),age.lo),age.hi)
    value=dep.dh(z) if derivative else dep.h(z)
    return I(0,value.hi) if derivative and age.lo<=0 else value

def partition(pending,index):
    remaining=pending[index:]
    arrivals=[(tt,j,origin,k) for k,(tt,actions) in enumerate(remaining) for a,j,origin in actions if a=='raw_on']
    if not arrivals or len(arrivals)%3:raise b.v.Ambiguous('Suffix is not a complete three-port train')
    if min(pos for _,_,_,pos in arrivals[:3])!=0:raise b.v.Ambiguous('Unaccounted prefix before regenerative cohort')
    cohorts=[]
    for k in range(0,len(arrivals),3):
        group=arrivals[k:k+3]
        if {j for _,j,_,_ in group}!={0,1,2}:raise b.v.Ambiguous('Regenerative cohort does not contain each port once')
        start=min(pos for _,_,_,pos in group)
        end=min(pos for _,_,_,pos in arrivals[k+3:k+6]) if k+3<len(arrivals) else len(remaining)
        records={j:{} for _,j,_,_ in group}
        for tt,actions in remaining[start:end]:
            for action,j,origin in actions:
                if action=='end':continue
                if j not in records or action in records[j]:raise b.v.Ambiguous('Repeated or unmatched suffix section')
                records[j][action]=(tt,origin)
        required={'raw_on','raw_off','mark_on','mark_off','error_on','error_off'}
        if any(set(d)!=required for d in records.values()):raise b.v.Ambiguous('Incomplete auxiliary cycle in suffix')
        for d in records.values():
            if d['raw_on'][1].token()!=d['raw_off'][1].token():raise b.v.Ambiguous('Unmatched incoming pulse')
            if d['mark_on'][1].token()!=d['mark_off'][1].token() or d['error_on'][1].token()!=d['error_off'][1].token():raise b.v.Ambiguous('Unmatched auxiliary section')
        cohorts.append(records)
    return cohorts

def certify(history,pending,cell='10,2'):
    x=history.branch;s=x.state
    if s['p']!=0 or s['q'].lo!=b.R.lo or s['q'].hi!=b.R.hi:return None
    if s['raw']!=[None]*3 or s['aux']!=[0]*3:return None
    if any(v.active is not None for hs in s['depot'] for v in hs):return None
    if any(v.fire is not None or v.marks for v in s['actuation']):return None
    G=[b.C if s['caps'][j] else s['z'][j].exp() for j in range(3)]
    if any(g.lo<=0 or g.hi>b.C.hi for g in G):return None
    B=s['b'];tau_min=1+I('2.5').ln()/I('1.1');tau_max=1+I('2.5').ln()/I(B.lo)
    try:cohorts=partition(pending,history.index)
    except b.v.Ambiguous:return None
    target=pending[-1][0]
    if any(a!='end' for a,_,_ in pending[-1][1]) or target.box().pair()!=I(1116).pair():return None
    proofs=[];emissions=[];previous=s['t'];last_records=None;root_cache={};cache_hits=0
    try:
        for k,records in enumerate(cohorts):
            starts=[records[j]['raw_on'][0] for j in range(3)]
            # Use common time expressions, including correlated parent dates.
            anchor=min(starts,key=lambda t:t.box().lo)
            low=min(t.minus(anchor).lo for t in starts)
            origin=anchor.plus(low);offsets=[t.minus(origin) for t in starts]
            if min(t.minus(previous).lo for t in starts)<=0:raise b.v.Ambiguous('Suffix cohort is not strictly after preceding return bound')
            H=D('.999999');roots=[]
            function_key=tuple((g.lo,g.hi,a.lo,a.hi) for g,a in zip(G,offsets))
            if function_key in root_cache:
                roots=root_cache[function_key];cache_hits+=1
            else:
                for high in (True,False):
                    gg=[I(g.hi if high else g.lo) for g in G]
                    aa=[I(a.lo if high else a.hi) for a in offsets]
                    f=lambda u:b.R+sum((g*hpos(u-a) for g,a in zip(gg,aa)),I(0))-1
                    df=lambda u:sum((g*hpos(u-a,True) for g,a in zip(gg,aa)),I(0))
                    if f(I(0)).hi>=0 or f(I(H)).lo<=0:raise b.v.Ambiguous('Regenerative head not bracketed')
                    root=b.v.root(f,df,D(0),H,b.v.guessroot(f,H));roots.append(root)
                root_cache[function_key]=roots
            interval=I(roots[0].lo,roots[1].hi)
            fire=dep.shift(origin,interval,f'{cell}:regenerative:{history.index}:{k}')
            # The earliest protected return uses the largest physically
            # allowed b; the latest uses monotonic b >= its current lower.
            earliest=fire.plus(tau_min.lo);latest=fire.plus(tau_max.hi)
            tail=min(earliest.minus(records[j]['raw_off'][0]).lo for j in range(3))
            gate=D('Infinity')
            for j in range(3):
                if not s['caps'][j]:
                    gate=min(gate,records[j]['error_on'][0].minus(fire).lo,earliest.minus(records[j]['error_off'][0]).lo)
            next_times=[cohorts[k+1][j]['raw_on'][0] for j in range(3)] if k+1<len(cohorts) else [target]
            recovery=min(t.minus(latest).lo for t in next_times)
            if min(tail,gate,recovery)<=0:raise b.v.Ambiguous('Live suffix gate/tail/recovery margin failed')
            # All auxiliary sections must finish before the next input too.
            if any(t.minus(records[j]['error_off'][0]).lo<=0 for t in next_times for j in range(3)):raise b.v.Ambiguous('Unfinished auxiliary cycle')
            proofs.append(dict(inputs=tuple(starts),head=fire,root_from_upper=roots[0],root_from_lower=roots[1],
                tail_margin=str(tail),gain_gate_margin=str(gate),recovery_margin=str(recovery),
                equation='r + sum_j g_j*h_positive(t-arrival_j) = 1',
                gain_binding='The same initial per-history g[0:3] for every head and the terminal state'))
            emissions.append(fire);previous=latest;last_records=records
    except (b.v.Ambiguous,AssertionError,ValueError):return None
    out=s.copy();out.update(t=target,q=b.R,p=0,raw=[None]*3,aux=[0]*3,fire=emissions[-1],
        b=I(B.lo,'1.1'),bstop=B.lo==D('1.1'),memory=dep.start(target,b.R,[]),
        mark=[last_records[j]['mark_on'][1] for j in range(3)],err=[last_records[j]['error_on'][1] for j in range(3)])
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
        terminal_auxiliary_charge=b.RM,terminal_resource_interval=(50,100),
        all_pending_incoming_auxiliary_and_main_currents_completed=True,
        head_root_cache_hits=cache_hits,distinct_scalar_head_functions=len(root_cache),
        scope='One joint history. No state/output hull and no transfer of narrow mixing coefficient.')
    y=replace(x,state=out,emissions=x.emissions+tuple(emissions),conditions=x.conditions+(certificate,),trace=x.trace+(certificate,))
    return h.History(y,len(pending),history.count+len(pending)-history.index,history.lineage)
