"""Read-only audit and exact terminal extraction from a campaign directory.

Same checks and same output format as proof/provenance_audit/audit_all_layers.py,
which reads the zipped v3.3 delivery; this version reads an output directory
(layer_NN/cell_NN/{receipt,result}.json). No engine import.
Usage: python3 -I extract_terminal.py <campaign dir> <output dir>
The terminal time is read from the campaign identity (training_calendar.terminal_time).
"""
import json,sys
from pathlib import Path
from fractions import Fraction as F
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_provenance import DAG,sha,canonical,dump

def main():
 if not __debug__:raise RuntimeError('Run without -O')
 root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
 cfg=json.loads((root/'campaign.json').read_text())
 TT=F(cfg['parameters']['training_calendar']['terminal_time']);TS=str(TT)
 cells=[];checks=[];totals={k:0 for k in ['no_fire_cover','recovery_group_local_cycle','fire_arrival_commutation']}
 for layer in range(1,19):
  base=root/f'layer_{layer:02d}'
  assert (base/'complete.json').exists() and (base/'verification.json').exists(),layer
  for lane in range(12):
   cd=base/f'cell_{lane:02d}'
   rb=(cd/'receipt.json').read_bytes();r=json.loads(rb)
   raw=(cd/'result.json').read_bytes();assert sha(raw)==r['payload_sha256'];doc=json.loads(raw)
   assert sha(canonical(doc))==r['check']['typed_content_sha256']
   d=DAG(doc);rt=d.fields(doc['root']);assert d.simple(rt['case'])==r['case'] and d.simple(rt['metrics'])==r['metrics']
   assert len(doc['nodes'])==r['check']['nodes']
   for view,key in [('state','state'),('emissions','outputs'),('provenance','case')]:
    assert sha(canonical(d.subgraph(rt[key])))==r['comparisons'][view]['disk'],(layer,lane,view)
   sf=d.fields(rt['state']);tf=d.fields(sf['terminal_affine'])
   selected=['q','g','b','E','m','main_phase','aux_phases','pending','caps','b_stop','gain_stops','actuation_summary','deposit_summary']
   entry={k:d.simple(sf[k]) for k in selected}
   entry.update(layer=layer,lane=lane,payload_sha256=r['payload_sha256'],state_sha256=r['comparisons']['state']['disk'],pulses=r['metrics']['pulses'])
   tn=d.ns[tf['t']];assert tn[0]=='time' and F(tn[3])==TT and d.affine_bounds(tn[2])==(F(0),F(0))
   for term in d.ns[tn[4]][1]:assert d.affine_bounds(d.ns[term][1][2])==(F(0),F(0))
   assert entry['main_phase']==0 and entry['aux_phases']==[0]*3 and entry['pending']==[]
   assert d.simple(tf['p'])==0 and d.simple(tf['aux'])==[0]*3 and d.simple(tf['raw'])==[None]*3
   entry['terminal_time']=TS;entry['raw_inputs']=[None]*3
   entry['q_is_exact_rest']=[F(x) for x in entry['q']]==[F('0.1')]*2
   entry['aux_is_exact_rest']=[list(map(F,m))==[F('.025')]*2 for m in entry['m']]
   entry['literal_affine_bounds']={}
   for key in ['q','b']:
    lo,hi=d.affine_bounds(tf[key]);box=list(map(F,entry[key]));assert box[0]<=lo<=hi<=box[1]
    entry['literal_affine_bounds'][key]=dict(lo=str(lo),hi=str(hi))
   assert F(entry['b'][0])>F('.07998') and F(entry['b'][1])<=F('1.1')
   zn=d.ns[tf['z']];assert zn[0]=='list'
   entry['literal_affine_bounds']['z']=[dict(lo=str(a),hi=str(b)) for a,b in (d.affine_bounds(i) for i in zn[1])]
   wp=d.fields(sf['width_profile']);proofs=d.simple(wp['relative_order_proofs'])
   counts={k:sum(p.get('guard')==k for p in proofs) for k in totals}
   for k,v in counts.items():totals[k]+=v
   entry['recorded_guard_counts']=counts
   cells.append(entry);checks.append(dict(layer=layer,lane=lane,nodes=len(doc['nodes']),bytes=len(raw),sha256=sha(raw)))
   del d,doc,raw
  print('Audited layer',layer,flush=True)
 assert len(cells)==216
 active=[c for c in cells if c['pulses']];inactive=[c for c in cells if not c['pulses']]
 assert all(c['q_is_exact_rest'] for c in active)
 report=dict(scope='All stored payloads and exact terminal states of one campaign directory; no engine execution and no physical soundness qualification',campaign=cfg,checks=checks,full_payloads_verified=len(cells),active_cells=len(active),inactive_cells=len(inactive),exact_rest_main_cells=sum(c['q_is_exact_rest'] for c in cells),exact_rest_aux_ports=sum(sum(c['aux_is_exact_rest']) for c in cells),pulses=sum(c['pulses'] for c in cells),recorded_guards=totals,gain_caps=[dict(layer=c['layer'],lane=c['lane'],port=j) for c in cells for j,v in enumerate(c['caps']) if v],missing_payloads=0)
 dump(out/'all_layers_audit.json',report)
 dump(out/'all_terminal_exact.json',dict(schema='A22-passive-terminal-extraction-1',campaign=cfg,time=TS,status='exact stored enclosures; physical entry conditional on engine soundness',cells=cells))
 print(json.dumps({k:report[k] for k in ['full_payloads_verified','active_cells','inactive_cells','exact_rest_main_cells','exact_rest_aux_ports','pulses','recorded_guards','gain_caps']}))

if __name__=='__main__':main()
