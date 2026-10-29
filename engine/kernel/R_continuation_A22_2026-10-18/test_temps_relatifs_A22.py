from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
import campagne_A22
import garde_relative_A22 as guards
import ordonnanceur_A22 as scheduler
import histoires_A21 as h
import cycle_local_A20 as cyc
import validation_A15 as b
import dependances_A17 as dep
import actuations_A19 as ac
import depot_A19 as dz
import intervalles_decimaux as iv
from intervalles_decimaux import I,D
iv.configure(160);b.settings('0','0');b.PROFILE=None
T=dep.Time('shared-phase',I(100,104));now=T.plus('.04')
s=dict(t=now,q=b.R+4*dep.h(I('.04')),p=0,fire=None,b=I('.3'),bstop=False,z=[b.Z,I('.3').ln(),I('.3').ln()],caps=[True,False,False],
 raw=[T,None,None],aux=[2,0,0],mark=[T.plus('.02'),None,None],err=[None]*3)
s['memory']=b.new_memory(s);s['actuation']=(ac.History(s['b']),);s['depot']=tuple((dz.History(z,clamped=cap),) for z,cap in zip(s['z'],s['caps']))
out=guards.ready_to(cyc.Branch(s),T.plus('.6'),'wide-clock')
assert len(out)==1 and len(out[0].emissions)==1
fire=out[0].emissions[0];lag=fire.minus(T)
assert D('.19')<lag.lo<=lag.hi<D('.20')
assert fire.box().width()>D(4) and T.plus('.6').minus(fire).hi<1
analytic=b.v.root(lambda u:b.R+4*dep.h(u)-1,lambda u:4*dep.dh(u),D(0),D('.6'),.2)
assert lag.lo<=analytic.hi and analytic.lo<=lag.hi
# Full causal order of one physical auxiliary cycle despite overlapping
# absolute boxes; each adjacent difference has its strict natural duration.
m=b.shift(T,b.D0,'m');off=b.shift(m,b.DM,'off');err=b.shift(off,b.DS,'err');end=b.shift(err,b.DE,'end')
pending=((T,(('raw_on',0,T),)),(m,(('mark_on',0,m),)),(off,(('mark_off',0,m),)),(T.plus(1),(('raw_off',0,T),)),(err,(('error_on',0,err),)),(end,(('error_off',0,err),)))
s={**s,'t':T.plus(-1),'q':b.R,'z':[I('.3').ln()]*3,'caps':[False]*3,'raw':[None]*3,'aux':[0]*3,'mark':[None]*3}
s['memory']=b.new_memory(s);s['depot']=tuple((dz.History(z),) for z in s['z'])
x=h.History(cyc.Branch(s));suffix=[D('Infinity')]*(len(pending)+1)
for k in range(len(pending)-1,-1,-1):suffix[k]=min(suffix[k+1],pending[k][0].box().lo)
for expected in range(1,4):
 ys=scheduler.step(x,pending,suffix,'causal');assert len(ys)==1 and ys[0].index==expected;x=ys[0]
assert any(c.get('kind')=='causal_earliest_exterior_boundary' for c in x.branch.conditions)
r=dict(status='pass',absolute_phase_width='4',head_lag=lag.pair(),same_phase_retained_in_guard_root=True,causal_exterior_order_uses_shared_differences=True)
(ROOT/'test_temps_relatifs_A22.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
# Follow the same four-unit uncertain phase through the fast/slow section.
import groupe_protege_A22 as prot
import avance_causale_A22 as causal
first=out[0];F=first.emissions[0]
sections=((T.plus(1),(('raw_off',0,T),)),(err,(('error_on',0,err),)),(end,(('error_off',0,err),)))
U=F.plus(max(t.minus(F).hi for t,_ in sections))
covered=prot.resolve_all(first,sections,U,'protected-phase')
assert covered is not None and len(covered)==1 and covered[0].state['p']==2
assert covered[0].state['raw']==[None]*3 and covered[0].state['aux']==[0]*3
assert covered[0].emissions==first.emissions
st=first.state
for t,actions in sections:
 while True:
  st,kind=causal.advance(st,t,'direct',0,b.advance)
  if kind=='external':break
  assert kind=='slow'
 st=b.act(st,actions)
st=b.flowing(st,U)
assert covered[0].state['q'].hi>=st['q'].lo and st['q'].hi>=covered[0].state['q'].lo
r.update(fast_slow_section_followed_with_shared_phase=True,protected_mark_and_error_gates_kept=True)
(ROOT/'test_temps_relatifs_A22.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
early_sections=sections[:2]
early_U=F.plus(max(t.minus(F).hi for t,_ in early_sections))
early=prot.resolve_all(first,early_sections,early_U,'protected-before-slow')
assert early is not None and len(early)==1 and early[0].state['p']==1
assert early[0].state['aux']==[3,0,0]
assert early[0].state['q'].pair()==(-b.A*early_U.minus(F)).exp().pair()
r['fast_endpoint_before_slow_section_does_not_evaluate_negative_slow_duration']=True
(ROOT/'test_temps_relatifs_A22.json').write_text(json.dumps(r,indent=2)+'\n')
