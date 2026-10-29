"""Conservative binary64 bounds. Reference implementation, no fast-math.
Each primitive rounds upward separately; no fixed global inflation factor.
Non-finite intermediates fail closed.
"""
import math
TINY=math.ulp(0.0)
def finite(x):
    if not math.isfinite(x):raise ArithmeticError('non-finite affine coefficient or radius')
    return x

def add_up(a,b):
    if a<0 or b<0:raise ArithmeticError('negative error bound')
    s=finite(a+b)
    return finite(math.nextafter(s,math.inf)) if a and b else s

def mul_up(a,b):
    if a<0 or b<0:raise ArithmeticError('negative error bound')
    p=finite(a*b)
    return finite(math.nextafter(p,math.inf)) if a and b else p

def error(value):
    finite(value)
    return finite(max(abs(math.nextafter(value,math.inf)-value),abs(value-math.nextafter(value,-math.inf))))

def sum_abs(d):
    s=0.0
    for v in d.values():s=add_up(s,abs(finite(v)))
    return s

def add_coeff(a,b):
    d=dict(a);e=0.0
    for k,v in b.items():
        if k in d:
            old=d[k];s=finite(old+v);d[k]=s
            if old and v and old!=-v:e=add_up(e,error(s))
        else:d[k]=v
    return d,e

def scale_coeff(a,s):
    d={};e=0.0
    for k,v in a.items():
        p=finite(s*v);d[k]=p
        if s and v and abs(s)!=1:e=add_up(e,error(p))
    return d,e

def multiply_coeff(a,b,mx,my):
    ad,ae=scale_coeff(a,my);bd,be=scale_coeff(b,mx)
    d,ce=add_coeff(ad,bd)
    return d,add_up(add_up(ae,be),ce)

def truncate_coeff(d,kmax):
    """Keep the kmax largest |coefficients| (ties: first in dict order).
    Returns (kept dict, upward-rounded sum of the dropped |coefficients|)."""
    if kmax<1:raise ValueError('kmax must be positive')
    if len(d)<=kmax:return dict(d),0.0
    mags=sorted((abs(finite(v)) for v in d.values()),reverse=True)
    thr=mags[kmax-1];above=0
    while above<len(mags) and mags[above]>thr:above+=1
    ties=kmax-above;keep={};extra=0.0
    for k,v in d.items():
        a=abs(v)
        if a>thr or (a==thr and ties>0):
            if a==thr:ties-=1
            keep[k]=v
        else:extra=add_up(extra,a)
    return keep,finite(extra)

# Override only with the separately tested equivalent native primitives.
import os
BACKEND='python'
if os.environ.get('A22_AFFINE_NATIVE','1')!='0':
    try:
        from _rounding_native import add_up,mul_up,sum_abs,add_coeff,scale_coeff,multiply_coeff
        BACKEND='native'
    except ImportError:
        pass
    if BACKEND=='native':
        try:from _rounding_native import truncate_coeff
        except ImportError:pass    # older binary: Python reference above
