"""Case partition of a completed, constant slow-phase recovery rate.

If every mark of this cycle ended before the slow section, its total
actuation is deposited before that section. Replacing the completed ledger
by that SAME rate as baseline preserves b(t) and its entire slow dose.
The old ledger and the equality binding remain in the branch conditions.
"""
from dataclasses import replace
import validation_A15 as b
import actuations_A19 as ac
from intervalles_decimaux import I,D
import metriques_A22 as measurements

def split(history,key):
 x=history.branch;s=x.state
 if s['p']!=2:return None
 section=s['fire'].plus(1);children=[]
 for ordinal,ledger in enumerate(s['actuation']):
  early=[mark for mark in ledger.marks if mark.end is not None and section.minus(mark.end).lo>=0]
  later=tuple(mark for mark in ledger.marks if mark not in early)
  B=ac.clip(ac.baseline(ledger)+sum((ac.final_potential(mark) for mark in early),I(0)))
  if B.lo==B.hi:return None
  midpoint=B.mid()
  if not B.lo<midpoint<B.hi:return None
  measurements.count('recovery_rate_partitions')
  for k,part in enumerate((I(B.lo,midpoint),I(midpoint,B.hi))):
   normal=ac.History(part,fire=s['fire'],marks=later,saturated=part.lo==part.hi==D('1.1'))
   q=(b.R*ac.ell(normal,s['t']).exp())
   if q.hi<s['q'].lo or q.lo>s['q'].hi or q.hi<b.R.lo or q.lo>D('.25'):continue
   q=q.intersect(s['q']).intersect(I(b.R.lo,'.25'))
   current=ac.rate(normal,s['t'])
   out={**s,'actuation':(normal,),'b':current,'q':q,'bstop':current.lo==current.hi==D('1.1')}
   proof=dict(kind='constant_slow_rate_case_partition',source_ledger=ledger,
    new_baseline=part,original_current_rate=B,slow_section=section,
    retained_equality='new baseline = actual rate deposited by the slow section; every later mark remains in the ledger',
    folded_marks=tuple(early),retained_later_marks=later,
    dose_identity='Same slow-phase rate and dose after folding only completed pre-section marks; later primitives retained',
    case=(ordinal,k),split_point=str(midpoint),initial_box_unchanged=True)
   y=replace(x,state=out,conditions=x.conditions+(proof,))
   children.append(type(history)(y,history.index,history.count+1,history.lineage+(('rate-partition',ordinal,k),)))
 if not children:raise b.v.Ambiguous('No constant-rate partition is consistent with the validated state')
 return children
