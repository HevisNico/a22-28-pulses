"""Continuation of coherent, explicitly selected source histories.

An input is a whole source record. Compatible ancestral selectors are
retained on every output; distinct source trains are never united.
"""
from pathlib import Path
import sys,argparse,json,gzip,pickle,hashlib,time,traceback,inspect,itertools,os
from dataclasses import replace
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent
A21=ROOT.parent/'R_histoires_A21_2026-10-18'
sys.path.insert(0,str(A21))
import histoires_A21 as h
import queue_regenerative_A22 as reg
import groupe_pret_A21 as ready_group
import validation_A15 as b
import cycle_local_A20 as cyc
import intervalles_decimaux as iv
import avance_causale_A22 as causal_advance
from canonical_bytes_A22 import write_payload_stream as dump
import metriques_A22 as measurements
import temps_valides_A22 as checked_times
import provenance_A22 as provenance
checked_times.require_certifier_assertions()
checked_times.install()
import ready_general_A22 as ready_general
ready_general.install()

class CertifiedTail(Exception):
 def __init__(self,terminal,pending):self.terminal=terminal;self.pending=pending;super().__init__('Certified tail')
class ValidatedContinuation(Exception):
 def __init__(self,history,pending):self.history=history;self.pending=pending;super().__init__('Validated continuation')

def read(path):
 from canonical_bytes_A22 import load_payload_stream
 return load_payload_stream(path)
def context_options_join(records):
 options=[{}]
 for r in records:
  candidates=r.get('context_options',(r['context'],));next_options={}
  for old in options:
   for candidate in candidates:
    if any(key in old and old[key]!=value for key,value in candidate.items()):continue
    merged={**old,**candidate};next_options[tuple(sorted(merged.items()))]=merged
  options=list(next_options.values())
  if not options:return ()
 return tuple(options)

def common_context(options):
 if not options:return None
 return {key:value for key,value in options[0].items() if all(other.get(key)==value for other in options[1:])}

def context_join(records):return common_context(context_options_join(records))

KERNEL_MODULES=(
 'intervalles_decimaux','outils_validation','dependances_A17','flux_charge_A19','actuations_A19','depot_A19',
 'profil_largeurs_A19','validation_A15','branche_retour_A19','cycle_local_A20','histoires_A21','groupe_pret_A21',
 'queue_regenerative_A21','etat_A20','charger_foret_A20','reprise_A21','temps_symboliques_A22','translation_tetes_A22',
 'temps_valides_A22','identite_temps_A22','queue_regenerative_A22','avance_causale_A22','metriques_A22',
 'provenance_A22','ready_general_A22','reprise_groupe_A22','groupe_protege_A22','retour_file_A22',
 'groupe_pret_feu_A22','subdivision_recuperation_A22','garde_relative_A22','ordonnanceur_A22','cycle_relatif_A22','source_reuse_A22','campagne_A22','rejeu_qualifie_A22','reprendre_A22','canonical_bytes_A22')

def output_root():
 return Path(os.environ.get('A22_ARTIFACT_DIR',str(ROOT))).resolve()

def validity_environment(settings, *, budget=2048):
 import importlib
 modules={name:importlib.import_module(name) for name in KERNEL_MODULES}
 files={str(Path(module.__file__).resolve().relative_to(ROOT.parent)):Path(module.__file__) for module in modules.values()}
 for caller in ('campagne_A22.py','reprendre_A22.py','rejeu_qualifie_A22.py'):
  files[str((ROOT/caller).relative_to(ROOT.parent))]=ROOT/caller
 env=provenance.environment(ROOT,settings=settings,precision=iv.PREC,kernel_files=files,loaded_modules=KERNEL_MODULES,
  adapters=dict(advance_base=provenance.descriptor(b.advance),advance_adapter=provenance.descriptor(causal_advance.advance),
   history_step=provenance.descriptor(h.step),time_minus=provenance.descriptor(b.dep.Time.minus),
   regenerative_tail=provenance.descriptor(reg.certify),worker=provenance.descriptor(worker),
   ready_to=provenance.descriptor(cyc._ready_to),scalar_root=provenance.descriptor(cyc._scalar_root),peak_upper=provenance.descriptor(cyc._peak_upper),
   canonical_source=provenance.descriptor(canonical_initial_source),source_atoms=provenance.descriptor(checked_source_atoms)),
  options=dict(return_groups=os.environ.get('A22_RETURN_GROUPS','0'),prefix_mode=os.environ.get('A22_PREFIX_MODE',''),budget=budget))
 env['arithmetic']['interval_contexts']={name:dict(precision=ctx.prec,rounding=str(ctx.rounding),Emin=ctx.Emin,Emax=ctx.Emax) for name,ctx in (('DOWN',iv.DOWN),('UP',iv.UP),('NEAR',iv.NEAR))}
 return env

