"""Finite-cycle cover using the elapsed-time first-guard lemma."""
from dataclasses import replace
import validation_A15 as b
import actuations_A19 as ac
import dependances_A17 as dep
import branche_retour_A19 as recovery
from cycle_local_A20 import Branch,Forest,no_new_fire_bound,_fast_flow
from garde_relative_A22 import ready_to
from intervalles_decimaux import I,D

def _until(x,tt,key):
    if x.state['p']==0:return ready_to(x,tt,key)
    if x.state['p']==1:
        if len(x.emissions)!=1:raise b.v.Ambiguous('Untracked principal fast cycle in relative branch')
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
