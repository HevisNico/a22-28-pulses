"""Independent product boxes: initial states AND heterogeneous A14 devices.

Uncertain external-event orders are all enumerated and joined at a common
time, after proving no internal guard lies in the cluster. Any unresolved
internal ambiguity aborts, never selects a float order. No reflection used.
"""
from pathlib import Path
from itertools import permutations
from fractions import Fraction
import argparse,json,time,copy
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import multiprocessing
import intervalles_decimaux as iv
from intervalles_decimaux import I,D,hull
import outils_validation as v
import dependances_A17 as dep
import actuations_A19 as ac
import depot_A19 as dz
from profil_largeurs_A19 import Profile
PROFILE=None
v.T=dep.Time

ROOT=Path(__file__).resolve().parent

def settings(delta,epsilon):
    global A,K,R,RM,LM,LS,LE,C,Z,M,D0,D1,DM,DS,DE,U0,DELTA,EPS
    v.constants();A=v.A;K=v.K;R=v.R;RM=v.RM;DELTA=I(delta);EPS=I(epsilon)
    dep.configure(A,K,R)
    C=4*(1+I(-EPS.hi,EPS.hi));Z=C.ln()
    LM=v.LM*(1+I(-EPS.hi,EPS.hi));LS=v.LS*(1+I(-EPS.hi,EPS.hi));LE=v.LE*(1+I(-EPS.hi,EPS.hi));M=v.M*(1+I(-EPS.hi,EPS.hi))
    def hh(u):return A/(A-K)*((-K*u).exp()-(-A*u).exp())
    def dh(u):return A/(A-K)*(A*(-A*u).exp()-K*(-K*u).exp())
    U0=I((2*DELTA/(LE*RM)).hi)
    init=I(-DELTA.hi,DELTA.hi)
    f=lambda u:RM+M*hh(u)-1
    D0=v.root(f,lambda u:M*dh(u),D(0),D('.1'),.02)
    f=lambda u:RM+init*(-K*u).exp()+M*hh(u)-1
    df=lambda u:-K*init*(-K*u).exp()+M*dh(u)
    fast=v.root(f,df,D(0),D('.1'),.02)
    attenuation=(-A*U0).exp()
    f=lambda u:RM+init*(-K*u).exp()+M*attenuation*hh(u)-1
    df=lambda u:-K*init*(-K*u).exp()+M*attenuation*dh(u)
    slow=v.root(f,df,D(0),D('.1'),.02)
    D1=I(fast.lo,(U0+slow).hi)
    DM=I('1.25').ln()/LM;DS=I(8).ln()/LS;DE=I(4).ln()/LE
    ac.configure(LM);dz.configure(LE,Z)
    assert (D1+DM+DS+DE).hi<D('1.3') and U0.hi<D1.lo and D1.hi<D('.1')
    assert (D0+DM+DS+DE).lo>1 and (D1+DM+DS+DE).lo>1
    assert (D0+DM+DS).lo>1 and (D1+DM+DS).lo>1
    assert (R+DELTA+3*C*A*U0).hi<D('.2') and (RM+DELTA+M*A*U0).hi<1
    assert LM.lo>(I('.8')*LS).hi and LM.lo>(I('.1')*LE).hi
    work=(3*C+3*M+1)*A+I('1.1')+I('4.5')*LM+I('2.4')*LE
    assert work.hi<270 and work.hi<500 and C.lo>D('3.9') and M.hi<40
    return dict(delta=delta,epsilon=epsilon,initial_slab_end=U0.pair(),first_monitor_delay=D1.pair(),subsequent_monitor_delay=D0.pair(),
        mark_duration=DM.pair(),silent_duration=DS.pair(),error_duration=DE.pair(),cap_range=C.pair(),resource_work_upper=str(work.hi),resource_interval=[50,100])

def shift(t,u,key):
    return dep.shift(t,u,key)

def new_memory(s):
    return dep.start(s['t'],s['q'],[(j,o,C if s['caps'][j] else s['z'][j].exp()) for j,o in enumerate(s['raw']) if o is not None])

def coefficients(s):
    t=s['t'];g=[C if s['caps'][j] else s['z'][j].exp() for j in range(3)]
    J=sum((g[j]*A*(-A*t.minus(x)).exp() for j,x in enumerate(s['raw']) if x is not None),I(0))
    cg=[8*I('.1')*(-LE*t.minus(s['err'][j])).exp() if s['p']==0 and s['aux'][j]==3 and not s['caps'][j] else I(0) for j in range(3)]
    cb=[I('.5')*(-LM*t.minus(s['mark'][j])).exp() if s['p']!=0 and s['aux'][j]==1 and not s['bstop'] else I(0) for j in range(3)]
    assert all(s['raw'][j] is None or cg[j].hi==0 for j in range(3))
    return J,cg,cb

