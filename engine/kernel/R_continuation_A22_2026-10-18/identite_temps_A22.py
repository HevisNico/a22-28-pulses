"""F02: fresh uncertainty atoms and expression-based event tokens.

Logical labels are never evidence of physical equality. Each uncertain
construction allocates a fresh atom; only an explicit copy of an existing
expression preserves it. Forgetting a real dependency is an outer relaxation.
Imported atoms require a catalogue bound to a checked producer receipt.
This module checks representation, not the differential equation producing
an enclosure or the validity of that receipt (the provenance layer does).
"""
from dataclasses import fields,is_dataclass
from decimal import localcontext
import json
from functools import lru_cache
import dependances_A17 as dep
from intervalles_decimaux import I,D
from temps_symboliques_A22 import relative,fraction_to_decimal_exact

SCHEMA='A22-atoms-v2'
class AtomIdentityRefusal(RuntimeError):pass
_RECORDS={}
_USED_OWNERS=set()
_OWNER='local-only'
_SERIAL=0
_INSTALLED=False
_ORIGINAL_INIT=dep.Time.__init__

def begin_producer(owner):
    """Reserve one namespace for one fresh producer, never a loaded result."""
    global _OWNER,_SERIAL
    if not isinstance(owner,str) or not owner or owner=='local-only':
        raise AtomIdentityRefusal('A producer needs an explicit nonlocal identity')
    if owner in _USED_OWNERS or any(r['owner']==owner for r in _RECORDS.values()):
        raise AtomIdentityRefusal('Producer namespace already used; no counter reset or silent migration')
    _USED_OWNERS.add(owner);_OWNER=owner;_SERIAL=0

def _fresh(label,value,kind):
    global _SERIAL
    identity='A22:'+json.dumps([_OWNER,_SERIAL],ensure_ascii=True,separators=(',',':'))
    record=dict(owner=_OWNER,serial=_SERIAL,bounds=value.pair(),label=str(label),kind=kind)
    _SERIAL+=1
    if identity in _RECORDS:raise AtomIdentityRefusal('Fresh atom collision')
    _RECORDS[identity]=record
    return identity

def _check_term(identity,coefficient,value):
    if not isinstance(coefficient,int):raise AtomIdentityRefusal('Noninteger affine coefficient')
    value=I(value)
    record=_RECORDS.get(identity)
    if record is not None:
        if (value.lo,value.hi)!=tuple(map(D,record['bounds'])):
            raise AtomIdentityRefusal('Time atom bounds changed: '+str(identity))
        return I(*record['bounds'])
    # An allocated variable cannot become a constant by changing its bounds.
    # Reserved atom identities require a checked import even when punctual.
    if isinstance(identity,str) and identity.startswith('A22:['):
        raise AtomIdentityRefusal('Unknown time atom; checked catalogue required: '+str(identity))
    if value.lo==value.hi:return value
    raise AtomIdentityRefusal('Unknown time atom; checked catalogue required: '+str(identity))

def time_init(self,key,base,offset=D(0),terms=None):
    base=I(base);offset=D(offset)
    if terms is None:
        if base.lo==base.hi:terms=((str(key),1,base),)
        else:terms=((_fresh(key,base,'absolute-date-enclosure'),1,base),)
    else:
        terms=tuple((identity,coefficient,_check_term(identity,coefficient,value))
                    for identity,coefficient,value in terms)
    _ORIGINAL_INIT(self,key,base,offset,terms)

@lru_cache(maxsize=16384)
def _parsed_bounds(lo,hi):
    # Cache immutable Decimal endpoints only; never share a mutable interval.
    value=I(lo,hi)
    return value.lo,value.hi

def _validate_term(identity,coefficient,value):
    if type(value) is not I:
        _check_term(identity,coefficient,value);return
    if not isinstance(coefficient,int):raise AtomIdentityRefusal('Noninteger affine coefficient')
    record=_RECORDS.get(identity)
    if record is not None:
        bounds=record['bounds']
        if (type(bounds) in (list,tuple) and len(bounds)==2
                and type(bounds[0]) is str and type(bounds[1]) is str):
            if (value.lo,value.hi)!=_parsed_bounds(bounds[0],bounds[1]):
                raise AtomIdentityRefusal('Time atom bounds changed: '+str(identity))
        else:_check_term(identity,coefficient,value)
        return
    if isinstance(identity,str) and identity.startswith('A22:['):
        raise AtomIdentityRefusal('Unknown time atom; checked catalogue required: '+str(identity))
    if value.lo==value.hi:return
    raise AtomIdentityRefusal('Unknown time atom; checked catalogue required: '+str(identity))

