"""Independent check of fixed future-wave brackets using directed Decimal
operations and unscaled Taylor series. No root search, engine import or replay.
Decimal exp/ln are not used. All transcendental bounds are finite series with
explicit positive remainders; arithmetic uses two 70-digit directed contexts.
"""
import json,sys,hashlib
from pathlib import Path
from decimal import Decimal as D,Context,ROUND_FLOOR,ROUND_CEILING
LO=Context(prec=70,rounding=ROUND_FLOOR);HI=Context(prec=70,rounding=ROUND_CEILING)
class B:
 def __init__(self,x,hi=None):
  if isinstance(x,B):self.l,self.u=x.l,x.u;return
  self.l=D(str(x));self.u=D(str(x if hi is None else hi));assert self.l<=self.u
 def __add__(a,b):
  b=B(b);return B(LO.add(a.l,b.l),HI.add(a.u,b.u))
 __radd__=__add__
 def __neg__(a):return B(a.u.copy_negate(),a.l.copy_negate())
 def __sub__(a,b):return a+-B(b)
 def __rsub__(a,b):return B(b)+-a
 def __mul__(a,b):
  b=B(b);pairs=[(x,y) for x in (a.l,a.u) for y in (b.l,b.u)]
  return B(min(LO.multiply(x,y) for x,y in pairs),max(HI.multiply(x,y) for x,y in pairs))
 __rmul__=__mul__
 def __truediv__(a,b):
  b=B(b);assert not b.l<=0<=b.u
  pairs=[(x,y) for x in (a.l,a.u) for y in (b.l,b.u)]
  return B(min(LO.divide(x,y) for x,y in pairs),max(HI.divide(x,y) for x,y in pairs))
 def pair(a):return [str(a.l),str(a.u)]

def positive_exp(x):
 assert 0<=x.l<=x.u<=2
 t=s=B(1)
 for k in range(1,91):t=t*x/k;s=s+t
 remainder=t*x/91/(B(1)-x/92)
 return B(s.l,HI.add(s.u,remainder.u))

def ep(x):return B(1)/positive_exp(B(x.copy_negate())) if x<0 else positive_exp(B(x))
def exp(x):return B(ep(x.l).l,ep(x.u).u)
def log(x):
 y=(x-1)/(x+1);y2=y*y;p=y;s=B(0)
 for k in range(250):s=s+p/(2*k+1);p=p*y2
 tail=p/501/(B(1)-y2)
 return B(LO.multiply(D(2),s.l),HI.multiply(D(2),HI.add(s.u,tail.u)))
A=2*log(B(2));K=B('.5');LN25=log(B('2.5'))
def h(x):
 assert 0<=x.l<=x.u<=1
 return A/(A-K)*(exp(-K*x)-exp(-A*x))

