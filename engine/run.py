"""Research-only affine campaign, bounded workers and per-cell checkpoints.
A completed layer means software checks completed, not a proof qualification.
"""
from pathlib import Path
import argparse,sys,os,json,time,hashlib,platform,subprocess,zipfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'affine'))

def identity():
    """Freeze every shipped executable source, C source and built extension."""
    h=hashlib.sha256()
    paths=[ROOT/name for name in ('run.py','build_native.py','build_all_native.py','launch_fresh.py')]
    paths.append(ROOT/'reference'/'full_model_reference.md')
    for directory in ('affine','kernel'):
        paths.extend(p for p in (ROOT/directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts
                     and p.suffix in ('.py','.c','.h','.so','.pyd','.dll','.dylib'))
    for path in sorted(paths):
        h.update(str(path.relative_to(ROOT)).encode()+b'\0');h.update(path.read_bytes())
    return h.hexdigest()

def affine_iv_kmax():
    import affine_iv
    return affine_iv.KMAX

def initialize(artifact_dir):
    if not __debug__:raise RuntimeError('Python -O is forbidden')
    os.environ['A22_ARTIFACT_DIR']=str(artifact_dir);Path(artifact_dir).mkdir(parents=True,exist_ok=True)
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
    import experiment_parameters
    if experiment_parameters.PHYSICAL_EPSILON != experiment_parameters.validate_epsilon(os.environ.get('A22_PHYSICAL_EPSILON', '1e-4')):
        raise RuntimeError('physical epsilon changed after import')
    import engine,artifacts,temporal
    return engine,artifacts,temporal

def initial_trains(run_id,temporal):
    from affine_iv import I
    temporal.begin_producer(run_id+'/source')
    clock=temporal.Time('canonical-initial-clock',I(0))
    return [tuple(clock.plus(8*k) for k in range(28))]+[()]*11

def worker(case):
    root=Path(case['run_dir']);layer=case['layer'];lane=case['lane']
    target=root/f'layer_{layer:02d}'/f'cell_{lane:02d}'
    target.mkdir(parents=True,exist_ok=True)
    engine,a,t=initialize(target/'diagnostics')
    expected={'run_id':case['run_id'],'kernel_id':case['kernel_id'],'layer':layer,'lane':lane,'parent_receipts':case['parent_receipts']}
    started=time.perf_counter()
    try:
        import resource
        if case['memory_mib']:
            limit=case['memory_mib']*1024*1024
            resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
        if case['cpu_seconds']:
            resource.setrlimit(resource.RLIMIT_CPU,(case['cpu_seconds'],case['cpu_seconds']))
        payload=target/'result.json';receipt=target/'receipt.json'
        if 'source_id' in case and identity()!=case['source_id']:raise ValueError('source code changed after planning')
        if receipt.exists():
            r=json.loads(receipt.read_text())
            if r['case']!=expected:raise ValueError('receipt case mismatch')
            a.read(payload,r['payload_sha256'])
            return r
        if payload.exists():payload.rename(target/f'unreceipted_{time.time_ns()}.json')
        if layer==1:trains=initial_trains(case['run_id'],t)
        else:
            trains=[]
            needed={(lane-1)%12,lane,(lane+1)%12}
            for j,source in enumerate(case['sources']):
                if j not in needed:
                    trains.append(())
                    continue
                data=a.read(source['path'],source['sha256'])
                if data['case']['layer']!=layer-1 or data['case']['lane']!=j:raise ValueError('wrong source cell')
                if data['case']['run_id']!=case['run_id'] or data['case']['kernel_id']!=case['kernel_id']:raise ValueError('wrong source identity')
                trains.append(data['outputs'])
        result=engine.compute_cell(layer,lane,trains,case['run_id']+f'/cell/{layer}/{lane}')
        if 'source_id' in case and identity()!=case['source_id']:raise ValueError('source code changed during calculation')
        result['case']=expected
        sha,check=a.write_checked(payload,result)
        r={'status':'research_cell_complete','case':expected,'payload_sha256':sha,'check':check,'metrics':result['metrics'],'total_seconds':time.perf_counter()-started}
        # Check five explicit views in addition to the complete typed payload.
        reread=a.read(payload,sha)
        views={'state':lambda x:x['state'],'emissions':lambda x:x['outputs'],
               'time_dependencies':lambda x:tuple((q.token(),q.expression()) for q in x['outputs']),
               'provenance':lambda x:x['case'],'complete':lambda x:x}
        r['comparisons']={}
        for name,view in views.items():
            before=a.canonical_hash(a.Encoder().encode(view(result)))
            after=a.canonical_hash(a.Encoder().encode(view(reread)))
            if before!=after:raise ValueError('fresh/disk comparison failed: '+name)
            r['comparisons'][name]={'fresh':before,'disk':after,'equal':True}
        r['peak_rss_after_checks_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        a.atomic_json(receipt,r)
        return r
    except BaseException as e:
        import traceback
        failure={'status':'not_certified','type':type(e).__name__,'traceback':traceback.format_exc(),'case':expected}
        if hasattr(e,'forest') and hasattr(e,'continuation'):
            fs,fc=a.write_checked(target/'unresolved_forest.json',{'forest':e.forest,'continuation':e.continuation,'case':expected})
            failure['unresolved_forest_sha256']=fs
        a.atomic_json(target/'refusal.json',failure)
        raise

def verify_layer(root,n,kernel_id,run_id):
    _,a,_=initialize(root/'verification_diagnostics')
    p=root/f'layer_{n:02d}';rows=[]
    expected_parents=[]
    if n>1:
        expected_parents=[a.file_hash(root/f'layer_{n-1:02d}'/f'cell_{j:02d}'/'receipt.json') for j in range(12)]
    for lane in range(12):
        r=json.loads((p/f'cell_{lane:02d}'/'receipt.json').read_text())
        case=r['case']
        if case!={'run_id':run_id,'kernel_id':kernel_id,'layer':n,'lane':lane,'parent_receipts':expected_parents}:raise ValueError('layer lineage mismatch')
        if r['status']!='research_cell_complete' or set(r['comparisons'])!={'state','emissions','time_dependencies','provenance','complete'}:raise ValueError('incomplete comparison receipt')
        data=a.read(p/f'cell_{lane:02d}'/'result.json',r['payload_sha256'])
        if data['case']!=case:raise ValueError('payload lineage mismatch')
        if a.canonical_hash(a.Encoder().encode(data))!=r['check']['typed_content_sha256']:raise ValueError('typed digest mismatch')
        views={'state':lambda x:x['state'],'emissions':lambda x:x['outputs'],
               'time_dependencies':lambda x:tuple((q.token(),q.expression()) for q in x['outputs']),
               'provenance':lambda x:x['case'],'complete':lambda x:x}
        for name,v in r['comparisons'].items():
            if v['equal'] is not True or v['fresh']!=v['disk']:raise ValueError('failed comparison')
            actual=a.canonical_hash(a.Encoder().encode(views[name](data)))
            if actual!=v['fresh']:raise ValueError('comparison view digest mismatch: '+name)
        rows.append(r)
    a.atomic_json(p/'verification.json',{'kernel_id':kernel_id,'run_id':run_id,'layer':n,'receipts':[a.file_hash(p/f'cell_{j:02d}'/'receipt.json') for j in range(12)],'payloads':[r['payload_sha256'] for r in rows]})
    return rows

def zip_run(root,layer):
    """Layers 1..layer only: a pipelined later layer is never shipped as accepted."""
    path=root.parent/(root.name+f'_through_{layer:02d}.zip');tmp=path.with_suffix('.zip.tmp')
    def wanted(p):
        top=p.relative_to(root).parts[0]
        if top.startswith('layer_'):return int(top[6:])<=layer
        return top!='controller.lock'
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file() and not p.name.endswith('.tmp') and wanted(p):z.write(p,str(Path(root.name)/p.relative_to(root)))
    with zipfile.ZipFile(tmp) as z:
        if z.testzip() is not None:raise ValueError('ZIP CRC verification failed')
    os.replace(tmp,path)
    return str(path)

def proven_rows(root,n,kernel_id,run_id,_a):
    """Reuse a fresh verifier decision only while every file it covered is byte-identical."""
    p=root/f'layer_{n:02d}';proof=json.loads((p/'verification.json').read_text())
    if (proof['kernel_id'],proof['run_id'],proof['layer'])!=(kernel_id,run_id,n):raise ValueError('wrong verification proof')
    rows=[]
    for j in range(12):
        d=p/f'cell_{j:02d}'
        if _a.file_hash(d/'receipt.json')!=proof['receipts'][j] or _a.file_hash(d/'result.json')!=proof['payloads'][j]:raise ValueError('files changed after verification')
        rows.append(json.loads((d/'receipt.json').read_text()))
    return rows,proof

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--through',type=int,required=True)
    ap.add_argument('--workers',type=int,choices=range(1,13),default=8)
    ap.add_argument('--memory-mib',type=int,default=1536,help='per-worker virtual memory budget, not an environment quota')
    ap.add_argument('--cpu-seconds',type=int,default=14400,help='per-worker process CPU budget; 0 disables')
    ap.add_argument('--verify-layer',type=int);ap.add_argument('--zip-each-layer',action='store_true')
    ap.add_argument('--epsilon',default=os.environ.get('A22_PHYSICAL_EPSILON','1e-4'),help='relative physical-parameter half-width; initial delta stays 1e-5')
    args=ap.parse_args()
    from experiment_parameters import validate_epsilon
    try:epsilon=validate_epsilon(args.epsilon)
    except Exception as exc:ap.error(str(exc))
    os.environ['A22_PHYSICAL_EPSILON']=epsilon
    # validate_epsilon is imported before the CLI value is installed; synchronize
    # this controller's module before importing the engine. Children import fresh.
    import experiment_parameters
    experiment_parameters.PHYSICAL_EPSILON=epsilon
    if not 1<=args.through<=18:ap.error('--through must be 1..18')
    if args.memory_mib<0 or args.cpu_seconds<0:ap.error('budgets must be nonnegative')
    root=args.out.resolve();root.mkdir(parents=True,exist_ok=True)
    from contextlib import ExitStack
    with ExitStack() as stack:
        # An OS lock prevents two controllers from sharing a mutable campaign.
        lock=None
        if not args.verify_layer:
            import fcntl
            lock=stack.enter_context((root/'controller.lock').open('a+'))
            try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('another controller owns this campaign directory')
        _,a,_=initialize(root/'diagnostics')
        import rounding,importlib.metadata as md
        env={'python':platform.python_version(),'numpy':md.version('numpy'),'scipy':md.version('scipy'),'arithmetic_backend':rounding.BACKEND}
        if rounding.BACKEND=='native':
            import _rounding_native
            env['native_sha256']=a.file_hash(_rounding_native.__file__)
        frozen_source_id=identity()
        parameters={'epsilon_relative':epsilon,'initial_delta':'1e-5',
                    'training_calendar':{'count':28,'gap':'8','first':'0','last':'216',
                                         'source_lane':0,'terminal_time':'230'}}
        kernel_id=a.canonical_hash({'sources':frozen_source_id,'environment':env,'parameters':parameters,'precision':160,'symbols':affine_iv_kmax()})
        config=root/'campaign.json'
        if config.exists():
            cfg=json.loads(config.read_text())
            if cfg['kernel_id']!=kernel_id:raise ValueError('changed kernel/environment: use a new output directory')
        else:
            import uuid
            cfg={'schema':'A22-affine-research-campaign-1','run_id':uuid.uuid4().hex,'kernel_id':kernel_id,'environment':env,'parameters':parameters,'scientific_status':'experimental_not_qualified'}
            a.atomic_json(config,cfg)
        if args.verify_layer:
            verify_layer(root,args.verify_layer,kernel_id,cfg['run_id']);print('VERIFIED',args.verify_layer,flush=True);return
        from concurrent.futures import ProcessPoolExecutor,as_completed
        import multiprocessing as mp
        # Fresh process per cell, started with spawn (one new interpreter per cell):
        # environment adaptation, Unix sockets required by forkserver are forbidden.
        ctx=mp.get_context('spawn')
        pending=None   # fresh verification of the previous layer, overlapped with this layer
        def launch_verifier(n,timing):
            cmd=[sys.executable,'-B',str(ROOT/'run.py'),'--out',str(root),'--through',str(n),'--verify-layer',str(n),'--epsilon',epsilon]
            return {'layer':n,'proc':subprocess.Popen(cmd),'timing':timing,'launched':time.perf_counter(),'launched_wall':time.time()}
        def accept(job,used_receipts=None):
            n=job['layer'];rc=job['proc'].wait();done=time.perf_counter()
            if identity()!=frozen_source_id:raise ValueError('source code changed during campaign; use a new output directory')
            if rc!=0:raise RuntimeError(f'fresh verification of layer {n} failed (exit {rc})')
            # Verifier's own duration: from launch to its verification.json write.
            vdur=(root/f'layer_{n:02d}'/'verification.json').stat().st_mtime-job['launched_wall']
            rows,proof=proven_rows(root,n,kernel_id,cfg['run_id'],a)
            if used_receipts is not None and proof['receipts']!=used_receipts:raise ValueError('next layer consumed receipts other than the verified ones')
            t=job['timing'];layer_dir=root/f'layer_{n:02d}'
            ph={'planning':t['planned']-t['started'],'workers_and_cache':t['worked']-t['planned'],'revalidation':vdur,'waited_for_revalidation':done-job['launched'],
                'revalidation_overlapped_with_next_layer':used_receipts is not None}
            a.atomic_json(layer_dir/'complete.json',{'status':'research_layer_complete','layer':n,'elapsed_seconds':t['worked']-t['started']+vdur,
                'critical_path_seconds':t['worked']-t['started'],'phase_seconds':ph,
                'receipts':[a.file_hash(layer_dir/f'cell_{j:02d}'/'receipt.json') for j in range(12)],'scientific_status':'experimental_not_qualified'})
            with (layer_dir/'cells.tsv').open('w') as f:
                f.write('lane\tpulses\tclusters\torders\tcompute_seconds\tpeak_rss_kib\tmax_width\n')
                for r in rows:
                    m=r['metrics'];f.write('\t'.join(str(m[k]) for k in ('lane','pulses','clusters','orders','elapsed_seconds','peak_rss_kib','max_width'))+'\n')
            print('LAYER',n,'RESEARCH COMPLETE',round(t['worked']-t['started'],3),'s compute+plan;',round(ph['revalidation'],3),'s fresh verification'+(' (overlapped)' if used_receipts is not None else ''),flush=True)
            if args.zip_each_layer:
                zs=time.perf_counter();zp=zip_run(root,n)
                a.atomic_json(layer_dir/'delivery.json',{'zip':Path(zp).name,'zip_sha256':a.file_hash(zp),'zip_seconds':time.perf_counter()-zs})
                print('ZIP VERIFIED',zp,flush=True)
            return rows
        prev_rows=None
        for n in range(1,args.through+1):
            layer_dir=root/f'layer_{n:02d}';layer_dir.mkdir(exist_ok=True)
            if (layer_dir/'complete.json').exists():
                prev_rows=verify_layer(root,n,kernel_id,cfg['run_id']);print('REUSED LAYER',n,flush=True);continue
            started=time.perf_counter();parents=[];sources=[]
            if n>1:
                if pending is not None and pending['layer']==n-1:
                    # Hash-bound receipts of n-1; layer n is accepted only after n-1 passes.
                    prev=root/f'layer_{n-1:02d}'
                    prev_rows=[json.loads((prev/f'cell_{j:02d}'/'receipt.json').read_text()) for j in range(12)]
                elif (root/f'layer_{n-1:02d}'/'verification.json').exists():
                    prev_rows,_=proven_rows(root,n-1,kernel_id,cfg['run_id'],a)
                else:prev_rows=verify_layer(root,n-1,kernel_id,cfg['run_id'])
                for j,r in enumerate(prev_rows):
                    d=root/f'layer_{n-1:02d}'/f'cell_{j:02d}'
                    parents.append(a.file_hash(d/'receipt.json'));sources.append({'path':str(d/'result.json'),'sha256':r['payload_sha256']})
            cases=[{'run_dir':str(root),'run_id':cfg['run_id'],'kernel_id':kernel_id,'layer':n,'lane':j,'parent_receipts':parents,'sources':sources,'memory_mib':args.memory_mib,'cpu_seconds':args.cpu_seconds,'source_id':frozen_source_id} for j in range(12)]
            # Longest expected cells first (previous-layer cost of the three source lanes).
            if prev_rows:
                cost=lambda j:sum(prev_rows[k]['metrics']['elapsed_seconds'] for k in ((j-1)%12,j,(j+1)%12))
                cases.sort(key=lambda c:-cost(c['lane']))
            planned=time.perf_counter()
            with ProcessPoolExecutor(max_workers=args.workers,mp_context=ctx,max_tasks_per_child=1) as pool:
                futures={pool.submit(worker,c):c['lane'] for c in cases}
                try:
                    for future in as_completed(futures):
                        r=future.result();print('CELL',n,r['case']['lane'],'COMPLETE',round(r['metrics']['elapsed_seconds'],3),'s',flush=True)
                except BaseException as exc:
                    a.atomic_json(layer_dir/'stopped.json',{'status':'not_certified','layer':n,'exception_type':type(exc).__name__,'reason':str(exc),'completed_receipts':[str(p.relative_to(layer_dir)) for p in sorted(layer_dir.glob('cell_*/receipt.json'))]})
                    for f in futures:f.cancel()
                    # The previous layer still receives its full fresh verification.
                    if pending is not None:accept(pending,None);pending=None
                    raise
            worked=time.perf_counter()
            if pending is not None:accept(pending,parents);pending=None
            pending=launch_verifier(n,{'started':started,'planned':planned,'worked':worked})
        if pending is not None:accept(pending,None)

if __name__=='__main__':main()
