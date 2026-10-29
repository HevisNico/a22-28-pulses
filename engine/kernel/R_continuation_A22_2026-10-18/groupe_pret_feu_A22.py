"""A bounded ready/exterior cluster with zero or one optional first fire."""
from dataclasses import replace
import validation_A15 as b
import histoires_A21 as h
import cycle_local_A20 as cyc
from garde_relative_A22 import ready_to
import dependances_A17 as dep
from intervalles_decimaux import I,D

def resolve(history,pending,suffix,cell,budget=2048):
 x=history.branch;s=x.state;idx=history.index;count=history.count
 if s['p']!=0:raise b.v.Ambiguous('Ready cluster requires initial READY mode')
 stop=idx+1;upper=pending[idx][0].box().hi
 while stop<len(pending) and upper>suffix[stop]:upper=max(upper,pending[stop][0].box().hi);stop+=1
 group=pending[idx:stop];lower=min(t.box().lo for t,_ in group)
 L=dep.Time(f'{cell}:A22:ready-L:{count}',I(lower));U=dep.Time(f'{cell}:A22:ready-U:{count}',I(upper))
 try:ss,kind=b.advance(s,L,cell,count)
 except (b.v.Ambiguous,ValueError):
  # Retain all first-guard possibilities from the original state when
  # the entire exterior group is inside one fast-section-sized window.
  cyc.no_new_fire_bound(dep.Time(f'{cell}:A22:ready-start:{count}',I(s['t'].box().lo)),upper)
  ss=s;kind='external';L=dep.Time(f'{cell}:A22:ready-start:{count}',I(s['t'].box().lo))
 if kind!='external':
  y=replace(x,state=ss,emissions=x.emissions+(ss['t'],) if kind=='fire' else x.emissions,trace=x.trace+(dict(kind=kind,time=ss['t']),))
  return [h.History(y,idx,count+1,history.lineage)]
 if ss['q'].lo<b.R.lo:raise b.v.Ambiguous('Optional ready cluster requires charge at least r')
 bound=cyc.no_new_fire_bound(L,upper)
 finished=[];orders=0
 for order in b.admissible_orders(ss,group):
  branches=[cyc.Branch(ss,conditions=(dict(kind='ready_exterior_cluster_order',order=tuple(t for t,_ in order),bound=bound),))]
  for k,(tt,actions) in enumerate(order):
   children=[]
   for local in branches:
    if local.state['p']==0:ys=ready_to(local,tt,f'{cell}:A22:ready:{count}:{orders}:{k}:{len(children)}')
    elif local.state['p']==1:ys=[replace(local,state=cyc._fast_flow(local.state,tt))]
    else:raise b.v.Ambiguous('Unexpected mode inside bounded ready cluster')
    for y in ys:children.append(replace(y,state=b.act(y.state,actions),trace=y.trace+(dict(kind='external',time=tt,actions=actions),)))
   branches=children
   if len(branches)+len(finished)>budget:raise b.v.Ambiguous('Ready exterior cluster branch budget exceeded')
  for local in branches:
   ys=ready_to(local,U,f'{cell}:A22:ready:{count}:{orders}:end:{len(finished)}') if local.state['p']==0 else [replace(local,state=cyc._fast_flow(local.state,U))]
   finished.extend(ys)
  orders+=1
  if len(finished)>budget:raise b.v.Ambiguous('Ready exterior cluster branch budget exceeded')
 if not finished:raise b.v.Ambiguous('Ready exterior cluster has no covering branch')
 return [h.History(h.extension(x,local),stop,count+len(group)+1,history.lineage+(i,)) for i,local in enumerate(finished)]
