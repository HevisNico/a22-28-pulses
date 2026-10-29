"""The same actuation accounting for ready-gated logarithmic gains.

Each full auxiliary error section contributes 8*(.1-.025)=.6. Partial
sections retain their physical gate endpoints. Port-specific cap projection
is exact because each gain is nondecreasing and its own raw current is zero
through every useful error section (checked by the physical kernel).
"""
from dataclasses import dataclass,replace
from intervalles_decimaux import I,hull
from actuations_A19 import Segment
from flux_charge_A19 import transfer
def configure(lam,target):
    global LAM,TARGET
    LAM=lam;TARGET=target
@dataclass(frozen=True)
class History:
    initial:I
    full:int=0
    partial:tuple=()
    active:Segment|None=None
    clamped:bool=False
    conditions:tuple=()
def offered(h,t):
    if h.clamped:return TARGET
    value=h.initial+I('.6')*h.full+sum((transfer(s,LAM,'.1','.025',8) for s in h.partial),I(0))
    if h.active is not None:
        value=value+transfer(replace(h.active,end=t),LAM,'.1','.025',8)
    return value
def value(h,t):
    if h.clamped:return TARGET
    x=offered(h,t)
    return I(min(x.lo,TARGET.lo),min(x.hi,TARGET.hi))
def certain_cap(h,t):return h.clamped or offered(h,t).lo>=TARGET.hi
def bounds(histories,t):return hull([value(h,t) for h in histories])
def unique(histories,limit=128):
    seen={repr(h):h for h in histories}
    if len(seen)>limit:raise RuntimeError(f'deposit disjunction budget exceeded: {len(seen)}>{limit}')
    return tuple(seen.values())
def open_gate(h,j,origin,t,full_start):
    assert h.active is None
    if h.clamped:return h
    return replace(h,active=Segment(j,origin,t,full_start))
def close_gate(h,t,full_end):
    if h.active is None:return h
    if certain_cap(h,t):return History(TARGET,clamped=True)
    s=replace(h.active,end=t,full_end=full_end)
    if s.full_start and s.full_end:return replace(h,full=h.full+1,active=None)
    return replace(h,partial=h.partial+(s,),active=None)
def refresh(h,t):
    return History(TARGET,clamped=True) if certain_cap(h,t) else h
