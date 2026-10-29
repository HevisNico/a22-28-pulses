"""Conditional first-guard covers in elapsed time, retaining the anchor.

Absolute clock uncertainty is not elapsed-time uncertainty. Every probe
and the returned conditional root keep the same starting time expression.
"""
from dataclasses import replace
import validation_A15 as b
import cycle_local_A20 as cyc
import dependances_A17 as dep
from intervalles_decimaux import I,D
import metriques_A22 as measurements
from ready_general_A22 import ready_endpoint, scalar_root, peak_upper

def cover(s,tt,key,depth=7):
 J,_,_=b.coefficients(s);H=tt.minus(s['t']).nonnegative().hi
 earliest=scalar_root(s['q'].hi,J.hi,H,key+':upper')
 lo=D(0) if earliest is None else earliest.lo;hi=H
 latest=scalar_root(s['q'].lo,J.lo,H,key+':lower')
 if latest is not None:hi=min(hi,latest.hi)
 if hi<lo:return None,[]
 stack=[(lo,hi,0)];parts=[]
 while stack:
  a,z,n=stack.pop();probe=b.shift(s['t'],I(a,z),key+f':probe:{n}')
  value=dep.evaluate(s['memory'],probe) if s.get('memory') is not None else b.v.ready(s['q'],J,I(a,z))
  if value.hi<1 or value.lo>1:continue
  if n>=depth or a==z:parts.append((a,z));continue
  midpoint=I(a,z).mid();measurements.count('guard_cover_bisections');stack.extend([(a,midpoint,n+1),(midpoint,z,n+1)])
 if not parts:return None,[]
 root=b.shift(s['t'],I(min(a for a,z in parts),max(z for a,z in parts)),key+':conditional-first-fire')
 return root,parts

def ready_to(x,tt,key):
 s=x.state
 if s['p']!=0:raise b.v.Ambiguous('General ready cover requires READY mode')
 if tt.minus(s['t']).hi<0:return []
 outcomes=[];possible=peak_upper(s,tt)>=1
 end=ready_endpoint(b.flowing(s,tt,False))
 if end is not None:
  outcomes.append(replace(x,state=end,conditions=x.conditions+(dict(kind='no_fire_through',time=tt),)))
 if possible:
  fire,parts=cover(s,tt,key)
  if fire is not None:
   at=b.fire_reset(b.flowing(s,fire,False));fired=cyc._fast_flow(at,tt)
   outcomes.append(replace(x,state=fired,emissions=x.emissions+(fire,),
    conditions=x.conditions+(dict(kind='conditional_first_threshold',start=s['t'],end=tt,root=fire,
      guard='q(root)=1 and no previous crossing',elapsed_time_cover=parts,
      coordinate='root = starting time + covered elapsed duration; the common anchor is retained',
      existence='Outer may branch; existence for every parameter is not asserted'),),
    trace=x.trace+(dict(kind='fire',time=fire),)))
 if not outcomes:raise b.v.Ambiguous('Relative ready cover has no enclosing outcome')
 return outcomes