def ready_root(q,J,hi):
    """Monotone comparison in initial charge and incoming current.

    On u>=0 both coefficients are nonnegative. Thus the earliest root is
    bounded by the upper scalar trajectory, the latest by the lower one.
    Each scalar root still requires endpoint signs and positive derivative.
    This avoids testing a derivative on a product box containing unrelated
    times from different trajectories.
    """
    roots=[]
    for q0,j0 in ((q.hi,J.hi),(q.lo,J.lo)):
        qi=I(q0);ji=I(j0);bb=ji/(A-K)
        f=lambda u:v.ready(qi,ji,u)-1
        df=lambda u:-K*(qi-R+bb)*(-K*u).exp()+A*bb*(-A*u).exp()
        roots.append(v.root(f,df,D(0),hi,v.guessroot(f,hi)))
    return I(roots[0].lo,roots[1].hi)

def flowing(s,tt,guardfree=False):
    previous=s
    s=s.copy();J,cg,cb=coefficients(s);u=tt.minus(s['t']).nonnegative();H=u.hi;q=s['q'];b=s['b'];cs=sum(cb,I(0))
    if s['p']==0:
        if guardfree and J.hi>0:
            bb=J/(A-K);aa=q-R+bb;pk=(A*bb/(K*aa)).ln()/(A-K)
            x=I(min(H,max(D(0),pk.lo)),min(H,max(D(0),pk.hi)))
            assert v.ready(q,J,x).hi<1,'internal crossing inside uncertain external cluster'
        s['q']=v.ready(q,J,u)
    elif s['p']==1:
        if guardfree:assert tt.box().hi<s['fire'].plus(1).box().lo,'fast section inside external cluster'
        s['q']=q*(-A*u).exp()
    else:
        e=ac.bounds(s['actuation'],tt,'ell');s['q']=R*e.exp()
        if guardfree:assert e.lo>0,'slow section inside external cluster (actuation ledger)'
    if 'depot' not in s:s['depot']=tuple((dz.History(s['z'][j],clamped=s['caps'][j]),) for j in range(3))
    s['depot']=tuple(dz.unique(dz.refresh(h,tt) for h in hs) for hs in s['depot'])
    s['z']=[dz.bounds(hs,tt) for hs in s['depot']]
    s['caps']=[all(h.clamped for h in hs) for hs in s['depot']]
    if 'actuation' not in s:s['actuation']=(ac.History(b),)
    s['b']=ac.bounds(s['actuation'],tt)
    s['bstop']=s['b'].lo==s['b'].hi==D('1.1')
    if guardfree:
        assert all(s['z'][j].hi<=Z.hi for j in range(3)),'gain saturation invariant'
        assert s['b'].hi<=D('1.1'),'recovery saturation invariant'
    s['t']=tt
    if s['p']==0 and s.get('memory') is not None:s['q']=dep.evaluate(s['memory'],tt)
    if PROFILE is not None:PROFILE.observe('continuous',previous,s)
    return s

def act(s,changes):
    s=s.copy()
    for k in ('raw','mark','err','aux'):s[k]=s[k].copy()
    for action,j,origin in changes:
        if action=='end':continue
        if action=='raw_on':
            assert s['raw'][j] is None;s['raw'][j]=origin
            if s['p']==0 and s.get('memory') is not None:
                s['memory']=dep.add(s['memory'],j,origin,C if s['caps'][j] else s['z'][j].exp())
        elif action=='raw_off':assert s['raw'][j] is not None;s['raw'][j]=None
        elif action=='mark_on':
            assert s['aux'][j]==0;s['aux'][j]=1;s['mark'][j]=origin
            s['actuation']=tuple(ac.on(h,j,origin) for h in s['actuation'])
        elif action=='mark_off':
            assert s['aux'][j]==1;s['aux'][j]=2
            s['actuation']=tuple(ac.off(h,j,origin,s['t']) for h in s['actuation'])
        elif action=='error_on':
            assert s['aux'][j]==2;s['aux'][j]=3;s['err'][j]=origin
            if s['p']==0:s['depot']=tuple(tuple(dz.open_gate(h,j,origin,s['t'],True) for h in hs) if k==j else hs for k,hs in enumerate(s['depot']))
        elif action=='error_off':
            assert s['aux'][j]==3;s['aux'][j]=0
            if s['p']==0:s['depot']=tuple(dz.unique(dz.close_gate(h,s['t'],True) for h in hs) if k==j else hs for k,hs in enumerate(s['depot']))
    s['b']=ac.bounds(s['actuation'],s['t']);s['bstop']=s['b'].lo==s['b'].hi==D('1.1')
    s['z']=[dz.bounds(hs,s['t']) for hs in s['depot']];s['caps']=[all(h.clamped for h in hs) for hs in s['depot']]
    if s['p']==2:s['q']=R*ac.bounds(s['actuation'],s['t'],'ell').exp()
    return s

