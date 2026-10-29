"""Registry-specific nonphysical regressions derived from the independent audit."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import gzip,json,pickle,sys,unittest,uuid
ROOT=Path(__file__).resolve().parent

import rejeu_qualifie_A22 as q
import provenance_A22 as p
import identite_temps_A22 as atoms
from intervalles_decimaux import I
from source_reuse_A22 import SourceReuseScope

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/'registry_synthetic_fixtures'/uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.env=q.configure(self.root,fixture=True)
        self.initial=q.initial_records(self.env)
        self.files=[]

    def producer(self,parents,depth,uncertain=False):
        manifest=p.make_manifest(self.env,parents,layer=depth,lane=0)
        owner=p.digest(manifest)+':registry-regression:'+uuid.uuid4().hex
        atoms.begin_producer(owner)
        outputs=(q.c.b.dep.Time('shared-label',I(10,11) if uncertain else I(20+depth)),)
        state=dict(q=I('.1'),caps=(False,False,False),aux=(0,0,0),E=50,b=I('.2'),fixture_only=True)
        data=dict(status='single_history_terminal_enclosed',outputs=outputs,terminal=state,
            source_records=parents,source_ids=tuple(r['id'] for r in parents),layer=depth,lane=0)
        data['atom_catalog']=atoms.atom_catalog(data)
        p.attach(data,manifest,origin=dict(kind='from_initialisation',source_chain_verified=True,
            synthetic_fixture_only_no_physics=True),producer_owner=owner)
        path=self.root/f'producer_{depth}.pkl.gz'
        path.write_bytes(gzip.compress(pickle.dumps(data,protocol=5),mtime=0));self.files.append(path)
        record=dict(id=f'registry-L{depth}U0',layer=depth,lane=0,outputs=outputs,
            terminal_state=deepcopy(state),context={},context_options=({},),proof={'synthetic_fixture_only':True})
        p.source_receipt(record,self.env,kind='derived_output',payload=path.name,sha256=p.file_hash(path),
            selector='outputs',atom_catalog=atoms.atom_catalog(record))
        return record

    def chain(self,depth=2):
        parent=self.producer(tuple(self.initial[:3]),1,True)
        identity=next(iter(parent['source_provenance']['atom_catalog']['records']))
        record=parent
        for n in range(2,depth+1):record=self.producer((record,self.initial[1],self.initial[2]),n)
        self.assertNotIn(identity,record['source_provenance']['atom_catalog']['records'])
        return (record,),identity

    def scope(self):
        return SourceReuseScope(self.env,base=self.root,
            canonical_initial=q.c.canonical_initial_source,atom_validator=q.c.checked_source_atoms)

    def fresh(self,records):
        return p.check_sources(records,self.env,base=self.root,
            canonical_initial=q.c.canonical_initial_source,atom_validator=q.c.checked_source_atoms)

    def test_independent_witness_now_refuses_without_changing_inputs(self):
        records,identity=self.chain();before=p.digest(records);hashes=[p.file_hash(f) for f in self.files]
        self.assertTrue(self.fresh(records))
        with self.scope() as scope:
            scope.check(records)
            atoms._RECORDS[identity]=dict(atoms._RECORDS[identity],bounds=['10','12'])
            with self.assertRaises(atoms.AtomIdentityRefusal):self.fresh(records)
            with self.assertRaises(atoms.AtomIdentityRefusal):scope.check(records)
            self.assertTrue(scope.failed)
            with self.assertRaises(p.BrokenChain):scope.check(records)
        self.assertEqual(before,p.digest(records));self.assertEqual(hashes,[p.file_hash(f) for f in self.files])

    def test_distant_ancestor_metadata_replacement_refuses(self):
        records,identity=self.chain(4)
        with self.scope() as scope:
            scope.check(records)
            self.assertIn(identity,scope.atom_definitions)
            atoms._RECORDS[identity]=dict(atoms._RECORDS[identity],label='changed-metadata')
            with self.assertRaises(atoms.AtomIdentityRefusal):scope.check(records)

    def test_deletion_refuses_without_restoring_the_entry(self):
        records,identity=self.chain()
        with self.scope() as scope:
            scope.check(records);atoms._RECORDS.pop(identity)
            with self.assertRaises(atoms.AtomIdentityRefusal):scope.check(records)
            self.assertNotIn(identity,atoms._RECORDS)

    def test_same_label_and_bounds_fresh_atoms_are_allowed_and_distinct(self):
        records,identity=self.chain()
        with self.scope() as scope:
            scope.check(records)
            atoms.begin_producer('fresh-registry-addition:'+uuid.uuid4().hex)
            a=q.c.b.dep.Time('shared-label',I(10,11));b=q.c.b.dep.Time('shared-label',I(10,11))
            ia=a.expression()[0][0];ib=b.expression()[0][0]
            self.assertNotEqual(ia,ib);self.assertNotEqual(ia,identity)
            self.assertTrue(scope.check(records))
            self.assertIn(ia,atoms._RECORDS);self.assertIn(ib,atoms._RECORDS)

    def test_conflicting_change_detected_on_close_without_next_check(self):
        records,identity=self.chain();scope=self.scope();scope.check(records)
        atoms._RECORDS[identity]=dict(atoms._RECORDS[identity],bounds=['10','12'])
        with self.assertRaises(atoms.AtomIdentityRefusal):scope.close()
        self.assertTrue(scope.closed);self.assertTrue(scope.failed)
        self.assertEqual(atoms._RECORDS[identity]['bounds'],['10','12'])

    def test_conflicting_change_during_first_final_scan_is_not_pinned_as_truth(self):
        records,identity=self.chain();path=self.files[0];read=Path.read_bytes;calls=[]
        def replacement(item):
            if item.resolve()==path.resolve():
                calls.append(1)
                if len(calls)==2:atoms._RECORDS[identity]=dict(atoms._RECORDS[identity],bounds=['10','12'])
            return read(item)
        with self.scope() as scope:
            with patch.object(Path,'read_bytes',replacement):
                with self.assertRaises(atoms.AtomIdentityRefusal):scope.check(records)
            self.assertTrue(scope.failed)

    def test_conflicting_change_during_close_final_scan_refuses(self):
        records,identity=self.chain();scope=self.scope();scope.check(records)
        path=self.files[0];read=Path.read_bytes
        def replacement(item):
            if item.resolve()==path.resolve():atoms._RECORDS[identity]=dict(atoms._RECORDS[identity],label='late-change')
            return read(item)
        with patch.object(Path,'read_bytes',replacement):
            with self.assertRaises(atoms.AtomIdentityRefusal):scope.close()
        self.assertTrue(scope.closed);self.assertTrue(scope.failed)

    def test_noncanonical_structural_replacement_is_refused(self):
        records,identity=self.chain()
        with self.scope() as scope:
            scope.check(records)
            atoms._RECORDS[identity]=dict(atoms._RECORDS[identity],bounds=('10','11'))
            with self.assertRaises(atoms.AtomIdentityRefusal):scope.check(records)

    def test_absent_constant_label_dependency_is_also_preserved(self):
        records,identity=self.chain();previous=atoms._RECORDS.get('shared-label')
        try:
            with self.scope() as scope:
                scope.check(records)
                self.assertIn('shared-label',scope.absent_atoms)
                atoms._RECORDS['shared-label']=deepcopy(atoms._RECORDS[identity])
                with self.assertRaises(atoms.AtomIdentityRefusal):scope.check(records)
        finally:
            if previous is None:atoms._RECORDS.pop('shared-label',None)
            else:atoms._RECORDS['shared-label']=previous

if __name__=='__main__':unittest.main(verbosity=2)
