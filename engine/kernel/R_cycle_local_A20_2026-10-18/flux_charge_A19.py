"""Shared charge-transfer identity for gated exponential actuator currents."""
from intervalles_decimaux import I,D
def transfer(s,lam,high,low,scale):
    high=I(high);low=I(low);scale=I(scale);maximum=scale*(high-low)
    assert s.end is not None
    if s.full_start and s.full_end:return maximum
    if s.full_end:
        start=(high*(-lam*s.start.minus(s.origin).nonnegative()).exp()).intersect(I(low.lo,high.hi))
        return (scale*(start-low)).intersect(I(0,maximum.hi))
    if s.full_start:
        age=s.end.minus(s.origin).nonnegative()
        return (scale*high*(1-(-lam*age).exp())).intersect(I(0,maximum.hi))
    start=(high*(-lam*s.start.minus(s.origin).nonnegative()).exp()).intersect(I(low.lo,high.hi))
    elapsed=s.end.minus(s.start).nonnegative()
    return (scale*start*(1-(-lam*elapsed).exp())).intersect(I(0,maximum.hi))
