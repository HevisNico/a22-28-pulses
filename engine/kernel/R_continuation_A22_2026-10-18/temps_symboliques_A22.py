"""Exact affine-expression normal forms; no rounded equality of boxes."""
from fractions import Fraction
from functools import lru_cache
from decimal import localcontext
from intervalles_decimaux import D
import sys

def _validate_if_installed(value):
 module=sys.modules.get('identite_temps_A22')
 if module is not None and getattr(module,'_INSTALLED',False) and isinstance(value,module.dep.Time):
  module.validate_time(value)

def _fraction_to_decimal_reference(value):
 """Construct a finite Decimal without any rounded arithmetic operation."""
 value=Fraction(value)
 numerator,denominator=value.numerator,value.denominator
 if numerator==0:return D(0)
 twos=fives=0
 while denominator%2==0:denominator//=2;twos+=1
 while denominator%5==0:denominator//=5;fives+=1
 if denominator!=1:raise ValueError('Rational has no finite decimal expansion')
 scale=max(twos,fives)
 coefficient=abs(numerator)*2**(scale-twos)*5**(scale-fives)
 # Decimal(tuple) is exact and independent of the ambient precision.
 digits=D(coefficient).as_tuple().digits
 result=D((int(numerator<0),digits,-scale))
 if Fraction(result)!=value:raise ArithmeticError('Exact decimal conversion failed')
 return result

@lru_cache(maxsize=8192)
def _fraction_text(value):
 return _fraction_to_decimal_reference(value)

def fraction_to_decimal_exact(value):
 # Decimal results are immutable; the reference is context-independent.
 return _fraction_text(value) if type(value) is str else _fraction_to_decimal_reference(value)

def _relative_reference(t,anchor):
 _validate_if_installed(t);_validate_if_installed(anchor)
 terms={};constant=Fraction(0)
 for sign,expr in [(1,t.expression()),(-1,anchor.expression())]:
  for key,n,value in expr:
   n*=sign
   if value.lo==value.hi:constant+=n*Fraction(value.lo)
   elif key in terms:
    old,bounds=terms[key]
    if bounds!=tuple(value.pair()):raise ValueError('Common time atom has inconsistent bounds: '+key)
    terms[key]=(old+n,bounds)
   else:terms[key]=(n,tuple(value.pair()))
 return (str(constant),tuple(sorted((key,n,bounds) for key,(n,bounds) in terms.items() if n)))

@lru_cache(maxsize=8192)
def _point_fraction(text):
 return Fraction(D(text))

@lru_cache(maxsize=8192)
def _normal_form(signature):
 # Keyed by ALL current terms and exact endpoint strings, never object id.
 # Keep zero coefficients here: conflicting definitions must still refuse.
 terms={};constant=Fraction(0)
 for key,n,lo,hi in signature:
  if D(lo)==D(hi):constant+=n*_point_fraction(lo)
  elif key in terms:
   old,bounds=terms[key]
   if bounds!=(lo,hi):raise ValueError('Common time atom has inconsistent bounds: '+key)
   terms[key]=(old+n,bounds)
  else:terms[key]=(n,(lo,hi))
 return constant,tuple((key,n,bounds) for key,(n,bounds) in terms.items())

_ENDPOINT_TEXT={}
def _endpoint_text(value):
 # A retained Decimal is immutable; its identity preserves trailing zeros.
 if type(value) is not D:return str(value)
 previous=_ENDPOINT_TEXT.get(id(value))
 if previous is not None and previous[0] is value:return previous[1]
 result=str(value)
 if len(_ENDPOINT_TEXT)>=32768:_ENDPOINT_TEXT.clear()
 _ENDPOINT_TEXT[id(value)]=(value,result)
 return result

def _current_form(time):
 # Always inspect current mutable endpoints. A cache hit is not validation.
 signature=tuple((key,n,_endpoint_text(value.lo),_endpoint_text(value.hi)) for key,n,value in time.expression())
 return _normal_form(signature)

def _validated_form(time):
 module=sys.modules.get('identite_temps_A22')
 if module is not None and module._INSTALLED and type(time) is module.dep.Time:
  if time.terms is None and time.base.lo!=time.base.hi:
   raise module.AtomIdentityRefusal('Legacy uncertain Time has no allocated identity')
  from canonical_bytes_A22 import _native
  signature=_native.validated_terms(time.expression(),module._RECORDS,module.I,D,
                                    module._parsed_bounds,module.AtomIdentityRefusal,_ENDPOINT_TEXT)
  if signature is not NotImplemented:return _normal_form(signature)
 _validate_if_installed(time)
 return _current_form(time)

def relative(t,anchor):
 left,lt=_validated_form(t);right,rt=_validated_form(anchor)
 return _relative_forms(left,lt,right,rt)

@lru_cache(maxsize=8192)
def _relative_forms(left,lt,right,rt):
 terms={key:(n,bounds) for key,n,bounds in lt}
 for key,n,bounds in rt:
  if key in terms:
   old,previous=terms[key]
   if previous!=bounds:raise ValueError('Common time atom has inconsistent bounds: '+key)
   terms[key]=(old-n,bounds)
  else:terms[key]=(-n,bounds)
 return str(left-right),tuple(sorted((key,n,bounds) for key,(n,bounds) in terms.items() if n))

def exact_translation(t,anchor):
 # relative validates both current expressions before consulting its cache.
 constant,terms=relative(t,anchor)
 if terms:return None
 return fraction_to_decimal_exact(Fraction(constant))
