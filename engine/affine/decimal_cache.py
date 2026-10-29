"""Bounded memoization of Decimal scalar functions, preserving precision.
This module does not qualify the surrounding experimental affine engine.
"""
from decimal import Context
from functools import lru_cache
import intervalles_decimaux as iv

def signature():
    c=iv.NEAR
    return (c.prec,c.rounding,c.Emin,c.Emax,c.capitals,c.clamp)

@lru_cache(maxsize=8)
def context(sig):
    prec,rounding,Emin,Emax,capitals,clamp=sig
    return Context(prec=prec,rounding=rounding,Emin=Emin,Emax=Emax,capitals=capitals,clamp=clamp)

@lru_cache(maxsize=32768)
def scalar_exp(sig,x):
    return context(sig).exp(x)

@lru_cache(maxsize=4096)
def scalar_ln(sig,x):
    return context(sig).ln(x)

def exp(x):return scalar_exp(signature(),x)
def ln(x):return scalar_ln(signature(),x)
def stats():
    return {'exp':scalar_exp.cache_info()._asdict(),'ln':scalar_ln.cache_info()._asdict()}
