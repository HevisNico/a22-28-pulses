"""Persistent, disjunctive actuation histories for the unchanged recovery law.

Full marks are exact charge transfers. Partial marks retain gate endpoints.
The saturation is the exact projection of a monotone potential actuation;
only the small uncertain contact strip uses monotone interval quadrature.
No cell, event number, nominal order or target speed appears here.
"""
from dataclasses import dataclass,replace
import intervalles_decimaux as iv
from intervalles_decimaux import I,D,hull
import dependances_A17 as dep
from flux_charge_A19 import transfer as charge_transfer

BMAX=I('1.1');EB=I('.5');STEP=I('.1')
def configure(lam):
    global LAM,DM,MU
    LAM=lam;DM=I('1.25').ln()/LAM;MU=(1-4*I('1.25').ln())/LAM

@dataclass(frozen=True)
class Segment:
    port:int
    origin:dep.Time
    start:dep.Time
    full_start:bool
    end:dep.Time|None=None
    full_end:bool=False

@dataclass(frozen=True)
class History:
    initial:I
    full:int=0
    partial:tuple=()
    fire:dep.Time|None=None
    marks:tuple=()
    saturated:bool=False

def ordered(xs):return tuple(sorted(xs,key=lambda x:(x.port,repr(x.origin.token()),repr(x.start.token()))))
def gain(age):
    age=I(max(D(0),age.lo),max(D(0),age.hi))
    x=EB*(1-(-LAM*age).exp())
    return I(min(STEP.lo,max(D(0),x.lo)),min(STEP.hi,max(D(0),x.hi)))
def charge(s,t):return (-LAM*t.minus(s.origin).nonnegative()).exp().intersect(I('.8',1))

def transfer(s):
    return charge_transfer(s,LAM,1,'.8','.5')

def baseline(h):
    if h.saturated:return BMAX
    return h.initial+STEP*h.full+sum((transfer(s) for s in h.partial),I(0))

def primitive_point(x,lam):
    if x<=0:return I(0)
    x=I(x);lam=I(lam);threshold=I('1.25').ln()
    during=EB*(x-(1-(-lam*x).exp())/lam)
    complete=STEP*(x-(1-4*threshold)/lam)
    if (lam*x).hi<=threshold.lo:return during
    if (lam*x).lo>=threshold.hi:return complete
    return hull([during,complete])

def primitive(age,finished=False):
    if finished:return STEP*(age-MU)
    lo=primitive_point(max(D(0),age.lo),LAM.lo).lo
    hi=primitive_point(max(D(0),age.hi),LAM.hi).hi
    return I(max(D(0),lo),max(D(0),hi))

def final_potential(s):
    if s.full_start:return STEP
    return (EB*(charge(s,s.start)-I('.8'))).intersect(I(0,'.1'))

def increment(s,t,live=False):
    if live and s.full_end:return final_potential(s)
    if not s.full_start:
        # Every intercepted mark ends at most DM<1 after the firing.
        # Its value at an arbitrary earlier probe is evaluated naturally.
        if t.minus(s.start).hi<=0:return I(0)
        a=t.minus(s.origin)
        if a.lo>=DM.hi:return final_potential(s)
        elapsed=t.minus(s.start).nonnegative()
        x=EB*charge(s,s.start)*(1-(-LAM*elapsed).exp())
        cap=final_potential(s)
        return I(max(D(0),min(x.lo,cap.lo)),max(D(0),min(x.hi,cap.hi)))
    return gain(t.minus(s.origin))

def raw_rate(h,t,live=False):
    if h.saturated:return BMAX
    return baseline(h)+sum((increment(s,t,live) for s in h.marks),I(0))

def clip(x):return I(min(BMAX.lo,x.lo),min(BMAX.hi,x.hi))
def rate(h,t,live=False):return clip(raw_rate(h,t,live))

def raw_dose(h,t,live=False):
    assert h.fire is not None
    section=h.fire.plus(1);elapsed=t.minus(section).nonnegative()
    if elapsed.hi==0:return I(0)
    out=baseline(h)*elapsed
    for s in h.marks:
        if not s.full_start:
            # A mark already active at firing finishes during the fast phase.
            assert DM.hi<1
            contribution=final_potential(s)*elapsed
        else:
            initial_age=section.minus(s.origin)
            before_section=(s.end is not None and section.minus(s.end).lo>=0)
            if before_section or initial_age.lo>=DM.hi:
                contribution=STEP*elapsed
            else:
                contribution=primitive(t.minus(s.origin),live and s.full_end)-primitive(initial_age)
        out=out+contribution
    return out