def validate_time(time):
    # Legacy pickles bypass __init__. Checking at every symbolic/token
    # operation prevents an old name from acquiring a new meaning silently.
    if time.terms is None and time.base.lo!=time.base.hi:
        raise AtomIdentityRefusal('Legacy uncertain Time has no allocated identity')
    for identity,coefficient,value in time.expression():_validate_term(identity,coefficient,value)
    return time

class _Zero:
    def expression(self):return ()
_ZERO=_Zero()

def semantic_token(self):
    # relative validates the current expression, including cached forms.
    constant,terms=relative(self,_ZERO)
    if not terms:
        value=fraction_to_decimal_exact(constant)
        with localcontext() as context:
            context.prec=len(value.as_tuple().digits)+2
            return 'clock',str(value.normalize())
    return SCHEMA,constant,terms

def checked_shift(time,duration,key):
    validate_time(time);duration=I(duration)
    if duration.lo==duration.hi:return time.plus(duration.lo)
    identity=_fresh(key,duration,'elapsed-duration-enclosure')
    return dep.Time(key,time.box()+duration,D(0),time.expression()+((identity,1,duration),))

def _times(value):
    stack=[value];seen=set()
    while stack:
        item=stack.pop()
        if id(item) in seen:continue
        seen.add(id(item))
        if isinstance(item,dep.Time):yield item;continue
        if isinstance(item,dict):stack.extend(item.keys());stack.extend(item.values())
        elif isinstance(item,(list,tuple,set,frozenset)):stack.extend(item)
        elif is_dataclass(item):stack.extend(getattr(item,f.name) for f in fields(item))

def atom_catalog(value):
    records={}
    for time in _times(value):
        validate_time(time)
        for identity,coefficient,bounds in time.expression():
            if identity in _RECORDS:
                record=_RECORDS[identity]
                if record['owner']=='local-only':raise AtomIdentityRefusal('Unqualified local atoms cannot be exported as producer evidence')
                records[identity]=dict(record,bounds=list(record['bounds']))
    return dict(schema=SCHEMA,records={key:records[key] for key in sorted(records)})

def _checked_catalog(catalog):
    if not isinstance(catalog,dict) or catalog.get('schema')!=SCHEMA or not isinstance(catalog.get('records'),dict):
        raise AtomIdentityRefusal('Missing or incompatible atom catalogue')
    checked={}
    for identity,record in catalog['records'].items():
        if not isinstance(record,dict):raise AtomIdentityRefusal('Malformed atom record')
        owner=record.get('owner');serial=record.get('serial')
        expected='A22:'+json.dumps([owner,serial],ensure_ascii=True,separators=(',',':'))
        if not isinstance(owner,str) or not owner or owner=='local-only' or type(serial) is not int or serial<0 or identity!=expected:
            raise AtomIdentityRefusal('Invalid producer atom identity')
        if not isinstance(record.get('label'),str) or record.get('kind') not in ('absolute-date-enclosure','elapsed-duration-enclosure'):
            raise AtomIdentityRefusal('Invalid atom construction descriptor')
        bounds=I(*record['bounds'])
        if bounds.lo==bounds.hi:raise AtomIdentityRefusal('Point values do not need variable identities')
        canonical=dict(owner=owner,serial=serial,bounds=bounds.pair(),label=record.get('label'),kind=record.get('kind'))
        if canonical!=record:raise AtomIdentityRefusal('Noncanonical atom record')
        if identity in _RECORDS and _RECORDS[identity]!=record:
            raise AtomIdentityRefusal('Conflicting imported atom definition')
        checked[identity]=canonical
    return checked

def import_catalog(catalog):
    """Call only AFTER checking its binding to a qualified producer payload."""
    checked=_checked_catalog(catalog)
    _RECORDS.update(checked)
    return len(checked)

def validate_catalog(value,catalog):
    checked=_checked_catalog(catalog)
    for time in _times(value):
        if time.terms is None and time.base.lo!=time.base.hi:
            raise AtomIdentityRefusal('Legacy date cannot be certified by a later catalogue')
        for identity,coefficient,bounds in time.expression():
            if identity in checked:
                if (bounds.lo,bounds.hi)!=_parsed_bounds(*checked[identity]['bounds']):
                    raise AtomIdentityRefusal('Payload atom absent from or inconsistent with its catalogue')
            elif (identity in _RECORDS or bounds.lo!=bounds.hi
                  or isinstance(identity,str) and identity.startswith('A22:[')):
                raise AtomIdentityRefusal('Payload atom absent from or inconsistent with its catalogue')
    return True

def install():
    global _INSTALLED
    dep.Time.__init__=time_init
    dep.Time.token=semantic_token
    dep.shift=checked_shift
    _INSTALLED=True
    return SCHEMA
