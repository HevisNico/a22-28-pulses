"""Exact commuting ready-mode group, with a certified absence of firing.

Raw arrivals enter the same pulse memory by commutative set insertion.
Monitor marks cannot actuate recovery while READY. No error section or
active error is allowed, so gains are constant throughout. This proves the
same final physical map for every admissible inter-port event order.
"""
from dataclasses import replace
import validation_A15 as b
import dependances_A17 as dep
import depot_A19 as dz
from intervalles_decimaux import I,hull

def auxiliary_only(x,group,upper,key):
    """Independent per-port auxiliary ledger maps when every raw is zero."""
    s=x.state
    if s['p']!=0 or s['raw']!=[None]*3 or s['q'].hi>1:return None
    if any(v.fire is not None or v.marks for v in s['actuation']):return None
    actions=[(t,a,j,o) for t,aa in group for a,j,o in aa]
    if any(a not in ('mark_on','mark_off','error_on','error_off') for _,a,_,_ in actions):return None
    U=dep.Time(key+':aux-U',I(upper))
    if U.box().lo<s['t'].box().hi:return None
    out=s.copy()
    for name in ('aux','mark','err','caps'):out[name]=s[name].copy()
    ledgers=list(s['depot']);orders=[]
    expected={0:'mark_on',1:'mark_off',2:'error_on',3:'error_off'}
    try:
        for j in range(3):
            rest=[(t,a,o) for t,a,p,o in actions if p==j];previous=s['t'];path=[]
            while rest:
                candidates=[e for e in rest if e[1]==expected[out['aux'][j]]]
                if len(candidates)!=1:return None
                tt,action,origin=candidates[0]
                if tt.minus(previous).lo<0:return None
                if action=='mark_on':out['mark'][j]=origin;out['aux'][j]=1
                elif action=='mark_off':out['aux'][j]=2
                elif action=='error_on':
                    out['err'][j]=origin;out['aux'][j]=3
                    ledgers[j]=tuple(dz.open_gate(v,j,origin,tt,True) for v in ledgers[j])
                else:
                    out['aux'][j]=0;ledgers[j]=dz.unique(dz.close_gate(v,tt,True) for v in ledgers[j])
                previous=tt;path.append((tt,action,origin));rest.remove((tt,action,origin))
            orders.append(tuple(path))
        out['t']=U;out['depot']=tuple(dz.unique(dz.refresh(v,U) for v in hs) for hs in ledgers)
        out['z']=[dz.bounds(hs,U) for hs in out['depot']];out['caps']=[all(v.clamped for v in hs) for hs in out['depot']]
        elapsed=U.minus(s['t']).nonnegative();q=b.R+(s['q']-b.R)*(-b.K*elapsed).exp()
        if s.get('memory') is not None:q=q.intersect(dep.evaluate(s['memory'],U))
        out['q']=q
        if q.lo==q.hi==b.R.lo:out['memory']=dep.start(U,b.R,[])
    except (AssertionError,ValueError):return None
    proof=dict(kind='commuting_ready_auxiliary_group',events=tuple(group),per_port_physical_orders=tuple(orders),
        no_incoming_main_current=True,no_main_threshold=True,
        gain_actuations='Exact independent per-port ledger integrals, caps retained',
        all_inter_port_orders_covered=True)
    return replace(x,state=out,conditions=x.conditions+(proof,),trace=x.trace+(proof,))

def resolve(x,group,upper,key):
    s=x.state
    if s['p']!=0 or 3 in s['aux'] or s.get('memory') is None:return None
    if any(v.active is not None for hs in s['depot'] for v in hs):return None
    if any(v.fire is not None or v.marks for v in s['actuation']):return None
    actions=[a for _,aa in group for a in aa]
    if any(a not in ('raw_on','mark_on','mark_off') for a,_,_ in actions):return None
    for j in range(3):
        if any(sum(a==name and p==j for a,p,_ in actions)>1 for name in ('raw_on','mark_on','mark_off')):return None
    U=dep.Time(key+':U',I(upper))
    if U.box().lo<s['t'].box().hi:return None
    memory=s['memory']
    try:
        for action,j,origin in actions:
            if action=='raw_on':
                if s['raw'][j] is not None:return None
                memory=dep.add(memory,j,origin,b.C if s['caps'][j] else s['z'][j].exp())
        window=dep.Time(key+':window',I(s['t'].box().lo,upper))
        charge=dep.evaluate(memory,window)
        if charge.hi>=1:return None
        out=b.flowing(s,U)
        # These are commuting evaluation maps at the common endpoint, not
        # asserted physical event times. Raw terms keep actual origin times;
        # the marks affect only their own auxiliary states in this mode.
        rank={'raw_on':0,'mark_on':1,'mark_off':2}
        out=b.act(out,sorted(actions,key=lambda a:(rank[a[0]],a[1])))
        out['q']=dep.evaluate(out['memory'],U)
    except (AssertionError,ValueError):return None
    proof=dict(kind='commuting_ready_group',events=tuple(group),charge_upper=charge.hi,
        no_main_threshold=True,no_gain_actuation=True,no_recovery_actuation=True,
        all_inter_port_orders_covered=True,
        reason='Constant gains; pulse-memory insertions commute; auxiliary marks do not actuate b in READY; no errors present')
    return replace(x,state=out,conditions=x.conditions+(proof,),trace=x.trace+(proof,))