def main():
 if not __debug__:raise RuntimeError('Run without -O')
 src,cf,out=map(Path,sys.argv[1:4]);E=D(sys.argv[4]) if len(sys.argv)>4 else D('1e-4');LOW=str(1-E);UP=str(1+E);data=json.loads(src.read_text());c=json.loads(cf.read_text())
 assert hashlib.sha256(src.read_bytes()).hexdigest()==c['terminal_input_sha256'] and c['campaign']==data['campaign']
 deriv=A*exp(-A)-K*exp(-K);assert deriv.l>0
 M=B('.975')/h(B('.02'))*B(LOW,UP)
 D0=B(*c['constants']['D0']);DM=B('.02')/B(LOW,UP);DS=B('1.06')/B(LOW,UP);DE=B('.15')/B(LOW,UP)
 assert (B('.025')+B(M.u)*h(B(D0.l))).u<1
 assert (B('.025')+B(M.l)*h(B(D0.u))).l>1
 err=D0+DM+DS;end=err+DE;assert err.l>1 and end.u<D('1.3')
 LM=log(B('1.25'))/B('.02')*B(UP);LS=3*log(B(2))/B('1.06')*B(UP);LE=A/B('.15')*B(UP)
 assert max(LS.u,LE.u)<LM.l
 W=(3*B(str(4*(1+E)))+3*B(M.u)+1)*A+B('1.1')+B('4.5')*LM+B('2.4')*LE;assert W.u<500
 assert len(data['cells'])==216 and len({(x['layer'],x['lane']) for x in data['cells']})==216
 pmin=1+LN25/B('1.1');cells={(x['layer'],x['lane']):x for x in data['cells']};rows={(r['layer'],r['lane']):r for r in c['cells']}
 prev=[B(0)]+[None]*11;quiet=D(0);minima={};active=masked_n=influential_n=0
 for n in range(1,19):
  cur=[]
  for lane in range(12):
   s=cells[n,lane];ins={p:prev[(lane+p-1)%12] for p in range(3) if prev[(lane+p-1)%12] is not None}
   # Every cell, silent or active, must satisfy the structural premises of the terminal domain
   # (the same ones the first checker asserts); silent cells are not skipped unchecked.
   assert s['main_phase']==0 and s['aux_phases']==[0,0,0] and s['pending']==[] and s['raw_inputs']==[None]*3
   assert s['E']==[50,100] and all(D(g[0])>0 for g in s['g'])
   assert all(D(m[0])<=D('.025')<=D(m[1])<1 for m in s['m'])
   if not ins:
    assert s['pulses']==0 and D(s['q'][0])<=D('.1')<=D(s['q'][1])<1
    assert (n,lane) not in rows;cur.append(None);continue
   assert s['pulses']>0
   r=rows[n,lane];f=B(*r['fire']);active+=1
   assert {a['port']:B(*a['arrival']).pair() for a in r['inputs']}=={p:v.pair() for p,v in ins.items()}
   assert all(D(x)==D('.1') for x in s['q']) and all(all(D(x)==D('.025') for x in s['m'][p]) for p in ins)
   masked=[p for p,v in ins.items() if v.l>f.u];influential=[p for p in ins if p not in masked]
   assert r['masked_ports']==masked and r['influential_ports']==influential
   masked_n+=len(masked);influential_n+=len(influential)
   first=min(v.l for v in ins.values())
   def guard(t,upper):
    q=B('.1')
    for p in influential:
     arrival=ins[p].l if upper else ins[p].u
     age=B(t)-B(arrival)
     if age.u<=0:continue
     assert age.l>=0
     q=q+B(s['g'][p][1 if upper else 0])*h(age)
    return q
   assert guard(f.l,True).u<1 and guard(f.u,False).l>1
   pmax=1+LN25/B(s['b'][0]);assert D(s['b'][0])>0
   margins={
    'before_first_raw_end':B(first)+1-B(f.u),
    'before_first_error':B(first)+B(err.l)-B(f.u),
    'influential_errors_end_before_reopening':min((B(f.l)+B(pmin.l)-B(ins[p].u)-B(end.u) for p in influential),key=lambda v:v.l),
    'all_raw_inputs_end_before_reopening':min((B(f.l)+B(pmin.l)-B(v.u)-1 for v in ins.values()),key=lambda v:v.l),
    'ready_before_next_input':B(first)+20-B(f.u)-B(pmax.u),
    'auxiliary_ready_before_next_same_port_input':B(20)-B(end.u)
   }
   if masked:margins['masked_arrival_after_firing']=min((B(ins[p].l)-B(f.u) for p in masked),key=lambda v:v.l)
   for k,v in margins.items():assert v.l>0,(n,lane,k,v.pair());minima[k]=min(minima.get(k,v.l),v.l)
   quiet=max(quiet,(B(f.u)+B(pmax.u)).u,max((B(v.u)+B(end.u)).u for v in ins.values()),(B(f.u)+1).u)
   cur.append(f)
  prev=cur
 assert (active,masked_n,influential_n)==(191,15,525)
 assert quiet<D('12.791') and (B(20)-B(quiet)).l>D('7.209')
 result=dict(status='PASS',scope='Independent verification of fixed future-wave brackets and strict guard inequalities; no training-entry qualification',arithmetic='Decimal-directed 70-digit operations; degree-90 unscaled exponential series; 250-term atanh logarithms; explicit tails; no exp/ln library calls',certificate_sha256=hashlib.sha256(cf.read_bytes()).hexdigest(),terminal_input_sha256=c['terminal_input_sha256'],active_cells=active,masked_ports=masked_n,influential_ports=influential_n,global_quiescent_upper=str(quiet),global_quiescent_coarse_strict_bound='12.791',idle_margin_coarse_strict_lower='7.209',minimum_margins={k:str(v) for k,v in minima.items()},work_upper=str(W.u))
 out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
