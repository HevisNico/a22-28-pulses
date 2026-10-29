from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
import campagne_A22 as campaign
import groupe_pret_feu_A22 as solver
import histoires_A21 as h
import cycle_local_A20 as cyc
import validation_A15 as b
import dependances_A17 as dep
import actuations_A19 as ac
import depot_A19 as dz
import intervalles_decimaux as iv
from intervalles_decimaux import I,D
iv.configure(160);b.settings('0','0');b.PROFILE=None
T=dep.Time('start',I(0));events=[]
for j in range(2):
 a=dep.Time(f'arrival:{j}',I('.1','.12') if j==0 else I('.105','.125'))
 m=b.shift(a,b.D0,f'm:{j}');off=b.shift(m,b.DM,f'off:{j}');err=b.shift(off,b.DS,f'err:{j}');end=b.shift(err,b.DE,f'end:{j}')
 events.extend((t,((action,j,origin),)) for t,action,origin in [(a,'raw_on',a),(m,'mark_on',m),(off,'mark_off',m),(a.plus(1),'raw_off',a),(err,'error_on',err),(end,'error_off',err)])
pending=tuple(sorted(events,key=lambda e:e[0].box().mid()));suffix=[D('Infinity')]*(len(pending)+1)
for k in range(len(pending)-1,-1,-1):suffix[k]=min(suffix[k+1],pending[k][0].box().lo)
def initial(g):
 s=dict(t=T,q=I('.95'),p=0,fire=None,b=I('.3'),bstop=False,z=[g.ln(),g.ln(),I('.3').ln()],caps=[False]*3,
 raw=[None]*3,aux=[0]*3,mark=[None]*3,err=[None]*3)
 s['memory']=b.new_memory(s);s['depot']=tuple((dz.History(z),) for z in s['z']);s['actuation']=(ac.History(s['b']),)
 return h.History(cyc.Branch(s,(dep.Time('older-emission',I(-10)),)))
low=solver.resolve(initial(I('.01')),pending,suffix,'low')
assert low and all(len(x.branch.emissions)==1 for x in low)
mixed=solver.resolve(initial(I('.01',4)),pending,suffix,'mixed')
assert {len(x.branch.emissions) for x in mixed}=={1,2}
assert all(x.branch.emissions[0].key=='older-emission' for x in mixed)
assert all(len(x.branch.emissions)<=2 for x in mixed)
for x in mixed:
 if len(x.branch.emissions)==2:assert x.branch.state['p']==1
 else:assert x.branch.state['p']==0
r=dict(status='pass',quiet_branches=len(low),conditional_branches=len(mixed),parent_prefix_kept=True,additional_pulse_counts=[0,1],physical_mark_sections=True)
(ROOT/'test_groupe_pret_feu_A22.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
