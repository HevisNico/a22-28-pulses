"""Explicit time identities. Labels never assert dependence.
Creation allocates a new atom; plus()/copy() preserve the existing expression.
"""
from dataclasses import dataclass,field
from decimal import Decimal as D,localcontext
from fractions import Fraction
import intervalles_decimaux as iv
from affine_iv import I
_PREFIX=None
_COUNTER=0

def begin_producer(namespace):
    global _PREFIX,_COUNTER
    if not isinstance(namespace,str) or not namespace:raise ValueError('producer namespace required')
    _PREFIX=namespace;_COUNTER=0

def fresh():
    global _COUNTER
    if _PREFIX is None:raise RuntimeError('time producer not initialized')
    _COUNTER+=1
    return f'{_PREFIX}/time/{_COUNTER}'

def exact_decimal(f):
    f=Fraction(f)
    with localcontext() as c:
        c.prec=max(160,len(str(abs(f.numerator)))+len(str(f.denominator))+4)
        x=D(f.numerator)/D(f.denominator)
    if Fraction(x)!=f:raise ArithmeticError('non-terminating clock rational')
    return x

def text(x):
    if not x:return '0'
    with localcontext() as c:
        c.prec=len(x.as_tuple().digits)+2
        return str(x.normalize())

def same_form(a,b):
    return a is b or (a.clo==b.clo and a.chi==b.chi and a.e==b.e and a.d==b.d)

@dataclass(frozen=True,eq=False)
class Time:
    key:str
    base:I
    offset:D=D(0)
    terms:tuple|None=None
    _token:object=field(default=None,init=False,repr=False)
    _box:object=field(default=None,init=False,repr=False)
    def __post_init__(self):
        if not isinstance(self.key,str) or not isinstance(self.base,I):raise TypeError('invalid time')
        off=D(self.offset)
        if not off.is_finite():raise ValueError('non-finite time offset')
        object.__setattr__(self,'offset',off)
        if self.terms is None:object.__setattr__(self,'terms',((fresh(),1,self.base),))
        elif not isinstance(self.terms,tuple):raise TypeError('immutable time terms required')
        for atom,n,value in self.terms:
            if not isinstance(atom,str) or type(n) is not int or not isinstance(value,I):raise TypeError('invalid time atom')
    def box(self):
        if self._box is None:object.__setattr__(self,'_box',self.base if not self.offset else self.base+I(self.offset))
        return self._box
    def expression(self):
        if not self.offset:return self.terms
        return self.terms+((f'point:{text(self.offset)}',1,I(self.offset)),)
    def plus(self,u):
        return Time(self.key,self.base,exact_decimal(Fraction(self.offset)+Fraction(D(u))),self.terms)
    def copy(self):return Time(self.key,self.base,self.offset,self.terms)
    def minus(self,other):
        if not isinstance(other,Time):raise TypeError('attested affine time required')
        if self is other:return I(0)
        result={}
        for sign,t in ((1,self),(-1,other)):
            for key,n,value in t.terms:
                if key in result:
                    count,prev=result[key]
                    if not same_form(prev,value):raise ValueError('conflicting time atom definition: '+key)
                    result[key]=(count+sign*n,value)
                else:result[key]=(sign*n,value)
        a=I(exact_decimal(Fraction(self.offset)-Fraction(other.offset)))
        for n,v in result.values():
            if n==1:a=a+v
            elif n==-1:a=a-v
            elif n:a=a+n*v
        bx=self.box()-other.box()
        return bx if bx.width()<a.width() else a
    def token(self):
        if self._token is None:
            total=Fraction(self.offset);atoms={}
            definitions={}
            for key,n,x in self.terms:
                if key in definitions and not same_form(definitions[key],x):raise ValueError('conflicting time atom')
                definitions[key]=x
                if not x.symbolic() and x.clo==x.chi:total+=n*Fraction(x.clo)
                else:atoms[key]=atoms.get(key,0)+n
            expr=tuple(sorted((k,n) for k,n in atoms.items() if n))
            tok=('clock',text(exact_decimal(total))) if not expr else ('affine-time',(expr,total.numerator,total.denominator))
            object.__setattr__(self,'_token',tok)
        return self._token

def shift(t,u,key):
    u=I(u)
    if not u.symbolic() and u.lo==u.hi:return t.plus(u.lo)
    return Time(key,t.box()+u,D(0),t.expression()+((fresh(),1,u),))

def install(dep):
    dep.Time=Time;dep.shift=shift
