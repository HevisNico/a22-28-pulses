"""Commuting exterior maps under uniformly certified protection.

The hypothetical continued protected history includes every new mark.
A positive logarithmic charge at the common endpoint excludes all returns
through the group. Raw currents and auxiliary phases remain explicit.
"""
from dataclasses import replace
import validation_A15 as b
import dependances_A17 as dep
import actuations_A19 as ac
from intervalles_decimaux import I,D

def resolve_all(x,group,upper,key):
 s=x.state
 if s['p'] not in (1,2) or any(v.active is not None for hs in s['depot'] for v in hs):return None
 if any(a=='end' for _,aa in group for a,_,_ in aa):return None
 if any(j not in (0,1,2) for _,aa in group for _,j,_ in aa):return None
 U=upper if hasattr(upper,'box') else dep.Time(key+':protected-U',I(upper))
 if U.minus(s['t']).hi<0:return None
 # A supplied endpoint must enclose every exterior date, either in an
 # absolute slab or in the same fire-relative coordinate used by caller.
 absolute=all(t.box().hi<=U.box().lo for t,_ in group)
 relative=U.key==s['fire'].key and all(t.minus(s['fire']).hi<=U.minus(s['fire']).lo for t,_ in group)
 if not (absolute or relative):return None
 out=s.copy()
 for name in ('raw','aux','mark','err'):out[name]=s[name].copy()
 ledgers=s['actuation'];own_orders=[]
 expected={'mark_on':0,'mark_off':1,'error_on':2,'error_off':3};nextphase={'mark_on':1,'mark_off':2,'error_on':3,'error_off':0}
 try:
  for port in range(3):
   events=[(t,a,o) for t,aa in group for a,j,o in aa if j==port]
   events.sort(key=lambda e:e[0].box().mid());previous=s['t'];path=[]
   for t,action,origin in events:
    difference=t.minus(previous)
    if difference.hi<0 or (path and difference.lo<0):return None
    if action in expected:
     if out['aux'][port]!=expected[action]:return None
     out['aux'][port]=nextphase[action]
     if action=='mark_on':
      out['mark'][port]=origin;ledgers=tuple(ac.on(v,port,origin) for v in ledgers)
     elif action=='mark_off':ledgers=tuple(ac.off(v,port,origin,t) for v in ledgers)
     elif action=='error_on':out['err'][port]=origin
    elif action=='raw_on':
     if out['raw'][port] is not None:return None
     out['raw'][port]=origin
    elif action=='raw_off':
     if out['raw'][port] is None:return None
     out['raw'][port]=None
    else:return None
    previous=t;path.append((t,action,origin))
   own_orders.append(tuple(path))
  section=U.minus(s['fire'].plus(1))
  if section.hi<0:
   if s['p']!=1:return None
   ell=I('2.5').ln()
  else:ell=ac.bounds(ledgers,U,'ell')
  rate=ac.bounds(ledgers,U)
  if ell.lo<=0:return None
  out.update(t=U,actuation=ledgers,b=rate,bstop=rate.lo==rate.hi==D('1.1'),memory=None)
 except (AssertionError,ValueError):return None
 proof=dict(kind='commuting_protected_exterior_group',events=tuple(group),per_port_orders=tuple(own_orders),
  retained_order_conditions='State precedes its pending boundaries; every listed per-port order is weakly nondecreasing. Unresolved interval inequalities remain conditions.',
  terminal_log_charge=ell,all_returns_excluded=True,no_gain_actuation=True,
  recovery_marks_integrated_with_shared_history=True,all_inter_port_orders_covered=True,
  reason='Continued protection gives monotone logarithmic charge. Every new mark is included before testing its endpoint; raw/auxiliary per-port maps commute while gains remain closed.')
 results=[];section=U.minus(s['fire'].plus(1))
 if s['p']==1 and section.lo<=0:
  fast={**out,'p':1,'q':(-b.A*U.minus(s['fire']).intersect(I(0,1))).exp()}
  results.append(replace(x,state=fast,conditions=x.conditions+(proof,dict(kind='fast_at_endpoint',endpoint=U)),trace=x.trace+(proof,)))
 if s['p']==2 or section.hi>=0:
  charge=b.R*ell.exp()
  if charge.hi>=b.R.lo and charge.lo<=D('.25'):
   slow={**out,'p':2,'q':charge.intersect(I(b.R.lo,'.25'))}
   results.append(replace(x,state=slow,conditions=x.conditions+(proof,dict(kind='slow_at_endpoint',endpoint=U)),trace=x.trace+(proof,)))
 return tuple(results) if results else None

def resolve(x,group,upper,key):
 results=resolve_all(x,group,upper,key)
 return results[0] if results is not None and len(results)==1 else None
