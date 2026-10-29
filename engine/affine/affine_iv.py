"""Experimental corrected affine arithmetic; NOT a qualified verifier.

A value denotes, for every admissible parameter vector eps in [-1,1]^N,
    x(eps) in c + sum_k d[k]*eps_k + [-e, e],
with c=[clo,chi] an outward Decimal interval (kernel precision), d float
coefficients and e a float bound that absorbs every float rounding error
and every neglected nonlinear term.  All operations are valid pointwise in
eps, so correlations between quantities sharing symbols are retained.
Without symbols every operation reproduces the original interval result.
"""
import math
from types import MappingProxyType
from decimal import Decimal as D
import intervalles_decimaux as iv
import decimal_cache
from rounding import add_up, mul_up, sum_abs, add_coeff, multiply_coeff, scale_coeff, finite, truncate_coeff

# Allocation only: both paths use the same arithmetic and validation.
import rounding
if rounding.BACKEND == 'native':
    from _rounding_native import new_form as _new_form
else:
    def _new_form(cls, lo, hi, d, e):
        o = object.__new__(cls)
        o.clo=lo; o.chi=hi; o._d=dict(d); o.e=e
        o._r=None; o._lo=None; o._hi=None; o._dr=None; o._mc=None; o._key=None
        return o

TINY=math.nextafter(0.0,math.inf)
KMAX=256   # v3: 96 -> 256 (same measured time; fewer correlation-destroying truncations)
FRESH=None
ETHRESH=1e-9
_COUNTER=[0]


def fup(dec):        # float >= |Decimal|
    f = abs(float(dec))
    return math.nextafter(f, math.inf) if f else (TINY if dec else 0.0)


def _rad(d):
    return sum_abs(d)


def _same(x, y):
    return x is y or (x.clo == y.clo and x.chi == y.chi and x.e == y.e and x.d == y.d)


