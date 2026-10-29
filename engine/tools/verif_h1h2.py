"""Read-only H1/H2 diagnostic replay of one cell, including no-fire covers.

H1 checks absence of an earlier threshold crossing before a recorded fire.
H2 independently subdivides the full READY window and checks Q<1 throughout.
The evaluator and interval arithmetic are shared with the research engine;
this is a separate guard argument, not an independent arithmetic verifier.
Inconclusive enclosures do not establish a physical counterexample.

Example: python -B tools/verif_h1h2.py --campaign RUN --layer 18 --lane 4
Exit0: complete replay, every checked decision proved. Exit1: unproved checks.
Exit2: replay failed/incomplete. Setup/identity failures also exit nonzero.
No campaign files are written. An optional --out must be outside the campaign.
"""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D, localcontext
import argparse, hashlib, importlib.metadata as md, json, os, platform, sys, tempfile, time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'affine'))
sys.path.insert(0,str(ROOT))


def midpoint(lo,hi):
    with localcontext() as ctx:
        ctx.prec=180
        return (lo+hi)/2


class DecisionAudit:
    def __init__(self,b,I):
        self.b,self.I=b,I
        self.stats=Counter();self.counts=Counter();self.bad=[]

    def below_one(self,mem,t0,lo0,hi0,depth=16):
        stack=[(lo0,hi0,0)]
        while stack:
            lo,hi,n=stack.pop()
            q=self.b.dep.evaluate(mem,self.b.shift(t0,self.I(lo,hi),'h1h2-cover'))
            if q.hi<1:continue
            if n>=depth or hi-lo<D('1e-12'):return 'inconclusive'
            m=midpoint(lo,hi)
            if not lo<m<hi:return 'inconclusive'
            stack.append((m,hi,n+1));stack.append((lo,m,n+1))
        return 'proved'

    def no_earlier_crossing(self,mem,t0,rlo,rhi):
        u=D(0);step=rlo
        while u<rlo:
            with localcontext() as ctx:
                ctx.prec=180
                z=min(rlo,u+step)
            if z<=u:return 'inconclusive'
            q=self.b.dep.evaluate(mem,self.b.shift(t0,self.I(u,z),'h1h2-first'))
            if q.hi<1:
                u=z;step*=2;continue
            slope=self.b.dep.evaluate(mem,self.b.shift(t0,self.I(u,max(u,rhi)),'h1h2-first'),True)
            if slope.lo>0:return 'proved'
            step/=2
            if step<D('1e-13'):return 'inconclusive'
        return 'proved'

    def record(self,test,verdict,**detail):
        self.counts[test]+=1
        self.stats[f'{test}: {verdict}']+=1
        if verdict!='proved':self.bad.append(dict(test=test,verdict=verdict,**detail))

    def install_ready_checks(self):
        # The OUTERMOST advance includes causal handling AND nofire_cover.
        # Hooking engine.orig_advance would miss the fallback after a refusal.
        original=self.b.advance
        def checked(s,boundary,cell,count):
            profile=self.b.PROFILE
            before=len(profile.relative_order_proofs) if profile is not None else 0
            out=original(s,boundary,cell,count)
            if s['p']!=0 or s.get('memory') is None:return out
            new,kind=out;t0=s['t'];mem=s['memory']
            if kind=='fire':
                r=new['t'].minus(t0)
                verdict=self.no_earlier_crossing(mem,t0,r.lo,r.hi) if r.lo>0 else 'inconclusive'
                self.record('H1_fire',verdict,batch=count,root=r.pair())
            elif kind=='external':
                H=boundary.minus(t0)
                if H.hi>0:
                    added=profile.relative_order_proofs[before:] if profile is not None else []
                    covered=any(p.get('guard')=='no_fire_cover' for p in added)
                    test='H2_no_fire_cover' if covered else 'H2_standard'
                    # Recompute the entire window. Do not accept merely a
                    # safe endpoint and a safe prefix: an interior peak matters.
                    verdict=self.below_one(mem,t0,D(0),max(D(0),H.hi))
                    self.record(test,verdict,batch=count,window=H.pair())
            return out
        self.b.advance=checked

    def install_commutation_checks(self,commutation):
        last_root={};original_root=commutation._fire_root
        def root_spy(bb,s,H,cell,count):
            result=original_root(bb,s,H,cell,count);last_root[id(s)]=result
            return result
        commutation._fire_root=root_spy
        original_resolve=commutation.resolve
        def checked(bb,s,*rest):
            out=original_resolve(bb,s,*rest)
            if out is not None:
                found=last_root.get(id(s))
                verdict='inconclusive'
                if found is not None:
                    r=found[0]
                    if r.lo>0:verdict=self.no_earlier_crossing(s['memory'],s['t'],r.lo,r.hi)
                self.record('H1_commutation',verdict,fire=out[1].box().pair())
            last_root.pop(id(s),None)
            return out
        commutation.resolve=checked


