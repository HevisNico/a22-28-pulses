"""Exact canonical bytes stored as an immutable shared encoding tree.

Rebuild candidate. Contract: finite acyclic stable model data, side-effect-free
iteration and attributes. Sharing saves storage only: every occurrence is
emitted, without reference tokens or changed canonical hashes. Snapshots own
bytes/tuples, never references to mutable model objects. Per-call caches have
no recursive closure cycles and are explicitly cleared on success or failure.
The compatibility API canonical_bytes still materializes; production digest
and snapshot paths use freeze().blocks() instead.
"""
from pathlib import Path
from fractions import Fraction
from decimal import Decimal
from dataclasses import is_dataclass, fields
import hashlib
import json
import sys
import gc
import provenance_A22 as provenance
import importlib.util
import sysconfig
_NATIVE_DIR = Path(__file__).resolve().parents[1] / 'native'
_NATIVE_PATH = _NATIVE_DIR / ('_a22_native' + sysconfig.get_config_var('EXT_SUFFIX'))
_NATIVE_SPEC = importlib.util.spec_from_file_location('_a22_native', _NATIVE_PATH)
_native = importlib.util.module_from_spec(_NATIVE_SPEC)
_NATIVE_SPEC.loader.exec_module(_native)
_NATIVE_LOADED_SHA256 = hashlib.sha256(_NATIVE_PATH.read_bytes()).hexdigest()
_NATIVE_FUNCTIONS = tuple((name, getattr(_native, name)) for name in ('walk','node','metadata_key','atom_signature','validated_terms','check_atom_state'))

def _require_native_functions():
    if any(getattr(_native,name,None) is not fn for name,fn in _NATIVE_FUNCTIONS):
        raise provenance.ValidityMismatch('Loaded native encoder functions changed')




def _node(parts):
    parts = tuple(parts)
    if all(type(p) is bytes for p in parts) and sum(map(len, parts)) <= 4096:
        return b''.join(parts)
    return parts