class I:
    __slots__ = ('clo', 'chi', '_d', 'e', '_r', '_lo', '_hi', '_dr', '_mc', '_key')

    @property
    def d(self):return MappingProxyType(self._d)

    def __setattr__(self,name,value):
        if name not in ('_r','_lo','_hi','_dr','_mc','_key') and hasattr(self,name):
            raise AttributeError('affine forms are immutable')
        object.__setattr__(self,name,value)

    def __new__(cls, a=0, b=None):
        if b is None and isinstance(a, I):
            return a
        if isinstance(a, float) or isinstance(b, float):
            raise TypeError('float endpoint forbidden')
        lo = D(a); hi = D(a if b is None else b)
        assert lo <= hi and lo.is_finite() and hi.is_finite()
        return _new_form(cls, lo, hi, {}, 0.0)

    def __init__(self, a=0, b=None):
        pass

    def __getstate__(self):
        return (self.clo, self.chi, self._d, self.e)

    def __setstate__(self, st):
        clo,chi,d,e=st
        if not isinstance(clo,D) or not isinstance(chi,D) or clo>chi or not clo.is_finite() or not chi.is_finite():
            raise ValueError('invalid serialized affine center')
        if type(e) is not float or e<0:raise ValueError('invalid remainder')
        finite(e)
        for k,v in d.items():
            if not isinstance(k,str) or type(v) is not float:raise ValueError('invalid affine coefficient')
            finite(v)
        self.clo=clo;self.chi=chi;self._d=dict(d);self.e=e
        self._r=None;self._lo=None;self._hi=None;self._dr=None;self._mc=None;self._key=None

    @staticmethod
    def make(clo, chi, d, e):
        if clo > chi or not clo.is_finite() or not chi.is_finite() or e < 0:
            raise ArithmeticError('invalid affine form')
        finite(e)
        if len(d) > KMAX:
            # Same kept set as a stable sort by -|c| (largest first, ties in
            # dict order); dropped mass summed with upward rounding.  Native.
            d, extra = truncate_coeff(d, KMAX); e = add_up(e, extra)
        if FRESH is not None and e > ETHRESH and d:
            # Standard affine arithmetic: an error term becomes a new noise
            # symbol, so later reuse of this value cancels it exactly.
            _COUNTER[0] += 1
            d = dict(d); d[f'{FRESH}#{_COUNTER[0]}'] = e; e = 0.0
        return _new_form(I, clo, chi, d, e)

    @staticmethod
    def symbol(name, radius):
        """Fresh independent parameter eps_name in [-1,1], scaled by radius."""
        if D(radius)<0:raise ValueError('negative symbol radius')
        r = math.nextafter(float(D(radius)), math.inf) if D(radius) else 0.0
        finite(r)
        assert D(r) >= D(radius)
        return I.make(D(0), D(0), {name: r}, 0.0)

    # ---- range -------------------------------------------------------
    def drad(self):
        if self._dr is None:self._dr=_rad(self._d)
        return self._dr

    def rad(self):
        if self._r is None:
            self._r = add_up(self.drad(), self.e) if (self._d or self.e) else 0.0
        return self._r

    @property
    def lo(self):
        if self._lo is None:
            r = self.rad()
            self._lo = iv.DOWN.subtract(self.clo, D(r)) if r else self.clo
        return self._lo

    @property
    def hi(self):
        if self._hi is None:
            r = self.rad()
            self._hi = iv.UP.add(self.chi, D(r)) if r else self.chi
        return self._hi

    def plain(self):
        return I(D(self.lo), D(self.hi))

    def symbolic(self):
        return bool(self._d) or self.e > 0

    # ---- arithmetic --------------------------------------------------
    def __add__(self, o):
        o = I(o)
        if not o.symbolic() and o.clo==o.chi==0:return self
        if not self.symbolic() and self.clo==self.chi==0:return o
        clo = iv.DOWN.add(self.clo, o.clo); chi = iv.UP.add(self.chi, o.chi)
        d, rounding_error = add_coeff(self._d, o._d)
        return I.make(clo, chi, d, add_up(add_up(self.e, o.e), rounding_error))
    __radd__ = __add__

    def __neg__(self):
        d, _ = scale_coeff(self._d, -1.0)      # exact: |s| == 1 adds no error
        return I.make(self.chi.copy_negate(), self.clo.copy_negate(), d, self.e)

    def __sub__(self, o):
        return self + -I(o)

    def __rsub__(self, o):
        return I(o) + -self

    @staticmethod
    def _cmul(alo, ahi, blo, bhi):
        down=iv.DOWN.multiply;up=iv.UP.multiply
        if alo>=0 and blo>=0:return down(alo,blo),up(ahi,bhi)
        if ahi<=0 and bhi<=0:return down(ahi,bhi),up(alo,blo)
        if alo>=0 and bhi<=0:return down(ahi,blo),up(alo,bhi)
        if ahi<=0 and blo>=0:return down(alo,bhi),up(ahi,blo)
        l = [down(a, b) for a in (alo, ahi) for b in (blo, bhi)]
        h = [iv.UP.multiply(a, b) for a in (alo, ahi) for b in (blo, bhi)]
        return min(l), max(h)

    def _center(self):
        """float m and float bound of |c - m| over the whole center interval."""
        if self._mc is not None:return self._mc
        mid = iv.NEAR.divide(iv.NEAR.add(self.clo, self.chi), D(2))
        m = float(mid)
        dev = max(iv.UP.subtract(D(m), self.clo), iv.UP.subtract(self.chi, D(m)))
        self._mc=(m,fup(dev))
        return self._mc

    def __mul__(self, o):
        o = I(o)
        if not o.symbolic() and o.clo==o.chi==1:return self
        if not self.symbolic() and self.clo==self.chi==1:return o
        clo, chi = I._cmul(self.clo, self.chi, o.clo, o.chi)
        if not self.symbolic() and not o.symbolic():
            return I.make(clo, chi, {}, 0.0)
        mx, dx = self._center(); my, dy = o._center()
        Rx = self.drad(); Ry = o.drad()
        d, err = multiply_coeff(self._d, o._d, mx, my)
        ax = fup(max(self.clo.copy_abs(), self.chi.copy_abs()))
        ay = fup(max(o.clo.copy_abs(), o.chi.copy_abs()))
        terms = (mul_up(dx, Ry), mul_up(dy, Rx), mul_up(ax, o.e), mul_up(ay, self.e),
                 mul_up(add_up(Rx, self.e), add_up(Ry, o.e)), err)
        e = 0.0
        for term in terms: e = add_up(e, term)
        return I.make(clo, chi, d, e)
    __rmul__ = __mul__

    def _unary(self, fpoint, fslope):
        """Mean-value form around the center point x0 = mid(c)."""
        x0 = iv.NEAR.divide(iv.NEAR.add(self.clo, self.chi), D(2))
        flo, fhi = fpoint(x0)
        slo, shi = fslope(min(self.lo, x0), max(self.hi, x0))
        smid = iv.NEAR.divide(iv.NEAR.add(slo, shi), D(2))
        sm = float(smid)
        sr = fup(max(iv.UP.subtract(D(sm), slo), iv.UP.subtract(shi, D(sm))))
        rc = fup(max(iv.UP.subtract(x0, self.clo), iv.UP.subtract(self.chi, x0)))
        Rx = self.drad()
        d, err = scale_coeff(self._d, sm)
        e = add_up(add_up(mul_up(abs(sm), add_up(rc, self.e)),
                         mul_up(sr, add_up(add_up(Rx, rc), self.e))), err)
        return I.make(flo, fhi, d, e)

    def exp(self):
        if not self.symbolic():
            if self.clo == self.chi == 0:
                return I(1)
            return I(iv.NEAR.next_minus(decimal_cache.exp(self.clo)), iv.NEAR.next_plus(decimal_cache.exp(self.chi)))
        return self._unary(
            lambda x: (iv.NEAR.next_minus(decimal_cache.exp(x)), iv.NEAR.next_plus(decimal_cache.exp(x))),
            lambda lo, hi: (iv.NEAR.next_minus(decimal_cache.exp(lo)), iv.NEAR.next_plus(decimal_cache.exp(hi))))

    def ln(self):
        assert self.lo > 0
        if not self.symbolic():
            if self.clo == self.chi == 1:
                return I(0)
            return I(iv.NEAR.next_minus(decimal_cache.ln(self.clo)), iv.NEAR.next_plus(decimal_cache.ln(self.chi)))
        return self._unary(
            lambda x: (iv.NEAR.next_minus(decimal_cache.ln(x)), iv.NEAR.next_plus(decimal_cache.ln(x))),
            lambda lo, hi: (iv.DOWN.divide(D(1), hi), iv.UP.divide(D(1), lo)))

    def reciprocal(self):
        lo, hi = self.lo, self.hi
        assert not lo <= 0 <= hi
        if not self.symbolic():
            return I(iv.DOWN.divide(D(1), self.chi), iv.UP.divide(D(1), self.clo))
        def slope(l, h):
            small, big = sorted((l.copy_abs(), h.copy_abs()))   # x*x ranges over [small^2, big^2]
            return (iv.DOWN.divide(D(-1), iv.DOWN.multiply(small, small)),
                    iv.UP.divide(D(-1), iv.UP.multiply(big, big)))
        return self._unary(lambda x: (iv.DOWN.divide(D(1), x), iv.UP.divide(D(1), x)), slope)

    def __truediv__(self, o):
        o = I(o); assert not o.lo <= 0 <= o.hi
        return self * o.reciprocal()

    def __rtruediv__(self, o):
        return I(o) / self

    # ---- set operations ----------------------------------------------
    def intersect(self, o):
        o = I(o)
        if o.lo >= self.lo and o.hi <= self.hi:
            return o
        if self.lo >= o.lo and self.hi <= o.hi:
            return self
        return I(max(self.lo, o.lo), min(self.hi, o.hi))

    def nonnegative(self):
        assert self.hi >= 0
        if self.lo >= 0:
            return self
        return I(D(0), self.hi)

    def mid(self):
        return iv.NEAR.divide(iv.NEAR.add(self.lo, self.hi), D(2))

    def width(self):
        return iv.UP.subtract(self.hi, self.lo)

    def pair(self):
        return [str(self.lo), str(self.hi)]

    def fingerprint(self):
        if self._key is None:self._key=(self.clo,self.chi,tuple(sorted(self._d.items())),self.e)
        return self._key

    def __repr__(self):
        return 'Affine'+repr(self.fingerprint())


