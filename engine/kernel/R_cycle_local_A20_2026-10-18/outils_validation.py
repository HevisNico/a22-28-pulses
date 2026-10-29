"""Validated replay of the unchanged A14 learning transient.

Numerical suggestions locate roots only. Every root, event order, absence
of crossing and terminal inclusion is checked by outward intervals.
Auxiliary R cycles and energy are enclosed by analytic lemmas, not removed
from the physical mechanism. Exact initial conditions only.
"""
from pathlib import Path
from dataclasses import dataclass
import argparse,json,math,hashlib,shutil,time,gzip
from fractions import Fraction
from scipy.optimize import brentq
import intervalles_decimaux as iv
from intervalles_decimaux import I,D

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'R_frontiere_physique_A14_2026-10-18'

@dataclass(frozen=True)
class T:
    key:str
    base:I
    offset:D=D(0)
    def box(self):return self.base+I(self.offset)
    def plus(self,u):return T(self.key,self.base,iv.NEAR.add(self.offset,D(u)))
    def minus(self,other):
        if self.key==other.key:return I(iv.DOWN.subtract(self.offset,other.offset),iv.UP.subtract(self.offset,other.offset))
        return self.box()-other.box()
    def token(self):return self.key,str(self.offset.normalize(context=iv.NEAR))

class Ambiguous(RuntimeError):pass

def constants():
    global A,K,R,RM,LM,LS,LE,ZMAX,EG,EB,BMAX,M,TAUMIN,TAUMAX
    A=I(4).ln();K=I('.5');R=I('.1');RM=I('.025')
    LM=I('1.25').ln()/I('.02');LS=I(8).ln()/I('1.06');LE=A/I('.15')
    ZMAX=A;EG=I(8);EB=I('.5');BMAX=I('1.1')
    h=A/(A-K)*((-K*I('.02')).exp()-(-A*I('.02')).exp())
    M=(1-RM)/h;TAUMIN=1+I('2.5').ln()/BMAX;TAUMAX=1+I('2.5').ln()/I('.08')
    work=133*A+I('1.1')+I('4.5')*LM+I('2.4')*LE
    assert work.hi<260 and TAUMIN.lo>D('1.25') and M.hi<40
    assert LM.lo>(I('.8')*LS).hi and LM.lo>(I('.1')*LE).hi
    return dict(work_upper=str(work.hi),resource_invariant=['50','100'],
        main_minimum_separation=TAUMIN.pair(),auxiliary_sections=['.02','.04','1.10','1.25'],
        auxiliary_lemma='Each input pulse sees exactly RM; threshold at +.02, charge sections +.04,+1.10,+1.25; cycle ends before next own input',
        power_lemma='At E=50 the pump is 500>work; at E=100 derivative is nonpositive; plastic power gates never close')

def ready(q,J,u):
    e=(-K*u).exp();return R+(q-R)*e+J*(e-(-A*u).exp())/(A-K)

def root(fun,deriv,lo,hi,guess):
    """Existence by endpoint signs; uniqueness by positive derivative.

    A numerical guess only proposes a narrow bracket. It never accepts a
    predicate. Interval Newton then retains every root of the bracket.
    """
    lo=D(lo);hi=D(hi);rad=D('1e-10');g=D(str(guess))
    assert hi>lo
    for _ in range(80):
        l=max(lo,iv.DOWN.subtract(g,rad));h=min(hi,iv.UP.add(g,rad))
        fl=fun(I(l));fh=fun(I(h));slope=deriv(I(l,h))
        if fl.hi<=0 and fh.lo>=0 and slope.lo>0:break
        rad=iv.UP.multiply(rad,D(4))
    else:raise Ambiguous(f'root bracket failed: {lo},{hi}; f={fl},{fh}; slope={slope}')
    x=I(l,h)
    for _ in range(18):
        m=x.mid();slope=deriv(x)
        assert slope.lo>0
        y=x.intersect(I(m)-fun(I(m))/slope)
        if y.width()>=iv.NEAR.divide(x.width(),D(2)):x=y;break
        x=y
    return x

def guessroot(fun,hi):
    """Float-only proposal. A failed proposal cannot certify an event."""
    def ff(x):return float(fun(I(str(x))).mid())
    return brentq(ff,0.,float(hi),xtol=5e-14)

