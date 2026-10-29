"""Outer reachability for one return and at most one additional firing.

A conditional guard enclosure is NOT a claim that every parameter fires.
The complementary no-fire branch is retained unless contradicted by an
endpoint bound. Distinct emission histories are never flattened or joined.
"""
from dataclasses import dataclass,replace
import validation_A15 as b
import actuations_A19 as ac
import dependances_A17 as dep
import branche_retour_A19 as recovery
from intervalles_decimaux import I,D,hull

@dataclass(frozen=True)
class Branch:
    state:dict
    emissions:tuple=()
    conditions:tuple=()
    trace:tuple=()

@dataclass(frozen=True)
class Forest:
    branches:tuple
    certificate:dict
    def flat_train(self):
        raise b.v.Ambiguous('Disjoint pulse histories require scenario propagation; flattening is forbidden')
    def downstream(self):
        """One shared scenario ID for every destination of a source branch."""
        return tuple(dict(scenario_id=f'branch-{k}',source_pulses=x.emissions,
            pending_currents=tuple(dict(start=t,end=t.plus(1),amplitude=b.A,decay=b.A) for t in x.emissions),
            conditions=x.conditions,event_order=x.trace) for k,x in enumerate(self.branches))

def no_new_fire_bound(coarse,upper):
    width=I(upper)-I(coarse.box().lo)
    tau=1+I('2.5').ln()/I('1.1')
    if width.lo<0 or width.hi>=tau.lo:
        raise b.v.Ambiguous('One-additional-fire bound not certified for this window')
    # This implementation uses the stronger local fact to avoid a further
    # fast/slow split. Wider windows remain explicitly unsupported.
    if width.hi>=1:raise b.v.Ambiguous('Local solver requires the post-fire fast phase to cover the window')
    return dict(window_width=width.pair(),minimum_interfire=tau.pair(),
        one_fire_margin=(tau-width).pair(),fast_phase_margin=(1-width).pair(),maximum_additional_fires=1)

def _scalar_root(q,j,horizon,key):
    if q>=1:return I(0)
    if j<=0:return None
    qi=I(q);ji=I(j);bb=ji/(b.A-b.K);aa=qi-b.R+bb
    pk=(b.A*bb/(b.K*aa)).ln()/(b.A-b.K)
    hi=min(horizon,max(D(0),pk.lo))
    if hi<=0:return None
    f=lambda u:b.v.ready(qi,ji,u)-1
    if f(I(hi)).lo<=0:return None
    df=lambda u:-b.K*(qi-b.R+bb)*(-b.K*u).exp()+b.A*bb*(-b.A*u).exp()
    return b.v.root(f,df,D(0),hi,b.v.guessroot(f,hi))

def _peak_upper(s,tt):
    J,_,_=b.coefficients(s);H=tt.minus(s['t']).nonnegative().hi
    if J.hi<=0:return s['q'].hi
    # A scalar comparison, monotone in q(0) and J(0), bounds the whole
    # counterfactual ready trajectory between consecutive exterior events.
    q=I(s['q'].hi);j=I(J.hi);bb=j/(b.A-b.K);aa=q-b.R+bb
    pk=(b.A*bb/(b.K*aa)).ln()/(b.A-b.K)
    at=I(min(H,max(D(0),pk.lo)),min(H,max(D(0),pk.hi)))
    return b.v.ready(q,j,at).hi

