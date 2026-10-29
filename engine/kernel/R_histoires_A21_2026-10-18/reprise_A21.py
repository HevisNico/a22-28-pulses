"""Resume whole A20 histories; every result/checkpoint contains full states."""
from pathlib import Path
import argparse,json,time,gzip,pickle,hashlib,traceback
from concurrent.futures import ProcessPoolExecutor,as_completed
import histoires_A21 as h
import queue_regenerative_A21 as reg
from dataclasses import replace
import validation_A15 as b
import intervalles_decimaux as iv
from etat_A20 import decode
from charger_foret_A20 import branch

ROOT=Path(__file__).resolve().parent;A20=ROOT.parent/'R_cycle_local_A20_2026-10-18'
BUNDLE=ROOT/'depart_complet_A21.pkl.gz'

def dump(path,data):
    raw=pickle.dumps(data,protocol=5);compressed=gzip.compress(raw,compresslevel=5,mtime=0)
    path.write_bytes(compressed)
    reread=path.read_bytes()
    assert reread==compressed and gzip.decompress(reread)==raw,'Incomplete checkpoint write'
    return hashlib.sha256(reread).hexdigest()

def prepare():
    iv.configure(160);b.settings('1e-5','1e-4')
    record=json.loads((A20/'integration_unite_A20.json').read_text());c=decode(record['continuation']);del record
    record=json.loads((A20/'retour_silencieux_A20.json').read_text());xs=tuple(branch(x) for x in record['branches']);del record
    target=xs[0].state['t'];assert all(x.state['t'].token()==target.token() for x in xs)
    prefix=tuple(c['completed_output_prefix'])
    pending=tuple((t,actions) for t,actions in c['pending'] if t.box().hi>target.box().lo)
    assert pending and min(t.box().lo for t,_ in pending)>target.box().hi
    initial=tuple(h.History(replace(x,emissions=prefix+x.emissions),0,c['batch'],(k,)) for k,x in enumerate(xs))
    assert all(x.branch.state['p']==0 and x.branch.state['raw']==[None]*3 and x.branch.state['aux']==[0]*3 for x in initial)
    data=dict(initial=initial,pending=pending,target=target,prefix=prefix)
    sha=dump(BUNDLE,data)
    manifest=dict(status='whole_histories_prepared',histories=len(initial),old_prefix_pulses=len(prefix),
        pulse_count_histogram={str(n):sum(len(x.branch.emissions)==n for x in initial) for n in sorted(set(len(x.branch.emissions) for x in initial))},
        start=target.box().pair(),next_event_lower=str(min(t.box().lo for t,_ in pending)),pending_events=len(pending),
        state_emissions_conditions_and_cursors_joint=True,sha256=sha,
        source_sha256={name:hashlib.sha256((A20/name).read_bytes()).hexdigest() for name in ('retour_silencieux_A20.json','integration_unite_A20.json','manifeste_noyau_final_A20.json')})
    (ROOT/'depart_complet_A21.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest),flush=True)

def worker(args):
    k,tag,budget,resume=args;iv.configure(160);b.settings('1e-5','1e-4');b.PROFILE=None
    with gzip.open(BUNDLE,'rb') as f:data=pickle.load(f)
    initial=(data['initial'][k],);pending=data['pending'];del data
    previous=()
    if resume:
        with gzip.open(ROOT/f'histoire_{k:02d}_{resume}.pkl.gz','rb') as f:saved=pickle.load(f)
        assert saved['status']=='not_certified'
        initial=saved['frontier'];previous=saved['finished'];pending=saved['pending']
    stem=f'histoire_{k:02d}_{tag}';progress=ROOT/f'{stem}_progression.json';start=time.monotonic()
    def observe(info):
        info['seconds']=round(time.monotonic()-start,2);progress.write_text(json.dumps(info,indent=2)+'\n')
    try:
        finished,metrics=h.run(initial,pending,budget=budget,on_progress=observe,finish_tail=reg.certify)
        payload=dict(status='terminal_histories_enclosed',finished=previous+finished,pending=pending,metrics=metrics)
    except h.Refusal as e:
        payload=dict(status='not_certified',message=str(e),frontier=e.frontier,finished=previous+e.finished,pending=pending,traceback=traceback.format_exc())
    path=ROOT/f'{stem}.pkl.gz';sha=dump(path,payload)
    states=[x.branch.state for x in payload.get('finished',())];frontier=payload.get('frontier',())
    result=dict(root=k,status=payload['status'],seconds=round(time.monotonic()-start,2),sha256=sha,payload=path.name,
        terminal_histories=len(states),frontier_histories=len(frontier),message=payload.get('message'),
        earliest_frontier_time=min((x.branch.state['t'].box().lo for x in frontier),default=None),
        frontier=[dict(lineage=x.lineage,index=x.index,count=x.count,time=x.branch.state['t'].box().pair(),phase=x.branch.state['p'],
            pulses=len(x.branch.emissions),q=x.branch.state['q'].pair(),b=x.branch.state['b'].pair(),
            gain_widths=[str(z.exp().width()) for z in x.branch.state['z']]) for x in frontier[:10]],
        terminal_modes=sorted(set(s['p'] for s in states)),whole_histories_merged=0)
    (ROOT/f'{stem}.json').write_text(json.dumps(result,indent=2,default=str)+'\n');return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--roots',default='0,3');ap.add_argument('--workers',type=int,default=2);ap.add_argument('--tag',default='essai01');ap.add_argument('--budget',type=int,default=2048);ap.add_argument('--resume-tag');a=ap.parse_args()
    if a.prepare:prepare()
    else:
        roots=list(range(82)) if a.roots=='all' else [int(x) for x in a.roots.split(',')]
        with ProcessPoolExecutor(max_workers=a.workers) as pool:
            jobs=[pool.submit(worker,(k,a.tag,a.budget,a.resume_tag)) for k in roots]
            for job in as_completed(jobs):print(json.dumps(job.result(),default=str),flush=True)
