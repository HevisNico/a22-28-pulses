"""Lossless JSON encoding of the interval/history state, for local replay."""
from dataclasses import is_dataclass,fields
import dependances_A17 as dep
import actuations_A19 as ac
import depot_A19 as dz
from intervalles_decimaux import I,D

def encode(x):
    if isinstance(x,I):return dict(type='I',bounds=x.pair())
    if isinstance(x,dep.Time):return dict(type='Time',**dep.encode_time(x))
    if isinstance(x,D):return dict(type='Decimal',value=str(x))
    if is_dataclass(x):return {f.name:encode(getattr(x,f.name)) for f in fields(x)}
    if isinstance(x,dict):
        if any(not isinstance(k,str) for k in x):return dict(type='Map',items=[[encode(k),encode(v)] for k,v in x.items()])
        return {k:encode(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [encode(v) for v in x]
    return x

def decode(x):
    if isinstance(x,list):return tuple(decode(v) for v in x)
    if not isinstance(x,dict):return x
    if x.get('type')=='I':return I(*x['bounds'])
    if x.get('type')=='Time':return dep.decode_time(x)
    if x.get('type')=='Decimal':return D(x['value'])
    if x.get('type')=='Map':return {decode(k):decode(v) for k,v in x['items']}
    y={k:decode(v) for k,v in x.items()}
    if set(y)=={'port','origin','start','full_start','end','full_end'}:return ac.Segment(**y)
    if set(y)=={'initial','full','partial','fire','marks','saturated'}:return ac.History(**y)
    if set(y)=={'initial','full','partial','active','clamped','conditions'}:return dz.History(**y)
    return y

def state(x):
    s=decode(x)
    for name in ('raw','mark','err','aux','caps'):s[name]=list(s[name])
    # Local initial fixture is protected, so no ready-memory tuple keys.
    assert s['memory'] is None
    return s