def possible_order(start,order):
    earliest=start.box().lo
    previous=start
    for tt,_ in order:
        if tt.minus(previous).hi<0:return False
        earliest=max(earliest,tt.box().lo)
        if earliest>tt.box().hi:return False
        previous=tt
    return True

def admissible_orders(s,events,budget=4096):
    """Enumerate every weak order not excluded by dates or discrete phases.

    Bounds only reject proven contradictions. No floating nominal ordering
    selects a branch. Stage transitions are part of the physical automaton.
    """
    events=tuple(events);emitted=0;visited=0
    expected={'mark_on':0,'mark_off':1,'error_on':2,'error_off':3}
    following={'mark_on':1,'mark_off':2,'error_on':3,'error_off':0}
    def search(prefix,remaining,stages,raw):
        nonlocal emitted,visited
        visited+=1
        if visited>65536:raise v.Ambiguous('event-order search-node budget exceeded')
        if not remaining:
            emitted+=1
            if emitted>budget:raise v.Ambiguous('admissible event-order budget exceeded')
            yield tuple(prefix);return
        for k in remaining:
            tt,actions=events[k]
            # A remaining event certified strictly earlier must be taken first.
            if any(tt.minus(events[j][0]).lo>0 for j in remaining if j!=k):continue
            candidate=prefix+[events[k]]
            if not possible_order(s['t'],candidate):continue
            aphase=stages.copy();rphase=raw.copy();valid=True
            for action,j,_ in actions:
                if action in expected:
                    if aphase[j]!=expected[action]:valid=False;break
                    aphase[j]=following[action]
                elif action=='raw_on':
                    if rphase[j]:valid=False;break
                    rphase[j]=True
                elif action=='raw_off':
                    if not rphase[j]:valid=False;break
                    rphase[j]=False
                elif action not in ('end','principal_ready'):
                    raise v.Ambiguous('unknown discrete event in order enumeration')
            if valid:yield from search(candidate,tuple(j for j in remaining if j!=k),aphase,rphase)
    yield from search([],tuple(range(len(events))),s['aux'].copy(),[x is not None for x in s['raw']])

def join_states(poss,context):
    assert poss
    ss=poss[0].copy()
    ss['actuation']=ac.unique(h for x in poss for h in x['actuation'])
    ss['memory']=dep.join([x.get('memory') for x in poss])
    ss['q']=hull([x['q'] for x in poss]);ss['b']=ac.bounds(ss['actuation'],ss['t'])
    ss['bstop']=ss['b'].lo==ss['b'].hi==D('1.1')
    ss['depot']=tuple(dz.unique(h for x in poss for h in x['depot'][j]) for j in range(3))
    ss['z']=[dz.bounds(hs,ss['t']) for hs in ss['depot']]
    ss['caps']=[all(h.clamped for h in hs) for hs in ss['depot']]
    if ss['p']==2:ss['q']=R*ac.bounds(ss['actuation'],ss['t'],'ell').exp()
    if PROFILE is not None:
        # Compare the union with its widest constituent; this is branch
        # spread, not automatically numerical error.
        old=poss[0].copy()
        old['b']=max((x['b'] for x in poss),key=lambda x:x.width())
        old['q']=max((x['q'] for x in poss),key=lambda x:x.width())
        PROFILE.observe('branch_union',old,ss,context)
    return ss

def protected_section_cluster(s,group,upper,cell,count):
    """Fast/slow share admission gates; saturation is integrated explicitly."""
    assert s['p']==1
    section=s['fire'].plus(1);U=v.T(f'{cell}:protected-U:{count}',I(upper))
    assert U.box().lo>=section.box().hi
    assert min(t.box().lo for t,_ in group)>=s['t'].box().hi
    poss=[]
    for order in admissible_orders(s,group):
        ss=s
        for tt,actions in order:ss=act(flowing(ss,tt),actions)
        ss=flowing(ss,U)
        e=ac.bounds(ss['actuation'],U,'ell')
        assert e.lo>0,'possible recovery inside protected fast/slow cluster'
        ss['q']=R*e.exp();ss['p']=2;ss['memory']=None;poss.append(ss)
    assert all(x['aux']==poss[0]['aux'] and
        [(t.token() if t else None) for t in x['raw']]==[(t.token() if t else None) for t in poss[0]['raw']] for x in poss)
    return join_states(poss,dict(cell=cell,batch=count,orders=len(poss),kind='fast_slow')),len(poss)

def constant_recovery(s,cell,count):
    if s['p']!=2:return None
    if not all(h.fire.token()==s['fire'].token() and
        (h.saturated or ac.raw_rate(h,h.fire.plus(1)).lo>=D('1.1')) for h in s['actuation']):return None
    return shift(s['fire'].plus(1),I('2.5').ln()/I('1.1'),f'{cell}:{count}:constant-ready')

