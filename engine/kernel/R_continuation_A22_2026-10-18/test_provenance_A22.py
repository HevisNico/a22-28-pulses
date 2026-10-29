"""F03 synthetic regressions: no network result/checkpoint is loaded."""
from pathlib import Path
import tempfile,copy,gzip,pickle,json,unittest
import provenance_A22 as p

def save(path,data):
 path.write_bytes(gzip.compress(pickle.dumps(data,protocol=5)));return p.file_hash(path)

class ProvenanceTests(unittest.TestCase):
 def setUp(self):
  folder=Path(__file__).resolve().parent/'fixtures_provenance'
  folder.mkdir(exist_ok=True)
  self.root=Path(tempfile.mkdtemp(prefix='fixture_',dir=folder))
  self.kernel=self.root/'kernel.py';self.kernel.write_text('version = 1\n')
  self.env=self.environment();self.sources=[dict(id='s0',outputs=(0,8),context={})]
  p.source_receipt(self.sources[0],self.env,kind='canonical_initial')
  self.manifest=p.make_manifest(self.env,self.sources,layer=1,lane=0)
  self.data=dict(status='joint_terminal_histories_enclosed',frontier=('live',),finished=('done',),pending=('next',),
                 source_ids=('s0',),source_proofs=({'canonical':True},),source_records=self.sources,layer=1,lane=0)
  p.attach(self.data,self.manifest,origin=dict(kind='from_initialisation',source_chain_verified=True))
 def environment(self,**kw):
  options=dict(settings={'delta':'1e-5','epsilon':'1e-4'},adapters={'step':'test'},options={'budget':2048},precision=160,kernel_files={'kernel.py':self.kernel})
  options.update(kw);return p.environment(self.root,**options)
 def test_valid_cache_without_verifier_execution(self):
  payload=self.root/'result.pkl.gz';sha=save(payload,self.data)
  summary=dict(payload=payload.name,sha256=sha,status=self.data['status'],source_ids=self.data['source_ids'],provenance_manifest_sha256=p.digest(self.manifest))
  path=self.root/'result.json';path.write_text(json.dumps(summary))
  # No hybrid verifier is even imported. The cache is reused only after
  # manifest + complete coverage + ancestry verification.
  self.assertEqual(p.cached_result(path,self.manifest,base=self.root),json.loads(path.read_text()))
 def test_manifest_missing(self):
  del self.data['provenance']
  with self.assertRaises(p.MissingManifest):p.verify(self.data,self.manifest,base=self.root)
 def test_environment_changes(self):
  for changed in (self.environment(precision=161),self.environment(settings={'delta':'1e-6','epsilon':'1e-4'}),self.environment(options={'budget':1})):
   with self.subTest(changed=changed):
    manifest=p.make_manifest(changed,self.sources,layer=1,lane=0)
    with self.assertRaises(p.ValidityMismatch):p.verify(self.data,manifest,base=self.root)
  self.kernel.write_text('version = 2\n')
  with self.assertRaises(p.ValidityMismatch):p.verify(self.data,p.make_manifest(self.environment(),self.sources,layer=1,lane=0),base=self.root)
 def test_sources_changed(self):
  sources=copy.deepcopy(self.sources);sources[0]['outputs']=(0,9)
  with self.assertRaises(p.ValidityMismatch):p.verify(self.data,p.make_manifest(self.env,sources,layer=1,lane=0),base=self.root)
  with self.assertRaises(p.CoverageMismatch):p.check_sources(sources,self.env,base=self.root,canonical_initial=lambda x:True)
 def test_frontier_and_finished_both_bound(self):
  for key in ('frontier','finished','pending'):
   data=copy.deepcopy(self.data);data[key]+=('corruption',)
   with self.subTest(key=key):
    with self.assertRaises(p.CoverageMismatch):p.verify(data,self.manifest,base=self.root)
 def test_old_finished_cannot_hide_in_new_suffix(self):
  old=copy.deepcopy(self.data);del old['provenance'];sha=save(self.root/'old.pkl.gz',old)
  suffix=copy.deepcopy(self.data)
  p.attach(suffix,self.manifest,origin=dict(kind='resume'),parents=(dict(payload='old.pkl.gz',sha256=sha),))
  with self.assertRaises(p.MissingManifest):p.verify(suffix,self.manifest,base=self.root)
 def test_resume_full_chain_and_changed_ancestor(self):
  sha=save(self.root/'parent.pkl.gz',self.data)
  suffix=copy.deepcopy(self.data);suffix['finished']+=('new_done',)
  p.attach(suffix,self.manifest,origin=dict(kind='resume'),parents=(dict(payload='parent.pkl.gz',sha256=sha),))
  p.verify(suffix,self.manifest,base=self.root)
  self.data['finished']+=('changed',);save(self.root/'parent.pkl.gz',self.data)
  with self.assertRaises(p.BrokenChain):p.verify(suffix,self.manifest,base=self.root)
 def test_suffix_only_and_unverified_root_rejected(self):
  for changes in ({'whole_history_current_environment':False},{'origin':{'kind':'from_initialisation','source_chain_verified':False}}):
   data=copy.deepcopy(self.data);data['provenance'].update(changes)
   with self.assertRaises(p.BrokenChain):p.verify(data,self.manifest,base=self.root)
 def test_initial_source_is_rechecked_not_merely_hashed(self):
  p.check_sources(self.sources,self.env,base=self.root,canonical_initial=lambda r:r['outputs']==(0,8))
  with self.assertRaises(p.UnestablishedSourceChain):p.check_sources(self.sources,self.env,base=self.root,canonical_initial=lambda r:False)
  with self.assertRaises(p.UnestablishedSourceChain):p.check_sources([{'id':'old','outputs':()}],self.env,base=self.root,canonical_initial=lambda r:True)
 def test_source_producer_missing_manifest_refused(self):
  path=self.root/'old-source.pkl.gz';sha=save(path,{'outputs':(0,8),'finished':()})
  record={'id':'s1','outputs':(0,8)}
  p.source_receipt(record,self.env,kind='derived_output',payload=path.name,sha256=sha,selector='outputs',parent_source_records=self.sources)
  with self.assertRaises(p.MissingManifest):p.check_sources([record],self.env,base=self.root,canonical_initial=lambda r:True)
 def test_summary_cannot_bypass_manifest(self):
  path=self.root/'good.pkl.gz';sha=save(path,self.data)
  summary=dict(payload=path.name,sha256=sha,status=self.data['status'],source_ids=('s0',))
  meta=self.root/'good.json';meta.write_text(json.dumps(summary))
  with self.assertRaises(p.ValidityMismatch):p.cached_result(meta,self.manifest,base=self.root)

 def test_real_interval_slots_and_context_precision(self):
  import importlib.util
  path=Path(__file__).resolve().parent.parent/'R_cycle_local_A20_2026-10-18'/'intervalles_decimaux.py'
  spec=importlib.util.spec_from_file_location('synthetic_interval_fixture',path)
  iv=importlib.util.module_from_spec(spec);spec.loader.exec_module(iv)
  iv.configure(160)
  self.assertNotEqual(p.digest(iv.I('0.1','0.2')),p.digest(iv.I('0.1','0.20000000000000001')))
  self.assertEqual(p.digest(iv.I('0.1','0.2')),p.digest(iv.I('0.1','0.2')))
  self.assertIn('slots',p.normal(iv.I(0,1)))
  self.assertEqual(self.environment(precision=iv.PREC)['arithmetic']['precision'],160)
  self.assertEqual((iv.DOWN.prec,iv.UP.prec,iv.NEAR.prec),(160,160,160))
 def test_loaded_kernel_replacement_detected(self):
  import types,sys
  module=types.ModuleType('synthetic_kernel_fixture');module.__file__=str(self.kernel)
  exec('def unit(): return 1',module.__dict__)
  sys.modules[module.__name__]=module;self.addCleanup(sys.modules.pop,module.__name__,None)
  before=self.environment()
  exec('def unit(): return 2',module.__dict__)
  after=self.environment()
  self.assertEqual(before['kernel'],after['kernel'])
  self.assertNotEqual(before['loaded_code'],after['loaded_code'])
 def test_derived_source_chain_checked(self):
  data=copy.deepcopy(self.data);data['outputs']=(10,18);data['terminal']={'synthetic':'terminal'}
  p.attach(data,self.manifest,origin=dict(kind='from_initialisation',source_chain_verified=True))
  path=self.root/'source-result.pkl.gz';sha=save(path,data)
  record=dict(id='s1',outputs=data['outputs'],terminal_state=data['terminal'])
  p.source_receipt(record,self.env,kind='derived_output',payload=path.name,sha256=sha,selector='outputs',parent_source_records=self.sources)
  p.check_sources([record],self.env,base=self.root,canonical_initial=lambda r:r['id']=='s0')
  wrong_state=copy.deepcopy(record);wrong_state['terminal_state']={'synthetic':'wrong-state'}
  p.source_receipt(wrong_state,self.env,kind='derived_output',payload=path.name,sha256=sha,selector='outputs')
  with self.assertRaises(p.CoverageMismatch):p.check_sources([wrong_state],self.env,base=self.root,canonical_initial=lambda r:True)
  record2=copy.deepcopy(record);record2['source_provenance']['parent_source_records']=[]
  with self.assertRaises(p.BrokenChain):p.check_sources([record2],self.env,base=self.root,canonical_initial=lambda r:True)
 def test_nested_snapshot_resume_uses_project_reference_base(self):
  folder=self.root/'provenance_inputs';folder.mkdir()
  first=folder/'first.pkl.gz';sha1=save(first,self.data)
  second=copy.deepcopy(self.data)
  p.attach(second,self.manifest,origin=dict(kind='resume'),parents=(dict(payload='provenance_inputs/first.pkl.gz',sha256=sha1),))
  path=folder/'second.pkl.gz';sha2=save(path,second)
  third=copy.deepcopy(self.data)
  p.attach(third,self.manifest,origin=dict(kind='resume'),parents=(dict(payload='provenance_inputs/second.pkl.gz',sha256=sha2),))
  p.verify(third,self.manifest,base=self.root)

 def test_atom_authority_only_current_or_inherited(self):
  owner=p.digest(self.manifest)+':attempt:unique'
  own={'owner':owner,'serial':0,'bounds':['0','1']}
  old={'owner':'earlier','serial':0,'bounds':['1','2']}
  catalog={'records':{'new':own,'old':old}}
  p.check_atom_authority(catalog,self.manifest,owner,[{'records':{'old':old}}])
  with self.assertRaises(p.BrokenChain):p.check_atom_authority(catalog,self.manifest,owner,[])
  with self.assertRaises(p.BrokenChain):p.check_atom_authority(catalog,self.manifest,'unbound',[])
 def test_worker_cache_control_flow_and_old_cache_refusal(self):
  from unittest.mock import patch
  import campagne_A22 as c
  sources=[dict(id=f'L0U{j}',outputs=(),context={},proof={'canonical':True}) for j in (1,2,3)]
  for r in sources:p.source_receipt(r,self.env,kind='canonical_initial',atom_catalog={'schema':'A22-atoms-v2','records':{}})
  manifest=p.make_manifest(self.env,sources,layer=1,lane=0)
  data=copy.deepcopy(self.data);data.update(source_records=sources,source_ids=tuple(r['id'] for r in sources),source_proofs=tuple(r['proof'] for r in sources))
  p.attach(data,manifest,origin=dict(kind='from_initialisation',source_chain_verified=True))
  payload=self.root/'cellule_1_0_fixture.pkl.gz';sha=save(payload,data)
  summary=dict(status=data['status'],payload=payload.name,sha256=sha,source_ids=data['source_ids'],provenance_manifest_sha256=p.digest(manifest))
  summary_path=self.root/'cellule_1_0_fixture.json';summary_path.write_text(json.dumps(summary))
  # Only control flow is tested here; runtime patch detection is covered
  # separately by test_loaded_kernel_replacement_detected.
  with patch.dict(__import__('os').environ,{'A22_ARTIFACT_DIR':str(self.root)}),patch.object(c,'ROOT',self.root),patch.object(c,'validity_environment',lambda settings:self.env),patch.object(c.b,'unit',side_effect=AssertionError('must not recalculate')) as unit:
   self.assertEqual(c.worker((1,0,sources,'fixture'))['status'],data['status']);unit.assert_not_called()
   del data['provenance'];summary['sha256']=save(payload,data);summary_path.write_text(json.dumps(summary))
   with self.assertRaises(p.MissingManifest):c.worker((1,0,sources,'fixture'))
   unit.assert_not_called()

 def test_manifest_stable_across_resume_import_and_interval_contexts(self):
  from unittest.mock import patch
  import os,campagne_A22 as c,reprise_groupe_A22 as hook
  c.iv.configure(160);settings=c.b.settings('1e-5','1e-4')
  with patch.dict(os.environ,{'A22_RETURN_GROUPS':'1','A22_PREFIX_MODE':'regenerative'}),patch.object(c.h,'step',hook.step):
   before=c.validity_environment(settings)
   import reprendre_A22
   after=c.validity_environment(settings)
   self.assertEqual(before,after)
   self.assertNotIn('__main__',before['loaded_code'])
   self.assertEqual(before['arithmetic']['interval_contexts']['DOWN']['precision'],160)
   original=c.iv.UP.prec
   try:
    c.iv.UP.prec=159
    self.assertNotEqual(before,c.validity_environment(settings))
   finally:c.iv.UP.prec=original

 def test_descriptor_stable_during_true_invocation_and_changes_detected(self):
  def fixture(value):
   nested=lambda other:(value+other,'named constant')
   return nested(2)
  before=p.descriptor(fixture)
  for value in range(64):self.assertEqual(fixture(value),(value+2,'named constant'))
  self.assertEqual(before,p.descriptor(fixture))
  def different(value):return value+3
  fixture.__code__=different.__code__
  self.assertNotEqual(before,p.descriptor(fixture))
 def test_fraction_time_token_memory_is_canonically_serializable(self):
  from fractions import Fraction
  self.assertEqual(p.normal(Fraction(2,3)),{'rational':[2,3]})
  memory={('A22-atoms-v2',Fraction(2,3),(('atom',1,('0','1')),)):('pulse',)}
  self.assertEqual(p.digest(memory),p.digest(copy.deepcopy(memory)))

 def test_real_worker_entry_keeps_code_fingerprint(self):
  import os,sys
  from unittest.mock import patch
  import campagne_A22 as c,reprise_groupe_A22 as hook
  selected=[dict(id=f'L0U{j}',outputs=(),context={},proof={}) for j in (1,2,3)]
  with patch.dict(os.environ,{'A22_ARTIFACT_DIR':str(self.root),'A22_RETURN_GROUPS':'1','A22_PREFIX_MODE':'regenerative'}),patch.object(c.h,'step',hook.step):
   c.iv.configure(160);settings=c.b.settings('1e-5','1e-4')
   expected=c.validity_environment(settings);before=p.descriptor(c.worker)
   captured=[]
   # Observe the real return without replacing an inventoried function
   # with a closure that captures the provenance module itself.
   def witness(frame,event,value):
    if event=='return' and frame.f_code is c.validity_environment.__code__:
     captured.append((p.descriptor(c.worker),value))
   previous=sys.getprofile();sys.setprofile(witness)
   try:
    with self.assertRaises(p.UnestablishedSourceChain):c.worker((1,6,selected,'fingerprint'))
   finally:sys.setprofile(previous)
   self.assertEqual(before,captured[0][0]);self.assertEqual(expected,captured[0][1])
   self.assertFalse(list(self.root.glob('cellule_*')))
 def test_code_hash_portable_but_semantic_mutation_detected(self):
  def function(x):return x+1
  original=p.descriptor(function)
  function.__code__=function.__code__.replace(co_filename='/different/extracted/root/file.py')
  self.assertEqual(original,p.descriptor(function))
  function.__code__=function.__code__.replace(co_consts=(None,2))
  self.assertNotEqual(original,p.descriptor(function))

 def test_descriptor_closure_defaults_kwdefaults_and_shared_values(self):
  def make(value):
   def function():return value
   return function
  one,two=make(1),make(2)
  self.assertEqual(p.descriptor(one)['code_sha256'],p.descriptor(two)['code_sha256'])
  self.assertNotEqual(p.descriptor(one),p.descriptor(two))
  def function(value=1,*,limit=2):return value+limit
  before=p.descriptor(function);function.__defaults__=(3,)
  self.assertNotEqual(before,p.descriptor(function))
  before=p.descriptor(function);function.__kwdefaults__={'limit':4}
  self.assertNotEqual(before,p.descriptor(function))
  shared=[]
  def captured(value=shared):return value is shared
  before=p.descriptor(captured);shared.append(7)
  self.assertNotEqual(before,p.descriptor(captured))
  before=p.descriptor(captured);captured.__defaults__=([7],)
  self.assertNotEqual(before,p.descriptor(captured))
  self.assertEqual(p.descriptor(captured),p.descriptor(captured))
 def test_full_environment_detects_closure_defaults_and_kwdefaults(self):
  from unittest.mock import patch
  import campagne_A22 as c
  c.iv.configure(160);settings=c.b.settings('1e-5','1e-4')
  def make(value):
   def function():return value
   return function
  with patch.object(c.b,'unit',make(1)):
   first=c.validity_environment(settings)
  with patch.object(c.b,'unit',make(2)):
   second=c.validity_environment(settings)
  self.assertNotEqual(first,second)
  def function(value=1,*,limit=2):return value+limit
  with patch.object(c.b,'unit',function):
   first=c.validity_environment(settings);function.__defaults__=(3,)
   second=c.validity_environment(settings);self.assertNotEqual(first,second)
   function.__kwdefaults__={'limit':4}
   third=c.validity_environment(settings);self.assertNotEqual(second,third)
  with patch.object(c.h,'step',make(1)):
   first=c.validity_environment(settings)
  with patch.object(c.h,'step',make(2)):
   self.assertNotEqual(first,c.validity_environment(settings))
 def test_unsupported_capture_cycles_modules_opaque_classes_and_empty_cells_refuse(self):
  import sys
  def make(value):
   def function():return value
   return function
  class Opaque:pass
  class CustomList(list):pass
  for value in (sys,Opaque(),Opaque,CustomList([1])):
   with self.subTest(type=type(value).__qualname__):
    with self.assertRaises(p.CapturedStateRefusal):p.descriptor(make(value))
  cyclic=[];cyclic.append(cyclic)
  with self.assertRaises(p.CapturedStateRefusal):p.descriptor(make(cyclic))
  def recursive():
   value=None
   def function():return value
   value=function
   return function
  with self.assertRaises(p.CapturedStateRefusal):p.descriptor(recursive())
  def empty():
   value=1
   def function():return value
   del value
   return function
  with self.assertRaises(p.CapturedStateRefusal):p.descriptor(empty())
 def test_nested_captured_python_function_contents_are_covered(self):
  def outer(value):
   def leaf():return value
   def wrapper():return leaf()
   return wrapper
  self.assertNotEqual(p.descriptor(outer(1)),p.descriptor(outer(2)))

if __name__=='__main__':unittest.main(verbosity=2)
