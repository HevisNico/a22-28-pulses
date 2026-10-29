"""Exterior scheduling from certified causal differences and elapsed guards."""
from dataclasses import replace
import validation_A15 as b
import cycle_local_A20 as cyc
import dependances_A17 as dep
from histoires_A21 import History,extension,section_branches
from garde_relative_A22 import ready_to
import retour_file_A22 as queue_return
from intervalles_decimaux import I,D

def step(h,pending,suffix,cell):
    x=h.branch;s=x.state;idx=h.index;count=h.count
    stop=idx+1;upper=pending[idx][0].box().hi
    while stop<len(pending) and upper>suffix[stop]:
        upper=max(upper,pending[stop][0].box().hi);stop+=1
    group=pending[idx:stop]
    # Absolute overlap alone does not make a causal order ambiguous.
    # A single boundary can be selected when its common-date differences
    # prove it strictly earlier than every member of the overlap closure.
    if len(group)>1 and all(group[0][0].minus(t).hi<0 for t,_ in group[1:]):
        proof=dict(kind='causal_earliest_exterior_boundary',time=group[0][0],
            later_boundaries=tuple(t for t,_ in group[1:]),strict_relative_differences=True)
        x=replace(x,conditions=x.conditions+(proof,))
        stop=idx+1;upper=group[0][0].box().hi;group=pending[idx:stop]
    if len(group)>1 and s['p']==0:
        from groupe_pret_A21 import resolve as commute_ready,auxiliary_only
        common=commute_ready(x,group,upper,f'{cell}:commuting:{count}')
        if common is None:common=auxiliary_only(x,group,upper,f'{cell}:commuting:{count}')
        if common is not None:return [History(common,stop,count+len(group),h.lineage)]
    if s['p']==1:
        section=s['fire'].plus(1).box()
        if section.lo<=upper and section.hi>=min(t.box().lo for t,_ in group):
            upper=max(upper,section.hi)
            while stop<len(pending) and upper>suffix[stop]:
                upper=max(upper,pending[stop][0].box().hi);stop+=1
            ys=section_branches(x,pending[idx:stop],upper,cell,count)
            return [History(y,stop,count+stop-idx+1,h.lineage+(k,)) for k,y in enumerate(ys)]
    if len(group)>1:
        lower=min(t.box().lo for t,_ in group)
        L=dep.Time(f'{cell}:A21:L:{count}',I(lower))
        # A clock slab cannot precede any member of the state enclosure.
        if L.minus(s['t']).hi<0:raise b.v.Ambiguous('Exterior group lower slab precedes state')
        ss,kind=b.advance(s,L,cell,count)
        if kind!='external':
            y=replace(x,state=ss,emissions=x.emissions+(ss['t'],) if kind=='fire' else x.emissions,
                trace=x.trace+(dict(kind=kind,time=ss['t']),))
            return [History(y,idx,count+1,h.lineage)]
        U=dep.Time(f'{cell}:A21:U:{count}',I(upper));ys=[]
        for order in b.admissible_orders(ss,group):
            out=ss
            for tt,actions in order:out=b.act(b.flowing(out,tt,True),actions)
            out=b.flowing(out,U,True)
            ys.append(replace(x,state=out,conditions=x.conditions+(dict(kind='exterior_weak_order',order=tuple(t for t,_ in order)),),
                trace=x.trace+tuple(dict(kind='external',time=t,actions=a) for t,a in order)))
        if not ys:raise b.v.Ambiguous('No enclosing exterior order')
        return [History(y,stop,count+len(group)+1,h.lineage+(k,)) for k,y in enumerate(ys)]
    tt,actions=group[0]
    try:ss,kind=b.advance(s,tt,cell,count)
    except (b.v.Ambiguous,ValueError) as error:
        # The float-only root proposal may fail to bracket the midpoint
        # of a conditional box. It accepts nothing; the independent outer
        # guard cover below must still establish coverage by intervals.
        if isinstance(error,ValueError) and str(error)!='f(a) and f(b) must have different signs':raise
        if s['p']==2:
            forest,nextidx,handled=queue_return.pending_window(s,pending,idx,cell,count)
            return [History(extension(x,y),nextidx,count+len(handled)+1,h.lineage+(k,)) for k,y in enumerate(forest.branches)]
        if s['p']!=0:raise
        # A bounded clock slab can resolve a possible guard before a distant
        # exterior event. It is merely a verifier subdivision, with no act.
        endpoint=tt;external=True
        if tt.minus(s['t']).hi>=1:
            if tt.minus(s['t']).lo<=D('.5'):raise b.v.Ambiguous('Ready guard cover requires a finer causal-time partition')
            endpoint=s['t'].plus('.5');external=False
            import metriques_A22 as measurements
            measurements.count('ready_clock_cuts')
        ys=ready_to(x,endpoint,f'{cell}:A21:guard:{count}')
        return [History(replace(y,state=b.act(y.state,actions) if external else y.state),idx+int(external),count+1,h.lineage+(k,)) for k,y in enumerate(ys)]
    y=replace(x,state=b.act(ss,actions) if kind=='external' else ss,
        emissions=x.emissions+(ss['t'],) if kind=='fire' else x.emissions,
        trace=x.trace+(dict(kind=kind,time=ss['t'],actions=actions if kind=='external' else ()),))
    return [History(y,idx+int(kind=='external'),count+1,h.lineage)]