def independent_recovery(s,cell,count):
    """Return prediction under the recorded marks, before any new mark_on.

    Raw and auxiliary error boundaries do not alter protected b or q.
    The caller checks that no new unrecorded mark enters the join window.
    """
    exact=constant_recovery(s,cell,count)
    if exact is not None:return exact
    anchor=s['t'];e=ac.bounds(s['actuation'],anchor,'ell')
    if e.lo<=0:return None
    common=v.T(f'{cell}:{count}:independent-anchor',I(anchor.box().hi))
    if ac.bounds(s['actuation'],common,'ell').lo>0:anchor=common
    probe=lambda u:shift(anchor,u,f'{cell}:{count}:independent-probe')
    f=lambda u:-ac.bounds(s['actuation'],probe(u),'ell')
    df=lambda u:ac.bounds(s['actuation'],probe(u))
    hi=(2*I(e.hi)/I(df(I(0)).lo)+I('.001')).hi
    for _ in range(12):
        if f(I(hi)).lo>0:break
        hi=(I(hi)*2).hi
    else:return None
    root=v.root(f,df,D(0),hi,v.guessroot(f,hi))
    return shift(anchor,root,f'{cell}:{count}:independent-ready')

def reopen(s,tt):
    s=flowing(s,tt)
    s['actuation']=ac.unique(ac.finish(h,tt) for h in s['actuation'])
    s['b']=ac.bounds(s['actuation'],tt);s['bstop']=s['b'].lo==s['b'].hi==D('1.1')
    s['q']=R;s['p']=0;s['memory']=new_memory(s)
    s['depot']=tuple(tuple(dz.open_gate(h,j,s['err'][j],tt,False) for h in hs) if s['aux'][j]==3 else hs for j,hs in enumerate(s['depot']))
    return s

def recovery_auxiliary_cluster(s,group,upper,ready,cell,count):
    """All weak orders of a return and dynamically independent boundaries.

    A raw current already present can be admitted after return. Its exact
    ready response is propagated, and absence of a further fire is checked.
    The orders use distinct actuator gates and histories throughout.
    """
    assert s['p']==2
    assert all(a not in ('raw_on','raw_off','end') for _,actions in group for a,_,_ in actions)
    U=v.T(f'{cell}:recovery-U:{count}',I(upper));poss=[];orders=[]
    events=list(group)+[(ready,[('principal_ready',-1,None)])]
    for order in admissible_orders(s,events):
        feasible=True
        ss=s;conditions=tuple(('le',order[k][0],order[k+1][0]) for k in range(len(order)-1))
        for tt,actions in order:
            if actions[0][0]=='principal_ready':ss=reopen(ss,tt)
            else:
                ss=flowing(ss,tt,ss['p']==0)
                if ss['p']==2:
                    if ss['q'].hi<R.lo or ss['q'].lo>D('.25'):
                        if PROFILE is not None:PROFILE.pruned_recovery_orders.append(dict(cell=cell,batch=count,time=tt.box().pair(),
                            enclosed_q=ss['q'].pair(),required_q=[str(R.lo),'.25'],reason='empty intersection with the slow-phase state domain'))
                        feasible=False;break
                    ss['q']=ss['q'].intersect(I(R.lo,'.25'))
                ss=act(ss,actions)
        if not feasible:continue
        ss=flowing(ss,U,True)
        assert ss['p']==0 and ss['q'].hi<1 and ss['raw']==s['raw']
        affected={j for _,actions in group for a,j,_ in actions if a in ('error_on','error_off')}
        affected.update(j for j in range(3) if s['aux'][j]==3)
        ss['depot']=tuple(tuple(replace(h,conditions=h.conditions+conditions) if not h.clamped else h for h in hs) if j in affected else hs for j,hs in enumerate(ss['depot']))
        poss.append(ss);orders.append([dict(time=t.box().pair(),actions=[a for a,_,_ in actions]) for t,actions in order])
    if not poss:raise v.Ambiguous('no recovery/auxiliary branch remained certifiable')
    assert all(x['aux']==poss[0]['aux'] for x in poss)
    if PROFILE is not None:PROFILE.recovery_branch_groups.append(dict(cell=cell,batch=count,join_time=U.box().pair(),orders=orders,
        scope='Weak inequalities retained as branch labels and in gate endpoints; no global constraint solver. Simultaneity is covered by both weak orders; finite auxiliary currents create no instantaneous gain jump.'))
    return join_states(poss,dict(cell=cell,batch=count,orders=len(poss),kind='recovery_auxiliary')),len(poss)

def fire_reset(s):
    """Physical threshold transition, with state already evaluated at its guard."""
    s=s.copy();tt=s['t']
    s['depot']=tuple(dz.unique(dz.close_gate(h,tt,False) for h in hs) for hs in s['depot'])
    s['z']=[dz.bounds(hs,tt) for hs in s['depot']];s['caps']=[all(h.clamped for h in hs) for hs in s['depot']]
    s['actuation']=tuple(ac.begin(h,tt,s['aux'],s['mark']) for h in s['actuation'])
    s['q']=I(1);s['p']=1;s['fire']=tt;s['memory']=None
    return s