def outcome(cell_complete,bad):
    return 2 if not cell_complete else (1 if bad else 0)


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--layer',type=int,required=True)
    parser.add_argument('--lane',type=int,required=True)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if not __debug__:raise RuntimeError('Python -O is forbidden')
    if not 1<=args.layer<=18 or not 0<=args.lane<=11:parser.error('Layer1..18, lane0..11 required')
    camp=args.campaign.resolve()
    if args.out is not None and args.out.resolve().is_relative_to(camp):parser.error('--out must be outside the read-only campaign')
    os.environ['A22_ARTIFACT_DIR']=tempfile.mkdtemp(prefix='a22_h1h2_')
    import engine,artifacts as a,temporal,rounding,run,commutation
    from affine_iv import I
    cfg=json.loads((camp/'campaign.json').read_text())
    env=dict(python=platform.python_version(),numpy=md.version('numpy'),scipy=md.version('scipy'),arithmetic_backend=rounding.BACKEND)
    if rounding.BACKEND=='native':
        import _rounding_native
        env['native_sha256']=a.file_hash(_rounding_native.__file__)
    kernel_id=a.canonical_hash(dict(sources=run.identity(),environment=env,precision=160,symbols=run.affine_iv_kmax()))
    if kernel_id!=cfg['kernel_id']:raise ValueError('Changed program/environment: diagnostic replay refused')
    run_id=cfg['run_id']
    if args.layer==1:
        trains=run.initial_trains(run_id,temporal)
    else:
        prev=camp/f'layer_{args.layer-1:02d}'
        proof=json.loads((prev/'verification.json').read_text())
        if (proof['run_id'],proof['kernel_id'],proof['layer'])!=(run_id,kernel_id,args.layer-1):raise ValueError('Wrong parent verification identity')
        trains=[()]*12
        for j in ((args.lane-1)%12,args.lane,(args.lane+1)%12):
            d=prev/f'cell_{j:02d}'
            if a.file_hash(d/'receipt.json')!=proof['receipts'][j]:raise ValueError('Parent receipt changed after verification')
            receipt=json.loads((d/'receipt.json').read_text())
            if receipt['payload_sha256']!=proof['payloads'][j]:raise ValueError('Parent payload digest mismatch')
            data=a.read(d/'result.json',proof['payloads'][j]);case=data['case']
            if (case['run_id'],case['kernel_id'],case['layer'],case['lane'])!=(run_id,kernel_id,args.layer-1,j):raise ValueError('Wrong parent payload identity')
            trains[j]=data['outputs']
    audit=DecisionAudit(engine.b,I)
    audit.install_ready_checks();audit.install_commutation_checks(commutation)
    started=time.perf_counter();complete=False;error=None
    try:
        engine.compute_cell(args.layer,args.lane,trains,f'h1h2/{run_id}/cell/{args.layer}/{args.lane}')
        complete=True
    except Exception as e:
        error=dict(type=type(e).__name__,message=str(e))
    code=outcome(complete,audit.bad)
    result=dict(layer=args.layer,lane=args.lane,run_id=run_id,kernel_id=kernel_id,
        status='complete' if complete else 'replay_failed',cell_complete=complete,
        all_checked_decisions_proved=complete and not audit.bad,exit_code=code,error=error,
        seconds=round(time.perf_counter()-started,1),
        decision_counts={key:audit.counts[key] for key in ('H1_fire','H1_commutation','H2_standard','H2_no_fire_cover')},
        decisions=dict(audit.stats),
        unproved_decision_count=len(audit.bad),unproved_decisions=audit.bad,
        tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='Diagnostic advance/commutation guard rechecks using the same interval evaluator; not every direct cluster-flow assertion, a campaign receipt or full kernel qualification')
    text=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if args.out is not None:
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(text)
    print(text,end='');raise SystemExit(code)


if __name__=='__main__':main()
