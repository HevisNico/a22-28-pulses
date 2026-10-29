"""F03: fail-closed validity receipts, independent of the hybrid physics.

Receipts are integrity/compatibility evidence, not signatures or proofs of
ODE correctness. Old artifacts are never upgraded by reading them.
"""
from pathlib import Path
from decimal import Decimal, getcontext
from fractions import Fraction
from types import CodeType, FunctionType, ModuleType
from functools import _lru_cache_wrapper
from dataclasses import is_dataclass, fields
import hashlib, json, sys, gzip, pickle, weakref

SCHEMA = 'A22-validity-v5-time-dag'
_OWNER_ARTIFACTS = {}
class ProvenanceRefusal(RuntimeError): pass
class MissingManifest(ProvenanceRefusal): pass
class ValidityMismatch(ProvenanceRefusal): pass
class CoverageMismatch(ProvenanceRefusal): pass
class BrokenChain(ProvenanceRefusal): pass
class UnestablishedSourceChain(ProvenanceRefusal): pass
class CapturedStateRefusal(ProvenanceRefusal): pass

def normal(value):
    if value is None or isinstance(value, (str, bool, int, float)): return value
    if isinstance(value, Fraction): return {'rational':[value.numerator,value.denominator]}
    if isinstance(value, Decimal): return {'decimal': str(value)}
    if isinstance(value, bytes): return {'bytes_sha256': hashlib.sha256(value).hexdigest()}
    if isinstance(value, Path): return str(value)
    if isinstance(value, dict):
        return {'mapping': sorted(((normal(k), normal(v)) for k,v in value.items()), key=lambda x: json.dumps(x[0],sort_keys=True))}
    if isinstance(value, (tuple,list)):
        return {type(value).__name__: [normal(v) for v in value]}
    if isinstance(value, (set,frozenset)):
        return {type(value).__name__: sorted((normal(v) for v in value),key=lambda x:json.dumps(x,sort_keys=True))}
    if is_dataclass(value): return {'class':type(value).__module__+'.'+type(value).__qualname__, 'fields': normal({f.name:getattr(value,f.name) for f in fields(value)})}
    slots=tuple(name for cls in type(value).__mro__ for name in getattr(cls,'__slots__',()) if name not in ('__dict__','__weakref__'))
    if slots: return {'class':type(value).__module__+'.'+type(value).__qualname__, 'slots':normal({name:getattr(value,name) for name in slots if hasattr(value,name)})}
    if hasattr(value,'__dict__'): return {'class':type(value).__module__+'.'+type(value).__qualname__, 'fields':normal(vars(value))}
    raise ProvenanceRefusal('Unsupported object in provenance: '+type(value).__qualname__)

_TEXT_DIGEST_CACHE = {}
_ENV_DIGEST_CACHE = {}
_ENV_KEYS = frozenset(('schema', 'kernel', 'loaded_code', 'adapters', 'settings', 'options', 'arithmetic', 'runtime'))


def _metadata_key(value, remaining):
    remaining[0] -= 1
    if remaining[0] < 0:
        raise ValueError('Metadata guard budget exceeded')
    cls = type(value)
    if value is None:
        return ('none',)
    if cls in (str, bool, int):
        return (cls.__name__, value)
    if cls is float:
        return ('float', value.hex())
    if cls in (tuple, list):
        return (cls.__name__, tuple(_metadata_key(v, remaining) for v in value))
    if cls is dict and all(type(k) is str for k in value):
        return ('dict', tuple((k, _metadata_key(value[k], remaining)) for k in sorted(value)))
    raise ValueError('Non-JSON metadata needs ordinary encoding')


def digest(value):
    if type(value) is str:
        cached = _TEXT_DIGEST_CACHE.get(value)
        if cached is not None:
            return cached
        from canonical_bytes_A22 import digest as canonical_digest
        result = canonical_digest(value)
        if len(value) <= 1024:
            if len(_TEXT_DIGEST_CACHE) >= 4096:
                _TEXT_DIGEST_CACHE.clear()
            _TEXT_DIGEST_CACHE[value] = result
        return result
    from canonical_bytes_A22 import digest as canonical_digest
    if type(value) is dict and value.keys() == _ENV_KEYS and value.get('schema') == SCHEMA:
        try:
            from canonical_bytes_A22 import _native
            key = _native.metadata_key(value)
        except (ValueError, RecursionError):
            return canonical_digest(value)
        cached = _ENV_DIGEST_CACHE.get(key)
        if cached is not None:
            return cached
        result = canonical_digest(value)
        if len(_ENV_DIGEST_CACHE) >= 8:
            _ENV_DIGEST_CACHE.clear()
        _ENV_DIGEST_CACHE[key] = result
        return result
    return canonical_digest(value)
