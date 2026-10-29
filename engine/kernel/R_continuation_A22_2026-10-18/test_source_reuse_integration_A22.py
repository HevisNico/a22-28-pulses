"""Integration regressions only; fixtures never execute a physical trajectory."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import hashlib, json, os, threading, unittest, sys
import rejeu_qualifie_A22 as r
import provenance_A22 as p
import identite_temps_A22 as atoms
from source_reuse_A22 import SourceReuseScope
import test_rejeu_qualifie_A22 as fixtures
import test_ancestor_reuse as scope_fixtures


class BindingTests(unittest.TestCase):
    setUp=scope_fixtures.ScopeTests.setUp
    producer=scope_fixtures.ScopeTests.producer
    graph=scope_fixtures.ScopeTests.graph
    scope=scope_fixtures.ScopeTests.scope

    def request(self, scope, records, **options):
        return p.check_sources(records,self.env,base=self.root,
            canonical_initial=r.c.canonical_initial_source,
            atom_validator=r.c.checked_source_atoms,scope=scope,**options)

    def test_dispatch_reuses_success_but_default_calls_stay_fresh(self):
        records=self.graph(2)
        stats={}
        with self.scope() as scope:
            self.request(scope,records)
            self.request(scope,records,stats=stats)
        self.assertEqual(stats.get('producer_validations',0),0)
        self.assertGreater(stats['memo_hits'],0)
        fresh={}
        p.check_sources(records,self.env,base=self.root,
            canonical_initial=r.c.canonical_initial_source,
            atom_validator=r.c.checked_source_atoms,stats=fresh)
        self.assertEqual(fresh['producer_validations'],6)

    def test_different_callback_request_invalidates_scope(self):
        records=self.graph(1)
        with self.scope() as scope:
            self.request(scope,records)
            with self.assertRaises(p.ValidityMismatch):
                p.check_sources(records,self.env,base=self.root,
                    canonical_initial=r.c.canonical_initial_source,
                    atom_validator=None,scope=scope)
            self.assertTrue(scope.failed)
            self.assertIsNone(scope.session)

    def test_invalid_options_discard_successes(self):
        for options in ({'memo':1},{'stats':[]}):
            with self.scope() as scope:
                self.request(scope,self.graph(1))
                with self.assertRaises(p.ProvenanceRefusal):self.request(scope,(),**options)
                self.assertTrue(scope.failed)
                self.assertIsNone(scope.session)

    def test_other_thread_refused_and_discarded(self):
        records=self.graph(1);errors=[]
        with self.scope() as scope:
            self.request(scope,records)
            def other_thread():
                try:self.request(scope,records)
                except BaseException as error:errors.append(type(error))
            thread=threading.Thread(target=other_thread);thread.start();thread.join()
            self.assertEqual(errors,[p.ValidityMismatch])
            self.assertTrue(scope.failed)

    def test_other_process_identity_refused(self):
        records=self.graph(1)
        with self.scope() as scope:
            self.request(scope,records)
            with patch.object(os,'getpid',return_value=scope.owner[0]+1):
                with self.assertRaises(p.ValidityMismatch):self.request(scope,records)
            self.assertTrue(scope.failed)

    def test_effective_inventory_covers_new_module_and_integration_functions(self):
        names=self.env['kernel'];loaded=self.env['loaded_code']
        self.assertIn('R_continuation_A22_2026-10-18/source_reuse_A22.py',names)
        for name in ('source_reuse_A22.SourceReuseScope.check_bound',
                     'source_reuse_A22.SourceReuseScope.read_artifact',
                     'rejeu_qualifie_A22._prepare_layer','campagne_A22.worker',
                     'reprendre_A22.validate_input'):
            self.assertIn(name,loaded)
        self.assertTrue(p._qualified_source_callbacks(self.env,
            r.c.canonical_initial_source,r.c.checked_source_atoms))

    def test_loaded_pipeline_mutation_refused(self):
        records=self.graph(1)
        def replacement(*args,**kwargs):return ()
        with self.scope() as scope:
            self.request(scope,records)
            with patch.object(r,'_collect_cell_records',replacement):
                with self.assertRaises(p.ValidityMismatch):self.request(scope,records)

    def test_closed_scope_cannot_be_reopened(self):
        scope=self.scope();scope.close()
        with self.assertRaises(p.BrokenChain):self.request(scope,())


class PipelineTests(unittest.TestCase):
    setUp=fixtures.FreshReplayTests.setUp
    fixture_producer=fixtures.FreshReplayTests.fixture_producer

    def test_plan_shares_one_scope_and_pins_every_input_table(self):
        with r.source_scope(self.root,self.env) as scope:
            jobs=r.plan_layer(self.root,self.index,self.env,1,scope=scope)
            self.assertEqual(len(jobs),12)
            self.assertTrue(scope.reports)
            self.assertEqual(sum(report['record_links'] for report in scope.reports),12)
            self.assertEqual(sum(report['atom_callbacks'] for report in scope.reports),12)
            self.assertEqual(len(scope.bound_files),13)
        self.assertTrue(scope.closed)

    def test_campaign_index_mutation_detected_on_scope_close(self):
        scope=r.source_scope(self.root,self.env)
        r.plan_layer(self.root,self.index,self.env,1,scope=scope)
        path=self.root/r.INDEX;path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(p.BrokenChain):scope.close()

    def test_cache_gate_refusal_discards_borrowed_successes(self):
        name,_=self.fixture_producer()
        with r.source_scope(self.root,self.env) as scope:
            meta,data=r.load_producer(self.root,self.env,name,1,0,scope=scope)
            changed=deepcopy(data);changed['instrumentation']={'unexpected':True}
            with self.assertRaises(p.ProvenanceRefusal):
                r.verify_cache_check(self.root,meta,changed,scope=scope)
            self.assertTrue(scope.failed)
            self.assertIsNone(scope.session)

    def test_source_table_mutation_detected_on_scope_close(self):
        scope=r.source_scope(self.root,self.env)
        r.source_table(self.root,self.index,self.env,0,0,scope=scope)
        path=self.root/'sources_0_0.pkl.gz';path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaises(p.BrokenChain):scope.close()
        self.assertTrue(scope.failed)

    def test_bad_source_table_invalidates_borrowed_scope(self):
        with r.source_scope(self.root,self.env) as scope:
            r.source_table(self.root,self.index,self.env,0,0,scope=scope)
            with self.assertRaises(p.ProvenanceRefusal):
                r.source_table(self.root,self.index,self.env,0,99,scope=scope)
            self.assertTrue(scope.failed)

    def test_new_producer_reads_summary_payload_and_cache_proof_under_scope(self):
        name,_=self.fixture_producer()
        with r.source_scope(self.root,self.env) as scope:
            meta,data=r.load_producer(self.root,self.env,name,1,0,scope=scope)
            cache=r.verify_cache_check(self.root,meta,data,scope=scope)
            self.assertTrue(all(str((self.root/n).resolve()) in scope.bound_files
                                for n in (name,meta['payload'],cache['payload'])))
            r.load_producer(self.root,self.env,name,1,0,scope=scope)
            self.assertEqual(scope.reports[-1].get('producer_validations',0),0)

    def test_summary_mutation_detected_on_scope_close(self):
        name,_=self.fixture_producer();scope=r.source_scope(self.root,self.env)
        r.load_producer(self.root,self.env,name,1,0,scope=scope)
        path=self.root/name;path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(p.BrokenChain):scope.close()

    def test_cache_proof_mutation_detected_on_scope_close(self):
        name,_=self.fixture_producer();scope=r.source_scope(self.root,self.env)
        meta,data=r.load_producer(self.root,self.env,name,1,0,scope=scope)
        cache=r.verify_cache_check(self.root,meta,data,scope=scope)
        path=self.root/cache['payload'];path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(p.BrokenChain):scope.close()

    def test_cell_close_refusal_publishes_no_table(self):
        name,_=self.fixture_producer()
        # Mutate a pinned producer summary during the closing environment
        # scan, after all three prepared records have been checked.
        def trace(frame,event,arg):
            if event=='call' and frame.f_code is SourceReuseScope.close.__code__:
                (self.root/name).write_bytes((self.root/name).read_bytes()+b' ')
            return trace
        sys.setprofile(trace)
        try:
            with self.assertRaises(p.BrokenChain):r.collect_cell(self.root,self.env,1,0,[name])
        finally:sys.setprofile(None)
        self.assertFalse((self.root/'sources_1_0.pkl.gz').exists())

    def test_layer_prepares_all_histories_then_closes_before_publication(self):
        names=[self.fixture_producer(lane)[0] for lane in range(12)]
        prefix={p.name:p.read_bytes() for p in self.root.glob('sources_0_*.pkl.gz')}
        at_close=[]
        def trace(frame,event,arg):
            if event=='call' and frame.f_code is SourceReuseScope.close.__code__:
                scope=frame.f_locals['self']
                if len(scope.bound_files)>20:
                    at_close.append(scope)
                    self.assertFalse(list(self.root.glob('sources_1_*.pkl.gz')))
                    self.assertFalse((self.root/'couche_qualifiee_1.json').exists())
            return trace
        sys.setprofile(trace)
        try:report=r.collect_layer(self.root,names,layer=1,allow_fixture=True)
        finally:sys.setprofile(None)
        self.assertEqual(len(at_close),1)
        self.assertTrue(at_close[0].closed)
        self.assertEqual(report['jobs'],12)
        self.assertEqual([table['records'] for table in report['source_tables']],[3]*12)
        self.assertFalse(report['grouping'])
        self.assertTrue(any(s.get('scope_previous_successes',0)>0 for s in at_close[0].reports))
        self.assertEqual(prefix,{p.name:p.read_bytes() for p in self.root.glob('sources_0_*.pkl.gz')})
        with self.assertRaises(p.ProvenanceRefusal):
            r.collect_layer(self.root,names,layer=1,allow_fixture=True)

    def test_layer_close_refusal_publishes_no_tables_or_success_report(self):
        names=[self.fixture_producer(lane)[0] for lane in range(12)]
        def trace(frame,event,arg):
            if event=='call' and frame.f_code is SourceReuseScope.close.__code__:
                if len(frame.f_locals['self'].bound_files)>20:
                    path=self.root/names[0];path.write_bytes(path.read_bytes()+b' ')
            return trace
        sys.setprofile(trace)
        try:
            with self.assertRaises(p.BrokenChain):
                r.collect_layer(self.root,names,layer=1,allow_fixture=True)
        finally:sys.setprofile(None)
        self.assertFalse(list(self.root.glob('sources_1_*.pkl.gz')))
        self.assertFalse((self.root/'couche_qualifiee_1.json').exists())

    def test_scoped_worker_refuses_missing_cache_without_physical_fallback(self):
        # Configure the normal new candidate environment, use only canonical
        # initial records, then prove a borrowed-scope worker never computes.
        root=self.root/'unwritten_cache_diagnostic'
        env=r.configure(root)
        initial=r.initial_records(env)
        selected=tuple(initial[j] for j in (11,0,1))
        case=(1,0,selected,r.job_id(selected))
        with r.source_scope(root,env) as scope:
            with self.assertRaisesRegex(p.ProvenanceRefusal,'no physical fallback'):
                r.c.worker(case,source_scope=scope)
            self.assertTrue(scope.failed)
        self.assertFalse(list(self.root.glob('cellule_*.pkl.gz')))

    def test_original_environment_is_not_migrated(self):
        old=deepcopy(self.index);old['environment']['options']['legacy_environment_only']=True
        old['environment_sha256']=p.digest(old['environment'])
        path=self.root/r.INDEX;path.write_text(json.dumps(old))
        with self.assertRaises(p.ValidityMismatch):r.open_campaign(self.root,allow_fixture=True)
        self.assertEqual(json.loads(path.read_text()),old)


if __name__=='__main__':unittest.main(verbosity=2)