def resolve_local_cycle(s,group,upper,coarse,cell,count):
    """Disjoint output histories; never flatten optional emissions."""
    from cycle_local_A20 import resolve
    return resolve(s,group,upper,coarse,cell,count)

def advance(s,boundary,cell,count):
    """Reach boundary, or process a rigorously earlier internal guard."""
    H=boundary.minus(s['t']).nonnegative().hi;q=s['q'];b=s['b'];J,cg,cb=coefficients(s);cs=sum(cb,I(0));candidates=[(boundary,'external',-1)]
    def candidate(u,kind,j=-1):
        tt=shift(s['t'],u,f'{cell}:{count}:{kind}:{j}')
        if tt.box().lo<=boundary.box().hi:candidates.append((tt,kind,j))
    if H>0:
        if s['p']==0 and J.hi>0:
            bb=J/(A-K);aa=q-R+bb;pk=(A*bb/(K*aa)).ln()/(A-K)
            peak=I(max(D(0),pk.lo),max(D(0),pk.hi));x=I(min(H,peak.lo),min(H,peak.hi))
            legacy_max=v.ready(q,J,x)
            memory=s.get('memory')
            if memory is None:
                f=lambda u:v.ready(q,J,u)-1
                df=lambda u:-K*(q-R+bb)*(-K*u).exp()+A*bb*(-A*u).exp()
                possible=legacy_max.hi>=1
            else:
                probe=lambda u:shift(s['t'],u,f'{cell}:{count}:probe')
                f=lambda u:dep.evaluate(memory,probe(u))-1
                df=lambda u:dep.evaluate(memory,probe(u),True)
                memory_max=dep.evaluate(memory,probe(I(0,H)))
                possible=min(legacy_max.hi,memory_max.hi)>=1
            if possible:
                hi=min(H,peak.lo)
                if f(I(hi)).lo<0:raise v.Ambiguous('ready guard still overlaps external boundary or possible tangency')
                if memory is None:root=ready_root(q,J,hi)
                else:root=v.root(f,df,D(0),hi,v.guessroot(f,hi))
                candidate(root,'fire')
        elif s['p']==1:
            tt=s['fire'].plus(1)
            if tt.box().lo<=boundary.box().hi:candidates.append((tt,'slow',-1))
        elif s['p']==2:
            exact=constant_recovery(s,cell,count)
            if exact is not None:
                difference=exact.minus(boundary)
                if difference.hi<0:
                    out=reopen(s,exact)
                    if PROFILE is not None:PROFILE.guard('ready',exact)
                    return out,'ready'
                if difference.lo>0:return flowing(s,boundary),'external'
                raise v.Ambiguous('constant recovery relative order unresolved')
            anchor=s['t'];common=v.T(f'{cell}:{count}:recovery-anchor',I(s['t'].box().hi))
            if common.box().hi<boundary.box().lo and ac.bounds(s['actuation'],common,'ell').lo>0:anchor=common
            HH=boundary.minus(anchor).nonnegative().hi
            probe=lambda u:shift(anchor,u,f'{cell}:{count}:recovery-probe')
            f=lambda u:-ac.bounds(s['actuation'],probe(u),'ell')
            df=lambda u:ac.bounds(s['actuation'],probe(u));val=f(I(HH))
            if val.lo>=0:
                root=v.root(f,df,D(0),HH,v.guessroot(f,HH))
                tt=shift(anchor,root,f'{cell}:{count}:ready:-1')
                if tt.box().lo<=boundary.box().hi:candidates.append((tt,'ready',-1))
            elif val.hi>=0:raise v.Ambiguous('recovery guard overlaps external boundary (actuation history)')
    candidates.sort(key=lambda a:a[0].box().mid());tt,kind,j=candidates[0]
    if not all(tt.box().hi<=x.box().lo for x,_,_ in candidates[1:]):
        proof=None
        internals=[x for x in candidates if x[1]!='external']
        if len(internals)==1 and internals[0][1]=='fire' and s.get('memory') is not None:
            margin=dep.evaluate(s['memory'],boundary)-1
            if margin.lo>0:
                # The counterfactual ready trajectory is continuous and the
                # candidate is its certified first increasing root. A positive
                # charge at the actual exterior date proves the root earlier,
                # even when their independent absolute date boxes overlap.
                tt,kind,j=internals[0];proof=dict(guard='fire',margin=margin.pair(),predicate='q(boundary)>1')
        elif len(internals)==1 and internals[0][1]=='ready' and s['p']==2:
            margin=-ac.bounds(s['actuation'],boundary,'ell')
            if margin.lo>0:
                tt,kind,j=internals[0];proof=dict(guard='ready',margin=margin.pair(),predicate='ell(boundary)<0')
        if proof is None:
            raise v.Ambiguous(json.dumps(dict(reason='internal guard order',cell=cell,count=count,phase=s['p'],time=s['t'].box().pair(),q=s['q'].pair(),z=[x.pair() for x in s['z']],b=s['b'].pair(),candidates=[dict(kind=k,port=j,time=t.box().pair()) for t,k,j in candidates])))
        if PROFILE is not None:PROFILE.relative_order_proofs.append(dict(cell=cell,batch=count,**proof))
    s=flowing(s,tt)
    if kind=='fire':s=fire_reset(s)
    elif kind=='slow':s['q']=I('.25');s['p']=2
    elif kind=='ready':
        s['actuation']=ac.unique(ac.finish(h,tt) for h in s['actuation'])
        s['b']=ac.bounds(s['actuation'],tt);s['bstop']=s['b'].lo==s['b'].hi==D('1.1')
        s['q']=R;s['p']=0;s['memory']=new_memory(s)
        s['depot']=tuple(tuple(dz.open_gate(h,j,s['err'][j],tt,False) for h in hs) if s['aux'][j]==3 else hs for j,hs in enumerate(s['depot']))
    elif kind=='gstop':s['z']=s['z'].copy();s['z'][j]=Z;s['caps']=s['caps'].copy();s['caps'][j]=True
    elif kind=='bstop':s['b']=I('1.1');s['bstop']=True
    if PROFILE is not None and kind!='external':PROFILE.guard(kind,tt)
    return s,kind

