"""Read-only compact campaign summary, including recorded no-fire covers.

python -B tools/bilan_campagne.py --campaign RUN --out campaign_summary.json
--skip-results reads receipts only. --reference optionally compares exact gain
boxes. Counts summarize stored records; they are not new guard proofs.
The output path must be outside the campaign directory.
"""
from pathlib import Path
from collections import defaultdict
from fractions import Fraction as F
import argparse, hashlib, json, os, re, sys, tempfile, time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'affine'))
PHYS=re.compile(r':(C|LM|LS|LE|M|q0|z\d|b0|D1:\d|(LM|LS|LE|M):\d)$')  # v3.3 per-port names
LAYER=re.compile(r'/cell/(\d+)/(\d+):')


def short(x,n=4):return float(f'{float(x):.{n}g}')


def decompose(x):
    phys=rem=0.0;by_layer=defaultdict(float)
    for key,value in x.d.items():
        m=LAYER.search(key);layer=int(m.group(1)) if m else 0
        if PHYS.search(key):phys+=abs(value)
        else:rem+=abs(value)
        by_layer[layer]+=abs(value)
    anon=float(x.chi-x.clo)/2+x.e;total=phys+rem+anon or 1.0
    return dict(width=short(x.width()),named_physical_symbol_share=round(phys/total,3),
        other_symbol_share=round(rem/total,3),anonymous_or_center_share=round(anon/total,3),
        symbols=len(x.d),top_origin_layers={str(k):short(v/total,3) for k,v in sorted(by_layer.items(),key=lambda kv:-kv[1])[:4]},
        limitation='Symbol-label heuristic, not a physical/numerical error separation; parameter-box uncertainty can enter anonymous and center widths')


def cover_summary(proofs):
    covers=[p for p in proofs if p.get('guard')=='no_fire_cover']
    maxima=[F(leaf[2]) for p in covers for leaf in p['cover']]
    return dict(recorded_no_fire_cover_decisions=len(covers),
        recorded_no_fire_cover_leaves=len(maxima),
        recorded_no_fire_cover_minimum_margin_exact=str(1-max(maxima)) if maxima else None,
        no_fire_covers_reverified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path('campaign_summary.json'))
    parser.add_argument('--skip-results',action='store_true',help='Read receipts only; omit payload-derived metrics')
    parser.add_argument('--reference',type=Path,help='Optional A14 reference gain-box JSON')
    args=parser.parse_args();camp=args.campaign.resolve()
    if args.out.resolve().is_relative_to(camp):parser.error('--out must be outside the read-only campaign')
    os.environ['A22_ARTIFACT_DIR']=tempfile.mkdtemp(prefix='a22_summary_')
    if not args.skip_results:import engine,artifacts as a
    cfg=json.loads((camp/'campaign.json').read_text())
    result=dict(kernel_id=cfg['kernel_id'],run_id=cfg['run_id'],environment=cfg.get('environment'),
        scientific_status=cfg.get('scientific_status','unknown'),layers=[],
        scope='Summary of recorded research outputs; stored completion markers are not mathematical qualification',
        tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    started=time.perf_counter();reference=json.loads(args.reference.read_text())['entry_gain_boxes'] if args.reference else None
    ref_total=ref_in=recorded_in=0
    for n in range(1,19):
        directory=camp/f'layer_{n:02d}'
        if not directory.exists():break
        layer=dict(layer=n,stored_research_completion_markers_present=(directory/'complete.json').exists() and (directory/'verification.json').exists())
        if (directory/'complete.json').exists():
            complete=json.loads((directory/'complete.json').read_text())
            layer.update(critical_path_seconds=round(complete.get('critical_path_seconds',0),1),
                revalidation_seconds=round(complete.get('phase_seconds',{}).get('revalidation',0),1),
                elapsed_seconds=round(complete.get('elapsed_seconds',0),1))
        cells=[]
        for lane in range(12):
            cd=directory/f'cell_{lane:02d}'
            if not (cd/'receipt.json').exists():
                cells.append(dict(lane=lane,status='refusal' if (cd/'refusal.json').exists() else 'absent'));continue
            receipt=json.loads((cd/'receipt.json').read_text());metrics=receipt['metrics']
            cell=dict(lane=lane,status=receipt['status'],pulses=metrics['pulses'],clusters=metrics['clusters'],orders=metrics['orders'],
                seconds=round(metrics['elapsed_seconds'],1),peak_rss_mib=round(metrics['peak_rss_kib']/1024),max_date_width=short(metrics['max_width']))
            if not args.skip_results:
                payload=a.read(cd/'result.json',receipt['payload_sha256']);state=payload['state'];profile=state['width_profile']
                proofs=profile['relative_order_proofs'];commutations=[p for p in proofs if p.get('guard')=='fire_arrival_commutation']
                cell.update(q_width=short(state['q_width']),b_width=short(state['b_width']),gain_width=short(state['width']),
                    gains=[[short(lo,6),short(hi,6)] for lo,hi in state['g']],gain_caps=state['caps'],
                    commutations=len(commutations),max_commutation_widening=short(max((float(p['widening']) for p in commutations),default=0)),
                    max_actuation_histories=profile['maximum_distinct_actuation_histories'],max_deposit_histories=profile['maximum_distinct_deposit_histories'])
                cell.update(cover_summary(proofs))
                cell['recovery_group_resolutions']=sum(1 for p in proofs if p.get('guard')=='recovery_group_local_cycle')
                if reference is not None:
                    ref_flags=[];recorded_flags=[]
                    for port,(lo,hi) in enumerate(state['g']):
                        left,right=map(F,reference[n-1][lane][port]);lo,hi=F(lo),F(hi)
                        contains=lo<=left<=right<=hi;contained=left<=lo<=hi<=right
                        ref_flags.append(contains);recorded_flags.append(contained);ref_total+=1;ref_in+=contains;recorded_in+=contained
                    cell['reference_box_inside_recorded_enclosure']=ref_flags
                    cell['recorded_enclosure_inside_reference_box']=recorded_flags
                if payload['outputs']:
                    cell['widest_date']=decompose(max(payload['outputs'],key=lambda t:t.box().width()).box())
            cells.append(cell)
        layer['cells']=cells;result['layers'].append(layer)
        print(f'Layer{n} read',flush=True)
    if reference is not None:
        result['exact_reference_comparison']=dict(total=ref_total,reference_inside_recorded=ref_in,recorded_inside_reference=recorded_in,
            meaning='Literal inclusion of supplied exact endpoint boxes; no physical entry or model coverage proof')
    result['seconds_to_summarise']=round(time.perf_counter()-started,1)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(f'{args.out}: {args.out.stat().st_size} bytes')


if __name__=='__main__':main()