def checked_source_atoms(record,receipt):
 import identite_temps_A22 as atoms
 catalog=receipt.get('atom_catalog')
 if catalog is None:raise provenance.UnestablishedSourceChain('Source lacks a producer atom catalogue')
 atoms.import_catalog(catalog)
 atoms.validate_catalog(record,catalog)

def seal_payload(data,manifest,*,producer_owner,**kwargs):
 import identite_temps_A22 as atoms
 data['atom_catalog']=atoms.atom_catalog(data)
 provenance.attach(data,manifest,producer_owner=producer_owner,**kwargs)
 provenance.verify(data,manifest,base=output_root())
 return data

def canonical_initial_source(record):
 # An independently checked declared source, not a legacy transient result.
 identity=record.get('id','')
 if identity not in {f'L0U{j}' for j in range(12)}:return False
 j=int(identity[3:]);train=record.get('outputs',())
 if len(train)!=(128 if j==0 else 0):return False
 from fractions import Fraction
 return all(t.box().lo==t.box().hi==8*k and all(bounds.lo==bounds.hi for _,_,bounds in t.expression())
  and sum((coefficient*Fraction(bounds.lo) for _,coefficient,bounds in t.expression()),Fraction(0))==8*k for k,t in enumerate(train))

def worker(job, *, source_scope=None, persist_check=False, prepared_sources=None):
 try:
  if source_scope is not None and prepared_sources is not None:
   raise provenance.ProvenanceRefusal('Two different source scopes supplied')
  return _worker(job,source_scope=source_scope,persist_check=persist_check,prepared_sources=prepared_sources)
 except BaseException:
  if source_scope is not None:source_scope._discard()
  if prepared_sources is not None:prepared_sources._discard()
  raise