def unit(inputs,cell):
    global PROFILE
    PROFILE=Profile(inputs)
    events={};raw=[None]*3
    def add(t,action,j=-1,origin=None):events.setdefault(t.token(),[t,[]])[1].append((action,j,origin))
    for j,train in enumerate(inputs):
        assert all(train[k+1].minus(train[k]).lo>D('1.3') for k in range(len(train)-1))
        for k,start in enumerate(train):
            if start.box().hi<U0.lo:assert start.token()==('clock','0');raw[j]=start
            else:add(start,'raw_on',j,start)
            add(start.plus(1),'raw_off',j,start)
            mon=shift(start,D1 if k==0 else D0,f'{cell}:m:{j}:{k}')
            off=shift(mon,DM,f'{cell}:mo:{j}:{k}');err=shift(off,DS,f'{cell}:e:{j}:{k}');end=shift(err,DE,f'{cell}:eo:{j}:{k}')
            add(mon,'mark_on',j,mon);add(off,'mark_off',j,mon);add(err,'error_on',j,err);add(end,'error_off',j,err)
    add(v.T('clock',I(0),D(230)),'end')
    pending=sorted(events.values(),key=lambda e:e[0].box().mid());assert pending[-1][0].token()==('clock','2.3E+2')
    suffix=[D('Infinity')]*(len(pending)+1)
    for k in range(len(pending)-1,-1,-1):suffix[k]=min(suffix[k+1],pending[k][0].box().lo)
    s=dict(t=v.T('initial_slab',U0),q=R+I(-DELTA.hi,DELTA.hi)*(-K*U0).exp()+I(0,(3*C*A*U0).hi),
        z=[I(g).ln()+I(-DELTA.hi,(9*DELTA).hi) for g in ('.3','1.2','.3')],b=I('.08')+I(-DELTA.hi,DELTA.hi),
        p=0,raw=raw,aux=[0]*3,mark=[None]*3,err=[None]*3,caps=[False]*3,bstop=False,fire=None)
    s['memory']=new_memory(s);s['actuation']=(ac.History(s['b']),)
    s['depot']=tuple((dz.History(z),) for z in s['z'])
    out=[];idx=0;count=0;clusters=0;branches=0;stops=0
    while idx<len(pending):
        stopidx=idx+1;upper=pending[idx][0].box().hi
        while upper>suffix[stopidx]:
            assert stopidx<len(pending);upper=max(upper,pending[stopidx][0].box().hi);stopidx+=1
        group=pending[idx:stopidx]
        exact=constant_recovery(s,cell,count)
        auxiliary_only=all(a not in ('raw_on','raw_off','end','mark_on') for _,changes in group for a,_,_ in changes)
        if exact is None and s['p']==2 and auxiliary_only:
            span=v.T(f'{cell}:aux-span:{count}',I(min(t.box().lo for t,_ in group),upper))
            if span.minus(s['t']).hi>=0:
                envelope=ac.bounds(s['actuation'],span,'ell')
                if envelope.lo<=0<=envelope.hi:exact=independent_recovery(s,cell,count)
        if exact is not None and exact.box().lo<=upper and exact.box().hi>=min(t.box().lo for t,_ in group):
            uncertain=any(t.minus(exact).lo<=0<=t.minus(exact).hi for t,_ in group)
            if uncertain:
                upper=max(upper,exact.box().hi)
                while upper>suffix[stopidx]:
                    assert stopidx<len(pending)
                    upper=max(upper,pending[stopidx][0].box().hi);stopidx+=1
                group=pending[idx:stopidx]
                if all(a not in ('raw_on','raw_off','end') and (a!='mark_on' or s['bstop']) for _,changes in group for a,_,_ in changes):
                    s,number=recovery_auxiliary_cluster(s,group,upper,exact,cell,count)
                    idx=stopidx;clusters+=1;branches+=number;count+=len(group)+1
                    continue
        if s['p']==1:
            section=s['fire'].plus(1).box()
            if section.lo<=upper and section.hi>=min(t.box().lo for t,_ in group):
                upper=max(upper,section.hi)
                while upper>suffix[stopidx]:
                    assert stopidx<len(pending)
                    upper=max(upper,pending[stopidx][0].box().hi);stopidx+=1
                group=pending[idx:stopidx]
                s,number=protected_section_cluster(s,group,upper,cell,count)
                idx=stopidx;clusters+=1;branches+=number;count+=len(group)+1
                continue
        if len(group)>1:
            lower=min(x[0].box().lo for x in group);L=v.T(f'{cell}:L:{count}',I(lower))
            s,kind=advance(s,L,cell,count);count+=1
            if kind!='external':
                if kind=='fire':out.append(s['t'])
                if kind=='gstop':stops+=1
                continue
            U=v.T(f'{cell}:U:{count}',I(upper));poss=[]
            for order in admissible_orders(s,group):
                ss=s
                for tt,actions in order:ss=act(flowing(ss,tt,True),actions)
                ss=flowing(ss,U,True);poss.append(ss)
            assert all(x['aux']==poss[0]['aux'] and x['p']==poss[0]['p'] and
                [(t.token() if t else None) for t in x['raw']]==[(t.token() if t else None) for t in poss[0]['raw']] for x in poss)
            s=join_states(poss,dict(cell=cell,batch=count,orders=len(poss),kind='external'))
            idx=stopidx;clusters+=1;branches+=len(poss);count+=len(group)
        else:
            tt,actions=group[0]
            try:s,kind=advance(s,tt,cell,count)
            except v.Ambiguous:
                if s['p']!=2:raise
                from cycle_local_A20 import pending_window,BranchingRequired
                forest,nextidx,handled=pending_window(s,pending,idx,cell,count)
                # Joining zero-emission ready branches is compatible with the
                # legacy single-train interface. Every other forest escapes
                # intact, including past outputs and pending physical events.
                if all(not x.emissions and x.state['p']==0 for x in forest.branches):
                    s=join_states([x.state for x in forest.branches],dict(cell=cell,batch=count,kind='local_cycle_no_emission'))
                    idx=nextidx;count+=len(handled)+1;clusters+=1;branches+=len(forest.branches)
                    continue
                continuation=dict(cell=cell,batch=count,completed_output_prefix=tuple(out),
                    pending=tuple(pending[nextidx:]),next_index=nextidx,join_time=forest.branches[0].state['t'],
                    outputs_complete_through_window=True,terminal_output_train_complete=False)
                raise BranchingRequired(forest,continuation)
            count+=1
            if kind=='external':s=act(s,actions);idx+=1
            elif kind=='fire':out.append(s['t'])
            elif kind=='gstop':stops+=1
        assert count<20000
    assert s['p']==0 and s['aux']==[0]*3 and s['raw']==[None]*3
    aux=[RM if tr else RM+I(-DELTA.hi,DELTA.hi)*(-K*(I(230)-U0)).exp() for tr in inputs]
    return out,dict(q=s['q'].pair(),g=[(C if s['caps'][j] else s['z'][j].exp()).pair() for j in range(3)],b=s['b'].pair(),E=[50,100],m=[x.pair() for x in aux],
        main_phase=0,aux_phases=[0]*3,pending=[],caps=s['caps'],b_stop=s['bstop'],gain_stops=sum(s['caps']),clusters=clusters,orders_enclosed=branches,events=count,
        width_profile=PROFILE.export(),actuation_summary=[dict(full_marks=h.full,partial_marks=len(h.partial),saturated=h.saturated) for h in s['actuation']],
        deposit_summary=[[dict(full_errors=h.full,partial_errors=len(h.partial),clamped=h.clamped) for h in hs] for hs in s['depot']],
        width=str(max((C if s['caps'][j] else s['z'][j].exp()).width() for j in range(3))),q_width=str(s['q'].width()),b_width=str(s['b'].width()),maximum_time_width=str(max((t.box().width() for t in out),default=D(0))))

