"""Outward expression enclosures for times and ready-phase pulse histories.

Atoms with a common identifier denote a common physical quantity; no
independence of the remaining atom intervals is asserted. Dropping their
other constraints overapproximates the reachable set.
"""
from dataclasses import dataclass
from decimal import localcontext
import intervalles_decimaux as iv
from intervalles_decimaux import I,D,hull

def configure(a,k,r):
    global A,K,R,H1
    A,K,R=a,k,r;H1=hp(I(1))
    assert dp(I(1)).lo>0
    assert (A*A*(-A).exp()-K*K*(-K).exp()).lo>0

@dataclass(frozen=True)
class Time:
    key:str
    base:I
    offset:D=D(0)
    terms:tuple|None=None
    def box(self):return self.base+I(self.offset)
    def expression(self):
        terms=self.terms if self.terms is not None else ((self.key,1,self.base),)
        if self.offset:
            terms=terms+((f'point:{self.offset}',1,I(self.offset)),)
        return terms
    def plus(self,u):
        u=D(u)
        with localcontext() as ctx:
            ctx.prec=max(self.offset.adjusted(),u.adjusted())-min(self.offset.as_tuple().exponent,u.as_tuple().exponent)+3
            value=self.offset+u
        return Time(self.key,self.base,value,self.terms)
    def minus(self,other):
        if self.key==other.key:
            return I(iv.DOWN.subtract(self.offset,other.offset),iv.UP.subtract(self.offset,other.offset))
        result={}
        for sign,ts in ((1,self.expression()),(-1,other.expression())):
            for key,n,value in ts:
                if key in result:
                    count,previous=result[key]
                    assert previous.pair()==value.pair(),('inconsistent common time atom',key)
                    result[key]=(count+sign*n,value)
                else:result[key]=(sign*n,value)
        return sum((n*v for n,v in result.values() if n),I(0))
    def token(self):
        with localcontext() as ctx:
            ctx.prec=len(self.offset.as_tuple().digits)+2
            return self.key,str(self.offset.normalize())

def shift(t,u,key):
    if u.lo==u.hi:return t.plus(u.lo)
    return Time(key,t.box()+u,D(0),t.expression()+((f'duration:{key}',1,u),))

def encode_time(t):
    return dict(key=t.key,base=t.base.pair(),offset=str(t.offset),
        terms=None if t.terms is None else [[k,n,x.pair()] for k,n,x in t.terms])
def decode_time(t):
    return Time(t['key'],I(*t['base']),D(t['offset']),
        None if t['terms'] is None else tuple((k,n,I(*x)) for k,n,x in t['terms']))

def hp(u):return A/(A-K)*((-K*u).exp()-(-A*u).exp())
def dp(u):return A/(A-K)*(A*(-A*u).exp()-K*(-K*u).exp())
def h(u):
    assert 0<=u.lo<=u.hi<=1
    return I(hp(I(u.lo)).lo,hp(I(u.hi)).hi)
def dh(u):
    assert 0<=u.lo<=u.hi<=1
    return I(dp(I(u.hi)).lo,dp(I(u.lo)).hi)

def pulse(age):
    age=age.nonnegative()
    if age.hi<=1:return h(age)
    if age.lo>=1:return H1*(-K*(age-1)).exp()
    left=h(I(age.lo));right=H1*(-K*(I(age.hi)-1)).exp()
    return I(min(left.lo,right.lo),H1.hi)
def dpulse(age):
    age=age.nonnegative()
    if age.hi<=1:return dh(age)
    if age.lo>=1:return -K*pulse(age)
    return hull([dh(I(age.lo,1)),-K*pulse(I(1,age.hi))])

def start(t,q,active):
    return dict(anchor=t,q=q,pulses={(j,o.token()):dict(origin=o,g=g,tail=True) for j,o,g in active})

def add(mem,j,origin,g):
    mem=mem.copy();mem['pulses']=mem['pulses'].copy();key=(j,origin.token())
    assert key not in mem['pulses']
    mem['pulses'][key]=dict(origin=origin,g=g,tail=False)
    return mem

def tail(term,anchor,t,derivative):
    origin=term['origin'];g=term['g']
    initial_age=anchor.minus(origin).intersect(I(0,1))
    duration=1-initial_age;elapsed=t.minus(anchor).nonnegative()
    admitted=I(min(elapsed.lo,duration.lo),min(elapsed.hi,duration.hi))
    after=I(max(D(0),(elapsed-duration).lo),max(D(0),(elapsed-duration).hi))
    response=g*(-A*initial_age).exp()*h(admitted)*(-K*after).exp()
    if not derivative:return response
    current=g*A*(-A*t.minus(origin).nonnegative()).exp()
    if elapsed.lo>=duration.hi:current=I(0)
    elif elapsed.hi>duration.lo:current=I(0,current.hi)
    return -K*response+current

def evaluate(mem,t,derivative=False):
    elapsed=t.minus(mem['anchor']).nonnegative()
    homogeneous=(mem['q']-R)*(-K*elapsed).exp()
    result=-K*homogeneous if derivative else R+homogeneous
    for term in mem['pulses'].values():
        if term['tail']:result=result+tail(term,mem['anchor'],t,derivative)
        else:
            age=t.minus(term['origin']).nonnegative()
            result=result+term['g']*(dpulse(age) if derivative else pulse(age))
    return result

def join(memories):
    if all(x is None for x in memories):return None
    if any(x is None for x in memories):return None
    first=memories[0]
    if not all(x['anchor'].token()==first['anchor'].token() and x['pulses'].keys()==first['pulses'].keys() for x in memories):return None
    result=first.copy();result['q']=hull([x['q'] for x in memories]);result['pulses']={}
    for key,term in first['pulses'].items():
        if not all(x['pulses'][key]['tail']==term['tail'] for x in memories):return None
        result['pulses'][key]=dict(term,g=hull([x['pulses'][key]['g'] for x in memories]))
    return result