def _worker(job, *, source_scope=None, persist_check=False, prepared_sources=None):
 iv.configure(160);settings=b.settings('1e-5','1e-4');b.PROFILE=None
 if os.environ.get('A22_RETURN_GROUPS')=='1':
  import reprise_groupe_A22 as hook
  h.step=hook.step
 outroot=output_root();outroot.mkdir(parents=True,exist_ok=True)
 n,j,selected,jobid=job
 if len(selected)!=3:raise provenance.CoverageMismatch('A cell requires exactly its three declared input source records')
 start=time.monotonic();cell=f'{n},{j}:A22:{jobid}'
 env=validity_environment(settings)
 provenance.check_sources(selected,env,base=outroot,canonical_initial=canonical_initial_source,atom_validator=checked_source_atoms,
  scope=source_scope if prepared_sources is None else prepared_sources)
 manifest=provenance.make_manifest(env,selected,layer=n,lane=j)
 inputs=tuple(x['outputs'] for x in selected);context_options=context_options_join(selected);context=common_context(context_options)
 assert context is not None
 tag=os.environ.get('A22_RUN_TAG','')
 stem=f'cellule_{n}_{j}_{jobid}'+('_'+tag if tag else '');summary=outroot/f'{stem}.json';path=outroot/f'{stem}.pkl.gz'
 pointer=outroot/f'{stem}_reprise.json'
 if pointer.exists():
  ref=json.loads(pointer.read_text())
  if ref.get('provenance_manifest_sha256')!=provenance.digest(manifest):
   raise provenance.ValidityMismatch('Resume pointer has no matching producer manifest')
  cached=provenance.cached_result(outroot/ref['accepted_summary'],manifest,base=outroot)
  if cached['status']=='not_certified':raise provenance.CoverageMismatch('Resume pointer targets an unaccepted result')
  return cached
 if summary.exists():
  m=provenance.cached_result(summary,manifest,base=outroot)
  if m['status']!='not_certified':return m
  original_stem=stem;attempt=1
  while True:
   stem=f'{original_stem}_suite{attempt}';summary=outroot/f'{stem}.json';path=outroot/f'{stem}.pkl.gz'
   if summary.exists():
    previous=provenance.cached_result(summary,manifest,base=outroot)
    if previous['status']!='not_certified':return previous
   elif not path.exists():break
   attempt+=1
 if source_scope is not None:
  raise provenance.ProvenanceRefusal('Scoped worker requires an accepted cache; no physical fallback inside reuse')
 import identite_temps_A22 as atoms
 producer_owner=provenance.digest(manifest)+':'+stem+':'+__import__('uuid').uuid4().hex
 atoms.begin_producer(producer_owner)
 measurements.reset()
 original=b.advance;code=b.unit.__code__;last=0;last_checkpoint=0
 def checkpoint(frontier,finished,pending):
  nonlocal last_checkpoint
  if time.monotonic()-last_checkpoint<15:return
  last_checkpoint=time.monotonic()
  data=dict(frontier=frontier,finished=finished,pending=pending,context=context,context_options=context_options,
   source_ids=tuple(x['id'] for x in selected),source_proofs=tuple(x['proof'] for x in selected),source_records=selected,layer=n,lane=j)
  seal_payload(data,manifest,producer_owner=producer_owner,origin=dict(kind='from_initialisation',source_chain_verified=True))
  dump(outroot/f'{stem}_checkpoint.pkl.gz',data)
 def progress(info):
  info.update(seconds=round(time.monotonic()-start,2),cell=cell)
  (outroot/f'{stem}_progression.json').write_text(json.dumps(info,indent=2)+'\n')
 def checked(s,boundary,cell,count):
  nonlocal last
  frame=inspect.currentframe().f_back
  if frame.f_code is code:
   loc=frame.f_locals;idx=loc['idx'];pending=tuple(loc['pending'])
   if time.monotonic()-last>10:
    last=time.monotonic();progress(dict(index=idx,time=s['t'].box().pair(),phase=s['p'],pulses=len(loc['out'])))
   candidate=h.History(cyc.Branch(s,tuple(loc['out']),({'kind':'frozen_A20_prefix','source_context':context},),()),idx,count,(jobid,))
   terminal=reg.certify(candidate,pending,cell)
   if terminal is not None:raise CertifiedTail(terminal,pending)
   group=loc.get('group',())
   if len(group)>1 and s['p']==0 and not (os.environ.get('A22_PREFIX_MODE')=='regenerative' and n<=9):
    out=ready_group.resolve(candidate.branch,group,loc['upper'],f'{cell}:ready:{count}')
    if out is None:out=ready_group.auxiliary_only(candidate.branch,group,loc['upper'],f'{cell}:ready:{count}')
    if out is not None:raise ValidatedContinuation(replace(candidate,branch=out,index=loc['stopidx'],count=count+len(group)),pending)
  return causal_advance.advance(s,boundary,cell,count,original)
 b.advance=checked
 def unit_with_frontier():
  try:return b.unit(inputs,cell)
  except (CertifiedTail,ValidatedContinuation,cyc.BranchingRequired):raise
  except (b.v.Ambiguous,AssertionError,ValueError) as error:
   if isinstance(error,ValueError) and str(error)!='f(a) and f(b) must have different signs':raise
   tb=error.__traceback__;frame=None
   while tb is not None:
    if tb.tb_frame.f_code is code:frame=tb.tb_frame;break
    tb=tb.tb_next
   if frame is None:raise
   loc=frame.f_locals
   if not all(k in loc for k in ('s','idx','pending','out','count')) or loc['idx']>=len(loc['pending']):raise
   candidate=h.History(cyc.Branch(loc['s'],tuple(loc['out']),({'kind':'frozen_A20_validated_frontier','source_context':context},),()),loc['idx'],loc['count'],(jobid,))
   raise ValidatedContinuation(candidate,tuple(loc['pending'])) from None
 try:
  try:
   outputs,state=unit_with_frontier()
   payload=dict(status='single_history_terminal_enclosed',outputs=tuple(outputs),terminal=state)
  except CertifiedTail as e:
   payload=dict(status='joint_terminal_histories_enclosed',finished=(e.terminal,),pending=e.pending,metrics=dict(certified_regenerative_suffixes=1))
  except (ValidatedContinuation,cyc.BranchingRequired) as e:
   if isinstance(e,ValidatedContinuation):initial=(e.history,);pending=e.pending
   else:
    c=e.continuation;pending=c['pending']
    initial=tuple(h.History(replace(x,emissions=tuple(c['completed_output_prefix'])+x.emissions),0,c['batch'],(jobid,k)) for k,x in enumerate(e.forest.branches))
   checkpoint(initial,(),pending)
   try:
    done,metrics=h.run(initial,pending,cell=cell,budget=2048,finish_tail=reg.certify,on_progress=progress,
      checkpoint=lambda front,done:checkpoint(front,done,pending))
    payload=dict(status='joint_terminal_histories_enclosed',finished=done,pending=pending,metrics=metrics)
   except h.Refusal as refusal:
    payload=dict(status='not_certified',frontier=refusal.frontier,finished=refusal.finished,pending=pending,message=str(refusal),traceback=''.join(traceback.format_exception(type(refusal),refusal,refusal.__traceback__,chain=False)))
 except Exception as e:payload=dict(status='not_certified',message=f'{type(e).__name__}: {e}',traceback=''.join(traceback.format_exception(type(e),e,e.__traceback__,chain=False)))
 finally:b.advance=original
 payload.update(context=context,context_options=context_options,source_ids=tuple(x['id'] for x in selected),source_proofs=tuple(x['proof'] for x in selected),layer=n,lane=j,instrumentation=measurements.snapshot())
 payload['source_records']=selected
 seal_payload(payload,manifest,producer_owner=producer_owner,origin=dict(kind='from_initialisation',source_chain_verified=True))
 if persist_check:
  import rejeu_qualifie_A22 as replay
  sha,storage_proof=replay.persist_new_payload(path,payload)
 else:sha=dump(path,payload)
 result=dict(layer=n,lane=j,job=jobid,status=payload['status'],seconds=round(time.monotonic()-start,2),payload=path.name,sha256=sha,
 provenance_manifest_sha256=provenance.digest(manifest),context=context,source_ids=payload['source_ids'],terminal_histories=1 if 'terminal' in payload else len(payload.get('finished',())),
 frontier_histories=len(payload.get('frontier',())),message=payload.get('message'))
 if persist_check:result['new_memory_disk_proof']=storage_proof
 summary.write_text(json.dumps(result,indent=2)+'\n');return result

def jobs(n,lanes):
 for j in lanes:
  sources=[read(output_root()/f'sources_{n-1}_{k}.pkl.gz') for k in ((j-1)%12,j,(j+1)%12)]
  for selected in itertools.product(*sources):
   if context_join(selected) is None:continue
   jobid=hashlib.sha256(json.dumps([x['id'] for x in selected]).encode()).hexdigest()[:16]
   yield (n,j,selected,jobid)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--layer',type=int,default=11);ap.add_argument('--lanes',default='0,5,6,7');ap.add_argument('--workers',type=int,default=4);ap.add_argument('--limit',type=int);args=ap.parse_args()
 cases=jobs(args.layer,[int(x) for x in args.lanes.split(',')]);cases=itertools.islice(cases,args.limit) if args.limit else cases
 with ProcessPoolExecutor(max_workers=args.workers) as pool:
  future=[pool.submit(worker,job) for job in cases]
  for f in as_completed(future):print(json.dumps(f.result()),flush=True)
