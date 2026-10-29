"""Local source/provenance fixtures only; never runs a physical cell.

Synthetic payloads are explicitly isolated by a fixture-only environment
option, and their directories cannot be opened by the physical runner.
All fixture directories are retained; no existing artifact is removed.
"""
from pathlib import Path
import copy
from dataclasses import replace
import json
import unittest
import uuid

import rejeu_qualifie_A22 as runner
import provenance_A22 as p
import identite_temps_A22 as atoms
import histoires_A21 as h
import cycle_local_A20 as cyc
from intervalles_decimaux import I

ROOT=Path(__file__).resolve().parent


class FreshReplayTests(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/'fixtures_rejeu_qualifie'/('fixture_'+uuid.uuid4().hex)
        self.index=runner.create_campaign(self.root,fixture=True)
        self.env=self.index['environment']

    def fixture_producer(self,lane=0):
        selected=tuple(runner.source_table(self.root,self.index,self.env,0,j)[0]
                       for j in ((lane-1)%12,lane,(lane+1)%12))
        manifest=p.make_manifest(self.env,selected,layer=1,lane=lane)
        owner=p.digest(manifest)+':synthetic-fixture:'+uuid.uuid4().hex
        atoms.begin_producer(owner)
        t=runner.c.b.dep.Time('fixture-observation',I(1116))
        firing=runner.c.b.dep.Time('fixture-uncertain-fire',I(10,'10.001'))
        def history(emissions,rate):
            # This is a provenance data fixture, NOT a validated ODE state.
            state=dict(t=t,p=0,q=I('.1'),b=I(rate),fixture_no_physics=True)
            return h.History(cyc.Branch(state,emissions),index=0,count=0)
        finished=(history((),'.08'),history((firing,),'.08'),history((firing,),'.09'))
        options=runner.c.context_options_join(selected)
        data=dict(status='joint_terminal_histories_enclosed',finished=finished,pending=(),
                  source_ids=tuple(r['id'] for r in selected),source_proofs=tuple(r['proof'] for r in selected),
                  source_records=selected,context=runner.c.common_context(options),context_options=options,
                  layer=1,lane=lane,fixture_only_no_physical_validation=True)
        runner.c.seal_payload(data,manifest,producer_owner=owner,
                             origin=dict(kind='from_initialisation',source_chain_verified=True,
                                         synthetic_fixture_no_physics=True))
        name=f'fixture_cell_1_{lane}_{uuid.uuid4().hex}.pkl.gz'
        sha=runner.exclusive_payload(self.root/name,data)
        summary=dict(layer=1,lane=lane,job=runner.job_id(selected),payload=name,sha256=sha,
                     status=data['status'],source_ids=data['source_ids'],
                     provenance_manifest_sha256=p.digest(manifest),fixture_only_no_physical_validation=True)
        meta=Path(name).with_suffix('').with_suffix('.json').name
        runner.exclusive_json(self.root/meta,summary)
        # Actual two reads of a synthetic payload. No worker/ODE execution
        # is claimed: the fixture-specific kind cannot attest a physical job.
        _,first_data=runner.load_producer(self.root,self.env,meta,1,lane)
        before=runner.payload_snapshot(first_data)
        _,second_data=runner.load_producer(self.root,self.env,meta,1,lane)
        runner.write_cache_check(self.root,summary,before,runner.payload_snapshot(second_data),
                                 baseline_kind='synthetic_fixture',first_file_sha=sha,cache_file_sha=sha)
        return meta,data

    def test_initialisation_is_new_and_canonical(self):
        trains=[runner.source_table(self.root,self.index,self.env,0,j)[0] for j in range(12)]
        self.assertEqual([len(r['outputs']) for r in trains],[128]+[0]*11)
        self.assertEqual([t.box().lo for t in trains[0]['outputs']],[8*k for k in range(128)])
        self.assertTrue(all(not r['source_provenance']['atom_catalog']['records'] for r in trains))
        with self.assertRaises(FileExistsError):runner.create_campaign(self.root,fixture=True)

    def test_fixture_cannot_be_a_physical_replay(self):
        with self.assertRaises(p.ProvenanceRefusal):runner.open_campaign(self.root)
        root,index,env=runner.open_campaign(self.root,allow_fixture=True)
        self.assertEqual(env,self.env)
        ordinary=runner.configure(self.root)
        self.assertNotEqual(ordinary,self.env)

    def test_new_layer_plan_has_shared_scenario_ids(self):
        jobs=runner.plan_layer(self.root,self.index,self.env,1)
        self.assertEqual(len(jobs),12)
        self.assertEqual({j for _,j,_,_ in jobs},set(range(12)))
        uses=[r['id'] for _,_,selected,_ in jobs for r in selected if r['lane']==0]
        self.assertEqual(uses,['L0U0']*3)

    def test_collect_zero_one_and_same_outputs_without_merging(self):
        meta,data=self.fixture_producer()
        table=runner.collect_cell(self.root,self.env,1,0,[meta])
        records=tuple(runner.c.read(self.root/table['payload']))
        self.assertEqual(table['records'],3)
        self.assertEqual([len(r['outputs']) for r in records],[0,1,1])
        self.assertEqual([r['source_provenance']['selector'] for r in records],[0,1,2])
        self.assertEqual(len({r['id'] for r in records}),3)
        self.assertNotEqual(records[1]['terminal_history'].branch.state['b'].pair(),
                            records[2]['terminal_history'].branch.state['b'].pair())
        self.assertEqual(p.digest(records[1]['outputs']),p.digest(records[2]['outputs']))
        self.assertTrue(all(r['context']['L1U0']==r['id'] for r in records))
        self.assertFalse(runner.c.context_options_join((records[1],records[2])))
        self.assertTrue(runner.c.context_options_join((records[1],records[1])))
        p.check_sources(records,self.env,base=self.root,
                        canonical_initial=runner.c.canonical_initial_source,
                        atom_validator=runner.c.checked_source_atoms)
        self.assertTrue(all('parent_source_records' not in r['source_provenance'] for r in records))
        with self.assertRaises(FileExistsError):runner.collect_cell(self.root,self.env,1,0,[meta])

    def test_missing_jobs_do_not_become_a_layer(self):
        meta,_=self.fixture_producer()
        with self.assertRaises(p.ProvenanceRefusal):
            runner.collect_layer(self.root,[meta],layer=1,allow_fixture=True)
        self.assertFalse((self.root/'sources_1_0.pkl.gz').exists())
        self.assertFalse((self.root/'couche_qualifiee_1.json').exists())

    def test_legacy_payload_cannot_be_collected(self):
        meta,data=self.fixture_producer()
        legacy=copy.deepcopy(data);legacy.pop('provenance')
        path=self.root/'fixture_legacy.pkl.gz';sha=runner.exclusive_payload(path,legacy)
        summary=json.loads((self.root/meta).read_text());summary.update(payload=path.name,sha256=sha)
        runner.exclusive_json(self.root/'fixture_legacy.json',summary)
        with self.assertRaises(p.MissingManifest):
            runner.collect_cell(self.root,self.env,1,0,['fixture_legacy.json'])

    def test_grouped_and_changed_sources_refuse(self):
        original=runner.source_table(self.root,self.index,self.env,0,0)[0]
        grouped=copy.deepcopy(original)
        p.source_receipt(grouped,self.env,kind='shared_affine_source_train_enclosure',
                         atom_catalog=atoms.atom_catalog(grouped))
        with self.assertRaises(p.UnestablishedSourceChain):
            p.check_sources((grouped,),self.env,base=self.root,
                            canonical_initial=runner.c.canonical_initial_source,
                            atom_validator=runner.c.checked_source_atoms)
        changed=copy.deepcopy(original);changed['outputs']=changed['outputs'][:-1]
        with self.assertRaises(p.CoverageMismatch):
            p.check_sources((changed,),self.env,base=self.root,
                            canonical_initial=runner.c.canonical_initial_source,
                            atom_validator=runner.c.checked_source_atoms)

    def test_path_outside_campaign_refused(self):
        with self.assertRaises(p.ProvenanceRefusal):runner.local_file(self.root,'../old.pkl.gz')

    def test_cache_snapshots_compare_every_content_section(self):
        meta,data=self.fixture_producer()
        before=runner.payload_snapshot(data)
        same=runner.compare_snapshots(before,runner.payload_snapshot(copy.deepcopy(data)))
        self.assertEqual(set(same),{'states_and_queue','emissions_by_history',
                                   'temporal_dependencies','provenance_and_sources','complete_payload'})
        self.assertTrue(all(part['equal'] for part in same.values()))
        # The stored snapshot is strings, not references into data.
        frozen=before['states_and_queue']['canonical']
        data['finished'][0].branch.state['q']=I('.10001')
        self.assertEqual(before['states_and_queue']['canonical'],frozen)
        with self.assertRaises(runner.CacheContentMismatch) as caught:
            runner.compare_snapshots(before,runner.payload_snapshot(data))
        self.assertFalse(caught.exception.comparison['states_and_queue']['equal'])

    def test_cache_mutation_emission_refused_even_with_same_metadata(self):
        meta,data=self.fixture_producer()
        before=runner.payload_snapshot(data)
        hh=data['finished'][0]
        altered=replace(hh,branch=replace(hh.branch,emissions=(runner.c.b.dep.Time('extra',I(9)),)))
        data['finished']=(altered,)+data['finished'][1:]
        with self.assertRaises(runner.CacheContentMismatch) as caught:
            runner.compare_snapshots(before,runner.payload_snapshot(data))
        self.assertFalse(caught.exception.comparison['emissions_by_history']['equal'])

    def test_cache_mutation_atom_dependency_in_state_refused(self):
        meta,data=self.fixture_producer()
        existing=data['finished'][1].branch.emissions[0]
        data['finished'][0].branch.state['dependency_clock']=existing
        before=runner.payload_snapshot(data)
        # Equal date boxes are deliberately insufficient: the fresh atom is
        # a different expression, even with the same logical label.
        data['finished'][0].branch.state['dependency_clock']=runner.c.b.dep.Time(
            existing.key,existing.base)
        with self.assertRaises(runner.CacheContentMismatch) as caught:
            runner.compare_snapshots(before,runner.payload_snapshot(data))
        self.assertFalse(caught.exception.comparison['temporal_dependencies']['equal'])

    def test_cache_mutation_provenance_and_pending_refused(self):
        meta,data=self.fixture_producer()
        before=runner.payload_snapshot(data)
        changed=copy.deepcopy(data)
        changed['provenance']['origin']['synthetic_fixture_no_physics']='changed'
        with self.assertRaises(runner.CacheContentMismatch) as caught:
            runner.compare_snapshots(before,runner.payload_snapshot(changed))
        self.assertFalse(caught.exception.comparison['provenance_and_sources']['equal'])
        changed=copy.deepcopy(data);changed['pending']=((runner.c.b.dep.Time('pending',I(1117)),()),)
        with self.assertRaises(runner.CacheContentMismatch) as caught:
            runner.compare_snapshots(before,runner.payload_snapshot(changed))
        self.assertFalse(caught.exception.comparison['states_and_queue']['equal'])

    def test_cache_report_required_for_collection(self):
        meta,data=self.fixture_producer()
        summary=json.loads((self.root/meta).read_text())
        current=runner.verify_cache_check(self.root,summary,data)
        self.assertEqual(current['baseline_kind'],'synthetic_fixture')
        altered=copy.deepcopy(data);altered['instrumentation']={'new':1}
        with self.assertRaises(p.ProvenanceRefusal):
            runner.verify_cache_check(self.root,summary,altered)
        with self.assertRaises(runner.CacheContentMismatch):
            runner.compare_snapshots(runner.payload_snapshot(data),runner.payload_snapshot(altered))

    def test_cache_only_cannot_requalify_missing_fresh_snapshot(self):
        # Unit fixture for the report predicate only. No payload file is
        # written and no synthetic ODE receipt is presented as physical.
        data=dict(terminal={'fixture_predicate_only':True},
                  provenance={'manifest':{'environment':{'options':{}}}})
        meta=dict(payload='unwritten_fixture_cache_predicate.pkl.gz',sha256='fixture-bytes',
                  provenance_manifest_sha256='fixture-manifest')
        snapshot=runner.payload_snapshot(data)
        runner.write_cache_check(self.root,meta,snapshot,snapshot,baseline_kind='cache_only',
                                 first_file_sha=meta['sha256'],cache_file_sha=meta['sha256'])
        with self.assertRaises(p.ProvenanceRefusal):
            runner.verify_cache_check(self.root,meta,data)
        runner.write_cache_check(self.root,meta,snapshot,snapshot,baseline_kind='new_computation',
                                 first_file_sha=meta['sha256'],cache_file_sha=meta['sha256'])
        qualified=runner.verify_cache_check(self.root,meta,data)
        self.assertEqual(qualified['baseline_kind'],'new_computation')


if __name__=='__main__':
    unittest.main(verbosity=2)