def worker(item):return unit(*item)

def layer_metrics(n,row,trains):
    target=json.loads((ROOT/'domaine_A14_reference.json').read_text())['entry_gain_boxes'][n]
    margins=[];outside=[]
    for j,state in enumerate(row):
        for p,x in enumerate(state['g']):
            lo,hi=map(Fraction,x);a,b=map(Fraction,target[j][p])
            if a==b==4:a,b=map(Fraction,C.pair())
            margin=min(lo-a,b-hi);margins.append(margin)
            if margin<0:outside.append(dict(lane=j,port=p,margin_exact=str(margin)))
    return dict(layer=n+1,units=len(row),main_events=sum(len(tr) for tr in trains),
        q_width=max((state['q_width'] for state in row),key=D),
        gain_width=max((state['width'] for state in row),key=D),
        b_width=max((state['b_width'] for state in row),key=D),
        time_width=max((state['maximum_time_width'] for state in row),key=D),
        auxiliary_width=str(max(I(*v).width() for state in row for v in state['m'])),
        resource_interval=[50,100],gain_inclusion_margin_exact=str(min(margins)),
        gain_inclusion_margin_display=float(min(margins)),outside_reference_gain_boxes=len(outside),
        first_violations=outside[:5],
        invariant_domain_scope='Gain inclusion against the inherited A15 domain, with independent parameterised cap faces. Other hybrid-state conditions checked separately.')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--delta',default='1e-5');ap.add_argument('--epsilon',default='1e-4');ap.add_argument('--layers',type=int,default=18);ap.add_argument('--tag',default='candidate');ap.add_argument('--workers',type=int,default=1);ap.add_argument('--resume',action='store_true');args=ap.parse_args()
    iv.configure(160);cfg=settings(args.delta,args.epsilon);start=time.monotonic()
    trains=[[v.T('clock',I(0),D(8*k)) for k in range(128)]]+[[] for _ in range(11)]
    field=[];history=[];expressions=[];metrics=[];first=0
    if args.resume:
        source=ROOT/f'validation_{args.tag}_checkpoint.json'
        if not source.exists():source=ROOT/f'validation_{args.tag}.json'
        saved=json.loads(source.read_text())
        assert saved['settings']['delta']==args.delta and saved['settings']['epsilon']==args.epsilon
        field=saved['field'];history=saved['history'];first=len(field)
        expressions=saved['expressions_history'];metrics=saved['layer_metrics']
        trains=[[dep.decode_time(t) for t in tr] for tr in expressions[-1]]
    pool=ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('fork')) if args.workers>1 else None
    row=[];nxt=[];n=first
    try:
        for n in range(first,args.layers):
            nxt=[];row=[]
            jobs=[([trains[(j-1)%12],trains[j],trains[(j+1)%12]],f'{n+1},{j}') for j in range(12)]
            answers=pool.map(worker,jobs) if pool else map(worker,jobs)
            for j,(tr,state) in enumerate(answers):
                nxt.append(tr);row.append(state)
                print(json.dumps(dict(layer=n+1,lane=j,width=state['width'],q_width=state['q_width'],time_width=state['maximum_time_width'],seconds=round(time.monotonic()-start,1))),flush=True)
            trains=nxt;field.append(row);history.append([[t.box().pair() for t in tr] for tr in trains])
            expressions.append([[dep.encode_time(t) for t in tr] for tr in trains])
            metric=layer_metrics(n,row,trains);metrics.append(metric)
            result=dict(status='prefix_propagated',settings=cfg,field=field,history=history,
                expressions_history=expressions,layer_metrics=metrics,completed_layers=len(field))
            (ROOT/f'validation_{args.tag}.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(dict(layer_summary=metric)),flush=True)
        included=all(x['outside_reference_gain_boxes']==0 for x in metrics)
        for layer,row in enumerate(field):
            for j,state in enumerate(row):
                assert state['main_phase']==0 and state['aux_phases']==[0]*3 and state['pending']==[]
                assert max(abs(D(x)-D('.1')) for x in state['q'])<D('1e-10')
                assert all(max(abs(D(x)-D('.025')) for x in value)<D('1e-10') for value in state['m'])
        result['reference_gain_inclusion']=included
        result['status']='entry_certified' if args.layers==18 and included else 'prefix_propagated'
        result['elapsed_seconds']=round(time.monotonic()-start,1)
        (ROOT/f'validation_{args.tag}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(done=True,status=result['status'],reference_gain_inclusion=included)),flush=True)
    except Exception as exc:
        obstruction=dict(status='not_certified',delta=args.delta,epsilon=args.epsilon,completed_layers=len(field),
            failed_layer=n+1,completed_units_in_failed_layer=len(row),error=type(exc).__name__,message=str(exc),layer_metrics=metrics,
            partial_units=row,partial_times=[[t.box().pair() for t in tr] for tr in nxt])
        if hasattr(exc,'forest'):
            from etat_A20 import encode
            obstruction['disjoint_local_forest']=encode(exc.forest)
            obstruction['continuation']=encode(exc.continuation)
        (ROOT/f'obstruction_{args.tag}.json').write_text(json.dumps(obstruction,indent=2)+'\n')
        raise
    finally:
        if pool:pool.shutdown(cancel_futures=True)

if __name__=='__main__':main()
