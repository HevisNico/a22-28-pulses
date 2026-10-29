"""Expected refusals are tests, not campaign failures. No physical simulation."""
from pathlib import Path
import sys, unittest
from copy import deepcopy
from unittest.mock import patch

import test_memo_DAG_A22 as fixture
import provenance_A22 as p
import rejeu_qualifie_A22 as r
from source_reuse_A22 import SourceReuseScope

class ScopeTests(unittest.TestCase):
    setUp=fixture.DAGTests.setUp
    producer=fixture.DAGTests.producer
    graph=fixture.DAGTests.graph
    check=fixture.DAGTests.check

    def scope(self, callback=None):
        return SourceReuseScope(self.env,base=self.root,
            canonical_initial=r.c.canonical_initial_source,
            atom_validator=r.c.checked_source_atoms if callback is None else callback)

    def reseal(self, record):
        proof=record.pop('source_provenance')
        p.source_receipt(record,self.env,**{k:v for k,v in proof.items()
            if k not in ('schema','environment_sha256','record_sha256')})
        return record

    def test_repeated_checks_reuse_only_complete_success(self):
        records=self.graph(3);first={};second={};original=p.digest(records)
        with self.scope() as scope:
            self.assertTrue(scope.check(records,stats=first))
            self.assertTrue(scope.check(records,stats=second))
        self.assertEqual(first['producer_validations'],9)
        self.assertEqual(second.get('producer_validations',0),0)
        self.assertEqual(second['record_links'],3)
        self.assertEqual(second['memo_hits'],3)
        self.assertGreater(second['snapshot_files_rechecked'],0)
        self.assertEqual(original,p.digest(records))

    def test_new_state_link_still_checked_after_previous_success(self):
        good=self.producer(tuple(self.initial[:3]),1,0)[0]
        bad=deepcopy(good);bad['terminal_state']['E']=99;self.reseal(bad)
        self.assertEqual(self.check((bad,),True)[0],'CoverageMismatch')
        with self.scope() as scope:
            scope.check((good,))
            with self.assertRaises(p.CoverageMismatch):scope.check((bad,))
            with self.assertRaises(p.BrokenChain):scope.check((good,))

    def test_new_emission_link_still_checked(self):
        good=self.producer(tuple(self.initial[:3]),1,0)[0]
        bad=deepcopy(good);bad['outputs']=bad['outputs'][:-1];self.reseal(bad)
        with self.scope() as scope:
            scope.check((good,))
            with self.assertRaises(p.CoverageMismatch):scope.check((bad,))

    def test_distinct_joint_histories_remain_distinct(self):
        records=self.producer(tuple(self.initial[:3]),1,0,joint=True)
        with self.scope() as scope:
            scope.check((records[0],))
            stats={};scope.check((records[1],),stats=stats)
            self.assertEqual(stats['memo_hits'],1)
            bad=deepcopy(records[1]);bad['terminal_history']=deepcopy(records[0]['terminal_history']);self.reseal(bad)
            with self.assertRaises(p.CoverageMismatch):scope.check((bad,))

    def test_changed_ancestor_is_refused_between_calls(self):
        roots=self.graph(2)
        with self.scope() as scope:
            scope.check(roots)
            path,_,_=self.producers[0]
            path.with_name(path.name+'.retained_original').write_bytes(path.read_bytes())
            path.write_bytes(path.read_bytes()+b'changed')
            self.assertEqual(self.check(roots,True)[0],'BrokenChain')
            with self.assertRaises(p.BrokenChain):scope.check(roots)

    def test_wrong_context_is_refused(self):
        roots=self.graph(1);wrong=deepcopy(self.env);wrong['options']['wrong_context']=True
        with self.scope() as scope:
            scope.check(roots)
            with self.assertRaises(p.ValidityMismatch):scope.check(roots,env=wrong)

    def test_file_base_is_part_of_context(self):
        roots=self.graph(1)
        with self.scope() as scope:
            scope.check(roots)
            with self.assertRaises(p.ValidityMismatch):scope.check(roots,base=self.root.parent)

    def test_owner_conflict_is_rechecked(self):
        roots=self.graph(1);_,_,owner=self.producers[0]
        saved=dict(p._OWNER_ARTIFACTS)
        try:
            with self.scope() as scope:
                scope.check(roots)
                p._OWNER_ARTIFACTS[owner]='wrong-authority'
                with self.assertRaises(p.BrokenChain):scope.check(roots)
        finally:p._OWNER_ARTIFACTS.clear();p._OWNER_ARTIFACTS.update(saved)

    def test_seen_cycle_still_refused(self):
        roots=self.graph(1);proof=roots[0]['source_provenance']
        stamp=(str((self.root/proof['payload']).resolve()),proof['sha256'])
        with self.scope() as scope:
            scope.check(roots)
            with self.assertRaises(p.BrokenChain):scope.check(roots,seen={stamp})

    def test_unknown_stateful_callback_remains_serial(self):
        good=self.producer(tuple(self.initial[:3]),1,0)[0];visits={}
        def callback(record, receipt):
            key=record['id'];visits[key]=visits.get(key,0)+1
            if key=='L0U0' and visits[key]>1:raise p.BrokenChain('Repeated ancestor rejected')
        with self.scope(callback) as scope:
            stats={};scope.check((good,),stats=stats)
            self.assertFalse(stats['memo_enabled'])
            with self.assertRaises(p.BrokenChain):scope.check((good,))

    def test_late_snapshot_replacement_refused(self):
        roots=self.graph(1)
        with self.scope() as scope:
            scope.check(roots);path,_,_=self.producers[0];original=path.read_bytes()
            path.with_name(path.name+'.retained_original').write_bytes(original)
            read=Path.read_bytes;calls=[]
            def replacement(item):
                if item.resolve()==path.resolve():
                    calls.append(1)
                    if len(calls)==2:item.write_bytes(original+b'changed-late')
                return read(item)
            with patch.object(Path,'read_bytes',replacement):
                with self.assertRaises(p.BrokenChain):scope.check(roots)

    def test_loaded_kernel_mutation_refused(self):
        roots=self.graph(1)
        def other_verify(*args,**kwargs):return True
        with self.scope() as scope:
            scope.check(roots)
            with patch.object(p,'verify',other_verify):
                with self.assertRaises(p.ValidityMismatch):scope.check(roots)

if __name__=='__main__':unittest.main(verbosity=2)
