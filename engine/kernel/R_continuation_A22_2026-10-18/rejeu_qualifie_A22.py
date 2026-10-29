"""Fresh producer-qualified replay; never upgrades an existing source table.

No source grouping is performed.  Every producer history remains a separate
record, including histories with the same output calendar.  Data live only
in a new A22_ARTIFACT_DIR; the effective kernel is frozen before source0.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import fields, is_dataclass
import argparse
import gzip
import hashlib
import itertools
import json
import os
import pickle
import uuid

import campagne_A22 as c
import provenance_A22 as provenance
import identite_temps_A22 as atoms
import reprise_groupe_A22 as hook
import intervalles_decimaux as iv
from intervalles_decimaux import I
from source_reuse_A22 import SourceReuseScope

SCHEMA = 'A22-fresh-campaign-v1'
INDEX = 'campagne_qualifiee.json'


def fail(message):
    raise provenance.ProvenanceRefusal(message)


def exclusive_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def exclusive_payload(path, value):
    from canonical_bytes_A22 import write_payload_stream
    return write_payload_stream(path,value,exclusive=True)


def configure(root, *, fixture=False):
    root = Path(root).resolve()
    os.environ['A22_ARTIFACT_DIR'] = str(root)
    os.environ['A22_RETURN_GROUPS'] = '1'
    os.environ['A22_PREFIX_MODE'] = 'regenerative'
    os.environ['A22_RUN_TAG'] = 'qualifie'
    iv.configure(160)
    settings = c.b.settings('1e-5', '1e-4')
    c.b.PROFILE = None
    c.h.step = hook.step
    env = c.validity_environment(settings)
    if fixture:
        # A synthetic test's receipts cannot be accepted by a physical worker,
        # whose environment never contains this extra option.
        env['options']['fixture_only_no_physical_validation'] = True
    return env


def initial_records(env):
    rows = []
    for lane in range(12):
        clock = c.b.dep.Time('canonical-initial-clock', I(0))
        train = tuple(clock.plus(8*k) for k in range(128)) if lane == 0 else ()
        record = dict(id=f'L0U{lane}', layer=0, lane=lane, outputs=train,
                      context={}, context_options=({},),
                      proof=dict(kind='canonical_initial', source_lane=0,
                                 pulse_count=128, dates='8*k, k=0..127',
                                 no_other_exterior_source=True))
        provenance.source_receipt(record, env, kind='canonical_initial',
                                  atom_catalog=atoms.atom_catalog(record))
        rows.append(record)
    provenance.check_sources(rows, env, base=c.output_root(),
                             canonical_initial=c.canonical_initial_source,
                             atom_validator=c.checked_source_atoms)
    return rows


def create_campaign(root, *, fixture=False):
    """Exclusive new directory; fixture=True is for the unit tests only."""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    env = configure(root, fixture=fixture)
    sources = initial_records(env)
    tables = []
    for lane, record in enumerate(sources):
        path = root/f'sources_0_{lane}.pkl.gz'
        tables.append(dict(layer=0, lane=lane, payload=path.name,
                           sha256=exclusive_payload(path, (record,)), records=1))
    index = dict(schema=SCHEMA, campaign_id=uuid.uuid4().hex,
                 status='canonical_initial_sources_created',
                 fixture_only_no_physical_validation=fixture,
                 environment=env, environment_sha256=provenance.digest(env),
                 source_tables=tables,
                 claim='Source preparation only; no physical cell trajectory has been computed',
                 protocol=dict(delta='1e-5', epsilon='1e-4', precision=160,
                               layers=18, lanes=12, source_lane=0, pulses=128,
                               source_dates='8*k, k=0..127', horizon='1116',
                               future_source_minimum_gap='20', grouping=False))
    exclusive_json(root/INDEX, index)
    return index


def open_campaign(root, *, allow_fixture=False):
    root = Path(root).resolve()
    index = json.loads((root/INDEX).read_text())
    if index.get('schema') != SCHEMA:
        fail('Not a fresh qualified campaign directory')
    fixture = index.get('fixture_only_no_physical_validation') is True
    if fixture and not allow_fixture:
        fail('Synthetic fixture directory cannot be used for a physical replay')
    env = configure(root, fixture=fixture)
    if (provenance.digest(index.get('environment')) != index.get('environment_sha256')
            or env != index.get('environment')):
        raise provenance.ValidityMismatch('Effective kernel changed after campaign creation; create a new campaign')
    return root, index, env


def local_file(root, name):
    path = (root/name).resolve()
    if not path.is_relative_to(root):
        fail('Artifact reference escapes the new campaign directory')
    return path


def source_scope(root, env):
    """One synchronous consumer operation; never shared with worker processes."""
    scope = SourceReuseScope(env, base=root,
                             canonical_initial=c.canonical_initial_source,
                             atom_validator=c.checked_source_atoms)
    try:
        index_path = Path(root)/INDEX
        if index_path.exists():
            index = json.loads(scope.read_artifact(index_path))
            if (index.get('environment') != env
                    or index.get('environment_sha256') != provenance.digest(env)):
                raise provenance.ValidityMismatch('Scoped campaign index environment changed')
        return scope
    except BaseException:
        scope._discard()
        scope.close()
        raise


def source_table(root, index, env, layer, lane, *, scope=None):
    if scope is None:
        with source_scope(root, env) as active:
            return source_table(root, index, env, layer, lane, scope=active)
    try:
        records = read_source_table(root, index, env, layer, lane, scope=scope)
        provenance.check_sources(records, env, base=root,
                                 canonical_initial=c.canonical_initial_source,
                                 atom_validator=c.checked_source_atoms, scope=scope)
        return records
    except BaseException:
        scope._discard()
        raise


def read_source_table(root, index, env, layer, lane, *, scope):
    """Read and bind a table; ancestry MUST be checked before using its rows.

    Batch callers combine all rows in one check_sources call. This function
    alone grants no source authority and never publishes a receipt.
    """
    try:
        if layer == 0:
            refs = index['source_tables']
        else:
            report = json.loads(scope.read_artifact(root/f'couche_qualifiee_{layer}.json'))
            if report.get('environment_sha256') != provenance.digest(env):
                raise provenance.ValidityMismatch('Source table layer environment changed')
            if report.get('status') != 'all_declared_cell_histories_collected':
                fail('Previous layer is not completely collected')
            refs = report['source_tables']
        matches = [r for r in refs if r['layer'] == layer and r['lane'] == lane]
        if len(matches) != 1:
            fail('Missing or duplicate qualified source table')
        ref = matches[0]
        path = local_file(root, ref['payload'])
        records = tuple(_stream_read(scope.read_artifact(path,ref['sha256'])))
        if not records or len(records) != ref['records']:
            fail('Empty or incomplete source table')
        if any(r.get('layer') != layer or r.get('lane') != lane for r in records):
            fail('Source table cell identity changed')
        if len({r['id'] for r in records}) != len(records):
            fail('Duplicate source scenario identity')
        return records
    except BaseException:
        scope._discard()
        raise


def job_id(selected):
    return hashlib.sha256(json.dumps([r['id'] for r in selected]).encode()).hexdigest()[:16]


class CacheContentMismatch(provenance.ProvenanceRefusal):
    def __init__(self, comparison):
        self.comparison=comparison
        super().__init__('Fresh calculation/cache contents differ: '+', '.join(
            name for name,part in comparison.items() if not part['equal']))


class _TemporalIndex:
    """Per-snapshot index: skip shared subgraphs with no Time occurrences.

    An index shares traversal work, never output occurrences or histories.
    Every emitted path follows the baseline sorting and field order.
    """
    def __init__(self):
        self.memo = {}
        self.active = set()

    def build(self, item):
        if isinstance(item, c.b.dep.Time):
            return ('time', item)
        if not isinstance(item, (dict, tuple, list, set, frozenset)) and not is_dataclass(item):
            return None
        identity = id(item)
        if identity in self.active:
            raise provenance.ProvenanceRefusal('Cycle in temporal-expression data')
        if identity in self.memo:
            return self.memo[identity][1]
        self.active.add(identity)
        try:
            children = []
            if isinstance(item, dict):
                ordered = sorted(item.items(), key=lambda pair: provenance.digest(pair[0]))
                for index, (key, entry) in enumerate(ordered):
                    children.extend(((f'/key:{index}', key), (f'/value:{index}', entry)))
            elif isinstance(item, (tuple, list)):
                children = [(f'/{index}', entry) for index, entry in enumerate(item)]
            elif isinstance(item, (set, frozenset)):
                children = [(f'/set:{index}', entry) for index, entry in enumerate(sorted(item, key=provenance.digest))]
            elif is_dataclass(item):
                children = [('/' + field.name, getattr(item, field.name)) for field in fields(item)]
            branches = []
            for prefix, child in children:
                node = self.build(child)
                if node is not None:
                    branches.append((prefix, node))
            node = ('branch', tuple(branches)) if branches else None
            self.memo[identity] = (item, node)
            return node
        finally:
            self.active.remove(identity)


def temporal_expressions(value):
    index = _TemporalIndex()
    try:
        root = index.build(value)
        if root is None:
            return ()
        found = []
        stack = [(root, 'payload')]
        while stack:
            node, path = stack.pop()
            if node[0] == 'time':
                item = node[1]
                found.append((path, dict(time=item, expression=item.expression(), box=item.box())))
            else:
                stack.extend((child, path + prefix) for prefix, child in reversed(node[1]))
        return tuple(found)
    finally:
        index.memo.clear()
        index.active.clear()


def _payload_snapshot_memory(data):
    """Independent immutable canonical byte trees, captured before cache access."""
    state_keys=('state','terminal','frontier','finished','pending')
    emissions={key:tuple(hh.branch.emissions for hh in data[key])
               for key in ('frontier','finished') if key in data}
    if 'outputs' in data:emissions['outputs']=data['outputs']
    provenance_keys=('provenance','source_records','source_ids','source_proofs',
                     'context','context_options','layer','lane')
    sections=dict(
        states_and_queue={key:data[key] for key in state_keys if key in data},
        emissions_by_history=emissions,
        temporal_dependencies=dict(expressions=temporal_expressions(data),
                                   atom_catalog=data.get('atom_catalog')),
        provenance_and_sources={key:data[key] for key in provenance_keys if key in data},
        complete_payload=data)
    from canonical_bytes_A22 import freeze_many
    snapshot={}
    for name,canonical in zip(sections, freeze_many(sections.values())):
        snapshot[name]=dict(canonical=canonical, sha256=canonical.sha256())
    return snapshot


def _payload_snapshot_encoded(data, *, spooled):
    from collections import OrderedDict
    from canonical_bytes_A22 import _SpoolMerkleBuilder, FrozenSpool, _MerkleBuilder, FrozenMerkle
    builder=_SpoolMerkleBuilder() if spooled else _MerkleBuilder()
    completed=False
    index=_TemporalIndex()
    temporal_cache={}
    term_cache=OrderedDict()
    try:
        state_keys=('state','terminal','frontier','finished','pending')
        emissions={key:tuple(hh.branch.emissions for hh in data[key])
                   for key in ('frontier','finished') if key in data}
        if 'outputs' in data:emissions['outputs']=data['outputs']
        provenance_keys=('provenance','source_records','source_ids','source_proofs',
                         'context','context_options','layer','lane')
        roots={}
        roots['states_and_queue']=builder.walk({key:data[key] for key in state_keys if key in data})
        roots['emissions_by_history']=builder.walk(emissions)
        temporal_root=index.build(data)
        def occurrences():
            stack=[] if temporal_root is None else [(temporal_root,'payload')]
            while stack:
                node,path=stack.pop()
                if node[0]=='time':
                    item=node[1];identity=id(item)
                    if identity not in temporal_cache:
                        # Encode transient wrappers directly: the exact tuple
                        # and mapping nodes survive, not their Python copies.
                        expression=item.expression()
                        term_nodes=[]
                        for term in expression:
                            prior=term_cache.get(id(term))
                            if prior is not None:
                                encoded=prior[1];term_cache.move_to_end(id(term))
                            else:
                                if type(term) in (tuple,list):
                                    encoded=builder.node('sequence',type(term).__name__.encode(),
                                                         (builder.walk(value) for value in term))
                                else:encoded=builder.walk(term)
                                term_cache[id(term)]=(term,encoded)
                                if len(term_cache)>32768:term_cache.popitem(last=False)
                            term_nodes.append(encoded)
                        expression_node=builder.node('sequence',type(expression).__name__.encode(),term_nodes)
                        descriptor_fields=dict(time=builder.walk(item),expression=expression_node,
                                               box=builder.walk(item.box()))
                        descriptor_children=[]
                        for key in sorted(descriptor_fields,key=builder.order_key):
                            descriptor_children.extend((builder.walk(key),descriptor_fields[key]))
                        descriptor=builder.node('mapping',children=descriptor_children)
                        temporal_cache[identity]=(item,descriptor)
                    descriptor=temporal_cache[identity][1]
                    # The path must not be retained twice (str + encoded bytes).
                    import json
                    path_node=builder.node('json',json.dumps(path,ensure_ascii=False,separators=(',',':')).encode())
                    yield builder.node('sequence',b'tuple',(path_node,descriptor))
                else:
                    stack.extend((child,path+prefix) for prefix,child in reversed(node[1]))
        expressions_node=builder.node('sequence',b'tuple',occurrences())
        children=[]
        values={'expressions':expressions_node,'atom_catalog':builder.walk(data.get('atom_catalog'))}
        for key in sorted(values,key=builder.order_key):children.extend((builder.walk(key),values[key]))
        roots['temporal_dependencies']=builder.node('mapping',children=children)
        roots['provenance_and_sources']=builder.walk({key:data[key] for key in provenance_keys if key in data})
        roots['complete_payload']=builder.walk(data)
        if spooled:
            builder.store.seal()
            captured={name:dict(canonical=FrozenSpool(root,builder.store,builder.hashes[root].hex()),
                                sha256=builder.hashes[root].hex()) for name,root in roots.items()}
        else:
            nodes=tuple(builder.nodes)
            captured={name:dict(canonical=FrozenMerkle((root,nodes,builder.hashes[root].hex())),
                                sha256=builder.hashes[root].hex()) for name,root in roots.items()}
        completed=True
        return captured
    finally:
        if not completed and spooled:builder.store.close()
        builder.clear();index.memo.clear();index.active.clear();temporal_cache.clear();term_cache.clear()

def _payload_snapshot_spooled(data):
    return _payload_snapshot_encoded(data, spooled=True)


def temporal_dependency_dag(data):
    """Lossless path trie: edges retain every occurrence; shared nodes encode once.

    Expanding edge labels from 'payload' produces exactly temporal_expressions.
    Equal subtrees may share storage; no edge, selector or history is removed.
    """
    index = _TemporalIndex()
    memo = {}
    def capture(node):
        if node is None:
            return None
        identity = id(node)
        if identity in memo:
            return memo[identity]
        if node[0] == 'time':
            item = node[1]
            result = ('time', dict(time=item, expression=item.expression(), box=item.box()))
        else:
            result = ('branch', tuple((prefix, capture(child)) for prefix, child in node[1]))
        memo[identity] = result
        return result
    try:
        return capture(index.build(data))
    finally:
        index.memo.clear(); index.active.clear(); memo.clear()


def _payload_snapshot_compact(data, *, spooled):
    from canonical_bytes_A22 import _MerkleBuilder, _SpoolMerkleBuilder, FrozenMerkle, FrozenSpool
    state_keys=('state','terminal','frontier','finished','pending')
    emissions={key:tuple(h.branch.emissions for h in data[key])
               for key in ('frontier','finished') if key in data}
    if 'outputs' in data: emissions['outputs']=data['outputs']
    provenance_keys=('provenance','source_records','source_ids','source_proofs',
                     'context','context_options','layer','lane')
    sections=dict(
        states_and_queue={key:data[key] for key in state_keys if key in data},
        emissions_by_history=emissions,
        temporal_dependencies=dict(schema='A22-temporal-path-dag-v1',
                                   root=temporal_dependency_dag(data),
                                   atom_catalog=data.get('atom_catalog')),
        provenance_and_sources={key:data[key] for key in provenance_keys if key in data},
        complete_payload=data)
    builder=_SpoolMerkleBuilder() if spooled else _MerkleBuilder()
    if not spooled:builder.node_budget=150000
    completed=False
    try:
        roots={name:builder.walk(value) for name,value in sections.items()}
        if spooled:
            builder.store.seal()
            captured={name:dict(canonical=FrozenSpool(root,builder.store,builder.hashes[root].hex()),
                                sha256=builder.hashes[root].hex()) for name,root in roots.items()}
        else:
            nodes=tuple(builder.nodes)
            captured={name:dict(canonical=FrozenMerkle((root,nodes,builder.hashes[root].hex())),
                                sha256=builder.hashes[root].hex()) for name,root in roots.items()}
        completed=True
        return captured
    finally:
        if spooled and not completed: builder.store.close()
        builder.clear()


def payload_snapshot(data):
    """New exact proof format, bounded RAM node count with disk fallback."""
    import gc
    enabled=gc.isenabled()
    if enabled:gc.disable()
    try:
        try:
            return _payload_snapshot_compact(data, spooled=False)
        except MemoryError:
            pass
        return _payload_snapshot_compact(data, spooled=True)
    finally:
        if enabled:gc.enable()


def compare_snapshots(before,after):
    if set(before)!=set(after):
        fail('Cache snapshot sections differ')
    comparison={name:dict(first_sha256=before[name]['sha256'],
                          cache_sha256=after[name]['sha256'],
                          equal=before[name]['canonical']==after[name]['canonical'])
                for name in before}
    if not all(part['equal'] for part in comparison.values()):
        raise CacheContentMismatch(comparison)
    return comparison


def write_cache_check(root,meta,before,after,*,baseline_kind,first_file_sha,cache_file_sha):
    """Write a fresh comparison receipt; never substitutes another calculation."""
    name='controle_cache_'+Path(meta['payload']).name[:-7]+'_'+uuid.uuid4().hex+'.json'
    report=dict(schema='A22-cache-comparison-v1',payload=meta['payload'],
                producer_manifest_sha256=meta['provenance_manifest_sha256'],
                first_file_sha256=first_file_sha,cache_file_sha256=cache_file_sha,
                baseline_kind=baseline_kind,
                second_invocation='effective_cache_reread' if baseline_kind!='synthetic_fixture'
                                  else 'synthetic_fixture_reread_no_physics')
    try:
        report['comparison']=compare_snapshots(before,after)
    except CacheContentMismatch as error:
        report.update(status='not_certified',comparison=error.comparison)
        exclusive_json(root/name,report)
        raise
    if first_file_sha!=cache_file_sha or first_file_sha!=meta['sha256']:
        report['status']='not_certified'
        exclusive_json(root/name,report)
        fail('Fresh/cache payload bytes changed despite content comparison')
    report['status']='all_payload_sections_equal'
    exclusive_json(root/name,report)
    return dict(report=name,report_sha256=provenance.file_hash(root/name),content=report)


def verify_cache_check(root,meta,data,*,scope=None):
    try:
        return _verify_cache_check(root,meta,data,scope=scope)
    except BaseException:
        if scope is not None:scope._discard()
        raise


def _verify_cache_check(root,meta,data,*,scope=None):
    """Collector gate: compare the attested hashes to the actual payload now."""
    current=payload_snapshot(data)
    pattern='controle_cache_'+Path(meta['payload']).name[:-7]+'_*.json'
    fixture=data['provenance']['manifest'].get('fixture_only_no_physical_validation') is True
    for path in sorted(root.glob(pattern),reverse=True):
        raw=path.read_bytes() if scope is None else scope.read_artifact(path)
        report=json.loads(raw)
        if (report.get('schema') not in ('A22-cache-comparison-v1', 'A22-memory-disk-comparison-v1')
                or report.get('status')!='all_payload_sections_equal'
                or report.get('payload')!=meta['payload']
                or report.get('producer_manifest_sha256')!=meta['provenance_manifest_sha256']
                or report.get('first_file_sha256')!=meta['sha256']
                or report.get('cache_file_sha256')!=meta['sha256']):continue
        if fixture:
            if report.get('baseline_kind')!='synthetic_fixture':continue
        elif report.get('schema') == 'A22-memory-disk-comparison-v1':
            if (report.get('baseline_kind') != 'new_computation_in_memory'
                    or report.get('second_invocation') != 'independent_disk_roundtrip'):continue
        elif (report.get('baseline_kind')!='new_computation'
              or report.get('second_invocation')!='effective_cache_reread'):continue
        parts=report.get('comparison',{})
        if set(parts)!=set(current):continue
        if not all(parts[name].get('equal') is True
                   and parts[name].get('first_sha256')==current[name]['sha256']
                   and parts[name].get('cache_sha256')==current[name]['sha256']
                   for name in current):continue
        return dict(payload=path.name,sha256=hashlib.sha256(raw).hexdigest(),
                    baseline_kind=report['baseline_kind'],comparison=parts)
    fail('No matching fresh-calculation/cache comparison for this producer; cache/cache cannot qualify it')


def persist_new_payload(path, data):
    """Capture the actual new in-memory result BEFORE serializing it.

    No cache lookup, no second physics calculation. A failed comparison leaves
    no successful report or producer summary. Both paths retain every section.
    """
    path = Path(path)
    if path.exists():
        fail('A new-memory proof cannot overwrite or adopt a prior payload')
    before = payload_snapshot(data)
    sha = exclusive_payload(path, data)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        fail('Payload write/read bytes differ')
    after = payload_snapshot(_stream_read(raw))
    comparisons = compare_snapshots(before, after)
    name = 'controle_cache_' + path.name[:-7] + '_' + uuid.uuid4().hex + '.json'
    report = dict(schema='A22-memory-disk-comparison-v1', payload=path.name,
                  producer_manifest_sha256=data['provenance']['manifest_sha256'],
                  first_file_sha256=sha, cache_file_sha256=sha,
                  baseline_kind='new_computation_in_memory',
                  second_invocation='independent_disk_roundtrip',
                  status='all_payload_sections_equal', comparison=comparisons)
    exclusive_json(path.parent/name, report)
    return sha, dict(payload=name, sha256=provenance.file_hash(path.parent/name),
                     baseline_kind=report['baseline_kind'], comparison=comparisons)


def worker_with_storage_check(case, *, prepared_sources=None):
    """New-only production path; persisted proof is independently reread later."""
    root, index, env = open_campaign(c.output_root())
    before = {path.name for path in root.glob('*.pkl.gz')}
    result = c.worker(case, persist_check=True, prepared_sources=prepared_sources)
    if (result['status'] not in ('single_history_terminal_enclosed', 'joint_terminal_histories_enclosed')
            or result['payload'] in before or 'new_memory_disk_proof' not in result):
        fail('Storage qualification requires a newly computed accepted producer')
    return dict(result, baseline_kind='new_computation_in_memory',
                qualifying_original_cache_check=result['new_memory_disk_proof'])


def worker_with_cache_check(case):
    """Exactly the worker call, snapshot, effective cache call, and reread."""
    root,index,env=open_campaign(c.output_root())
    layer,lane,selected,job=case
    before_files={path.name:provenance.file_hash(path)
                  for path in root.glob('*.pkl.gz')}
    first=c.worker(case)
    if first['status']=='not_certified':fail('Cell refused; no cache equivalence claim')
    summary=str(Path(first['payload']).with_suffix('').with_suffix('.json'))
    # The physical first call above has no long-lived scope. Reuse starts
    # only for the validated result and the subsequent effective cache call.
    with source_scope(root,env) as scope:
        meta,data=load_producer(root,env,summary,layer,lane,scope=scope)
        first_file_sha=provenance.file_hash(root/meta['payload'])
        if meta['payload'] in before_files:
            if before_files[meta['payload']]!=first_file_sha:
                fail('First worker call overwrote an existing payload')
            baseline_kind='cache_only'
        else:baseline_kind='new_computation'
        before=payload_snapshot(data)
        cached=c.worker(case,source_scope=scope)
        if (cached.get('payload'),cached.get('sha256'),cached.get('status')) != (
                meta['payload'],meta['sha256'],meta['status']):
            fail('Second worker call did not return the same qualified cached payload')
        # Reopen actual bytes; do not reuse a decoded result as evidence.
        cached_meta,cached_data=load_producer(root,env,summary,layer,lane,scope=scope)
        after=payload_snapshot(cached_data)
        cache_file_sha=provenance.file_hash(root/cached_meta['payload'])
    # Scope closure must succeed before a comparison receipt is published.
    comparison=write_cache_check(root,meta,before,after,baseline_kind=baseline_kind,
                                 first_file_sha=first_file_sha,cache_file_sha=cache_file_sha)
    # A cache/cache diagnostic cannot retroactively attest an unsnapshotted
    # fresh calculation. Reuse requires the original new/cache report.
    original_check=verify_cache_check(root,meta,cached_data)
    return dict(first,cache_check_report=comparison['report'],
                cache_check_sha256=comparison['report_sha256'],baseline_kind=baseline_kind,
                qualifying_original_cache_check=original_check)


def plan_layer(root, index, env, layer, *, scope=None):
    if scope is None:
        with source_scope(root, env) as active:
            return plan_layer(root, index, env, layer, scope=active)
    try:
        if not 1 <= layer <= 18:
            fail('Layer outside the declared 1..18 protocol')
        previous = [read_source_table(root, index, env, layer-1, lane, scope=scope) for lane in range(12)]
        provenance.check_sources(tuple(record for table in previous for record in table), env, base=root,
                                 canonical_initial=c.canonical_initial_source,
                                 atom_validator=c.checked_source_atoms, scope=scope)
        jobs = []
        selectors = {}
        for lane in range(12):
            choices = [previous[j] for j in ((lane-1)%12, lane, (lane+1)%12)]
            for selected in itertools.product(*choices):
                if c.context_options_join(selected):
                    job = job_id(selected)
                    key = (lane, job)
                    if key in selectors:
                        fail('Duplicate/truncated-hash collision in the declared cell plan')
                    selectors[key] = tuple(r['id'] for r in selected)
                    jobs.append((layer, lane, selected, job))
        if {job[1] for job in jobs} != set(range(12)):
            fail('At least one cell has no compatible source scenario')
        return tuple(jobs)
    except BaseException:
        scope._discard()
        raise


def load_producer(root, env, summary_path, layer, lane, *, scope=None):
    if scope is None:
        with source_scope(root, env) as active:
            return load_producer(root, env, summary_path, layer, lane, scope=active)
    try:
        summary_path = local_file(root, summary_path)
        meta = json.loads(scope.read_artifact(summary_path))
        path = local_file(root, meta['payload'])
        data = _stream_read(scope.read_artifact(path,meta['sha256']))
        if data.get('layer') != layer or data.get('lane') != lane:
            fail('Producer belongs to a different cell')
        selected = data.get('source_records')
        if selected is None or len(selected) != 3:
            fail('Producer has no complete bound input records')
        expected_lanes = ((lane-1)%12, lane, (lane+1)%12)
        if any(r.get('layer') != layer-1 or r.get('lane') != j
               for r, j in zip(selected, expected_lanes)):
            fail('Producer input records do not match the physical parents')
        provenance.check_sources(selected, env, base=root,
                                 canonical_initial=c.canonical_initial_source,
                                 atom_validator=c.checked_source_atoms, scope=scope)
        manifest = provenance.make_manifest(env, selected, layer=layer, lane=lane)
        # These are the exact summary and producer bytes pinned above; avoid
        # decoding and checking a second copy of the same producer.
        provenance.verify(data, manifest, base=root)
        if meta.get('provenance_manifest_sha256') != provenance.digest(manifest):
            fail('Summary lacks matching validity manifest')
        if meta.get('status') != data.get('status'):
            fail('Summary status disagrees with payload')
        if tuple(meta.get('source_ids', ())) != tuple(data.get('source_ids', ())):
            fail('Summary source selectors disagree')
        if data.get('status') not in ('single_history_terminal_enclosed', 'joint_terminal_histories_enclosed'):
            fail('A refusal or unsupported status cannot become a source')
        if tuple(data.get('source_ids', ())) != tuple(r['id'] for r in selected):
            fail('Producer source scenario selectors changed')
        options = c.context_options_join(selected)
        if (provenance.digest(data.get('context_options')) != provenance.digest(options)
                or data.get('context') != c.common_context(options)):
            fail('Producer ancestral selectors do not match its input scenarios')
        catalog = data.get('atom_catalog')
        if catalog is None:
            fail('Producer has no attested atom catalogue')
        atoms.import_catalog(catalog)
        atoms.validate_catalog(data, catalog)
        return meta, data
    except BaseException:
        scope._discard()
        raise


def _collect_cell_records(root, env, layer, lane, summary_paths, *, scope):
    """Prepare separate qualified histories; publish nothing inside a scope."""
    records = []
    seen_payloads = set()
    for summary_path in sorted(map(str, summary_paths)):
        meta, data = load_producer(root, env, summary_path, layer, lane, scope=scope)
        cache_check = verify_cache_check(root, meta, data, scope=scope)
        if meta['sha256'] in seen_payloads:
            fail('A producer payload was supplied twice')
        seen_payloads.add(meta['sha256'])
        if data['status'] == 'single_history_terminal_enclosed':
            alternatives = [('outputs', data['outputs'], dict(terminal_state=data['terminal']))]
        else:
            if not data.get('finished'):
                fail('A successful joint producer has no terminal histories')
            if data.get('frontier'):
                fail('A successful producer still has a live frontier')
            alternatives = [(i, hh.branch.emissions, dict(terminal_history=hh))
                            for i, hh in enumerate(data['finished'])]
        from canonical_bytes_A22 import freeze_many
        use_references = env.get('options', {}).get('fixture_only_no_physical_validation') is not True
        state_hashes = (tuple(value.sha256() for value in freeze_many(
            next(iter(state.values())) for _, _, state in alternatives)) if use_references else ())
        producer_records = []
        for position, (selector, outputs, state) in enumerate(alternatives):
            # The complete terminal state/history stays in its producer file.
            # Each source keeps a distinct exact selector and state digest.
            # Synthetic legacy fixtures deliberately exercise inline records;
            # the new format has additional direct mutation/differential tests.
            if use_references:
                state = dict(terminal_ref=('A22-terminal-reference-v1', meta['sha256'],
                                          selector, state_hashes[position]))
            identity = f'L{layer}U{lane}:P{meta["sha256"]}:H{selector}'
            options = tuple({**old, f'L{layer}U{lane}':identity}
                            for old in data['context_options'])
            record = dict(id=identity, layer=layer, lane=lane, outputs=tuple(outputs),
                          context=c.common_context(options), context_options=options,
                          **state,
                          proof=dict(kind='producer_selected_joint_history',
                                     payload=meta['payload'], sha256=meta['sha256'],
                                     selector=selector,
                                     state_and_emissions_remain_bound=True,
                                     producer_manifest_sha256=data['provenance']['manifest_sha256'],
                                     producer_origin=data['provenance']['origin'],
                                     cache_comparison=cache_check))
            provenance.source_receipt(record, env, kind='derived_output',
                                      payload=meta['payload'], sha256=meta['sha256'],
                                      selector=selector,
                                      atom_catalog=atoms.atom_catalog(record))
            producer_records.append(record)
        # One synchronous request still visits every selector and callback.
        # Scope closure rechecks all pinned inputs before any table is written.
        provenance.check_sources(tuple(producer_records), env, base=root,
                                 canonical_initial=c.canonical_initial_source,
                                 atom_validator=c.checked_source_atoms, scope=scope)
        records.extend(producer_records)
    if not records:
        fail('No qualified history to collect')
    return tuple(records)


def _write_source_table(root, layer, lane, records):
    path = root/f'sources_{layer}_{lane}.pkl.gz'
    return dict(layer=layer, lane=lane, payload=path.name,
                sha256=exclusive_payload(path, records), records=len(records),
                pulse_counts=sorted({len(r['outputs']) for r in records}),
                grouping=False)


def collect_cell(root, env, layer, lane, summary_paths):
    """Close all reuse obligations before publishing one new source table."""
    with source_scope(root, env) as scope:
        records = _collect_cell_records(root, env, layer, lane, summary_paths, scope=scope)
    return _write_source_table(root, layer, lane, records)


def collect_layer(root, summaries, *, layer, allow_fixture=False, scope=None):
    root, index, env = open_campaign(root, allow_fixture=allow_fixture)
    if scope is None:
        with source_scope(root, env) as active:
            jobs, actual, prepared = _prepare_layer(root, index, env, summaries, layer, scope=active)
    else:
        jobs, actual, prepared = _prepare_layer(root, index, env, summaries, layer, scope=scope)
        scope.checkpoint()
    # No table or successful layer report exists before the final scan and
    # scope closure. A refusal leaves the acquired prefix untouched.
    tables=[_write_source_table(root,layer,lane,prepared[lane]) for lane in range(12)]
    report=dict(schema=SCHEMA, layer=layer, status='all_declared_cell_histories_collected',
                environment_sha256=provenance.digest(env), source_tables=tables,
                producer_summaries=[actual[k] for k in sorted(actual)],
                jobs=len(jobs), grouping=False,
                claim='Finite histories collected; no future invariant domain or mixing coefficient is asserted')
    exclusive_json(root/f'couche_qualifiee_{layer}.json',report)
    return report


def _prepare_layer(root, index, env, summaries, layer, *, scope):
    jobs = plan_layer(root, index, env, layer, scope=scope)
    expected = {(lane, job):tuple(r['id'] for r in selected)
                for _,lane,selected,job in jobs}
    actual = {}
    by_lane = {lane:[] for lane in range(12)}
    for summary in summaries:
        path = local_file(root, summary)
        meta = json.loads(scope.read_artifact(path))
        key = (meta['lane'],meta['job'])
        if key in actual:
            fail('A cell/source combination was supplied twice')
        if meta.get('layer') != layer or key not in expected:
            fail('Summary is not one of the declared coherent cell jobs')
        if tuple(meta.get('source_ids',())) != expected[key]:
            fail('Summary input selectors differ from the layer plan')
        actual[key] = path.name
        by_lane[meta['lane']].append(path.name)
    if set(actual) != set(expected):
        fail('Whole-layer collection requires every compatible declared cell job')
    # _collect_cell_records validates every producer and cache proof. All
    # twelve results remain private until every lane and scope.close succeed.
    targets=[root/f'sources_{layer}_{lane}.pkl.gz' for lane in range(12)]
    targets.append(root/f'couche_qualifiee_{layer}.json')
    if any(path.exists() for path in targets):
        fail('Refusing to overwrite an existing source collection')
    prepared=[_collect_cell_records(root, env, layer, lane, by_lane[lane], scope=scope)
              for lane in range(12)]
    return jobs, actual, prepared


def run_layer(root, *, layer, workers=1):
    root, index, env = open_campaign(root)
    jobs = plan_layer(root, index, env, layer)
    summaries=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(worker_with_cache_check,job) for job in jobs]):
            result=future.result()
            print(json.dumps(result),flush=True)
            if result['status']=='not_certified':
                fail('A cell refused; no whole-layer collection will be produced')
            summaries.append(str(Path(result['payload']).with_suffix('').with_suffix('.json')))
    return collect_layer(root,summaries,layer=layer)


def check_cell(root, *, layer, lane, job=None):
    """One physical cell job, its qualified payload, then a cache reread.

    This command computes a real local trajectory. It never collects a
    whole layer, and it is deliberately not invoked by the fixture tests.
    """
    root,index,env=open_campaign(root)
    choices=[case for case in plan_layer(root,index,env,layer)
             if case[1]==lane and (job is None or case[3]==job)]
    if len(choices)!=1:
        fail('check-cell requires exactly one compatible job; specify --job if necessary')
    selected=choices[0]
    report_path=root/f'integration_cellule_{layer}_{lane}_{selected[3]}_{uuid.uuid4().hex}.json'
    first=worker_with_cache_check(selected)
    summary=str(Path(first['payload']).with_suffix('').with_suffix('.json'))
    meta,data=load_producer(root,env,summary,layer,lane)
    comparison=verify_cache_check(root,meta,data)
    if 'outputs' in data:
        pulse_counts=[len(data['outputs'])]
    else:
        pulse_counts=sorted({len(hh.branch.emissions) for hh in data['finished']})
    report=dict(status='one_physical_cell_and_cache_reread_checked',layer=layer,lane=lane,
                job=selected[3],payload=meta['payload'],sha256=meta['sha256'],
                source_ids=meta['source_ids'],pulse_counts=pulse_counts,
                atom_count=len(data['atom_catalog']['records']),
                producer_manifest_sha256=data['provenance']['manifest_sha256'],
                producer_origin=data['provenance']['origin'],cache_same_payload=True,
                baseline_kind=first['baseline_kind'],cache_comparison=comparison,
                claim='One physical cell job only; not a whole-layer or future-invariance certificate')
    exclusive_json(report_path,report)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init');init.add_argument('--directory',required=True)
    run=sub.add_parser('run-layer');run.add_argument('--directory',required=True)
    run.add_argument('--layer',type=int,required=True);run.add_argument('--workers',type=int,default=1)
    collect=sub.add_parser('collect-layer');collect.add_argument('--directory',required=True)
    collect.add_argument('--layer',type=int,required=True);collect.add_argument('summaries',nargs='+')
    check=sub.add_parser('check-cell');check.add_argument('--directory',required=True)
    check.add_argument('--layer',type=int,required=True);check.add_argument('--lane',type=int,required=True)
    check.add_argument('--job')
    args=parser.parse_args(argv)
    if args.command=='init':report=create_campaign(args.directory)
    elif args.command=='run-layer':report=run_layer(args.directory,layer=args.layer,workers=args.workers)
    elif args.command=='check-cell':report=check_cell(args.directory,layer=args.layer,lane=args.lane,job=args.job)
    else:report=collect_layer(args.directory,args.summaries,layer=args.layer)
    print(json.dumps({k:report[k] for k in ('status','layer','jobs') if k in report}),flush=True)


if __name__=='__main__':
    main()


def _stream_read(value):
    from canonical_bytes_A22 import load_payload_stream
    return load_payload_stream(value)