def contact(h,anchor,hi,iterations=12):
    """Earliest possible / latest certain cap contact, relative to anchor.

    A missing certain upper contact is explicitly marked; no existence of
    a cap hit is assumed for every parameter in a mixed-contact branch.
    """
    hi=D(hi)
    f=lambda x:raw_rate(h,anchor.plus(x))
    if f(0).lo>=BMAX.hi:return D(0),D(0),True
    if f(hi).hi<BMAX.lo:return hi,hi,False
    a=D(0);z=hi
    for _ in range(iterations):
        m=I(a,z).mid()
        if f(m).hi<BMAX.lo:a=m
        else:z=m
    lower=a
    if f(hi).lo<BMAX.hi:return lower,hi,False
    a=D(0);z=hi
    for _ in range(iterations):
        m=I(a,z).mid()
        if f(m).lo>=BMAX.hi:z=m
        else:a=m
    return lower,z,True

def capped_dose(h,t,live=False):
    section=h.fire.plus(1);duration=t.minus(section).nonnegative()
    if h.saturated or raw_rate(h,section).lo>=BMAX.hi:return BMAX*duration
    uncapped=raw_dose(h,t,live)
    if raw_rate(h,t,live).hi<=BMAX.lo:return uncapped
    lower,upper,certain=contact(h,section,duration.hi)
    def at(x):
        if x<=lower:return raw_dose(h,section.plus(x))
        out=raw_dose(h,section.plus(lower))
        stop=min(x,upper)
        # Monotone lower/upper Riemann sums, all endpoints outward.
        points=[lower]
        for k in range(1,9):points.append((I(lower)+(I(stop)-I(lower))*I(k)/8).mid())
        points[-1]=stop
        for a,z in zip(points,points[1:]):
            left=rate(h,section.plus(a));right=rate(h,section.plus(z))
            out=out+I(left.lo,right.hi)*(I(z)-I(a))
        if x>upper:
            assert certain
            out=out+BMAX*(I(x)-I(upper))
        return out
    lo=at(duration.lo).lo;hi=at(duration.hi).hi
    # Intersection of independently valid dose enclosures.
    return I(lo,hi).intersect(I(0,(BMAX*duration).hi)).intersect(I(0,uncapped.hi))

def ell(h,t,live=False):return I('2.5').ln()-capped_dose(h,t,live)

def begin(h,fire,aux,origins):
    assert h.fire is None
    marks=[]
    if not h.saturated:
        for j in range(3):
            if aux[j]==1:marks.append(Segment(j,origins[j],fire,False))
    return replace(h,fire=fire,marks=ordered(marks))

def on(h,j,origin):
    if h.fire is None or h.saturated:return h
    assert all((s.port,s.origin.token())!=(j,origin.token()) for s in h.marks)
    return replace(h,marks=ordered(h.marks+(Segment(j,origin,origin,True),)))

def off(h,j,origin,t):
    if h.fire is None or h.saturated:return h
    found=False;marks=[]
    for s in h.marks:
        if (s.port,s.origin.token())==(j,origin.token()):
            assert s.end is None;found=True;s=replace(s,end=t,full_end=True)
        marks.append(s)
    assert found,'Untracked mark during protection'
    return replace(h,marks=ordered(marks))

def finish(h,t):
    assert h.fire is not None
    if rate(h,t,True).lo==BMAX.lo:
        return History(BMAX,saturated=True)
    full=h.full;partial=list(h.partial)
    for s in h.marks:
        if s.end is None:s=replace(s,end=t,full_end=False)
        if s.full_start and s.full_end:full+=1
        else:partial.append(s)
    return History(h.initial,full,tuple(partial))

def unique(histories,limit=128):
    # Exact structural deduplication only. Different counts or gate histories
    # are never replaced with an independent rate/dose box.
    seen={repr(h):h for h in histories}
    if len(seen)>limit:raise RuntimeError(f'actuation disjunction budget exceeded: {len(seen)}>{limit}')
    return tuple(seen.values())

def bounds(histories,t,quantity='rate',live=True):
    fun=ell if quantity=='ell' else rate
    return hull([fun(h,t,live) for h in histories])