def file_hash(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def code_form(code):
    """Stable logical bytecode: no marshal interning/adaptive-state flags."""
    def constant(value):
        if isinstance(value,CodeType):return {'code':code_form(value)}
        if value is Ellipsis:return {'ellipsis':True}
        if value is None or isinstance(value,(bool,int,str)):return value
        if isinstance(value,bytes):return {'bytes':value.hex()}
        if isinstance(value,float):return {'float':value.hex()}
        if isinstance(value,complex):return {'complex':[value.real.hex(),value.imag.hex()]}
        if isinstance(value,tuple):return {'tuple':[constant(item) for item in value]}
        if isinstance(value,frozenset):return {'frozenset':sorted((constant(item) for item in value),key=lambda x:json.dumps(x,sort_keys=True))}
        raise ProvenanceRefusal('Unsupported code constant: '+type(value).__qualname__)
    names=('co_argcount','co_posonlyargcount','co_kwonlyargcount','co_nlocals','co_stacksize','co_flags',
           'co_names','co_varnames','co_freevars','co_cellvars','co_name','co_qualname','co_firstlineno')
    result={name:getattr(code,name) for name in names}
    result.update(co_code=code.co_code.hex(),co_consts=[constant(value) for value in code.co_consts],
                  co_exceptiontable=code.co_exceptiontable.hex(),co_linetable=code.co_linetable.hex())
    return result

def _descriptor_uncached(fn, *, allowed_classes=()):
    """Code + invocation defaults + captured cells, with a strict graph codec.

    Mutable sharing is preserved. Cycles, empty cells, modules and opaque
    objects are rejected. Classes are stable global references only when
    builtin or their methods are covered by this effective kernel inventory.
    """
    memo={};active=set();allowed_classes=set(allowed_classes)
    def captured(value):
        if value is None or type(value) in (bool,int,str):return value
        if type(value) is float:return {'float':value.hex()}
        numpy=sys.modules.get('numpy')
        if numpy is not None and type(value) is getattr(numpy,'float64',None):return {'numpy.float64':float(value).hex()}
        if type(value) is complex:return {'complex':[value.real.hex(),value.imag.hex()]}
        if type(value) is Decimal:return {'decimal':str(value)}
        if type(value) is Fraction:return {'rational':[value.numerator,value.denominator]}
        if type(value) is bytes:return {'bytes':value.hex()}
        if value is Ellipsis:return {'ellipsis':True}
        if isinstance(value,ModuleType):raise CapturedStateRefusal('Captured module is not an admissible value')
        if isinstance(value,type):
            module=sys.modules.get(value.__module__);resolved=module
            for name in value.__qualname__.split('.'):
                if name=='<locals>' or resolved is None:raise CapturedStateRefusal('Captured local/unresolved class')
                resolved=vars(resolved).get(name)
            if resolved is not value:raise CapturedStateRefusal('Captured class is not its declared global binding')
            if value.__module__=='builtins' or value in allowed_classes:
                return {'global_class':[value.__module__,value.__qualname__]}
            # Generated frozen dataclasses capture this exception class. It
            # is transparent only in its trivial stdlib shape: no behavior
            # beyond the exact builtin AttributeError base. Mutation refuses.
            import dataclasses
            if value is dataclasses.FrozenInstanceError and value.__bases__==(AttributeError,) and set(vars(value))<={'__module__','__doc__','__weakref__'}:
                return {'trivial_stdlib_exception':[value.__module__,value.__qualname__,'builtins.AttributeError',value.__doc__]}
            raise CapturedStateRefusal('Captured class methods are outside the effective kernel: '+value.__module__+'.'+value.__qualname__)
        identity=id(value)
        if identity in active:raise CapturedStateRefusal('Cycle in captured/default values')
        if identity in memo:return {'ref':memo[identity]}
        number=len(memo);memo[identity]=number;active.add(identity)
        try:
            if isinstance(value,FunctionType):
                closure=[]
                for name,cell in zip(value.__code__.co_freevars,value.__closure__ or ()):
                    try:item=cell.cell_contents
                    except ValueError:raise CapturedStateRefusal('Empty captured cell: '+name) from None
                    closure.append([name,captured(item)])
                body={'module':value.__module__,'qualname':value.__qualname__,
                      'code':code_form(value.__code__),'defaults':captured(value.__defaults__),
                      'kwdefaults':captured(value.__kwdefaults__),'closure':closure}
                return {'id':number,'function':body}
            if type(value) is dict:return {'id':number,'dict':[[captured(k),captured(v)] for k,v in value.items()]}
            if type(value) in (list,tuple,set,frozenset):
                return {'id':number,type(value).__name__:[captured(item) for item in value]}
            # Interval values occur in potential adapters. Retain the exact
            # registered class and endpoint values, not an arbitrary __dict__.
            cls=type(value)
            if cls in allowed_classes and cls.__module__=='intervalles_decimaux' and cls.__name__=='I':
                return {'id':number,'interval':[str(value.lo),str(value.hi)]}
            raise CapturedStateRefusal('Unsupported captured/default type: '+cls.__module__+'.'+cls.__qualname__)
        finally:active.remove(identity)
    if not isinstance(fn,FunctionType):raise CapturedStateRefusal('Only Python functions have a qualified invocation descriptor')
    return {'module':fn.__module__,'qualname':fn.__qualname__,
            'code_sha256':digest(code_form(fn.__code__)),'invocation_sha256':digest(captured(fn))}

# Function objects are weak keys: temporary callbacks are not kept alive.
# A hit is allowed only for immutable captured values. Mutable/default/class
# graphs always take the original full descriptor path. Code objects are
# immutable; replacing __code__ or any guarded binding invalidates the hit.
_DESCRIPTOR_CACHE = weakref.WeakKeyDictionary()


def _immutable_capture_guard(value, remaining, allowed_classes):
    remaining[0] -= 1
    if remaining[0] < 0:
        raise ValueError('Capture guard budget exceeded')
    cls = type(value)
    if value is None:
        return ('none',)
    if cls in (bool, int, str, bytes):
        return (cls.__name__, value)
    if cls is float:
        return ('float', value.hex())
    if cls is complex:
        return ('complex', value.real.hex(), value.imag.hex())
    if cls is Decimal:
        return ('decimal', str(value))
    if cls is Fraction:
        return ('fraction', value.numerator, value.denominator)
    if value is Ellipsis:
        return ('ellipsis',)
    if isinstance(value, type):
        resolved = sys.modules.get(value.__module__)
        for name in value.__qualname__.split('.'):
            if name == '<locals>' or resolved is None:
                raise ValueError('Unresolved captured class')
            resolved = vars(resolved).get(name)
        if resolved is not value:
            raise ValueError('Captured class binding changed')
        if value.__module__ == 'builtins' or value in allowed_classes:
            return ('class', id(value), value.__module__, value.__qualname__)
        import dataclasses
        if (value is dataclasses.FrozenInstanceError and value.__bases__ == (AttributeError,)
                and set(vars(value)) <= {'__module__', '__doc__', '__weakref__'}):
            return ('stdlib_exception', id(value), value.__module__, value.__qualname__, value.__doc__)
        raise ValueError('Class needs the full descriptor')
    if cls is tuple:
        # Identity preserves the captured graph's sharing, even for equal tuples.
        return ('tuple', id(value), tuple(_immutable_capture_guard(v, remaining, allowed_classes) for v in value))
    raise ValueError('Capture needs the full descriptor')


def _descriptor_guard(fn, allowed_classes):
    remaining = [256]
    defaults = _immutable_capture_guard(fn.__defaults__, remaining, allowed_classes)
    keywords = fn.__kwdefaults__
    if keywords is None:
        kwguard = None
    elif type(keywords) is dict and all(type(k) is str for k in keywords):
        kwguard = (id(keywords), tuple((k, _immutable_capture_guard(v, remaining, allowed_classes)) for k, v in keywords.items()))
    else:
        raise ValueError('Keyword defaults need the full descriptor')
    cells = tuple(_immutable_capture_guard(cell.cell_contents, remaining, allowed_classes) for cell in fn.__closure__ or ())
    if type(fn.__module__) is not str or type(fn.__qualname__) is not str:
        raise ValueError('Metadata needs the full descriptor')
    return (id(fn.__code__), fn.__code__, fn.__module__, fn.__qualname__, defaults, kwguard, cells)


def descriptor(fn, *, allowed_classes=()):
    if not isinstance(fn, FunctionType):
        return _descriptor_uncached(fn, allowed_classes=allowed_classes)
    allowed_classes = set(allowed_classes)
    try:
        guard = _descriptor_guard(fn, allowed_classes)
    except (ValueError, RecursionError):
        return _descriptor_uncached(fn, allowed_classes=allowed_classes)
    previous = _DESCRIPTOR_CACHE.get(fn)
    if previous is not None and previous[0] == guard:
        return dict(previous[1])
    result = _descriptor_uncached(fn, allowed_classes=allowed_classes)
    _DESCRIPTOR_CACHE[fn] = (guard, dict(result))
    return result


def environment(root, *, settings, adapters, options, precision=None, kernel_files=None, loaded_modules=None):
    root=Path(root)
    if kernel_files is None:
        raise ProvenanceRefusal('Explicit effective kernel inventory is required')
    # The compiled encoder is part of this new software identity. Refuse a
    # replaced on-disk image even when the process still holds its old code.
    import canonical_bytes_A22 as codec
    native=codec._NATIVE_PATH
    if any(getattr(codec._native,name,None) is not fn for name,fn in codec._NATIVE_FUNCTIONS):
        raise ValidityMismatch('Loaded native encoder functions changed')
    if file_hash(native)!=codec._NATIVE_LOADED_SHA256:
        raise ValidityMismatch('Loaded native encoder differs from its file')
    kernel_files=dict(kernel_files)
    kernel_files['native/'+native.name]=native
    kernel_files['native/a22_native.c']=native.with_name('a22_native.c')
    loaded_code={}
    known_files={str(Path(path).resolve()) for path in kernel_files.values()}
    included={name:module for name,module in tuple(sys.modules.items())
              if (loaded_modules is None or name in loaded_modules)
              and getattr(module,'__file__',None) and str(Path(module.__file__).resolve()) in known_files}
    allowed_classes={value for name,module in included.items() for value in vars(module).values()
                     if isinstance(value,type) and value.__module__==name}
    for name,module in included.items():
        for attr,value in tuple(vars(module).items()):
            if isinstance(value,FunctionType):
                loaded_code[name+'.'+attr]=descriptor(value,allowed_classes=allowed_classes)
            elif isinstance(value,_lru_cache_wrapper):
                # Cache wrappers must not hide the implementation they call.
                loaded_code[name+'.'+attr]={
                    'wrapped':descriptor(value.__wrapped__,allowed_classes=allowed_classes),
                    'cache_parameters':value.cache_parameters()}
            elif isinstance(value,type) and value.__module__==name:
                for method,fn in tuple(vars(value).items()):
                    if isinstance(fn,FunctionType):loaded_code[name+'.'+attr+'.'+method]=descriptor(fn,allowed_classes=allowed_classes)
    ctx=getcontext()
    from importlib.metadata import version, PackageNotFoundError
    dependencies={}
    for package in ('numpy','scipy'):
        try: dependencies[package]=version(package)
        except PackageNotFoundError: dependencies[package]=None
    return {'schema':SCHEMA,'kernel':{name:file_hash(p) for name,p in sorted(kernel_files.items())},
            'loaded_code':loaded_code,'adapters':adapters,'settings':settings,'options':options,
            'arithmetic':{'precision':ctx.prec if precision is None else precision,'rounding':str(ctx.rounding),
                          'Emin':ctx.Emin,'Emax':ctx.Emax,'assertions':__debug__},
            'runtime':{'python':sys.version,'implementation':sys.implementation.name,'dependencies':dependencies}}

def coverage(data):
    # Both live frontier AND already finished histories are bound, together
    # with their exterior queue and coherent source selectors.
    keys=('status','frontier','finished','pending','outputs','terminal','source_ids','source_proofs','source_records','atom_catalog','context','context_options','layer','lane')
    from canonical_bytes_A22 import freeze_many
    present = tuple(key for key in keys if key in data)
    return dict(zip(present, (value.sha256() for value in freeze_many(data[key] for key in present))))

def make_manifest(env, source_records, *, layer, lane):
    return {'schema':SCHEMA,'environment_sha256':digest(env),
            'fixture_only_no_physical_validation':env.get('options',{}).get('fixture_only_no_physical_validation') is True,
            'sources':[{'id':r['id'],'record_sha256':digest(r)} for r in source_records],
            'scope':{'layer':layer,'lane':lane,'training_source':'lane0: 128 canonical pulses at 8*k',
                     'observation_time':'1116','future_source':'canonical lane0 pulses, gaps >= 20',
                     'claim':'finite cell history only; no global invariance or mixing assertion'}}

def attach(data, manifest, *, origin, parents=(), producer_owner=None):
    """Producer-only: call after this invocation actually validates data.

    Never use this to bless a loaded legacy artifact. Parent receipts are
    mandatory for resumed computations and checked before this call.
    """
    data['provenance']={'schema':SCHEMA,'manifest':manifest,'manifest_sha256':digest(manifest),
                        'coverage':coverage(data),'origin':origin,'parents':list(parents),
                        'whole_history_current_environment':True,'producer_owner':producer_owner}
    return data

def verify(data, expected, *, base, seen=None):
    receipt=data.get('provenance')
    if not isinstance(receipt,dict): raise MissingManifest('Artifact has no producer manifest; replay from initialisation required')
    if receipt.get('schema')!=SCHEMA or receipt.get('manifest_sha256')!=digest(receipt.get('manifest')):
        raise ValidityMismatch('Invalid manifest integrity/schema')
    if receipt['manifest']!=expected: raise ValidityMismatch('Kernel, settings, precision, sources, options or scope changed')
    if 'source_records' in data:
        actual=[{'id':r['id'],'record_sha256':digest(r)} for r in data['source_records']]
        if actual!=expected.get('sources'):raise CoverageMismatch('Embedded input records do not match manifest sources')
    if any(key in data and data[key]!=expected['scope'][key] for key in ('layer','lane')):
        raise CoverageMismatch('Cell scope differs from manifest')
    if receipt.get('coverage')!=coverage(data): raise CoverageMismatch('Frontier, finished histories, queue or source binding changed')
    if receipt.get('whole_history_current_environment') is not True: raise BrokenChain('Suffix-only receipt is not whole-history validation')
    kind=receipt.get('origin',{}).get('kind')
    inherited_catalogs=[r.get('source_provenance',{}).get('atom_catalog',{}) for r in data.get('source_records',())]
    parents=receipt.get('parents',())
    if kind=='from_initialisation':
        if parents: raise BrokenChain('Initialisation receipt has unexpected resume parents')
        if receipt['origin'].get('source_chain_verified') is not True: raise BrokenChain('Unverified input source ancestry')
    elif kind=='resume':
        if len(parents)!=1: raise BrokenChain('A resume must bind exactly its input artifact')
        seen=set() if seen is None else set(seen)
        ref=parents[0]; path=(Path(base)/ref['payload']).resolve(); stamp=(str(path),ref['sha256'])
        if stamp in seen: raise BrokenChain('Cycle in resume ancestry')
        seen.add(stamp)
        if not path.is_file() or file_hash(path)!=ref['sha256']: raise BrokenChain('Resume ancestor missing or changed')
        old=_stream_read(path.read_bytes())
        verify(old,expected,base=base,seen=seen)
        inherited_catalogs.append(old.get('atom_catalog',{}))
    else: raise BrokenChain('Unknown or missing initialisation origin')
    if 'atom_catalog' in data:
        check_atom_authority(data['atom_catalog'],expected,receipt.get('producer_owner'),inherited_catalogs)
    return receipt

def check_atom_authority(catalog,manifest,owner,inherited_catalogs):
    if not isinstance(owner,str) or not owner.startswith(digest(manifest)+':') or owner==digest(manifest)+':':
        raise BrokenChain('Producer namespace is not bound to this manifest and attempt')
    inherited={}
    for old in inherited_catalogs:
        for identity,record in old.get('records',{}).items():
            if identity in inherited and inherited[identity]!=record:raise BrokenChain('Conflicting inherited atom definitions')
            inherited[identity]=record
    for identity,record in catalog.get('records',{}).items():
        if record.get('owner')==owner:continue
        if inherited.get(identity)!=record:raise BrokenChain('Atom has no source/parent authority: '+str(identity))
    return True


def check_terminal_binding(record, receipt, expected_hash):
    """Resolve an explicit state reference; an output calendar is never its ID.

    The caller has independently verified the producer bytes and exact history
    selector. This is storage indirection, not a weaker state equivalence.
    """
    field = 'terminal_state' if receipt['selector'] == 'outputs' else 'terminal_history'
    if 'terminal_ref' in record:
        if 'terminal_state' in record or 'terminal_history' in record:
            raise CoverageMismatch('Ambiguous inline and referenced terminal state')
        ref = record['terminal_ref']
        expected = ('A22-terminal-reference-v1', receipt['sha256'], receipt['selector'], expected_hash)
        if (type(ref) is not tuple or len(ref) != 4
                or type(ref[2]) is not type(expected[2]) or ref != expected):
            raise CoverageMismatch('Referenced state differs from selected producer history')
    elif field not in record or digest(record[field]) != expected_hash:
        raise CoverageMismatch('Derived state/output pair differs from selected producer')

def source_receipt(record, env, *, kind, **evidence):
    """Used only by a source producer after checking its derivation.

    check_sources independently rechecks initial trains or parent outputs;
    a receipt with matching hashes alone never establishes the source chain.
    """
    record['source_provenance']={'schema':SCHEMA,'environment_sha256':digest(env),
       'record_sha256':digest({k:v for k,v in record.items() if k!='source_provenance'}),
       'kind':kind,**evidence}
    return record

# Qualified, idempotent kernel validators. Unknown/stateful callbacks retain
# the serial traversal. These invocation fingerprints are audited alongside
# the two source helpers and intentionally fail conservatively after edits.
_SOURCE_CALLBACK_FINGERPRINTS = {'canonical_initial_source': {'code_sha256': '5dc9cf05d8181a690352759653398f283630547978bf03d9a1c500b35d81be1a',
                              'invocation_sha256': '8c22cb4805db3d4a72d89224e97fd607671dc809ccf4f6ca403faf95889f5251',
                              'module': 'campagne_A22',
                              'qualname': 'canonical_initial_source'},
 'checked_source_atoms': {'code_sha256': '07ea093c66866c75ca89484374f9407d219c5521262781f420c46ba808bc4874',
                          'invocation_sha256': 'c54433f0a60f86217d320d7dac764cd83fa75765ba759523422d733eff1d2fdb',
                          'module': 'campagne_A22',
                          'qualname': 'checked_source_atoms'}}

def _qualified_source_callbacks(env,canonical_initial,atom_validator):
    module=sys.modules.get('campagne_A22')
    if module is None:return False
    for name,callback in (('canonical_initial_source',canonical_initial),('checked_source_atoms',atom_validator)):
        if callback is None or callback is not getattr(module,name,None):return False
        if getattr(callback,'__globals__',None) is not vars(module):return False
        expected=_SOURCE_CALLBACK_FINGERPRINTS.get(name)
        if expected is None or descriptor(callback)!=expected:return False
    adapters=env.get('adapters',{})
    return (adapters.get('canonical_source')==descriptor(canonical_initial)
            and adapters.get('source_atoms')==descriptor(atom_validator))


class _SourceSession:
    """One call, fixed context, immutable verified blobs; no persistent cache.

    Both comparison modes use the same snapshot reader. A final exact-byte
    scan rejects files changed during the call. Mutable decoded objects are
    never retained as evidence: every reference is decoded from its blob.
    """
    def __init__(self,env,base,canonical_initial,atom_validator,memo,stats,seen):
        self.env=env;self.env_sha=digest(env);self.base=Path(base).resolve()
        self.canonical_initial=canonical_initial;self.atom_validator=atom_validator
        self.memo=memo and _qualified_source_callbacks(env,canonical_initial,atom_validator)
        self.stats={} if stats is None else stats
        self.stats.update(memo_requested=memo,memo_enabled=self.memo,
                          callback_policy='qualified_idempotent_kernel' if self.memo else 'serial_traversal')
        self.blobs={};self.grey=set();self.black=set();self.authorities={}
        self.views={}
        self.paths=set() if seen is None else set(seen)
        self.context=(self.env_sha,str(self.base),id(canonical_initial),id(atom_validator))

    def count(self,key):self.stats[key]=self.stats.get(key,0)+1

    def read(self,path,expected):
        path=Path(path).resolve();key=str(path)
        if key not in self.blobs:
            if not path.is_file():raise BrokenChain('Source producer missing or changed')
            blob=path.read_bytes();actual=hashlib.sha256(blob).hexdigest()
            if actual!=expected:raise BrokenChain('Source producer missing or changed')
            self.blobs[key]=(actual,blob);self.count('snapshot_files_read')
        actual,blob=self.blobs[key]
        if actual!=expected:raise BrokenChain('One locator refers to incompatible producer bytes')
        self.count('references_decoded')
        return _stream_read(blob)

    def pin_resumes(self,data,seen=None):
        receipt=data.get('provenance',{});parents=receipt.get('parents',())
        if receipt.get('origin',{}).get('kind')!='resume' or len(parents)!=1:return
        seen=set() if seen is None else seen
        ref=parents[0];path=(self.base/ref['payload']).resolve();stamp=(str(path),ref['sha256'])
        if stamp in seen:raise BrokenChain('Cycle in resume ancestry')
        old=self.read(path,ref['sha256']);self.pin_resumes(old,seen|{stamp})

    def authority(self,owner,sha):
        if owner is None:return
        if owner in _OWNER_ARTIFACTS and _OWNER_ARTIFACTS[owner]!=sha:
            raise BrokenChain('Same producer namespace attached to distinct source artifacts')
        if owner in self.authorities and self.authorities[owner]!=sha:
            raise BrokenChain('Same producer namespace attached to distinct source artifacts')
        _OWNER_ARTIFACTS[owner]=sha;self.authorities[owner]=sha

    def callback(self,record,p):
        if self.atom_validator is not None:
            self.count('atom_callbacks');self.atom_validator(record,p)

    def walk(self,records):
        for record in records:self.edge(record)

    def retain_view(self, stamp, data, manifest):
        """Only immutable derived facts from a fully checked private blob.

        No decoded mutable producer is kept. The existing file, environment,
        atom registry and authority checks still delimit the reuse scope.
        """
        if data.get('status') == 'single_history_terminal_enclosed':
            selections = (('outputs', digest(data['terminal']), digest(data['outputs'])),)
        else:
            from canonical_bytes_A22 import freeze_many
            histories = tuple(data.get('finished', ()))
            hashes = tuple(value.sha256() for value in freeze_many(
                value for history in histories for value in (history, history.branch.emissions)))
            selections = tuple((index, hashes[2 * index], hashes[2 * index + 1])
                               for index in range(len(histories)))
        catalog = tuple((identity, json.dumps(definition, sort_keys=True, separators=(',', ':')))
                        for identity, definition in data.get('atom_catalog', {}).get('records', {}).items())
        self.views[stamp] = (data.get('layer'), data.get('lane'), selections,
                            digest(data['source_records']), catalog,
                            data['provenance'].get('producer_owner'))

    def checked_view_edge(self, record, receipt, stamp):
        layer, lane, selections, parents_sha, catalog, owner = self.views[stamp]
        selector = receipt['selector']
        selected = next((value for value in selections
                         if type(value[0]) is type(selector) and value[0] == selector), None)
        if selected is None:
            raise UnestablishedSourceChain('Unsupported source selector')
        check_terminal_binding(record, receipt, selected[1])
        if digest(record['outputs']) != selected[2]:
            raise CoverageMismatch('Derived output differs from producer')
        if any(key in record and record[key] != value for key, value in (('layer', layer), ('lane', lane))):
            raise CoverageMismatch('Derived source cell differs from producer')
        if ('parent_source_records' in receipt
                and digest(receipt['parent_source_records']) != parents_sha):
            raise BrokenChain('Source receipt parent records differ from producer')
        expected_catalog = dict(catalog)
        for identity, definition in receipt.get('atom_catalog', {}).get('records', {}).items():
            if expected_catalog.get(identity) != json.dumps(definition, sort_keys=True, separators=(',', ':')):
                raise BrokenChain('Derived source atom absent from its producer')
        for previous_owner, sha in tuple(self.authorities.items()):
            self.authority(previous_owner, sha)
        self.authority(owner, stamp[1])
        self.callback(record, receipt)
        self.count('memo_hits')
        self.count('immutable_view_hits')

    def edge(self,record):
        self.count('record_links')
        if digest(self.env)!=self.env_sha:raise ValidityMismatch('Validation context changed during source session')
        p=record.get('source_provenance')
        if not isinstance(p,dict): raise UnestablishedSourceChain('Source '+record.get('id','?')+' has no producer ancestry; no retrospective stamping')
        if p.get('schema')!=SCHEMA or p.get('environment_sha256')!=self.env_sha: raise ValidityMismatch('Source kernel/environment changed')
        if p.get('record_sha256')!=digest({k:v for k,v in record.items() if k!='source_provenance'}): raise CoverageMismatch('Source record changed')
        if p.get('kind')=='canonical_initial':
            if not self.canonical_initial(record): raise UnestablishedSourceChain('Source is not the declared canonical initial train')
            if p.get('atom_catalog',{}).get('records'):raise BrokenChain('Canonical initial clock cannot own uncertain atoms')
            self.callback(record,p)
        elif p.get('kind')=='derived_output':
            path=(self.base/p['payload']).resolve();stamp=(str(path),p['sha256'])
            if stamp in self.paths:raise BrokenChain('Cycle in source ancestry')
            if self.memo and stamp in self.views:
                self.checked_view_edge(record, p, stamp)
                return
            data=self.read(path,p['sha256']);receipt=data.get('provenance')
            if not receipt: raise MissingManifest('Source producer has no manifest')
            manifest=receipt['manifest']
            if (manifest.get('schema') != SCHEMA or manifest.get('environment_sha256') != self.env_sha
                    or manifest.get('fixture_only_no_physical_validation') is not (self.env.get('options',{}).get('fixture_only_no_physical_validation') is True)):
                raise ValidityMismatch('Source producer kernel/environment changed')
            key=(p['sha256'],digest(manifest),self.context)
            if key in self.grey:raise BrokenChain('Cycle in source ancestry')
            hit=self.memo and key in self.black
            if not hit:
                self.pin_resumes(data)
                verify(data,manifest,base=self.base);self.count('producer_validations')
                # Compact references no longer carry the whole terminal
                # history. Validate its atom catalogue in the producer itself,
                # after checking the byte binding and producer authority.
                if 'atom_catalog' in data:
                    import identite_temps_A22 as atoms
                    atoms.import_catalog(data['atom_catalog'])
                    atoms.validate_catalog(data, data['atom_catalog'])
                elif 'terminal_ref' in record:
                    raise BrokenChain('Referenced producer has no atom catalogue')
            else:
                self.count('memo_hits')
                # Authorities established by successful ancestors remain an
                # obligation of this session, also when a subtree is shared.
                for owner,sha in tuple(self.authorities.items()):self.authority(owner,sha)
            if data.get('status')=='not_certified': raise UnestablishedSourceChain('A refusal is not a certified source output')
            selector=p['selector']
            if selector=='outputs':
                output=data['outputs']
                check_terminal_binding(record, p, digest(data['terminal']))
            elif type(selector) is int and 0<=selector<len(data['finished']):
                history=data['finished'][selector];output=history.branch.emissions
                check_terminal_binding(record, p, digest(history))
            else: raise UnestablishedSourceChain('Unsupported source selector')
            if any(key in record and record[key]!=data[key] for key in ('layer','lane')):
                raise CoverageMismatch('Derived source cell differs from producer')
            if digest(output)!=digest(record['outputs']): raise CoverageMismatch('Derived output differs from producer')
            source_records=data.get('source_records')
            if source_records is None: raise BrokenChain('Source producer omits its bound input records')
            if 'parent_source_records' in p and digest(p['parent_source_records'])!=digest(source_records):
                raise BrokenChain('Source receipt parent records differ from producer')
            if make_manifest(self.env,source_records,layer=manifest['scope']['layer'],lane=manifest['scope']['lane'])!=manifest:
                raise BrokenChain('Producer source ancestry does not match its manifest')
            if not hit:self.grey.add(key)
            self.paths.add(stamp)
            try:
                if not hit:self.walk(source_records)
                catalog=p.get('atom_catalog',{})
                for identity,definition in catalog.get('records',{}).items():
                    if data.get('atom_catalog',{}).get('records',{}).get(identity)!=definition:raise BrokenChain('Derived source atom absent from its producer')
                self.authority(receipt.get('producer_owner'),p['sha256'])
                self.callback(record,p)
                # No failure or unfinished traversal can become a black node.
                if self.memo and not hit:
                    self.black.add(key);self.count('memo_successes')
                    self.retain_view(stamp, data, manifest)
            finally:
                self.paths.remove(stamp)
                if not hit:self.grey.remove(key)
        else: raise UnestablishedSourceChain('Unsupported source grouping/ancestry: '+str(p.get('kind')))

    def finish(self):
        if digest(self.env)!=self.env_sha:raise ValidityMismatch('Validation context changed during source session')
        for filename,(sha,blob) in self.blobs.items():
            path=Path(filename)
            if not path.is_file() or path.read_bytes()!=blob:
                raise BrokenChain('Producer snapshot bytes changed during source validation')
            self.count('snapshot_files_rechecked')


def check_sources(records, env, *, base, canonical_initial, seen=None, atom_validator=None, memo=True, stats=None, scope=None):
    """Validate each link; memoize only complete ancestor validations per call.

    memo=False is the differential-test traversal over the same immutable
    snapshot reader. Neither mode writes receipts or migrates old results.
    """
    if scope is not None:
        from source_reuse_A22 import SourceReuseScope
        if type(scope) is not SourceReuseScope:
            raise ProvenanceRefusal('Unsupported source reuse scope')
        return scope.check_bound(records,env,base=base,canonical_initial=canonical_initial,
            atom_validator=atom_validator,memo=memo,stats=stats,seen=seen)
    if type(memo) is not bool or stats is not None and type(stats) is not dict:
        raise ProvenanceRefusal('Unsupported source-validation session options')
    session=_SourceSession(env,base,canonical_initial,atom_validator,memo,stats,seen)
    session.walk(records);session.finish()
    return True

def cached_result(summary_path, manifest, *, base):
    """No verifier execution on a cache hit, but complete validity checks."""
    summary=json.loads(Path(summary_path).read_text()); path=Path(base)/summary['payload']
    if not path.is_file() or file_hash(path)!=summary['sha256']: raise CoverageMismatch('Cached payload integrity failed')
    data=_stream_read(path.read_bytes()); verify(data,manifest,base=path.parent)
    if summary.get('provenance_manifest_sha256')!=digest(manifest): raise ValidityMismatch('Summary lacks matching validity manifest')
    if summary.get('status')!=data.get('status'): raise CoverageMismatch('Summary status disagrees with payload')
    if tuple(summary.get('source_ids',()))!=tuple(data.get('source_ids',())): raise CoverageMismatch('Summary source selectors disagree')
    return summary


def _stream_read(value):
    from canonical_bytes_A22 import load_payload_stream
    return load_payload_stream(value)
