"""Fast-section order from exact time differences; physical maps unchanged."""
import validation_A15 as b
from intervalles_decimaux import D

def advance(s,boundary,cell,count,original):
 if s['p']==1:
  section=s['fire'].plus(1);difference=section.minus(boundary)
  if difference.hi<0 or difference.lo==difference.hi==0:
   out=b.flowing(s,section);out['q']=b.I('.25');out['p']=2
   return out,'slow'
  if difference.lo>0:return b.flowing(s,boundary),'external'
 return original(s,boundary,cell,count)
