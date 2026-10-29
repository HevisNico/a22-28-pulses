"""Read-only A22 audit. Standard library only; never imports or runs A22 code.
Usage: python3 audit_provenance.py UPLOAD_DIRECTORY OUTPUT_DIRECTORY
"""
import sys, json, hashlib, re
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from fractions import Fraction as F
from decimal import Decimal, localcontext, ROUND_FLOOR, ROUND_CEILING


def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def jread(z,n): return json.loads(z.read(n))
def dump(p,x): p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')

def child_indices(n):
    if n[0] in ('list','tuple'):return n[1]
    if n[0]=='dict':return [i for pair in n[1] for i in pair]
    if n[0]=='record':return [i for k,i in n[3]]
    if n[0]=='time':return [n[2],n[4]]
    return []

class DAG:
    def __init__(self,doc):
        assert doc['schema']=='A22-affine-research-DAG-1'
        self.doc=doc; self.ns=doc['nodes']; self.cache={}
        for i,n in enumerate(self.ns):
            assert n[0] in ('scalar','float','decimal','affine','time','list','tuple','dict','record')
            assert all(type(j) is int and 0<=j<i for j in child_indices(n))
        assert 0<=doc['root']<len(self.ns)
    def fields(self,i):
        n=self.ns[i];assert n[0]=='dict'
        pairs=[(self.simple(k),v) for k,v in n[1]];d=dict(pairs)
        assert len(d)==len(pairs);return d
    def simple(self,i):
        if i in self.cache:return self.cache[i]
        n=self.ns[i];t=n[0]
        if t in ('scalar','decimal'):v=n[1]
        elif t=='float':v=float.fromhex(n[1])
        elif t in ('list','tuple'):v=[self.simple(j) for j in n[1]]
        elif t=='dict':v={k:self.simple(j) for k,j in self.fields(i).items()}
        elif t=='affine':v={'type':'affine','center_lo':n[1],'center_hi':n[2],'coefficients_hex':n[3],'error_hex':n[4]}
        elif t=='time':v={'type':'time','key':n[1],'base':self.simple(n[2]),'offset':n[3],'terms':self.simple(n[4])}
        elif t=='record':v={'type':n[1]+'.'+n[2],'fields':{k:self.simple(j) for k,j in n[3]}}
        self.cache[i]=v;return v
    def subgraph(self,root):
        out=[];memo={}
        def visit(i):
            if i in memo:return memo[i]
            n=list(self.ns[i]);t=n[0]
            if t in ('list','tuple'):n[1]=[visit(j) for j in n[1]]
            elif t=='dict':n[1]=[[visit(k),visit(v)] for k,v in n[1]]
            elif t=='record':n[3]=[[k,visit(j)] for k,j in n[3]]
            elif t=='time':n[2]=visit(n[2]);n[4]=visit(n[4])
            memo[i]=len(out);out.append(n);return memo[i]
        rootnew=visit(root)
        return {'schema':self.doc['schema'],'nodes':out,'root':rootnew}
    def affine_bounds(self,i):
        n=self.ns[i];assert n[0]=='affine'
        radius=sum((abs(F(float.fromhex(v))) for k,v in n[3]),F(0))+F(float.fromhex(n[4]))
        assert F(float.fromhex(n[4]))>=0
        return F(n[1])-radius,F(n[2])+radius

def outward(x,upper=False):
    with localcontext() as c:
        c.prec=90;c.rounding=ROUND_CEILING if upper else ROUND_FLOOR
        return str(Decimal(x.numerator)/Decimal(x.denominator))


