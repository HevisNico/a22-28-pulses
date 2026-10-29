from pathlib import Path
import json,itertools,sys
ROOT=Path(__file__).resolve().parent
import campagne_A22 as campaign
import groupe_protege_A22 as solver
import histoires_A21 as h
import cycle_local_A20 as cyc
import validation_A15 as b
import dependances_A17 as dep
import actuations_A19 as ac
import depot_A19 as dz
import intervalles_decimaux as iv
from intervalles_decimaux import I,D
iv.configure(160);b.settings('0','0');b.PROFILE=None
F=dep.Time('F',I(-1));T=dep.Time('clock',I(0))
s=dict(t=T,q=I('.25'),p=2,fire=F,b=I('.2'),bstop=False,z=[I('.3').ln()]*3,caps=[False]*3,raw=[None]*3,
 aux=[0]*3,mark=[None]*3,err=[None]*3,memory=None)
s['depot']=tuple((dz.History(z),) for z in s['z']);s['actuation']=(ac.History(s['b'],fire=F),)
xs=[]
for j in range(2):
 t=dep.Time(f'arrival{j}',I('.1','.11'));m=b.shift(t,b.D0,f'm{j}');off=b.shift(m,b.DM,f'off{j}')
 xs.extend([(t,[('raw_on',j,t)]),(m,[('mark_on',j,m)]),(off,[('mark_off',j,m)])])
x=cyc.Branch(s,(F,));U=max(t.box().hi for t,_ in xs);out=solver.resolve(x,xs,U,'test')
assert out is not None and out.emissions==x.emissions and out.state['p']==2
assert out.state['b'].lo<=D('.4')<=out.state['b'].hi
orders=0
for order in b.admissible_orders(s,xs):
 ss=s
 for t,aa in order:ss=b.act(b.flowing(ss,t),aa)
 ss=b.flowing(ss,dep.Time('U',I(U)))
 assert out.state['q'].lo<=ss['q'].lo<=ss['q'].hi<=out.state['q'].hi
 assert out.state['b'].lo<=ss['b'].lo<=ss['b'].hi<=out.state['b'].hi
 assert out.state['aux']==ss['aux'] and [t.token() if t else None for t in out.state['raw']]==[t.token() if t else None for t in ss['raw']]
 orders+=1
assert orders>1
# A long group can contain the return: the commuting map must refuse.
assert solver.resolve(x,xs,D(10),'too-late') is None
assert solver.resolve(cyc.Branch({**s,'p':0}),xs,U,'not-protected') is None
result=dict(status='pass',enumerated_inter_port_orders=orders,all_mark_integrals_and_outputs_preserved=True,possible_return_refused=True)
(ROOT/'test_groupe_protege_A22.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
