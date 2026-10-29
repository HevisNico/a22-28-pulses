"""Differential source validation fixtures; no physical simulation or reuse."""
from pathlib import Path
from copy import deepcopy
import gzip,json,pickle,unittest,uuid
from unittest.mock import patch
import rejeu_qualifie_A22 as r
import provenance_A22 as p
from intervalles_decimaux import I

ROOT=Path(__file__).resolve().parent

class DAGTests(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/'fixtures_memo_DAG'/uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.env=r.configure(self.root,fixture=True)
        self.initial=r.initial_records(self.env)
        self.producers=[]

    def producer(self,parents,depth,lane,joint=False):
        outputs=tuple(r.c.b.dep.Time('fixture-clock',I(10*depth+lane+8*k)) for k in range(2))
        state=dict(q=I('.1'),caps=(False,False,False),aux=(0,0,0),E=50,b=I('.2'),fixture_only=True)
        manifest=p.make_manifest(self.env,parents,layer=depth,lane=lane)
        owner=p.digest(manifest)+':fixture-DAG:'+uuid.uuid4().hex
        data=dict(status='single_history_terminal_enclosed',outputs=outputs,terminal=state,
                  source_records=parents,source_ids=tuple(x['id'] for x in parents),
                  layer=depth,lane=lane,atom_catalog={'schema':r.atoms.SCHEMA,'records':{}})
        if joint:
            other=dict(state,caps=(True,False,False),aux=(1,0,0),E=99)
            histories=tuple(r.c.h.History(r.c.cyc.Branch(s,outputs)) for s in (state,other))
            data.pop('outputs');data.pop('terminal')
            data.update(status='joint_terminal_histories_enclosed',finished=histories,pending=())
        p.attach(data,manifest,origin={'kind':'from_initialisation','source_chain_verified':True,
                                     'synthetic_fixture_only_no_physics':True},producer_owner=owner)
        path=self.root/f'producer_{depth}_{lane}_{uuid.uuid4().hex}.pkl.gz'
        path.write_bytes(gzip.compress(pickle.dumps(data,protocol=5),mtime=0))
        sha=p.file_hash(path);records=[]
        for selector in range(2) if joint else ('outputs',):
            selected=({'terminal_state':deepcopy(state)} if selector=='outputs' else
                      {'terminal_history':deepcopy(data['finished'][selector])})
            record=dict(id=f'fixture-L{depth}U{lane}-H{selector}',layer=depth,lane=lane,
                        outputs=outputs,context={},proof={'synthetic_fixture_only':True},**selected)
            p.source_receipt(record,self.env,kind='derived_output',payload=path.name,sha256=sha,
                             selector=selector,atom_catalog={'schema':r.atoms.SCHEMA,'records':{}})
            records.append(record)
        self.producers.append((path,data,owner))
        return tuple(records)

    def graph(self,depth=5):
        parents=tuple(self.initial[:3])
        for layer in range(1,depth+1):
            parents=tuple(self.producer(parents,layer,lane)[0] for lane in range(3))
        return parents

    def check(self,records,memo,env=None,seen=None):
        stats={}
        try:
            result=p.check_sources(records,self.env if env is None else env,base=self.root,
                canonical_initial=r.c.canonical_initial_source,atom_validator=r.c.checked_source_atoms,
                memo=memo,stats=stats,seen=seen)
        except p.ProvenanceRefusal as error:return type(error).__name__,stats
        return 'accepted' if result else 'false',stats

    def both_refuse(self,records,env=None,seen=None):
        a,sa=self.check(records,False,env,seen);b,sb=self.check(records,True,env,seen)
        self.assertEqual(a,b);self.assertNotEqual(a,'accepted')
        self.assertTrue(sb['memo_enabled'])
        return a,sa,sb

    def test_dense_graph_same_success_with_active_hits(self):
        roots=self.graph();records=roots+(roots[0],roots[1]);before=p.digest(records)
        a,serial=self.check(records,False);b,memo=self.check(records,True)
        self.assertEqual((a,b),('accepted','accepted'))
        self.assertFalse(serial['memo_enabled']);self.assertTrue(memo['memo_enabled'])
        self.assertEqual(memo['producer_validations'],15)
        self.assertGreater(serial['producer_validations'],memo['producer_validations'])
        self.assertGreater(memo['memo_hits'],0);self.assertEqual(before,p.digest(records))
        self.assertEqual(memo['snapshot_files_read'],memo['snapshot_files_rechecked'])
        (ROOT/'test_memo_DAG_counts.json').write_text(json.dumps({'scope':'synthetic depth5 width3 DAG only',
            'serial':serial,'memo':memo,'same_decision':True},indent=2)+'\n')

    def test_active_hits_preserve_distinct_histories_and_selectors(self):
        records=self.producer(tuple(self.initial[:3]),1,0,joint=True)
        a,sa=self.check(records,False);b,sb=self.check(records,True)
        self.assertEqual((a,b),('accepted','accepted'));self.assertTrue(sb['memo_enabled'])
        self.assertEqual(sb['producer_validations'],1);self.assertEqual(sb['memo_hits'],1)
        bad=deepcopy(records[1]);bad['terminal_history']=deepcopy(records[0]['terminal_history'])
        proof=bad.pop('source_provenance');p.source_receipt(bad,self.env,**{k:v for k,v in proof.items()
            if k not in ('schema','environment_sha256','record_sha256')})
        self.both_refuse((records[0],bad))

    def test_each_new_state_link_checked_after_black_parent(self):
        good=self.producer(tuple(self.initial[:3]),1,0)[0]
        for field,value in (('caps',(True,False,False)),('aux',(1,0,0)),('E',99)):
            bad=deepcopy(good);bad['id']='wrong-'+field;bad['terminal_state'][field]=value
            proof=bad.pop('source_provenance');p.source_receipt(bad,self.env,**{k:v for k,v in proof.items()
                if k not in ('schema','environment_sha256','record_sha256')})
            self.both_refuse((good,bad))

    def test_changed_ancestor_between_sessions_and_repeated_failure(self):
        roots=self.graph(3);self.assertEqual(self.check(roots,True)[0],'accepted')
        path,data,owner=self.producers[0]
        retained=path.with_name(path.name+'.retained_original');retained.write_bytes(path.read_bytes())
        path.write_bytes(path.read_bytes()+b'changed')
        self.both_refuse(roots);self.both_refuse(roots)

    def test_context_incompatible_and_active_cycle_refuse(self):
        roots=self.graph(2);wrong=deepcopy(self.env);wrong['options']['incompatible_fixture']=True
        self.both_refuse(roots,env=wrong)
        proof=roots[0]['source_provenance'];stamp=(str((self.root/proof['payload']).resolve()),proof['sha256'])
        self.both_refuse(roots,seen={stamp})

    def test_owner_conflict_on_shared_artifact_refuses(self):
        roots=self.graph(1);path,data,owner=self.producers[0]
        saved=dict(p._OWNER_ARTIFACTS)
        try:
            p._OWNER_ARTIFACTS[owner]='incompatible-existing-authority'
            self.both_refuse(roots)
        finally:
            p._OWNER_ARTIFACTS.clear();p._OWNER_ARTIFACTS.update(saved)

    def test_stateful_unknown_callbacks_fall_back_to_serial(self):
        good=self.producer(tuple(self.initial[:3]),1,0)[0]
        for memo in (False,True):
            visits={};stats={}
            def callback(record,receipt):
                key=record['id'];visits[key]=visits.get(key,0)+1
                if key=='L0U0' and visits[key]>1:raise p.BrokenChain('Stateful fixture refuses repeated ancestor')
            with self.assertRaises(p.BrokenChain):
                p.check_sources((good,good),self.env,base=self.root,memo=memo,stats=stats,
                    canonical_initial=r.c.canonical_initial_source,atom_validator=callback)
            self.assertFalse(stats['memo_enabled'])

    def test_changed_snapshot_with_active_hit_refuses(self):
        # Model an external file replacement at the final scan, after the
        # shared producer has already been successfully validated and hit.
        # The kernel files and the two qualified validators are untouched.
        for memo in (False,True):
            records=self.producer(tuple(self.initial[:3]),1,0,joint=True)
            path,data,owner=self.producers[-1];original=path.read_bytes()
            path.with_name(path.name+'.retained_original').write_bytes(original)
            real_read=Path.read_bytes;calls=[]
            def external_replacement(item):
                if item.resolve()==path.resolve():
                    calls.append(1)
                    if len(calls)==2:item.write_bytes(original+b'external-change')
                return real_read(item)
            with patch.object(Path,'read_bytes',external_replacement):
                decision,stats=self.check(records,memo)
            self.assertEqual(decision,'BrokenChain');self.assertEqual(len(calls),2)
            self.assertEqual(stats['memo_enabled'],memo)
            if memo:self.assertEqual(stats['memo_hits'],1)

if __name__=='__main__':unittest.main(verbosity=2)