def _dev_up(a, m):
    """Float >= |a-m| exactly (a, m binary64).  a-m is rounded to nearest,
    so |exact| <= |fl(a-m)| + ulp/2 <= nextafter(|fl(a-m)|, +inf); and
    fl(a-m) == 0 iff a == m (gradual underflow)."""
    if a == m: return 0.0
    return finite(math.nextafter(abs(finite(a - m)), math.inf))


def hull_identical(values):
    """v2 union, kept for comparison/tests: only identical coefficients survive."""
    values = list(values)
    if not values: raise ValueError('empty affine hull')
    if all(_same(values[0], x) for x in values[1:]):return values[0]
    shared={k:v for k,v in values[0].d.items()
            if all(x.d.get(k, 0.0)==v for x in values[1:])}
    los=[];his=[]
    for x in values:
        r=add_up(x.e, _rad({k:v for k,v in x.d.items() if k not in shared}))
        los.append(iv.DOWN.subtract(x.clo,D(r)))
        his.append(iv.UP.add(x.chi,D(r)))
    return I.make(min(los),max(his),shared,0.0)


def hull(values):
    """Pointwise union with a common generator (v3, fix C).

    Branch i is x_i(eps) in [clo_i,chi_i] + sum_k a_ik eps_k + [-e_i,e_i].
    For every symbol k choose ONE float a*_k (the midpoint of the branch
    coefficients, 0 where a branch lacks k).  Then, for every eps,
        x_i(eps) - sum_k a*_k eps_k  in  [clo_i - r_i, chi_i + r_i],
        r_i >= e_i + sum_k |a_ik - a*_k|        (each term rounded up),
    so the union is enclosed by sum_k a*_k eps_k + [min(clo_i-r_i), max(chi_i+r_i)].
    This is valid pointwise whatever a* is; a* only decides tightness.
    v2 kept a*_k only when all a_ik were bit-identical and otherwise
    absorbed |a_ik| entirely: two branches differing in the last bit of a
    coefficient lost the whole correlation (re-independentised the radius).
    Here only the genuine branch spread |a_ik - a*_k| is absorbed.
    Audit witness x=eps, y=-eps: a*=0, r=1, result [-1,1] with no
    eps term, so no dependence is manufactured.
    """
    values = list(values)
    if not values: raise ValueError('empty affine hull')
    if all(_same(values[0], x) for x in values[1:]):return values[0]
    ds=[x._d for x in values]
    keys={}
    for d in ds:
        for k in d:keys[k]=None
    common={}
    for k in keys:
        lo=hi=None
        for d in ds:
            c=d.get(k,0.0)
            if lo is None or c<lo:lo=c
            if hi is None or c>hi:hi=c
        m=lo if lo==hi else finite(0.5*lo+0.5*hi)
        if m:common[k]=m
    los=[];his=[]
    for x,d in zip(values,ds):
        r=x.e
        for k,c in d.items():
            r=add_up(r,_dev_up(c,common.get(k,0.0)))
        for k,m in common.items():
            if k not in d:r=add_up(r,abs(m))
        los.append(iv.DOWN.subtract(x.clo,D(r)) if r else x.clo)
        his.append(iv.UP.add(x.chi,D(r)) if r else x.chi)
    return I.make(min(los),max(his),common,0.0)


def install():
    """Must run before any other kernel module imports intervalles_decimaux.I."""
    iv.I = I
    iv.hull = hull
