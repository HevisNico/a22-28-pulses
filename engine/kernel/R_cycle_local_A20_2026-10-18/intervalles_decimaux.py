"""Outward decimal intervals. No float enters a certified endpoint.

Basic operations use ROUND_FLOOR/ROUND_CEILING. exp and ln are correctly
rounded HALF_EVEN by libmpdec; one adjacent representable value is added
on each side. See Python 3.12 decimal documentation, Decimal.exp/ln.
"""
from decimal import Decimal as D, Context, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_EVEN

def configure(precision=128):
    global DOWN,UP,NEAR,PREC
    PREC=precision
    DOWN=Context(prec=precision,rounding=ROUND_FLOOR,Emin=-999999,Emax=999999)
    UP=Context(prec=precision,rounding=ROUND_CEILING,Emin=-999999,Emax=999999)
    NEAR=Context(prec=precision,rounding=ROUND_HALF_EVEN,Emin=-999999,Emax=999999)

configure()

class I:
    __slots__=('lo','hi')
    def __init__(self,a=0,b=None):
        if isinstance(a,I):self.lo,self.hi=a.lo,a.hi;return
        if isinstance(a,float) or isinstance(b,float):raise TypeError('float endpoint forbidden')
        self.lo=D(a);self.hi=D(a if b is None else b)
        assert self.lo<=self.hi and self.lo.is_finite() and self.hi.is_finite()
    def __add__(self,o):
        o=I(o);return I(DOWN.add(self.lo,o.lo),UP.add(self.hi,o.hi))
    __radd__=__add__
    def __neg__(self):return I(self.hi.copy_negate(),self.lo.copy_negate())
    def __sub__(self,o):return self+-I(o)
    def __rsub__(self,o):return I(o)+-self
    def __mul__(self,o):
        o=I(o);l=[DOWN.multiply(a,b) for a in (self.lo,self.hi) for b in (o.lo,o.hi)]
        h=[UP.multiply(a,b) for a in (self.lo,self.hi) for b in (o.lo,o.hi)]
        return I(min(l),max(h))
    __rmul__=__mul__
    def __truediv__(self,o):
        o=I(o);assert not o.lo<=0<=o.hi
        return self*I(DOWN.divide(D(1),o.hi),UP.divide(D(1),o.lo))
    def __rtruediv__(self,o):return I(o)/self
    def exp(self):
        if self.lo==self.hi==0:return I(1)
        return I(NEAR.next_minus(NEAR.exp(self.lo)),NEAR.next_plus(NEAR.exp(self.hi)))
    def ln(self):
        assert self.lo>0
        if self.lo==self.hi==1:return I(0)
        return I(NEAR.next_minus(NEAR.ln(self.lo)),NEAR.next_plus(NEAR.ln(self.hi)))
    def intersect(self,o):
        o=I(o);return I(max(self.lo,o.lo),min(self.hi,o.hi))
    def nonnegative(self):
        assert self.hi>=0
        return I(max(D(0),self.lo),self.hi)
    def mid(self):return NEAR.divide(NEAR.add(self.lo,self.hi),D(2))
    def width(self):return UP.subtract(self.hi,self.lo)
    def pair(self):return [str(self.lo),str(self.hi)]
    def __repr__(self):return f'I({self.lo},{self.hi})'

def hull(values):return I(min(x.lo for x in values),max(x.hi for x in values))