def _guard_cover(s,tt,key,depth=7):
    """Enclose every possible first threshold time, without assuming existence.

    Scalar comparison gives time bounds; interval subdivision only discards
    a time slab when the counterfactual charge cannot equal one there.
    Extra, infeasible roots may remain. They make this an outer cover.
    """
    J,_,_=b.coefficients(s);H=tt.minus(s['t']).nonnegative().hi
    earliest=_scalar_root(s['q'].hi,J.hi,H,key+':upper')
    lo=(s['t'].box()+I(0 if earliest is None else earliest.lo)).lo
    hi=tt.box().hi
    latest=_scalar_root(s['q'].lo,J.lo,H,key+':lower')
    if latest is not None:hi=min(hi,(s['t'].box()+I(latest.hi)).hi)
    if hi<lo:return None,[]
    stack=[(lo,hi,0)];cover=[]
    while stack:
        a,z,n=stack.pop();probe=dep.Time(key+f':probe:{n}',I(a,z))
        value=dep.evaluate(s['memory'],probe) if s.get('memory') is not None else b.v.ready(s['q'],J,probe.minus(s['t']).nonnegative())
        if value.hi<1 or value.lo>1:continue
        if n>=depth or a==z:cover.append((a,z));continue
        m=I(a,z).mid();stack.extend([(a,m,n+1),(m,z,n+1)])
    if not cover:return None,[]
    root=dep.Time(key+':conditional-first-fire',I(min(x[0] for x in cover),max(x[1] for x in cover)))
    return root,cover

def _fast_flow(s,tt):
    age=tt.minus(s['fire']).nonnegative()
    if age.hi>=1:raise b.v.Ambiguous('Post-fire fast section may end inside this local window')
    out=b.flowing(s,tt,False)
    out['q']=(-b.A*age).exp();out['p']=1
    return out

def _ready_to(x,tt,key):
    s=x.state
    if tt.minus(s['t']).hi<0:return []
    possible=_peak_upper(s,tt)>=1
    outcomes=[]
    # Even when the upper peak exceeds threshold, some members may not
    # cross. Keep their endpoint intersected with the ready-mode domain.
    end=b.flowing(s,tt,False)
    if end['q'].lo<=1 and end['q'].hi>=b.R.lo:
        end['q']=end['q'].intersect(I(b.R.lo,1))
        outcomes.append(replace(x,state=end,conditions=x.conditions+(dict(kind='no_fire_through',time=tt),)))
    if possible:
        fire,cover=_guard_cover(s,tt,key)
        if fire is not None:
            at=b.flowing(s,fire,False)
            at=b.fire_reset(at)
            fired=_fast_flow(at,tt)
            outcomes.append(replace(x,state=fired,emissions=x.emissions+(fire,),
                conditions=x.conditions+(dict(kind='conditional_first_threshold',start=s['t'],end=tt,root=fire,
                    guard='q(counterfactual root)=1 and no previous crossing',time_cover=cover,
                    existence='May branch only; existence for every parameter is not asserted'),),
                trace=x.trace+(dict(kind='fire',time=fire),)))
    if not outcomes:raise b.v.Ambiguous('Ready-mode split has no enclosing outcome')
    return outcomes

def _until(x,tt,key):
    if x.state['p']==0:return _ready_to(x,tt,key)
    if x.state['p']==1:
        if len(x.emissions)!=1:raise b.v.Ambiguous('Untracked principal fast cycle in local branch')
        return [replace(x,state=_fast_flow(x.state,tt))]
    raise b.v.Ambiguous('Unexpected mode after the initial local return')

