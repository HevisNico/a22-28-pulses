"""Small physical queues only; no network history or saved pickle is read."""
from copy import deepcopy
import json
import campagne_A22
import queue_regenerative_A22 as reg
import histoires_A21 as h
import cycle_local_A20 as cyc
import validation_A15 as b
import dependances_A17 as dep
import actuations_A19 as ac
import depot_A19 as dz
import intervalles_decimaux as iv
from intervalles_decimaux import I,D

def check(value,label):
    if not value:raise RuntimeError('Check failed: '+label)

def fixture(ports,gain='4'):
    s=dict(t=dep.Time('initial-local',I(-1)),q=b.R,p=0,fire=None,b=I('.3'),bstop=False,
        z=[I('.3').ln()]*3,caps=[False]*3,raw=[None]*3,aux=[0]*3,mark=[None]*3,err=[None]*3)
    for port in ports:s['z'][port]=I(gain).ln();s['caps'][port]=(gain=='4')
    s['memory']=b.new_memory(s);s['depot']=tuple((dz.History(z,clamped=cap),) for z,cap in zip(s['z'],s['caps']))
    s['actuation']=(ac.History(s['b']),);events={}
    for index in range(3):
        for port in ports:
            arrival=dep.Time('clock',I(0)).plus(8*index)
            mark=b.shift(arrival,b.D0,f'audit:m:{port}:{index}')
            off=b.shift(mark,b.DM,f'audit:mo:{port}:{index}')
            error=b.shift(off,b.DS,f'audit:e:{port}:{index}')
            end=b.shift(error,b.DE,f'audit:eo:{port}:{index}')
            for time,action,origin in ((arrival,'raw_on',arrival),(mark,'mark_on',mark),(off,'mark_off',mark),
                    (arrival.plus(1),'raw_off',arrival),(error,'error_on',error),(end,'error_off',error)):
                events.setdefault(time.token(),[time,[]])[1].append((action,port,origin))
    events['terminal']=[dep.Time('clock',I(0)).plus(1116),[('end',-1,None)]]
    pending=tuple(sorted(events.values(),key=lambda e:e[0].box().mid()))
    past=(dep.Time('past-local',I(-10)),)
    return h.History(cyc.Branch(s,emissions=past)),pending

def main():
    iv.configure(160);b.settings('0','0');b.PROFILE=None
    results=[]
    for ports in ((0,1,2),(1,)):
        x,pending=fixture(ports);out=reg.certify(x,pending,'audit-local:'+str(ports))
        check(out is not None,'physical suffix accepted')
        check(out.branch.emissions[:1]==x.branch.emissions,'past emission prefix retained')
        heads=out.branch.emissions[1:]
        check(len(heads)==3 and all(t2.minus(t1).pair()==I(8).pair() for t1,t2 in zip(heads,heads[1:])),'exact translated heads')
        check(out.index==len(pending),'whole queue consumed')
        check(out.branch.state['p']==0 and out.branch.state['q'].pair()==b.R.pair(),'READY at r')
        check(out.branch.state['raw']==[None]*3 and out.branch.state['aux']==[0]*3,'no unfinished currents or auxiliary cycle')
        results.append(dict(ports=ports,accepted=True,prefix_preserved=True,heads=3,exact_spacing='8'))
    x,pending=fixture((0,))
    bad=deepcopy(x);bad.branch.state['memory']['pulses']['undeclared-current']=dict(origin=dep.Time('hidden',I(-1)),g=I(1),tail=False)
    check(reg.certify(bad,pending) is None,'residual memory refused')
    for value in ('0','-.1','1.2'):
        bad=deepcopy(x);bad.branch.state['b']=I(value)
        check(reg.certify(bad,pending) is None,'invalid recovery bounds refused')
    missing=tuple((t,[(a,j,o) for a,j,o in actions if a!='error_off']) for t,actions in pending)
    check(reg.certify(x,missing) is None,'incomplete physical auxiliary cycle refused')
    x3,p3=fixture((0,),'3');x4,p4=fixture((0,),'4')
    a=reg.certify(x3,p3,'audit-g3');c=reg.certify(x4,p4,'audit-g4')
    check(a is not None and c is not None,'both fixed gain devices accepted')
    check(a.branch.emissions[1].minus(c.branch.emissions[1]).lo>0,'different gains do not share one cached head')
    print(json.dumps(dict(status='pass',fixtures=results,residual_memory_refused=True,
        invalid_recovery_refused=True,incomplete_auxiliary_cycle_refused=True,different_gain_calls_have_different_heads=True,
        all_inputs_built_locally=True,global_history_loaded=False)))

if __name__=='__main__':main()
