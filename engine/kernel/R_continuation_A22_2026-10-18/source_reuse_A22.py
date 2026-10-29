"""Explicit, fail-closed reuse scope. Integrated candidate, not a frozen kernel.

It uses the baseline verifier's exact per-edge checks. Only its successful
ancestor table and immutable compressed snapshots outlive a check_sources
call. Each boundary rechecks every pinned file, the effective environment,
qualified callback identities, implementation, and atom-owner obligations.
Unknown callbacks and explicit seen sets retain fresh serial/session behavior.
No source records, decoded producer objects, selectors or histories are merged.
"""
from pathlib import Path
from types import FunctionType
import json, os, threading, gzip, pickle, hashlib
import provenance_A22 as p

class SourceReuseScope:
    def __init__(self, env, *, base, canonical_initial, atom_validator):
        self.env=env
        self.expected=json.loads(json.dumps(env))
        self.base=Path(base).resolve()
        self.canonical=canonical_initial
        self.atoms=atom_validator
        self.qualified=p._qualified_source_callbacks(env,canonical_initial,atom_validator)
        self.owner=(os.getpid(),threading.get_ident())
        self.session=None
        self.closed=False
        self.failed=False
        self.reports=[]
        self.atom_definitions={}
        self.atom_signatures={}
        self.absent_atoms=set()
        self.catalogued_blobs=set()
        self.bound_files={}
        self.implementation=self._implementation_signature()
        self._assert_context()

    def _implementation_signature(self):
        return (p.file_hash(Path(__file__)),tuple((name,p.descriptor(value))
            for name,value in sorted(vars(type(self)).items()) if isinstance(value,FunctionType)))

    def _assert_context(self, supplied_env=None):
        if self.closed or self.failed:raise p.BrokenChain('Reuse scope is closed or failed')
        if self.owner!=(os.getpid(),threading.get_ident()):
            raise p.ValidityMismatch('Reuse scope cannot cross a process/thread boundary')
        if self._implementation_signature()!=self.implementation:
            raise p.ValidityMismatch('Reuse implementation changed inside its scope')
        if self.env!=self.expected or supplied_env is not None and supplied_env!=self.expected:
            raise p.ValidityMismatch('Reuse environment changed')
        # Pin loaded code, adapters, arithmetic, options and source bytes too;
        # a cached environment dictionary is not evidence of unchanged code.
        import campagne_A22 as c
        current=c.validity_environment(self.expected['settings'],
            budget=self.expected['options']['budget'])
        if self.expected['options'].get('fixture_only_no_physical_validation') is True:
            current['options']['fixture_only_no_physical_validation']=True
        if current!=self.expected:raise p.ValidityMismatch('Effective kernel/context changed')
        if self.qualified and not p._qualified_source_callbacks(
                self.expected,self.canonical,self.atoms):
            raise p.ValidityMismatch('Qualified source callbacks changed')
        if self.qualified:self._check_atom_state()
        self._check_bound_files()

    def _check_bound_files(self):
        for filename,blob in self.bound_files.items():
            path=Path(filename)
            if not path.is_file() or path.read_bytes()!=blob:
                raise p.BrokenChain('Scoped input artifact bytes changed')

    def read_artifact(self, path, expected=None):
        """Pin the exact table, summary or cache-proof bytes actually decoded."""
        try:
            if self.closed or self.failed:
                raise p.BrokenChain('Reuse scope is closed or failed')
            if self.owner!=(os.getpid(),threading.get_ident()):
                raise p.ValidityMismatch('Reuse scope cannot cross a process/thread boundary')
            path=Path(path).resolve()
            if not path.is_relative_to(self.base):
                raise p.BrokenChain('Scoped artifact escapes its campaign directory')
            blob=path.read_bytes()
            if expected is not None and hashlib.sha256(blob).hexdigest()!=expected:
                raise p.CoverageMismatch('Scoped input artifact integrity changed')
            key=str(path)
            if key in self.bound_files and self.bound_files[key]!=blob:
                raise p.BrokenChain('Scoped input artifact bytes changed')
            self.bound_files[key]=blob
            return blob
        except BaseException:
            self._discard()
            raise

    def _catalog_state(self, records):
        """Copy the exact definitions and absence tests consulted by callbacks."""
        import identite_temps_A22 as atoms
        definitions={};absent=set()
        for record in records:
            catalog=record.get('source_provenance',{}).get('atom_catalog')
            checked=atoms._checked_catalog(catalog)
            for identity,definition in checked.items():
                encoded=json.dumps(definition,sort_keys=True,separators=(',',':'))
                if identity in definitions and definitions[identity]!=encoded:
                    raise atoms.AtomIdentityRefusal('Conflicting scoped atom definitions')
                definitions[identity]=encoded
            for time in atoms._times(record):
                for identity,coefficient,bounds in time.expression():
                    if identity not in checked:absent.add(identity)
        return definitions,absent

    def _check_atom_state(self):
        import identite_temps_A22 as atoms
        from canonical_bytes_A22 import _native
        try:
            _native.check_atom_state(atoms._RECORDS,self.atom_definitions,
                                     self.atom_signatures,self.absent_atoms,json.loads)
        except ValueError as error:
            raise atoms.AtomIdentityRefusal(str(error)) from error

    def _retain_atom_dependencies(self, root_state, session):
        # The authoritative definitions come from checked records/immutable
        # producer bytes, never by adopting the current registry as truth.
        # A descendant export alone need not contain older ancestor atoms.
        import identite_temps_A22 as atoms
        states=[root_state];new_blobs=[]
        for filename,(digest,blob) in session.blobs.items():
            if filename in self.catalogued_blobs:continue
            data=_stream_read(blob)
            states.append(self._catalog_state(data.get('source_records',())))
            # The selected source rows may now contain state references only.
            # Pin every producer definition, including state-only ancestors,
            # and every absence condition used by any of its Time objects.
            if 'atom_catalog' in data:
                checked = atoms._checked_catalog(data['atom_catalog'])
                definitions = {identity:json.dumps(definition,sort_keys=True,separators=(',',':'))
                               for identity,definition in checked.items()}
                absent = {identity for time in atoms._times(data)
                          for identity,coefficient,bounds in time.expression() if identity not in checked}
                states.append((definitions, absent))
            new_blobs.append(filename)
        for definitions,absent in states:
            for identity,definition in definitions.items():
                if identity in self.atom_definitions and self.atom_definitions[identity]!=definition:
                    raise atoms.AtomIdentityRefusal('Conflicting retained atom definition')
                self.atom_definitions[identity]=definition
            self.absent_atoms.update(absent)
        self._check_atom_state()
        self.catalogued_blobs.update(new_blobs)

    def _discard(self):
        self.failed=True
        if self.session is not None:
            self.session.black.clear(); self.session.grey.clear()
            self.session.blobs.clear(); self.session.authorities.clear()
            self.session.views.clear()
        self.session=None
        self.atom_signatures.clear()
        self.atom_definitions.clear();self.absent_atoms.clear();self.catalogued_blobs.clear()
        self.bound_files.clear()

    def check_bound(self, records, env, *, base, canonical_initial,
                    atom_validator, memo=True, seen=None, stats=None):
        """Bind the caller's full validation request to this explicit scope."""
        try:
            if canonical_initial is not self.canonical or atom_validator is not self.atoms:
                raise p.ValidityMismatch('Reuse source callbacks do not match this request')
            return self.check(records,env=env,base=base,memo=memo,seen=seen,stats=stats)
        except BaseException:
            self._discard()
            raise

    def check(self, records, *, env=None, base=None, memo=True, seen=None, stats=None):
        if type(memo) is not bool or stats is not None and type(stats) is not dict:
            self._discard();raise p.ProvenanceRefusal('Unsupported reuse-session options')
        stats={} if stats is None else stats
        try:
            self._assert_context(env)
            if base is not None and Path(base).resolve()!=self.base:
                raise p.ValidityMismatch('Reuse artifact base changed')
            reusable=self.qualified and memo and seen is None
            root_state=None
            if reusable:
                records=tuple(records)
                root_state=self._catalog_state(records)
                if self.session is None:
                    self.session=p._SourceSession(self.expected,self.base,self.canonical,
                        self.atoms,True,stats,None)
                session=self.session
                session.stats=stats
                stats.update(memo_requested=True,memo_enabled=True,
                             callback_policy='qualified_idempotent_kernel',
                             scope_previous_successes=len(session.black))
                # Check the retained bytes BEFORE using a prior success.
                session.finish()
                for owner,sha in tuple(session.authorities.items()):session.authority(owner,sha)
            else:
                session=p._SourceSession(self.expected,self.base,self.canonical,
                    self.atoms,memo,stats,seen)
                stats['scope_previous_successes']=0
            session.walk(records)
            session.finish()
            if reusable:self._retain_atom_dependencies(root_state,session)
            self._assert_context(env)
            stats['scope_reuse_enabled']=reusable
            stats['scope_snapshot_bytes']=sum(len(blob) for sha,blob in session.blobs.values())
            stats['scope_pinned_atom_definitions']=len(self.atom_definitions)
            stats['scope_pinned_absence_conditions']=len(self.absent_atoms)
            self.reports.append(dict(stats))
            return True
        except BaseException:
            self._discard()
            raise

    def checkpoint(self):
        """Complete every closing obligation without discarding proven facts.

        Only the owning synchronous process may continue the scope. The next
        check repeats the same byte/context/atom guards before any reuse.
        """
        try:
            self._assert_context()
            if self.session is not None:
                self.session.finish()
                for owner,sha in tuple(self.session.authorities.items()):self.session.authority(owner,sha)
            self._assert_context()
        except BaseException:
            self._discard();raise

    def close(self):
        if self.closed:return
        try:
            if not self.failed:self.checkpoint()
        finally:
            self.closed=True
            self.session=None

    def __enter__(self):return self

    def __exit__(self, kind, value, traceback):
        if kind is not None:self._discard()
        self.close()
        return False


def _stream_read(value):
    from canonical_bytes_A22 import load_payload_stream
    return load_payload_stream(value)


def _atom_definition_signature(record):
    from canonical_bytes_A22 import _native
    import identite_temps_A22 as atoms
    try:
        return _native.atom_signature(record)
    except ValueError as error:
        raise atoms.AtomIdentityRefusal(str(error)) from error
