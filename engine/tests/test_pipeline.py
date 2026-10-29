from pathlib import Path
import unittest,tempfile,sys,os,json
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'affine')]
os.environ.setdefault('A22_ARTIFACT_DIR',str(ROOT/'test_diagnostics'))
import engine,artifacts as a,temporal,run
from affine_iv import I
import cycle_local_A20 as cy

class PipelineTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);temporal.begin_producer('fixture')
 def tearDown(self):self.tmp.cleanup()
 def fixture(self):
  self.receipts=[]
  for lane in range(12):
   p=self.root/'layer_01'/f'cell_{lane:02d}';p.mkdir(parents=True)
   case={'run_id':'fixture','kernel_id':'fixture','layer':1,'lane':lane,'parent_receipts':[]}
   t=temporal.Time('same label',I.symbol('x',1));u=temporal.Time('same label',I.symbol('y',1))
   data={'case':case,'state':{'histories':(engine.b.ac.History(I.symbol('a',1)),engine.b.ac.History(I.symbol('b',1)))},'outputs':(t,u),'metrics':{}}
   sha,check=a.write_checked(p/'result.json',data)
   views={'state':data['state'],'emissions':data['outputs'],'time_dependencies':tuple((q.token(),q.expression()) for q in data['outputs']),'provenance':case,'complete':data}
   r={'status':'research_cell_complete','case':case,'payload_sha256':sha,'check':check,'comparisons':{}}
   for key,value in views.items():
    digest=a.canonical_hash(a.Encoder().encode(value));r['comparisons'][key]={'fresh':digest,'disk':digest,'equal':True}
   a.atomic_json(p/'receipt.json',r);self.receipts.append(r)
 def test_full_layer_separate_histories(self):
  self.fixture();rows=run.verify_layer(self.root,1,'fixture','fixture');self.assertEqual(len(rows),12)
  d=a.read(self.root/'layer_01/cell_00/result.json')
  self.assertEqual(len(d['state']['histories']),2);self.assertNotEqual(d['outputs'][0].token(),d['outputs'][1].token())
 def test_all_five_digest_mutations_refused(self):
  self.fixture();p=self.root/'layer_01/cell_00/receipt.json';original=json.loads(p.read_text())
  for key in original['comparisons']:
   with self.subTest(view=key):
    changed=json.loads(json.dumps(original));changed['comparisons'][key].update(fresh='0'*64,disk='0'*64)
    a.atomic_json(p,changed)
    with self.assertRaises(ValueError):run.verify_layer(self.root,1,'fixture','fixture')
    self.assertFalse((self.root/'layer_01/complete.json').exists())
  a.atomic_json(p,original)
 def test_missing_cell_refused(self):
  self.fixture();(self.root/'layer_01/cell_11/receipt.json').unlink()
  with self.assertRaises(FileNotFoundError):run.verify_layer(self.root,1,'fixture','fixture')
  self.assertFalse((self.root/'layer_01/complete.json').exists())
 def test_payload_alteration_refused(self):
  self.fixture();p=self.root/'layer_01/cell_00/result.json';p.write_text(p.read_text()+' ')
  with self.assertRaises(ValueError):run.verify_layer(self.root,1,'fixture','fixture')
 def test_wrong_lineage_refused(self):
  self.fixture();p=self.root/'layer_01/cell_00/receipt.json';r=json.loads(p.read_text());r['case']['parent_receipts']=['invented']
  a.atomic_json(p,r)
  with self.assertRaises(ValueError):run.verify_layer(self.root,1,'fixture','fixture')
 def test_branching_refusal_preserves_forest(self):
  t=temporal.Time('emission',I.symbol('a',1));forest=cy.Forest((cy.Branch({'q':I('.1')},(t,)),cy.Branch({'q':I('.2')},())),{'fixture':True})
  continuation={'completed_output_prefix':(t,),'pending':((t.plus(1),()),),'outputs_complete_through_window':True,'terminal_output_train_complete':False}
  err=cy.BranchingRequired(forest,continuation)
  case={'run_dir':str(self.root),'layer':1,'lane':0,'run_id':'fixture','kernel_id':'fixture','parent_receipts':[],'sources':[],'memory_mib':0,'cpu_seconds':0}
  with patch.object(engine,'compute_cell',side_effect=err):
   with self.assertRaises(cy.BranchingRequired):run.worker(case)
  p=self.root/'layer_01/cell_00'
  self.assertFalse((p/'receipt.json').exists());self.assertFalse((self.root/'layer_01/complete.json').exists())
  d=a.read(p/'unresolved_forest.json');self.assertEqual(len(d['forest'].branches),2)
  self.assertEqual(len(d['forest'].branches[0].emissions),1);self.assertEqual(len(d['continuation']['pending']),1)
 def test_changed_kernel_refused_before_compute(self):
  a.atomic_json(self.root/'campaign.json',{'run_id':'fixture','kernel_id':'wrong'})
  with patch.object(sys,'argv',['run.py','--out',str(self.root),'--through','1']):
   with self.assertRaises(ValueError):run.main()
  self.assertFalse((self.root/'layer_01').exists())
 def test_horizon_bound(self):
  with patch.object(sys,'argv',['run.py','--out',str(self.root),'--through','19']):
   with self.assertRaises(SystemExit):run.main()
  self.assertFalse((self.root/'campaign.json').exists())

class BudgetOrderingTests(unittest.TestCase):
 def test_limit_installed_before_loading_sources(self):
  import resource
  with tempfile.TemporaryDirectory() as tmp:
   calls=[]
   case={'run_dir':tmp,'layer':2,'lane':0,'run_id':'fixture','kernel_id':'fixture','parent_receipts':['fixture']*12,'sources':[{'path':'missing','sha256':'fixture'}]*12,'memory_mib':64,'cpu_seconds':0}
   def read(*args,**kw):
    calls.append('read');raise ValueError('fixture refusal')
   with patch.object(resource,'setrlimit',side_effect=lambda *x:calls.append('limit')),patch.object(a,'read',side_effect=read):
    with self.assertRaises(ValueError):run.worker(case)
   self.assertEqual(calls,['limit','read'])

if __name__=='__main__':unittest.main(verbosity=2)