def main():
    if not __debug__:raise RuntimeError('Run without -O; validation assertions are required.')
    folder=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    def locate(prefix):
        xs=list(folder.glob(prefix+'*.zip'));assert len(xs)==1,(prefix,xs);return xs[0]
    paths={k:locate(p) for k,p in [('source','A22_fresh_launch_v3_3_EN'),('layer18','A22_v33_layer_18'),('receipts','A22_v33_verifications_and_receipts'),('summary','A22_v33_summary_h1h2')]}
    zs={k:ZipFile(p) for k,p in paths.items()};inventory={}
    for k,z in zs.items():
        assert len(z.namelist())==len(set(z.namelist()))
        assert all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts for n in z.namelist())
        assert z.testzip() is None
        inventory[k]={'filename':paths[k].name,'sha256':sha(paths[k].read_bytes()),'bytes':paths[k].stat().st_size,'members':len(z.namelist())}
    sz,lz,rz,bz=(zs[k] for k in ('source','layer18','receipts','summary'))
    cfg=jread(bz,'campaign.json');assert cfg==jread(lz,'A22_v33_001/campaign.json')
    source={n.split('/',1)[1]:sz.read(n) for n in sz.namelist() if not n.endswith('/')}
    used={n[len('program_used/'):]:lz.read(n) for n in lz.namelist() if n.startswith('program_used/') and not n.endswith('/')}
    assert all(used.get(n)==b for n,b in source.items())
    extra=sorted(set(used)-set(source));assert all(n.endswith('.so') for n in extra)
    source_sum_checks=0
    for line in source['SHA256SUMS'].decode().splitlines():
        if not line.strip():continue
        h,n=line.split(maxsplit=1);n=n.lstrip('*')
        assert sha(source[n])==h,(n,'package checksum');source_sum_checks+=1
    names=sorted(n for n in used if n in ('run.py','build_native.py','build_all_native.py','launch_fresh.py','reference/full_model_reference.md') or (PurePosixPath(n).parts[0] in ('affine','kernel') and '__pycache__' not in PurePosixPath(n).parts and PurePosixPath(n).suffix in ('.py','.c','.h','.so','.pyd','.dll','.dylib')))
    hh=hashlib.sha256()
    for n in names:hh.update(n.encode()+b'\0');hh.update(used[n])
    source_id=hh.hexdigest()
    assert re.search(rb'^KMAX\s*=\s*256\b',used['affine/affine_iv.py'],re.M)
    kernel_id=sha(canonical({'sources':source_id,'environment':cfg['environment'],'precision':160,'symbols':256}))
    assert kernel_id==cfg['kernel_id'],('kernel identity mismatch',kernel_id)
    native=[n for n in extra if n.startswith('affine/_rounding_native.')];assert len(native)==1
    assert sha(used[native[0]])==cfg['environment']['native_sha256']
    rows=[];prev=[];receipts={};total_pulses=0
    for layer in range(1,19):
        verification=jread(rz,f'layer_{layer:02d}/verification.json')
        complete=jread(bz,f'layer_{layer:02d}/complete.json')
        assert verification['run_id']==cfg['run_id'] and verification['kernel_id']==kernel_id and verification['layer']==layer
        assert complete['status']=='research_layer_complete' and complete['layer']==layer
        hashes=[];payloads=[]
        for lane in range(12):
            path=f'layer_{layer:02d}/cell_{lane:02d}/receipt.json';raw=rz.read(path);r=json.loads(raw);receipts[layer,lane]=r
            assert r['case']==dict(run_id=cfg['run_id'],kernel_id=kernel_id,layer=layer,lane=lane,parent_receipts=prev)
            assert r['status']=='research_cell_complete' and r['check']['full_content_equal'] is True
            assert r['payload_sha256']==r['check']['typed_content_sha256']
            assert set(r['comparisons'])=={'complete','state','emissions','time_dependencies','provenance'}
            assert all(v['equal'] is True and v['fresh']==v['disk'] for v in r['comparisons'].values())
            assert r['comparisons']['complete']['disk']==r['payload_sha256']
            assert (r['metrics']['layer'],r['metrics']['lane'])==(layer,lane)
            total_pulses+=r['metrics']['pulses'];hashes.append(sha(raw));payloads.append(r['payload_sha256'])
        assert hashes==verification['receipts']==complete['receipts']
        assert payloads==verification['payloads']
        rows.append(dict(layer=layer,receipt_hashes=hashes,payload_hashes=payloads,parent_chain_verified=True));prev=hashes
    assert total_pulses==21302
    for name in ['verification.json','complete.json','cells.tsv']:
        zz=rz if name=='verification.json' else bz
        assert lz.read('A22_v33_001/layer_18/'+name)==zz.read('layer_18/'+name)
    terminals=[];payload_checks=[]
    for lane in range(12):
        base=f'layer_18/cell_{lane:02d}/';r=receipts[18,lane]
        assert lz.read('A22_v33_001/'+base+'receipt.json')==rz.read(base+'receipt.json')
        raw=lz.read('A22_v33_001/'+base+'result.json');assert sha(raw)==r['payload_sha256']
        doc=json.loads(raw);assert sha(canonical(doc))==r['check']['typed_content_sha256']
        d=DAG(doc);root=d.fields(doc['root']);assert d.simple(root['case'])==r['case'];assert d.simple(root['metrics'])==r['metrics']
        assert len(doc['nodes'])==r['check']['nodes']
        for view,key in [('state','state'),('emissions','outputs'),('provenance','case')]:
            assert sha(canonical(d.subgraph(root[key])))==r['comparisons'][view]['disk'],(lane,view)
        sf=d.fields(root['state']);tf=d.fields(sf['terminal_affine'])
        selected=['q','g','b','E','m','main_phase','aux_phases','pending','caps','b_stop','gain_stops','actuation_summary','deposit_summary']
        entry={k:d.simple(sf[k]) for k in selected}
        entry.update(layer=18,lane=lane,payload_sha256=r['payload_sha256'],state_sha256=r['comparisons']['state']['disk'])
        entry['terminal_fields']={k:d.simple(tf[k]) for k in ['t','p','raw','aux','caps','bstop']}
        time=entry['terminal_fields']['t'];assert time['key']=='clock' and F(time['offset'])==1116
        tn=d.ns[tf['t']];assert d.affine_bounds(tn[2])==(F(0),F(0))
        for term in d.ns[tn[4]][1]:
            atom=d.ns[term][1][2];assert d.affine_bounds(atom)==(F(0),F(0))
        assert entry['main_phase']==0 and entry['aux_phases']==[0]*3 and entry['pending']==[]
        assert entry['terminal_fields']['p']==0 and entry['terminal_fields']['aux']==[0]*3
        assert entry['terminal_fields']['raw']==[None]*3
        entry['cached_auxiliary_origin_slots_present']={k:[d.ns[i]!=['scalar',None] for i in d.ns[tf[k]][1]] for k in ['mark','err']}
        assert [F(x) for x in entry['q']]==[F(1,10)]*2
        assert all([F(x) for x in m]==[F(1,40)]*2 for m in entry['m'])
        assert F(entry['b'][0])>=F('0.07999')-F('1e-18') and F(entry['b'][1])<=F('1.1')
        # Literal affine-form bounds use exact rational arithmetic, independently of engine floating sums.
        entry['literal_affine_bounds']={}
        for key in ['q','b']:
            lo,hi=d.affine_bounds(tf[key]);box=[F(x) for x in entry[key]]
            assert box[0]<=lo<=hi<=box[1]
            entry['literal_affine_bounds'][key]={'lo':str(lo),'hi':str(hi)}
        z_nodes=d.ns[tf['z']];assert z_nodes[0]=='list'
        entry['literal_affine_bounds']['z']=[{'lo':str(a),'hi':str(b)} for a,b in (d.affine_bounds(i) for i in z_nodes[1])]
        wp=d.fields(sf['width_profile']);proofs=d.simple(wp['relative_order_proofs'])
        counts={name:sum(p.get('guard')==name for p in proofs) for name in ['no_fire_cover','recovery_group_local_cycle','fire_arrival_commutation']}
        entry['recorded_guard_counts']=counts
        payload_checks.append(dict(lane=lane,nodes=len(doc['nodes']),payload_bytes=len(raw),payload_hash_verified=True,canonical_DAG_hash_verified=True,subview_hashes_verified=['state','emissions','provenance'],time_dependencies_subview_hash_recomputed=False,**counts))
        terminals.append(entry)
        print('Layer 18 lane',lane,'verified',flush=True)
    audit=dict(scope='Read-only artifact integrity and exact stored terminal-state audit; not campaign replay or mathematical soundness qualification',inputs=inventory,campaign=cfg,source_identity=dict(original_source_files_identical=len(source),package_checksums_verified=source_sum_checks,extra_built_extensions=extra,identity_files=len(names),sources_sha256=source_id,recomputed_kernel_id=kernel_id,kernel_id_match=True),receipt_chain=dict(cells=216,layers=18,total_pulses=total_pulses,layers_detail=rows),layer18_payload_checks=payload_checks,missing_full_payloads=204,limitations=['Layers 1-17 payload hashes are linked by receipts, but their bytes are not supplied.','Recorded fresh/disk comparisons are serialization checks, not independent physical computations.','The time_dependencies subview hash is not separately reconstructed in this passive audit; the entire stored DAG is authenticated.','Source identity matches using the recorded environment; this does not independently attest the runtime environment or the whole execution history.','Exact stored enclosures still require mathematical soundness and coverage justification.'])
    dump(out/'audit.json',audit)
    dump(out/'layer18_terminal_exact.json',dict(schema='A22-passive-terminal-extraction-1',run_id=cfg['run_id'],kernel_id=kernel_id,time='1116',status='exact stored data; physical entry conditional on enclosure soundness',cells=terminals))
    with (out/'layer18_terminal_readable.tsv').open('w') as f:
        f.write('lane\tq_lo\tq_hi\tb_lo\tb_hi\tg0_lo\tg0_hi\tg1_lo\tg1_hi\tg2_lo\tg2_hi\n')
        for e in terminals:
            bounds=e['q']+e['b']+[x for pair in e['g'] for x in pair]
            f.write(str(e['lane'])+'\t'+'\t'.join(outward(F(x),i%2==1) for i,x in enumerate(bounds))+'\n')
    print(json.dumps({'kernel_match':True,'receipts':216,'layer18_results':12,'source_files':len(source),'identity_files':len(names),'terminal_cells':len(terminals)}))

if __name__=='__main__':main()
