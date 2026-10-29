"""Resume only producer-attested complete prefixes under identical validity.

A legacy artifact is a diagnostic input, never a qualifying resume input.
"""
from pathlib import Path
import sys,json,time,argparse,traceback,os
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'R_histoires_A21_2026-10-18'))
import campagne_A22 as campaign
import histoires_A21 as h
import queue_regenerative_A22 as reg
import avance_causale_A22 as causal_advance
import reprise_groupe_A22 as hook
import validation_A15 as b
import intervalles_decimaux as iv
from reprise_A21 import dump
import metriques_A22 as measurements
import provenance_A22 as provenance

def validate_input(data, manifest, *, env=None):
 if env is None:
  import rejeu_qualifie_A22 as runner
  _,_,env=runner.open_campaign(campaign.output_root())
 if manifest.get('environment_sha256') != provenance.digest(env):
  raise provenance.ValidityMismatch('Resume environment differs from current campaign')
 provenance.verify(data,manifest,base=campaign.output_root())
 import identite_temps_A22 as atoms
 catalog=data.get('atom_catalog')
 if catalog is None:raise provenance.CoverageMismatch('Resume prefix lacks a producer atom catalogue')
 atoms.import_catalog(catalog);atoms.validate_catalog(data,catalog)
 provenance.check_sources(data.get('source_records',()),env,base=campaign.output_root(),canonical_initial=campaign.canonical_initial_source,atom_validator=campaign.checked_source_atoms)
 if provenance.make_manifest(env,data.get('source_records',()),layer=data['layer'],lane=data['lane'])!=manifest:
  raise provenance.BrokenChain('Resume source records do not match producer manifest')
 if 'frontier' not in data or 'finished' not in data or 'pending' not in data:
  raise provenance.CoverageMismatch('Resume requires explicit frontier, finished and pending fields')
 return data

