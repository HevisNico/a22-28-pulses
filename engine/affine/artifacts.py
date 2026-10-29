"""Exact typed DAG artifacts. No pickle or executable deserialization.
Sharing is a storage optimization, never a criterion for deleting a history.
"""
from pathlib import Path
from decimal import Decimal
from dataclasses import is_dataclass,fields
import hashlib,json,os,math
from affine_iv import I
from temporal import Time,same_form
SCHEMA='A22-affine-research-DAG-1'

def file_hash(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(65536),b''):h.update(chunk)
    return h.hexdigest()

def canonical_hash(x):
    h=hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(x):h.update(chunk.encode())
    return h.hexdigest()

def atomic_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w') as f:
        for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(obj):f.write(chunk)
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    return file_hash(path)

class Encoder:
    def __init__(self,node_limit=500000):
        self.nodes=[];self.memo={};self.active=set();self.intern={};self.limit=node_limit
    def walk(self,x):
        oid=id(x)
        if oid in self.memo:return self.memo[oid][1]
        if oid in self.active:raise ValueError('cyclic scientific payload')
        self.active.add(oid)
        if x is None or type(x) in (bool,int,str):node=('scalar',x)
        elif type(x) is float:
            if not math.isfinite(x):raise ValueError('non-finite float')
            node=('float',x.hex())
        elif isinstance(x,Decimal):
            if not x.is_finite():raise ValueError('non-finite Decimal')
            node=('decimal',str(x))
        elif isinstance(x,I):node=('affine',str(x.clo),str(x.chi),tuple((k,v.hex()) for k,v in sorted(x.d.items())),x.e.hex())
        elif isinstance(x,Time):node=('time',x.key,self.walk(x.base),str(x.offset),self.walk(x.terms))
        elif type(x) in (list,tuple):node=(type(x).__name__,tuple(self.walk(v) for v in x))
        elif type(x) is dict:node=('dict',tuple((self.walk(k),self.walk(v)) for k,v in x.items()))
        elif is_dataclass(x):node=('record',type(x).__module__,type(x).__name__,tuple((f.name,self.walk(getattr(x,f.name))) for f in fields(x)))
        else:raise TypeError('unsupported payload type: '+type(x).__name__)
        self.active.remove(oid)
        # bool and int must remain different types despite True == 1.
        key=(type(x).__name__,node)
        idx=self.intern.get(key)
        if idx is None:
            if len(self.nodes)>=self.limit:raise MemoryError('artifact node budget exceeded')
            idx=len(self.nodes);self.nodes.append(node);self.intern[key]=idx
        self.memo[oid]=(x,idx)
        return idx
    def encode(self,x):
        root=self.walk(x)
        return {'schema':SCHEMA,'nodes':self.nodes,'root':root}

def decode(doc):
    import actuations_A19 as ac,depot_A19 as dz,cycle_local_A20 as cy
    allowed={('actuations_A19','Segment'):ac.Segment,('actuations_A19','History'):ac.History,('depot_A19','History'):dz.History,('cycle_local_A20','Branch'):cy.Branch,('cycle_local_A20','Forest'):cy.Forest}
    if doc.get('schema')!=SCHEMA:raise ValueError('unattested or old artifact schema')
    nodes=doc['nodes'];values=[];atoms={}
    def child(i):
        if type(i) is not int or not 0<=i<len(values):raise ValueError('invalid DAG edge')
        return values[i]
    for node in nodes:
        tag=node[0]
        if tag=='scalar':
            x=node[1]
            if x is not None and type(x) not in (str,bool,int):raise TypeError('invalid scalar')
        elif tag=='float':
            x=float.fromhex(node[1])
            if not math.isfinite(x):raise ValueError('non-finite float')
        elif tag=='decimal':
            x=Decimal(node[1])
            if not x.is_finite():raise ValueError('non-finite Decimal')
        elif tag=='affine':
            pairs=node[3];d=dict((k,float.fromhex(v)) for k,v in pairs)
            if len(d)!=len(pairs):raise ValueError('duplicate affine symbol')
            x=object.__new__(I);x.__setstate__((Decimal(node[1]),Decimal(node[2]),d,float.fromhex(node[4])))
        elif tag=='time':
            terms=child(node[4])
            if not isinstance(terms,tuple):raise ValueError('explicit time expression required')
            x=Time(node[1],child(node[2]),Decimal(node[3]),terms)
            for key,n,v in x.terms:
                if key in atoms and not same_form(atoms[key],v):raise ValueError('time atom definition changed')
                atoms[key]=v
        elif tag in ('list','tuple'):
            x=[child(i) for i in node[1]]
            if tag=='tuple':x=tuple(x)
        elif tag=='dict':
            pairs=[(child(k),child(v)) for k,v in node[1]];x=dict(pairs)
            if len(x)!=len(pairs):raise ValueError('duplicate dictionary key')
        elif tag=='record':
            cls=allowed.get((node[1],node[2]))
            if cls is None:raise TypeError('unsupported record type')
            names=[k for k,v in node[3]]
            if names!=[f.name for f in fields(cls)]:raise ValueError('record fields changed')
            x=cls(**{k:child(v) for k,v in node[3]})
        else:raise ValueError('unknown DAG tag')
        values.append(x)
    return child(doc['root'])

def read(path,expected_sha=None,max_bytes=256*1024*1024):
    path=Path(path)
    if path.stat().st_size>max_bytes:raise MemoryError('artifact byte budget exceeded')
    if expected_sha is not None and file_hash(path)!=expected_sha:raise ValueError('artifact hash mismatch')
    with path.open() as f:return decode(json.load(f))

def write_checked(path,payload):
    """Capture before write, decode from disk, compare exact typed content."""
    before=Encoder().encode(payload);digest=canonical_hash(before)
    sha=atomic_json(path,before)
    reread=read(path,sha)
    after=Encoder().encode(reread)
    # Compare bytes represented by the full typed graph, not float tolerances.
    if canonical_hash(after)!=digest:raise ValueError('fresh/disk content mismatch')
    return sha,{'full_content_equal':True,'typed_content_sha256':digest,'nodes':len(before['nodes'])}