def resolve(s,group,upper,coarse,cell,count,branch_budget=256):
    if s['p']!=2:raise b.v.Ambiguous('Local cycle resolver requires an initial slow protected state')
    if any(a=='end' for _,actions in group for a,_,_ in actions):raise b.v.Ambiguous('Terminal event inside local cycle window')
    certificate=no_new_fire_bound(coarse,upper)
    U=dep.Time(f'{cell}:{count}:A20-window-end',I(upper))
    # Completeness of group vs pending queue is a caller obligation, recorded
    # and checked by the fixture driver against the first excluded boundary.
    events=list(group)+[(coarse,[('principal_ready',-1,None)])]
    final=[];pruned=[];order_count=0
    for ordinal,order in enumerate(b.admissible_orders(s,events)):
        order_count+=1;branches=[Branch(s)]
        for k,(tt,actions) in enumerate(order):
            next_branches=[]
            for x in branches:
                if actions[0][0]=='principal_ready':
                    if x.state['p']!=2:raise b.v.Ambiguous('Duplicate initial return')
                    ready=recovery.return_with_marks(x.state,f'{cell}:{count}:order-{ordinal}')
                    prefix=[(e['time'],[]) for e in x.trace]
                    refined=prefix+[(ready,actions)]+list(order[k+1:])
                    if not b.possible_order(s['t'],refined):pruned.append('contradictory return order');continue
                    # Restrict its absolute enclosure without discarding its
                    # common-date expressions (which remain an outer bound).
                    if ready.box().hi<coarse.box().lo or ready.box().lo>coarse.box().hi:
                        pruned.append('return outside certified coarse window');continue
                    box=ready.box().intersect(coarse.box())
                    ready=dep.Time(ready.key+':restricted-absolute',box,terms=ready.expression())
                    out=b.reopen(x.state,ready)
                    next_branches.append(replace(x,state=out,
                        conditions=x.conditions+(dict(kind='initial_return',time=ready),),
                        trace=x.trace+(dict(kind='ready',time=ready),)))
                elif x.state['p']==2:
                    out=b.flowing(x.state,tt,False)
                    if out['q'].hi<b.R.lo or out['q'].lo>D('.25'):
                        pruned.append('empty initial slow-phase domain');continue
                    out['q']=out['q'].intersect(I(b.R.lo,'.25'));out=b.act(out,actions)
                    next_branches.append(replace(x,state=out,trace=x.trace+(dict(kind='external',time=tt,actions=actions),)))
                else:
                    for y in _until(x,tt,f'{cell}:{count}:{ordinal}:{k}:{len(next_branches)}'):
                        out=b.act(y.state,actions)
                        next_branches.append(replace(y,state=out,trace=y.trace+(dict(kind='external',time=tt,actions=actions),)))
            branches=next_branches
            if len(branches)>branch_budget:raise b.v.Ambiguous('Local-cycle branch budget exceeded')
            if not branches:break
        for x in branches:final.extend(_until(x,U,f'{cell}:{count}:{ordinal}:end:{len(final)}'))
        if len(final)>branch_budget:raise b.v.Ambiguous('Local-cycle branch budget exceeded')
    if not final:raise b.v.Ambiguous('No local-cycle branch remained enclosing')
    assert all(len(x.emissions)<=1 and x.state['p'] in (0,1) for x in final)
    assert all(x.state['aux']==final[0].state['aux'] and x.state['raw']==final[0].state['raw'] for x in final)
    certificate.update(status='local_outer_reachability_certified',external_orders_considered=order_count,
        pruned_orders=pruned,branches=len(final),pulse_counts_retained=sorted(set(len(x.emissions) for x in final)),
        principal_modes_retained=sorted(set(x.state['p'] for x in final)),
        scope='Outer cover from the validated initial enclosure. Conditional branches may be spurious; existence of both pulse counts is not certified. No reunion is required and no different emission counts are merged.',
        new_main_fire_is_not_failure=True)
    return Forest(tuple(final),certificate)

class BranchingRequired(b.v.Ambiguous):
    """A valid local forest cannot be represented by a single output train."""
    def __init__(self,forest,continuation):
        self.forest=forest;self.continuation=continuation
        super().__init__('Local cycle enclosed; disjoint pulse histories require branch-aware continuation')
    def __reduce__(self):
        return type(self),(self.forest,self.continuation)

def pending_window(s,pending,index,cell,count):
    late=recovery.return_with_marks(s,f'{cell}:{count}:pending')
    upper=late.box().hi;stop=index;group=[]
    # Include the complete transitive overlap group through the latest
    # unforced return. New positive marks can only move the return earlier.
    while stop<len(pending):
        rest_lower=min(t.box().lo for t,_ in pending[stop:])
        if rest_lower>=upper:break
        t,actions=pending[stop];upper=max(upper,t.box().hi)
        group.append((t,actions));stop+=1
    if not group:raise b.v.Ambiguous('No exterior group for the local return window')
    coarse=recovery.enclosure(s,group,f'{cell}:{count}:pending')
    result=resolve(s,group,upper,coarse,cell,count)
    return result,stop,group