class _Encoder:
    def __init__(self):
        self.memo = {}
        self.active = set()
        self.strings = {}
        self.key_strings = {}
        self.layouts = {}

    def clear(self):
        self.memo.clear()
        self.active.clear()
        self.strings.clear()
        self.key_strings.clear()
        self.layouts.clear()

    def quoted(self, text):
        if type(text) is not str:
            return json.dumps(text, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        if text not in self.strings:
            self.strings[text] = json.dumps(text, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return self.strings[text]

    def key_order(self, key):
        if type(key) is str:
            if key not in self.key_strings:
                self.key_strings[key] = json.dumps(key, sort_keys=True)
            return self.key_strings[key]
        return json.dumps(provenance.normal(key), sort_keys=True)

    def layout(self, item):
        cls = type(item)
        if cls not in self.layouts:
            label = cls.__module__ + '.' + cls.__qualname__
            if is_dataclass(item):
                value = (label, 'dataclass', tuple(f.name for f in fields(item)))
            else:
                slots = tuple(n for base in cls.__mro__ for n in getattr(base, '__slots__', ())
                              if n not in ('__dict__', '__weakref__'))
                value = (label, 'slots' if slots else 'dict', slots)
            self.layouts[cls] = value
        return self.layouts[cls]

    def sequence(self, prefix, items, suffix):
        parts = [prefix]
        for index, item in enumerate(items):
            if index:
                parts.append(b',')
            parts.append(self.walk(item))
        parts.append(suffix)
        return _node(parts)

    def walk(self, item):
        if item is None:
            return b'null'
        if isinstance(item, str):
            return self.quoted(item)
        if isinstance(item, (bool, int, float)):
            return json.dumps(item, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        identity = id(item)
        if identity in self.active:
            raise provenance.ProvenanceRefusal('Cycle in canonical provenance value')
        if identity in self.memo:
            return self.memo[identity][1]
        self.active.add(identity)
        try:
            if isinstance(item, Fraction):
                out = b'{"rational":[' + str(item.numerator).encode() + b',' + str(item.denominator).encode() + b']}'
            elif isinstance(item, Decimal):
                out = b'{"decimal":' + self.quoted(str(item)) + b'}'
            elif isinstance(item, bytes):
                out = b'{"bytes_sha256":' + self.quoted(hashlib.sha256(item).hexdigest()) + b'}'
            elif isinstance(item, Path):
                out = self.quoted(str(item))
            elif isinstance(item, dict):
                parts = [b'{"mapping":[']
                for index, (key, value) in enumerate(sorted(item.items(), key=lambda pair: self.key_order(pair[0]))):
                    if index:
                        parts.append(b',')
                    parts.extend((b'[', self.walk(key), b',', self.walk(value), b']'))
                parts.append(b']}')
                out = _node(parts)
            elif isinstance(item, (tuple, list)):
                out = self.sequence(b'{' + self.quoted(type(item).__name__) + b':[', item, b']}')
            elif isinstance(item, (set, frozenset)):
                out = self.sequence(b'{' + self.quoted(type(item).__name__) + b':[',
                                    sorted(item, key=self.key_order), b']}')
            else:
                label, kind, names = self.layout(item)
                if kind == 'dataclass':
                    body = {n: getattr(item, n) for n in names}
                    field = b',"fields":'
                elif kind == 'slots':
                    body = {n: getattr(item, n) for n in names if hasattr(item, n)}
                    field = b',"slots":'
                elif hasattr(item, '__dict__'):
                    body = vars(item)
                    field = b',"fields":'
                else:
                    raise provenance.ProvenanceRefusal('Unsupported object in provenance: ' + type(item).__qualname__)
                out = _node((b'{"class":', self.quoted(label), field, self.walk(body), b'}'))
            # Pin inputs until the call ends, preventing id reuse for field dicts.
            self.memo[identity] = (item, out)
            return out
        finally:
            self.active.remove(identity)


class FrozenCanonical(tuple):
    """Immutable encoding tree. Equality compares all bytes, not just a hash."""
    __slots__ = ()
    __hash__ = None

    def blocks(self, size=65536):
        if type(size) is not int or size <= 0:
            raise ValueError('Positive integer block size required')
        stack = [iter(self)]
        buffer = bytearray()
        while stack:
            try:
                part = next(stack[-1])
            except StopIteration:
                stack.pop()
                continue
            if type(part) is tuple:
                stack.append(iter(part))
                continue
            if type(part) is not bytes:
                raise TypeError('Canonical tree must contain only bytes and tuples')
            offset = 0
            while offset < len(part):
                take = min(size - len(buffer), len(part) - offset)
                buffer.extend(part[offset:offset + take])
                offset += take
                if len(buffer) == size:
                    yield bytes(buffer)
                    buffer.clear()
        if buffer:
            yield bytes(buffer)

    def sha256(self):
        result = hashlib.sha256()
        for block in self.blocks():
            result.update(block)
        return result.hexdigest()

    def __eq__(self, other):
        if not isinstance(other, FrozenCanonical):
            return NotImplemented
        a, b = self.blocks(), other.blocks()
        sentinel = object()
        try:
            while True:
                x, y = next(a, sentinel), next(b, sentinel)
                if x is sentinel or y is sentinel:
                    return x is sentinel and y is sentinel
                if x != y:
                    return False
        finally:
            a.close()
            b.close()

    def __ne__(self, other):
        result = self.__eq__(other)
        return NotImplemented if result is NotImplemented else not result


def legacy_freeze(value):
    encoder = _Encoder()
    try:
        return FrozenCanonical((encoder.walk(value),))
    finally:
        encoder.clear()


def canonical_bytes(value):
    return b''.join(legacy_freeze(value).blocks())


def legacy_digest(value):
    return legacy_freeze(value).sha256()


class FrozenMerkle(tuple):
    """(root index, exact immutable node table, Merkle SHA-256).

    Tuple equality compares the full node table, not only the root hash.
    Node interning preserves every ordered child edge and its multiplicity.
    """
    __slots__ = ()

    def sha256(self):
        return self[2]

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        pending = [(self[0], other[0])]
        seen = set()
        while pending:
            left, right = pending.pop()
            if (left, right) in seen:
                continue
            seen.add((left, right))
            a, b = self[1][left], other[1][right]
            if a[:2] != b[:2] or len(a[2]) != len(b[2]):
                return False
            pending.extend(zip(a[2], b[2]))
        return True

    def __ne__(self, other):
        result = self.__eq__(other)
        return NotImplemented if result is NotImplemented else not result

    __hash__ = None


class _MerkleBuilder:
    def __init__(self):
        _require_native_functions()
        self.memo = {}
        self.active = set()
        self.nodes = []
        self.hashes = []
        self.interned = {}
        self.json_encode = json.JSONEncoder(ensure_ascii=False, separators=(',', ':')).encode
        self.json_quote = json.encoder.encode_basestring
        self.node_budget = 0
        self.scalar_nodes = {}
        self.hash_headers = {}
        self.pair_cache = {}
        self.decimal_class = Decimal
        self.decimal_texts = {}
        self.term_bytes = {}
        self.interval_class = getattr(sys.modules.get('intervalles_decimaux'), 'I', None)
        self.time_class = getattr(sys.modules.get('dependances_A17'), 'Time', None)
        self.key_strings = {}
        self.layouts = {}
        self.strings = {}

    def _node_python(self, tag, payload=b'', children=()):
        children = tuple(children)
        key = (tag, payload, children)
        existing = self.interned.get(key)
        if existing is not None:
            return existing
        number = len(self.nodes)
        prefix = self.hash_headers.get(tag)
        if prefix is None:
            header = tag.encode('utf-8')
            prefix = hashlib.sha256(b'A22-MERKLE-2\x00' + len(header).to_bytes(4, 'big') + header)
            self.hash_headers[tag] = prefix
        h = prefix.copy()
        h.update(len(payload).to_bytes(8, 'big')); h.update(payload)
        h.update(len(children).to_bytes(8, 'big'))
        for child in children:
            h.update(self.hashes[child])
        self.nodes.append(key)
        self.hashes.append(h.digest())
        self.interned[key] = number
        return number

    def layout(self, item):
        cls = type(item)
        if cls not in self.layouts:
            label = cls.__module__ + '.' + cls.__qualname__
            if is_dataclass(item):
                value = (label, 'fields', tuple(f.name for f in fields(item)))
            else:
                slots = tuple(n for base in cls.__mro__ for n in getattr(base, '__slots__', ())
                              if n not in ('__dict__', '__weakref__'))
                value = (label, 'slots' if slots else 'fields', slots)
            self.layouts[cls] = value
        return self.layouts[cls]

    def order_key(self, value):
        if type(value) is str:
            if value not in self.key_strings:
                self.key_strings[value] = json.dumps(value, sort_keys=True)
            return self.key_strings[value]
        return json.dumps(provenance.normal(value), sort_keys=True)

    def interval_pair(self, value):
        if type(value) is self.interval_class and type(value.lo) is Decimal and type(value.hi) is Decimal:
            key = id(value)
            old = self.pair_cache.get(key)
            if old is not None:
                return old[1]
            pair = (str(value.lo), str(value.hi))
            if len(self.pair_cache) < 32768:
                self.pair_cache[key] = (value, pair)
            return pair
        return None

    def time_fields(self, value):
        if type(value) is not self.time_class or type(value.key) is not str or type(value.offset) is not Decimal:
            return None
        base = self.interval_pair(value.base)
        if base is None:
            return None
        terms = value.terms
        encoded = None
        if terms is not None:
            if type(terms) is not tuple:
                return None
            encoded = []
            for term in terms:
                if type(term) is not tuple or len(term) != 3 or type(term[0]) is not str or type(term[1]) is not int:
                    return None
                pair = self.interval_pair(term[2])
                if pair is None:
                    return None
                encoded.append((term[0], term[1], pair))
        return (value.key, base, str(value.offset), encoded)

    def _walk_python(self, item):
        cls = type(item)
        if item is None or isinstance(item, (str, bool, int, float)):
            # Full type and hexadecimal float guard keep bool/int and -0 distinct.
            cacheable = cls in (str, bool, int, float, type(None))
            key = (cls, item.hex() if cls is float else item) if cacheable else None
            if cacheable:
                existing = self.scalar_nodes.get(key)
                if existing is not None:
                    return existing
            raw = json.dumps(item, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            result = self.node('json', raw)
            if cacheable:
                self.scalar_nodes[key] = result
            return result
        identity = id(item)
        if identity in self.active:
            raise provenance.ProvenanceRefusal('Cycle in Merkle provenance value')
        if identity in self.memo:
            return self.memo[identity][1]
        self.active.add(identity)
        try:
            interval = self.interval_pair(item)
            time = type(item) is self.time_class
            if interval is not None:
                result = self.node('native-interval-v1', json.dumps(interval, ensure_ascii=False, separators=(',', ':')).encode())
            elif time:
                result = self.node('native-time-dag-v1', children=(self.walk(item.key), self.walk(item.base), self.walk(item.offset), self.walk(item.terms)))
            elif isinstance(item, Fraction):
                result = self.node('rational', children=(self.walk(item.numerator), self.walk(item.denominator)))
            elif isinstance(item, Decimal):
                result = self.node('decimal', str(item).encode())
            elif isinstance(item, bytes):
                result = self.node('bytes_sha256', hashlib.sha256(item).digest())
            elif isinstance(item, Path):
                result = self.walk(str(item))
            elif isinstance(item, dict):
                children = []
                for key, value in sorted(item.items(), key=lambda pair: self.order_key(pair[0])):
                    children.extend((self.walk(key), self.walk(value)))
                result = self.node('mapping', children=children)
            elif isinstance(item, (tuple, list)):
                result = self.node('sequence', type(item).__name__.encode(), (self.walk(v) for v in item))
            elif isinstance(item, (set, frozenset)):
                result = self.node('sequence', type(item).__name__.encode(),
                                   (self.walk(v) for v in sorted(item, key=self.order_key)))
            else:
                label, kind, names = self.layout(item)
                if is_dataclass(item):
                    body = {n: getattr(item, n) for n in names}
                elif kind == 'slots':
                    body = {n: getattr(item, n) for n in names if hasattr(item, n)}
                elif hasattr(item, '__dict__'):
                    body = vars(item)
                else:
                    raise provenance.ProvenanceRefusal('Unsupported Merkle object: ' + type(item).__qualname__)
                result = self.node('object-' + kind, label.encode(), (self.walk(body),))
            self.memo[identity] = (item, result)
            return result
        finally:
            self.active.remove(identity)

    def node(self, tag, payload=b'', children=()):
        return _native.node(self, tag, payload, children)

    def walk(self, item):
        return _native.walk(self, item)

    def clear(self):
        self.memo.clear(); self.active.clear(); self.nodes.clear(); self.hashes.clear()
        self.interned.clear(); self.layouts.clear(); self.strings.clear(); self.key_strings.clear()
        self.scalar_nodes.clear(); self.hash_headers.clear(); self.pair_cache.clear(); self.term_bytes.clear()
        self.decimal_texts.clear()


def freeze(value):
    enabled=gc.isenabled()
    if enabled:gc.disable()
    builder = None
    try:
        builder = _MerkleBuilder()
        root = builder.walk(value)
        return FrozenMerkle((root, tuple(builder.nodes), builder.hashes[root].hex()))
    finally:
        if builder is not None:builder.clear()
        if enabled:gc.enable()


def digest(value):
    return freeze(value).sha256()


def freeze_many(values):
    """One synchronous immutable capture; no live-object cache survives it.

    Every requested root retains its own full graph and its original digest.
    Shared encoding work does not equate separate event or history records.
    """
    enabled=gc.isenabled()
    if enabled:gc.disable()
    builder = None
    try:
        builder = _MerkleBuilder()
        roots = tuple(builder.walk(value) for value in values)
        nodes = tuple(builder.nodes)
        return tuple(FrozenMerkle((root, nodes, builder.hashes[root].hex())) for root in roots)
    finally:
        if builder is not None:builder.clear()
        if enabled:gc.enable()


# The following classes implement the same Merkle grammar as _MerkleBuilder.
# They are included in the effective kernel inventory, not injected at runtime.
from array import array
from collections import OrderedDict
from dataclasses import dataclass
import struct
import tempfile

_SPOOL_HEADER = struct.Struct('>IQQ')

class _SnapshotStore:
    def __init__(self):
        self.stream = tempfile.TemporaryFile('w+b')
        self.offsets = array('Q')
        self.sealed = False
        self.closed = False
        self.fingerprint = None
        self.size = 0
        self.written_hash = hashlib.sha256()

    def _write(self, value):
        if self.stream.write(value) != len(value):
            raise OSError('Short snapshot write')
        self.written_hash.update(value)

    def append(self, tag, payload, children):
        if self.sealed or self.closed:
            raise provenance.ProvenanceRefusal('Snapshot store cannot be modified')
        raw = tag.encode('utf-8')
        self.stream.seek(0, 2)
        self.offsets.append(self.stream.tell())
        self._write(_SPOOL_HEADER.pack(len(raw), len(payload), len(children)))
        self._write(raw)
        self._write(payload)
        self._write(array('Q', children).tobytes())
        self.size = self.stream.tell()
        return len(self.offsets)-1

    def _read_exact(self, size):
        value = self.stream.read(size)
        if len(value) != size:
            raise provenance.ProvenanceRefusal('Truncated snapshot store')
        return value

    def read(self, index):
        if self.closed or type(index) is not int or not 0 <= index < len(self.offsets):
            raise provenance.ProvenanceRefusal('Invalid snapshot node')
        offset = self.offsets[index]
        self.stream.seek(offset)
        ntag, npayload, nchildren = _SPOOL_HEADER.unpack(self._read_exact(_SPOOL_HEADER.size))
        if offset+_SPOOL_HEADER.size+ntag+npayload+8*nchildren > self.size:
            raise provenance.ProvenanceRefusal('Invalid snapshot record size')
        tag = self._read_exact(ntag).decode('utf-8')
        payload = self._read_exact(npayload)
        children = array('Q')
        children.frombytes(self._read_exact(8*nchildren))
        if any(child >= index for child in children):
            raise provenance.ProvenanceRefusal('Invalid or cyclic snapshot edges')
        return tag, payload, children

    def _fingerprint(self):
        self.stream.seek(0)
        h = hashlib.sha256()
        size = 0
        while block := self.stream.read(65536):
            h.update(block)
            size += len(block)
        return size, h.digest(), hashlib.sha256(self.offsets.tobytes()).digest()

    def seal(self):
        if self.closed or self.sealed:
            raise provenance.ProvenanceRefusal('Snapshot already closed or sealed')
        self.stream.flush()
        self.fingerprint = self._fingerprint()
        if self.fingerprint[0] != self.size or self.fingerprint[1] != self.written_hash.digest():
            raise provenance.ProvenanceRefusal('Incomplete snapshot store')
        self.sealed = True

    def check_integrity(self):
        if self.closed or not self.sealed or self.fingerprint != self._fingerprint():
            raise provenance.ProvenanceRefusal('Snapshot store changed or is not sealed')

    def close(self):
        if not self.closed:
            self.stream.close()
            self.closed = True

    def __del__(self):
        if hasattr(self, 'stream'):
            self.close()

class FrozenSpool(tuple):
    __slots__ = ()

    def __new__(cls, root, store, digest):
        return tuple.__new__(cls, (root, store, digest))

    @property
    def root(self):return self[0]

    @property
    def store(self):return self[1]

    @property
    def digest(self):return self[2]

    def sha256(self):
        return self.digest

    def __eq__(self, other):
        if isinstance(other, FrozenSpool):
            other_root = other.root
            width = len(other.store.offsets)
            read_other = other.store.read
            stores = (self.store,) if self.store is other.store else (self.store, other.store)
        elif isinstance(other, FrozenMerkle):
            other_root = other[0]
            width = len(other[1])
            read_other = other[1].__getitem__
            stores = (self.store,)
        else:
            return NotImplemented
        for store in stores:
            store.check_integrity()
        try:
            seen = set()
            stack = [iter(((self.root, other_root),))]
            while stack:
                try:
                    left, right = next(stack[-1])
                except StopIteration:
                    stack.pop()
                    continue
                key = left*width+right
                if key in seen:
                    continue
                seen.add(key)
                a = self.store.read(left)
                b = read_other(right)
                if a[:2] != b[:2] or len(a[2]) != len(b[2]):
                    return False
                stack.append(iter(zip(a[2], b[2])))
            return True
        finally:
            for store in stores:
                store.check_integrity()

    def __ne__(self, other):
        value = self.__eq__(other)
        return NotImplemented if value is NotImplemented else not value

    __hash__ = None

class _SpoolMerkleBuilder(_MerkleBuilder):
    def __init__(self):
        super().__init__()
        self.store = _SnapshotStore()
        self.candidates = {}
        self.native_intervals = OrderedDict()

    def node(self, tag, payload=b'', children=()):
        children = tuple(children)
        raw = tag.encode('utf-8')
        h = hashlib.sha256(b'A22-MERKLE-2\x00')
        h.update(len(raw).to_bytes(4, 'big'))
        h.update(raw)
        h.update(len(payload).to_bytes(8, 'big'))
        h.update(payload)
        h.update(len(children).to_bytes(8, 'big'))
        for child in children:
            h.update(self.hashes[child])
        digest = h.digest()
        candidates = self.candidates.get(digest)
        if candidates is not None:
            for number in ((candidates,) if type(candidates) is int else candidates):
                old = self.store.read(number)
                if old[0] == tag and old[1] == payload and tuple(old[2]) == children:
                    return number
        number = self.store.append(tag, payload, children)
        self.hashes.append(digest)
        if candidates is None:
            self.candidates[digest] = number
        elif type(candidates) is int:
            self.candidates[digest] = (candidates, number)
        else:
            self.candidates[digest] = candidates+(number,)
        return number

    def walk(self, item):
        if type(item) is self.interval_class and type(item.lo) is Decimal and type(item.hi) is Decimal:
            identity = id(item)
            previous = self.native_intervals.get(identity)
            if previous is not None:
                self.native_intervals.move_to_end(identity)
                return previous[1]
            raw = json.dumps((str(item.lo), str(item.hi)), ensure_ascii=False, separators=(',', ':')).encode()
            result = self.node('native-interval-v1', raw)
            self.native_intervals[identity] = (item, result)
            if len(self.native_intervals) > 32768:
                self.native_intervals.popitem(last=False)
            return result
        return super().walk(item)

    def clear(self):
        super().clear()
        self.candidates.clear()
        self.native_intervals.clear()

class _SerializedTee:
    def __init__(self, compressed, raw):
        self.compressed = compressed
        self.raw = raw

    def write(self, value):
        if self.raw.write(value) != len(value) or self.compressed.write(value) != len(value):
            raise OSError('Short serialized payload write')
        return len(value)

def write_payload_stream(path, data, *, exclusive=False):
    """Atomic gzip output; exact raw byte round-trip checked in 64-KiB blocks."""
    import gzip, pickle, os, uuid
    path = Path(path)
    if exclusive and path.exists():
        raise FileExistsError(path)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.partial')
    try:
        with tempfile.TemporaryFile('w+b') as raw:
            with temporary.open('xb') as output:
                with gzip.GzipFile(filename='', fileobj=output, mode='wb', compresslevel=5, mtime=0) as zipped:
                    pickle.dump(data, _SerializedTee(zipped, raw), protocol=5)
                output.flush()
                os.fsync(output.fileno())
            raw.seek(0)
            with gzip.open(temporary, 'rb') as reread:
                while True:
                    a, b = raw.read(65536), reread.read(65536)
                    if a != b:
                        raise provenance.ProvenanceRefusal('Serialized byte round-trip differs')
                    if not a:
                        break
        if exclusive:
            # Atomic no-overwrite publication. The temporary name is then
            # removed; no shared campaign file remains after publication.
            os.link(temporary, path)
            temporary.unlink()
        else:
            os.replace(temporary, path)
        h = hashlib.sha256()
        with path.open('rb') as stream:
            while block := stream.read(65536):
                h.update(block)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return h.hexdigest()
    finally:
        temporary.unlink(missing_ok=True)

def _load_payload_stream(path_or_bytes):
    """Preserve the pickle object graph without a full decompressed buffer."""
    import gzip, pickle, io
    if type(path_or_bytes) is bytes:
        with gzip.GzipFile(fileobj=io.BytesIO(path_or_bytes), mode='rb') as stream:
            value = pickle.load(stream)
            # Consume the remainder to verify gzip CRC/length and reject
            # hidden trailing serialized content, as required by this format.
            if stream.read(1):
                raise provenance.ProvenanceRefusal('Trailing serialized payload data')
            return value
    with gzip.open(path_or_bytes, 'rb') as stream:
        value = pickle.load(stream)
        if stream.read(1):
            raise provenance.ProvenanceRefusal('Trailing serialized payload data')
        return value


def load_payload_stream(path_or_bytes):
    """Batch graph decoding; restore cyclic-GC scheduling on every exit."""
    enabled=gc.isenabled()
    if enabled:gc.disable()
    try:
        return _load_payload_stream(path_or_bytes)
    finally:
        if enabled:gc.enable()