def main(argv=None):
 ap=argparse.ArgumentParser()
 ap.add_argument('--input',required=True);ap.add_argument('--tag',default='retours')
 ap.add_argument('--budget',type=int,default=2048);ap.add_argument('--register-base');ap.add_argument('--metadata')
 ap.add_argument('--prefix-mode',default=os.environ.get('A22_PREFIX_MODE',''))
 args=ap.parse_args(argv)
 os.environ['A22_RETURN_GROUPS']='1';os.environ['A22_PREFIX_MODE']=args.prefix_mode
 iv.configure(160);settings=b.settings('1e-5','1e-4');b.PROFILE=None;h.step=hook.step
 outroot=campaign.output_root();outroot.mkdir(parents=True,exist_ok=True)
 p=outroot/args.input;data=campaign.read(p);start=time.monotonic();stem=p.name[:-7]+'_'+args.tag
 if 'source_records' not in data:raise provenance.MissingManifest('Legacy resume has no bound source records; no metadata grafting is permitted')
 env=campaign.validity_environment(settings,budget=args.budget)
 manifest=provenance.make_manifest(env,data['source_records'],layer=data['layer'],lane=data['lane'])
 validate_input(data,manifest,env=env)
 if args.metadata:
  metadata=campaign.read(outroot/args.metadata);validate_input(metadata,manifest,env=env)
  for key in ('pending','source_ids','source_proofs','source_records','context','context_options','layer','lane'):
   if provenance.digest(data.get(key))!=provenance.digest(metadata.get(key)):
    raise provenance.CoverageMismatch('Metadata disagrees with attested input: '+key)
 # Freeze the input bytes under their content address. Later progress writes
 # cannot change the ancestor on which this particular resume relies.
 raw=p.read_bytes();sha_input=provenance.file_hash(p)
 if __import__('hashlib').sha256(raw).hexdigest()!=sha_input:raise provenance.BrokenChain('Input bytes changed during snapshot')
 if provenance.digest(campaign.read(p))!=provenance.digest(data):raise provenance.BrokenChain('Input changed during validation')
 archive=outroot/'provenance_inputs'/f'{sha_input}.pkl.gz';archive.parent.mkdir(exist_ok=True)
 if archive.exists():
  if provenance.file_hash(archive)!=sha_input:raise provenance.BrokenChain('Content-addressed ancestor changed')
 else:archive.write_bytes(raw)
 if provenance.file_hash(archive)!=sha_input:raise provenance.BrokenChain('Ancestor snapshot integrity failed')
 parent=dict(payload=str(archive.relative_to(outroot)),sha256=sha_input)
 for output in (outroot/f'{stem}.pkl.gz',outroot/f'{stem}.json'):
  if output.exists():raise provenance.ProvenanceRefusal('Refusing to overwrite a provenance artifact: '+output.name)
 import identite_temps_A22 as atoms
 producer_owner=provenance.digest(manifest)+':'+stem+':'+__import__('uuid').uuid4().hex
 atoms.begin_producer(producer_owner)
 initial=data['frontier'];previous=tuple(data['finished']);pending=data['pending']
 measurements.reset();cell=f"{data['layer']},{data['lane']}:A22:{p.name.split('_')[3]}"
 def with_metadata(result):
  for key in ('context','context_options','source_ids','source_proofs','source_records','layer','lane'):
   if key in data:result[key]=data[key]
  return campaign.seal_payload(result,manifest,producer_owner=producer_owner,origin=dict(kind='resume'),parents=(parent,))
 def progress(info):
  info.update(seconds=round(time.monotonic()-start,2));(outroot/f'{stem}_progression.json').write_text(json.dumps(info,indent=2)+'\n')
 last_checkpoint=0
 def checkpoint(front,done):
  nonlocal last_checkpoint
  if time.monotonic()-last_checkpoint<15:return
  last_checkpoint=time.monotonic()
  dump(outroot/f'{stem}_checkpoint.pkl.gz',with_metadata(dict(frontier=front,finished=previous+done,pending=pending)))
 original_advance=b.advance
 b.advance=lambda s,tt,cell,count:causal_advance.advance(s,tt,cell,count,original_advance)
 try:
  try:
   finished,metrics=h.run(initial,pending,cell=cell,budget=args.budget,finish_tail=reg.certify,on_progress=progress,checkpoint=checkpoint)
   result=dict(status='joint_terminal_histories_enclosed',finished=previous+finished,pending=pending,metrics=metrics)
  except h.Refusal as e:
   result=dict(status='not_certified',frontier=e.frontier,finished=previous+e.finished,pending=pending,message=str(e),
    traceback=''.join(traceback.format_exception(type(e),e,e.__traceback__,chain=False)))
 finally:b.advance=original_advance
 result.update(instrumentation=measurements.snapshot(),previous_completed_histories=len(previous),initial_frontier_histories=len(initial))
 with_metadata(result);sha=dump(outroot/f'{stem}.pkl.gz',result)
 summary=dict(status=result['status'],payload=f'{stem}.pkl.gz',sha256=sha,seconds=round(time.monotonic()-start,2),
  terminal_histories=len(result['finished']),frontier_histories=len(result.get('frontier',())),message=result.get('message'),
  source_sha256=sha_input,provenance_manifest_sha256=provenance.digest(manifest))
 summary.update(layer=data['layer'],lane=data['lane'],job=p.name.split('_')[3],source_ids=data['source_ids'],context=data['context'])
 (outroot/f'{stem}.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
 if args.register_base and result['status']!='not_certified':
  (outroot/f'{args.register_base}_reprise.json').write_text(json.dumps(dict(accepted_summary=f'{stem}.json',source_sha256=sha_input,
    provenance_manifest_sha256=provenance.digest(manifest)),indent=2)+'\n')
 return 0 if result['status']!='not_certified' else 2
if __name__=='__main__':raise SystemExit(main())
