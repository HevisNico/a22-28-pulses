"""Wide-layer consumer of the frozen A20 kernel; whole histories never join.

All clocks, ledgers, ready memories and emitted pulses belong to one record.
Queue cursors are also per record. A refusal preserves the entire frontier.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'R_cycle_local_A20_2026-10-18'))
from dataclasses import dataclass,replace,fields,is_dataclass
import validation_A15 as b
import cycle_local_A20 as cyc
import actuations_A19 as ac
import dependances_A17 as dep
from intervalles_decimaux import I,D

@dataclass(frozen=True)
class History:
    branch:cyc.Branch
    index:int=0
    count:int=0
    lineage:tuple=()

class Refusal(Exception):
    def __init__(self,message,frontier,finished=()):
        self.frontier=tuple(frontier);self.finished=tuple(finished)
        super().__init__(message)

def structural(x):
    """Exact expression identity, including every ledger and shared time atom.

    This is deliberately stronger than equality of displayed boxes. It never
    identifies two different emitted dates or two different gate histories.
    """
    if isinstance(x,I):return ('interval',tuple(x.pair()))
    if isinstance(x,D):return ('decimal',str(x))
    if is_dataclass(x):return (type(x).__name__,tuple((f.name,structural(getattr(x,f.name))) for f in fields(x)))
    if isinstance(x,dict):return ('map',tuple(sorted(((structural(k),structural(v)) for k,v in x.items()),key=repr)))
    if isinstance(x,(tuple,list)):return (type(x).__name__,tuple(structural(v) for v in x))
    return x

def share_identical(parent,children):
    """Share a continuation only for equal full state/output expressions.

    The alternatives remain an explicit OR of JOINT conditions and traces.
    No interval hull, Cartesian product, pulse union or guard is introduced.
    """
    if len(children)<2:return children,0
    groups={}
    for child in children:
        key=(child.index,child.count,structural(child.branch.state),structural(child.branch.emissions))
        groups.setdefault(key,[]).append(child)
    result=[];shared=0
    for same in groups.values():
        if len(same)==1:result.extend(same);continue
        alternatives=tuple(dict(lineage=c.lineage,
            conditions=c.branch.conditions[len(parent.branch.conditions):],
            trace=c.branch.trace[len(parent.branch.trace):]) for c in same)
        node=dict(kind='exact_joint_payload_alternatives',alternatives=alternatives,
            rule='identical full state and output expressions; all prior weak orders retained')
        c=same[0];y=replace(c.branch,conditions=parent.branch.conditions+(node,),trace=parent.branch.trace+(node,))
        result.append(replace(c,branch=y,lineage=parent.lineage+(('same_payload',tuple(c.lineage[-1] for c in same)),)))
        shared+=len(same)-1
    return result,shared

def extension(x,y):
    """A local solver starts its emission tuple empty; append to its parent."""
    return cyc.Branch(y.state,x.emissions+y.emissions,x.conditions+y.conditions,x.trace+y.trace)

def section_branches(x,group,upper,cell,count):
    s=x.state;section=s['fire'].plus(1)
    U=dep.Time(f'{cell}:A21:section:{count}',I(upper))
    if U.box().lo<section.box().hi or min(t.box().lo for t,_ in group)<s['t'].box().hi:
        raise b.v.Ambiguous('Protected section group is not bracketed')
    result=[]
    # Fast and slow have identical admission/deposit/actuation gates.
    # Their order against the section is immaterial to those gates. Prove
    # the return absent throughout using monotone recovery dose at U.
    for order in b.admissible_orders(s,group):
        ss=s
        for tt,actions in order:ss=b.act(b.flowing(ss,tt),actions)
        ss=b.flowing(ss,U);ell=ac.bounds(ss['actuation'],U,'ell')
        if ell.lo<=0:raise b.v.Ambiguous('Recovery may lie inside protected section group')
        ss['q']=b.R*ell.exp();ss['p']=2;ss['memory']=None
        result.append(replace(x,state=ss,conditions=x.conditions+(dict(kind='protected_section_order',order=tuple(t for t,_ in order),section=section),),
            trace=x.trace+tuple(dict(kind='external',time=t,actions=a) for t,a in order)+(dict(kind='slow',time=section),)))
    if not result:raise b.v.Ambiguous('Empty protected section cover')
    return result

def step(h,pending,suffix,cell):
    x=h.branch;s=x.state;idx=h.index;count=h.count
    stop=idx+1;upper=pending[idx][0].box().hi
    while stop<len(pending) and upper>suffix[stop]:
        upper=max(upper,pending[stop][0].box().hi);stop+=1
    group=pending[idx:stop]
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
            forest,nextidx,handled=cyc.pending_window(s,pending,idx,cell,count)
            return [History(extension(x,y),nextidx,count+len(handled)+1,h.lineage+(k,)) for k,y in enumerate(forest.branches)]
        if s['p']!=0:raise
        # A bounded clock slab can resolve a possible guard before a distant
        # exterior event. It is merely a verifier subdivision, with no act.
        endpoint=tt;external=True
        if tt.minus(s['t']).hi>=1:
            value=(I(s['t'].box().hi)+I('.5')).hi
            if value>=tt.box().lo:raise b.v.Ambiguous('Ready guard cover wider than supported fast section')
            endpoint=dep.Time(f'{cell}:A21:subdivide:{count}',I(value));external=False
        ys=cyc._ready_to(x,endpoint,f'{cell}:A21:guard:{count}')
        return [History(replace(y,state=b.act(y.state,actions) if external else y.state),idx+int(external),count+1,h.lineage+(k,)) for k,y in enumerate(ys)]
    y=replace(x,state=b.act(ss,actions) if kind=='external' else ss,
        emissions=x.emissions+(ss['t'],) if kind=='fire' else x.emissions,
        trace=x.trace+(dict(kind=kind,time=ss['t'],actions=actions if kind=='external' else ()),))
    return [History(y,idx+int(kind=='external'),count+1,h.lineage)]

def run(initial,pending,cell='10,2',budget=2048,on_progress=None,finish_tail=None,checkpoint=None):
    suffix=[D('Infinity')]*(len(pending)+1)
    for k in range(len(pending)-1,-1,-1):suffix[k]=min(suffix[k+1],pending[k][0].box().lo)
    stack=list(initial);finished=[];steps=0;peak=len(stack);shared=0;regenerative=0
    while stack:
        h=stack.pop()
        if h.index==len(pending):finished.append(h);continue
        try:
            if finish_tail is not None:
                terminal=finish_tail(h,pending,cell)
                if terminal is not None:
                    if terminal.index!=len(pending):raise b.v.Ambiguous('Suffix certificate did not consume the complete queue')
                    finished.append(terminal);regenerative+=1
                    if checkpoint:checkpoint(tuple(stack),tuple(finished))
                    continue
            children=step(h,pending,suffix,cell)
            if not children:raise b.v.Ambiguous('A history disappeared without an exclusion proof')
            children,number=share_identical(h,children);shared+=number
            if h.count>20000:raise b.v.Ambiguous('Per-history event budget exceeded')
            if len(stack)+len(finished)+len(children)>budget:
                raise b.v.Ambiguous('Whole-history branch budget exceeded; no histories merged')
        except Exception as e:
            raise Refusal(f'{type(e).__name__}: {e}',stack+[h],finished) from e
        stack.extend(reversed(children));steps+=1;peak=max(peak,len(stack)+len(finished))
        if checkpoint and steps%50==0:checkpoint(tuple(stack),tuple(finished))
        if on_progress and steps%20==0:on_progress(dict(steps=steps,pending_index=h.index,events=len(pending),time=h.branch.state['t'].box().pair(),histories=len(stack)+len(finished),finished=len(finished),exact_payload_shares=shared))
    return tuple(finished),dict(steps=steps,peak_histories=peak,whole_histories_merged=0,interval_hulls=0,exact_payload_shares=shared,certified_regenerative_suffixes=regenerative)
