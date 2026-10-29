"""A return bound from the complete known queue, in continued protection.

This is a verifier lemma, not a physical control law. Until its first return,
the principal remains protected; every pending monitor mark therefore has
its natural primitive in that hypothetical protected continuation. Marks
starting after the zero contribute zero before it.
"""
from dataclasses import replace
import validation_A15 as b
import branche_retour_A19 as recovery
import actuations_A19 as ac
import cycle_local_A20 as cyc
import cycle_relatif_A22 as relative_cycle
from intervalles_decimaux import I,D

def anticipate(s,pending,index,key):
 late=recovery.return_with_marks(s,key+':without-new-marks')
 ledgers=s['actuation'];added=[]
 for t,aa in pending[index:]:
  if t.box().lo>late.box().hi:continue
  for action,j,origin in aa:
   if action!='mark_on':continue
   ledgers=tuple(ac.on(v,j,origin) for v in ledgers);added.append((t,j,origin))
 hypothetical={**s,'actuation':ledgers}
 exact=recovery.return_with_marks(hypothetical,key+':all-protected-marks')
 # Nonnegative marks cannot delay the first return.
 box=exact.box().intersect(I(s['t'].box().lo,late.box().hi))
 exact=b.dep.Time(exact.key+':restricted',box,terms=exact.expression())
 return exact,dict(kind='first_return_from_complete_queue',unforced_return=late,
  additional_marks=tuple(added),return_time=exact,
  hypothesis='Continued protection only until its first logarithmic zero; future marks retain their natural unfinished primitives',
  source='Complete already-validated exterior queue; no new physical feedback or observation is added')

def pending_window(s,pending,index,cell,count):
 ready,proof=anticipate(s,pending,index,f'{cell}:{count}:A22-return')
 upper=ready.box().hi;stop=index;group=[]
 while stop<len(pending):
  rest_lower=min(t.box().lo for t,_ in pending[stop:])
  if rest_lower>=upper:break
  t,actions=pending[stop];upper=max(upper,t.box().hi);group.append((t,actions));stop+=1
 if not group:raise b.v.Ambiguous('Queue-derived return window has no exterior overlap')
 forest=relative_cycle.resolve(s,group,upper,ready,cell,count)
 branches=tuple(replace(x,conditions=(proof,)+x.conditions) for x in forest.branches)
 return cyc.Forest(branches,{**forest.certificate,'queue_derived_return':proof}),stop,group
