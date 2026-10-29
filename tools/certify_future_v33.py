"""Finite inequality certificate for future waves, independent of the A22 engine.
No training simulation or replay. Integer directed intervals; scale 10**90.
Input: authenticated stored terminal endpoints. Entry soundness is a premise.
"""
import json,sys,hashlib
from pathlib import Path
from fractions import Fraction as F
S=10**90

def ceildiv(a,b):return -((-a)//b)
class I:
 def __init__(self,x=0,hi=None,raw=False):
  if raw:self.lo,self.hi=x,hi;return
  if isinstance(x,I):self.lo,self.hi=x.lo,x.hi;return
  f=F(x);g=F(x if hi is None else hi);self.lo=(f.numerator*S)//f.denominator;self.hi=ceildiv(g.numerator*S,g.denominator)
  assert self.lo<=self.hi
 def __add__(a,b):
  b=I(b);return I(a.lo+b.lo,a.hi+b.hi,raw=True)
 __radd__=__add__
 def __neg__(a):return I(-a.hi,-a.lo,raw=True)
 def __sub__(a,b):return a+-I(b)
 def __rsub__(a,b):return I(b)+-a
 def __mul__(a,b):
  b=I(b);xs=[a.lo*b.lo,a.lo*b.hi,a.hi*b.lo,a.hi*b.hi];return I(min(xs)//S,ceildiv(max(xs),S),raw=True)
 __rmul__=__mul__
 def __truediv__(a,b):
  b=I(b);assert not b.lo<=0<=b.hi
  xs=[F(x*S,y) for x in (a.lo,a.hi) for y in (b.lo,b.hi)];l,h=min(xs),max(xs)
  return I(l.numerator//l.denominator,ceildiv(h.numerator,h.denominator),raw=True)
 def pair(a):return [decimal(a.lo),decimal(a.hi)]
 def low(a):return I(a.lo,a.lo,raw=True)
 def high(a):return I(a.hi,a.hi,raw=True)

def decimal(n):
 sign='-' if n<0 else '';q,r=divmod(abs(n),S)
 return sign+str(q)+('.'+str(r).zfill(90).rstrip('0') if r else '')

def exp_positive(x):
 assert x.lo>=0
 count=0
 while x.hi>S//8:x=x/2;count+=1
 term=I(1);total=I(1)
 for n in range(1,46):term=term*x/n;total=total+term
 nextterm=term*x/46
 tail=nextterm/(I(1)-x/47)
 total=I(total.lo,total.hi+tail.hi,raw=True)
 for _ in range(count):total=total*total
 return total

def exp_point(n):
 if n<0:return I(1)/exp_positive(I(-n,-n,raw=True))
 return exp_positive(I(n,n,raw=True))

def exp(x):
 x=I(x);return I(exp_point(x.lo).lo,exp_point(x.hi).hi,raw=True)

def log_rational(x):
 # x>=1; log x = 2 sum_{k>=0} y^(2k+1)/(2k+1).
 assert F(x)>=1
 y=I((F(x)-1)/(F(x)+1));ysq=y*y;power=y;total=I(0)
 for k in range(220):total=total+power/(2*k+1);power=power*ysq
 tail=power/441/(I(1)-ysq)
 return I(2*total.lo,2*(total.hi+tail.hi),raw=True)

A=2*log_rational(2);K=I('.5');R=I('.1');RM=I('.025')
LN25=log_rational(F(5,2))
# h'(u)>0 throughout [0,1]: A exp(-A) > K exp(-K).
DERIVATIVE_BRACKET=A*exp(-A)-K*exp(-K)
assert DERIVATIVE_BRACKET.lo>0

def h(u):
 u=I(u)
 if u.hi<=0:return I(0)
 assert u.lo>=0 and u.hi<=S
 return A/(A-K)*(exp(-K*u)-exp(-A*u))

def bisect_threshold(fun,left,right,iterations=42):
 assert fun(left).hi<S and fun(right).lo>S
 lo,hi=left,right
 for _ in range(iterations):
  mid=(lo+hi)//2
  if mid==lo or mid==hi:break
  q=fun(mid)
  if q.hi<S:lo=mid
  elif q.lo>S:hi=mid
  else:break
 assert fun(lo).hi<S and fun(hi).lo>S
 return lo,hi

def main():
 if not __debug__:raise RuntimeError('Run without -O')
 src=Path(sys.argv[1]);target=Path(sys.argv[2]);data=json.loads(src.read_text());cells=data['cells'];assert len(cells)==216
 Mnom=I('.975')/h(I('.02'));M=Mnom*I('.9999','1.0001')
 def aq(t,upper):return RM+(M.high() if upper else M.low())*h(I(t,t,raw=True))
 dlo=bisect_threshold(lambda t:aq(t,True),0,S//10)[0]
 dhi=bisect_threshold(lambda t:aq(t,False),0,S//10)[1]
 DM=I('.02')/I('.9999','1.0001');DS=I('1.06')/I('.9999','1.0001');DE=I('.15')/I('.9999','1.0001')
 D0=I(dlo,dhi,raw=True);ERR=D0+DM+DS;END=ERR+DE
 assert ERR.lo>S and END.hi<I('1.3').lo
 LM=log_rational(F(5,4))/I('.02')*I('1.0001')
 LE=A/I('.15')*I('1.0001')
 LS=3*log_rational(2)/I('1.06')*I('1.0001')
 assert LE.hi<LM.lo and LS.hi<LM.lo
 W=(3*I('4.0004')+3*M.high()+1)*A+I('1.1')+I('4.5')*LM+I('2.4')*LE
 assert W.hi<I(500).lo
 pmin=I(1)+LN25/I('1.1')
 prev=[(0,0)]+[None]*11;rows=[];quiet_max=0;inactive=[];masked_all=[];margins_all=[]
 for n in range(1,19):
  cur=[]
  for j in range(12):
   c=cells[(n-1)*12+j];assert (c['layer'],c['lane'])==(n,j)
   assert c['main_phase']==0 and c['aux_phases']==[0,0,0] and c['pending']==[] and c['raw_inputs']==[None]*3
   assert c['E']==[50,100]
   ins=[(p,prev[(j+p-1)%12]) for p in range(3) if prev[(j+p-1)%12] is not None]
   gains=[I(*pair) for pair in c['g']]
   assert all(g.lo>0 for g in gains)
   assert all(F(m[0])<=F('.025')<=F(m[1])<1 for m in c['m'])
   if not ins:
    assert c['pulses']==0 and F(c['q'][0])<=F('.1')<=F(c['q'][1])<1
    inactive.append(dict(layer=n,lane=j));cur.append(None);continue
   assert c['pulses']>0 and list(map(F,c['q']))==[F('.1')]*2
   assert all(list(map(F,c['m'][p]))==[F('.025')]*2 for p,v in ins)
   first=min(v[0] for p,v in ins);right=first+S
   def q(t,upper,allowed=None):
    val=R
    for p,v in ins:
     if allowed is not None and p not in allowed:continue
     age=t-v[0 if upper else 1]
     if age<=0:continue
     assert age<=S
     val=val+(gains[p].high() if upper else gains[p].low())*h(I(age,age,raw=True))
    return val
   fl=bisect_threshold(lambda t:q(t,True),first,right)[0]
   fh=bisect_threshold(lambda t:q(t,False),first,right)[1]
   masked=[p for p,v in ins if v[0]>fh];influential=[p for p,v in ins if p not in masked]
   # Recheck threshold bounds after removing masked inputs entirely. Thus the
   # brackets hold for arbitrary future masked gains up to their physical caps.
   qlo=q(fl,True,influential);qhi=q(fh,False,influential)
   assert qlo.hi<S and qhi.lo>S
   bfloor=I(c['b'][0]).low();assert bfloor.lo>0
   pmax=I(1)+LN25/bfloor
   ms={
    'before_first_raw_end':I(first+S-fh,first+S-fh,raw=True),
    'before_first_error':I(first,first,raw=True)+ERR.low()-I(fh,fh,raw=True),
    'influential_errors_end_before_reopening':min((I(fl,fl,raw=True)+pmin.low()-I(v[1],v[1],raw=True)-END.high() for p,v in ins if p in influential),key=lambda x:x.lo),
    'all_raw_inputs_end_before_reopening':min((I(fl,fl,raw=True)+pmin.low()-I(v[1]+S,v[1]+S,raw=True) for p,v in ins),key=lambda x:x.lo),
    'ready_before_next_input':I(first+20*S-fh,first+20*S-fh,raw=True)-pmax.high(),
    'auxiliary_ready_before_next_same_port_input':I(20)-END.high()
   }
   if masked:ms['masked_arrival_after_firing']=min((I(v[0]-fh,v[0]-fh,raw=True) for p,v in ins if p in masked),key=lambda x:x.lo)
   assert all(v.lo>0 for v in ms.values()),(n,j,{k:v.pair() for k,v in ms.items()})
   quiet=max(fh+pmax.hi,max(v[1]+END.hi for p,v in ins),fh+S)
   quiet_max=max(quiet_max,quiet);assert quiet<20*S
   row=dict(layer=n,lane=j,inputs=[dict(port=p,arrival=[decimal(v[0]),decimal(v[1])]) for p,v in ins],fire=[decimal(fl),decimal(fh)],influential_ports=influential,masked_ports=masked,protection_duration=[decimal(pmin.lo),decimal(pmax.hi)],quiescent_by=decimal(quiet),lower_guard_at_left=qlo.pair(),upper_guard_at_right=qhi.pair(),positive_margins={k:v.pair() for k,v in ms.items()})
   rows.append(row);margins_all.append(ms);masked_all.extend(dict(layer=n,lane=j,port=p) for p in masked);cur.append((fl,fh))
  prev=cur;print('Inequalities certified through layer',n,flush=True)
 assert len(rows)==191 and len(inactive)==25 and len(masked_all)==15
 minima={k:decimal(min(ms[k].lo for ms in margins_all if k in ms)) for k in {k for ms in margins_all for k in ms}}
 result=dict(status='PASS: future closure conditional on physical entry into the specified terminal domain',scope='Finite directed-integer inequality certificate, not a campaign replay and not an entry-soundness certificate',terminal_input_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),campaign=data['campaign'],arithmetic=dict(scale=str(S),exp_Taylor_degree=45,log_terms=220,root_bisection_iterations=42),constants=dict(ln4=A.pair(),ln2_5=LN25.pair(),h_derivative_sign_at_one=DERIVATIVE_BRACKET.pair(),D0=D0.pair(),DM=DM.pair(),DS=DS.pair(),DE=DE.pair(),aux_error_start=ERR.pair(),aux_cycle_end=END.pair(),work_upper_bound=W.pair()),active_cells=len(rows),inactive_cells=inactive,masked_ports=masked_all,influential_active_ports=sum(len(r['influential_ports']) for r in rows),all_active_ports=sum(len(r['inputs']) for r in rows),global_quiescent_by=decimal(quiet_max),global_idle_margin_before_20=decimal(20*S-quiet_max),minimum_margins=minima,cells=rows)
 target.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ['status','global_quiescent_by','global_idle_margin_before_20','minimum_margins','influential_active_ports']}))

if __name__=='__main__':main()
