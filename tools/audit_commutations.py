"""Read-only audit of the recorded fire/exterior commutations of a campaign directory.

Extracts every recorded fire_arrival_commutation and reports event patterns, branch
counts and widening diagnostics. The all_* fields describe the historical single
mark_off case of Section 8(vi); they are diagnostics, not acceptance conditions.
The 28-pulse campaign also has raw_on/mark_on/mark_off, raw_off and error_on groups,
covered by the general lemma E in proof/extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt.
This script checks payload hashes and summarizes records; it does not independently
prove lemma E or event-order coverage. No engine import.
Usage: python3 -I audit_commutations.py <campaign dir> <output.json>
"""
import json,sys
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_provenance import DAG,sha,canonical,dump

def main():
 if not __debug__:raise RuntimeError('Run without -O')
 root=Path(sys.argv[1]);dest=Path(sys.argv[2])
 cfg=json.loads((root/'campaign.json').read_text())
 records=[]
 for layer in range(1,19):
  for lane in range(12):
   cd=root/f'layer_{layer:02d}'/f'cell_{lane:02d}'
   r=json.loads((cd/'receipt.json').read_bytes())
   raw=(cd/'result.json').read_bytes();assert sha(raw)==r['payload_sha256'];doc=json.loads(raw)
   assert sha(canonical(doc))==r['check']['typed_content_sha256']
   d=DAG(doc);sf=d.fields(d.fields(doc['root'])['state'])
   proofs=d.simple(d.fields(sf['width_profile'])['relative_order_proofs'])
   records+=[dict(p,layer=layer,lane=lane) for p in proofs if p.get('guard')=='fire_arrival_commutation']
   del d,doc,raw
  print('Audited layer',layer,flush=True)
 patterns=Counter(json.dumps(p['events']) for p in records)
 report=dict(
  scope='Recorded fire_arrival_commutation entries of one campaign directory; no engine execution',
  campaign=cfg,count=len(records),
  event_patterns=[dict(events=json.loads(k),count=v) for k,v in patterns.most_common()],
  branches={str(k):v for k,v in sorted(Counter(p['branches'] for p in records).items())},
  cells={f"{l},{n}":v for (l,n),v in sorted(Counter((p['layer'],p['lane']) for p in records).items())},
  first=records[0] if records else None,
  all_events_are_one_mark_off=all(p['events']==[['mark_off']] for p in records),
  all_widenings_zero=all(F(p['widening'])==0 for p in records),
  all_branch_counts_two=all(p['branches']==2 for p in records))
 dump(dest,report)
 print(json.dumps({k:report[k] for k in ['count','branches','cells','all_events_are_one_mark_off','all_widenings_zero','all_branch_counts_two']}))

if __name__=='__main__':main()
