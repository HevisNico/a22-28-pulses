"""Joint recovery/input branches, including marks that change the guard.

Only branches with a single principal return and no subsequent principal
firing are handled. Unsupported branching is an explicit refusal.
"""
from dataclasses import replace
import validation_A15 as b
import actuations_A19 as ac
import dependances_A17 as dep
from intervalles_decimaux import I,D,hull

def return_with_marks(s,key):
    """Unique zero of the continued protected history, from its fast section.

    Full mark-off flags are deliberately ignored during root isolation:
    a probe before that boundary must use the unfinished primitive.
    """
    section=s['fire'].plus(1)
    assert all(h.fire.token()==s['fire'].token() for h in s['actuation'])
    probe=lambda u:b.shift(section,u,key+':probe')
    f=lambda u:-hull([ac.ell(h,probe(u),False) for h in s['actuation']])
    df=lambda u:hull([ac.rate(h,probe(u),False) for h in s['actuation']])
    hi=(2*I('2.5').ln()/I(df(I(0)).lo)).hi
    root=b.v.root(f,df,D(0),hi,b.v.guessroot(f,hi))
    return b.shift(section,root,key+':ready')

def enclosure(s,group,key):
    """No new mark can delay return, nor accelerate it before its start."""
    late=return_with_marks(s,key+':unforced')
    lower=min([late.box().lo]+[t.box().lo for t,actions in group for a,_,_ in actions if a=='mark_on'])
    return dep.Time(key+':coarse',I(lower,late.box().hi))

def resolve(s,group,upper,coarse,cell,count):
    assert s['p']==2
    if any(a=='end' for _,actions in group for a,_,_ in actions):raise b.v.Ambiguous('terminal boundary in joint recovery cluster')
    U=dep.Time(f'{cell}:joint-recovery-U:{count}',I(upper))
    events=list(group)+[(coarse,[('principal_ready',-1,None)])]
    possibilities=[];descriptions=[];pruned=[]
    for order in b.admissible_orders(s,events):
        ss=s;valid=True;actual=[]
        for k,(tt,actions) in enumerate(order):
            if actions[0][0]=='principal_ready':
                tt=return_with_marks(ss,f'{cell}:{count}:branch-{len(descriptions)}')
                # Coarse orders are only proposals. Reject a refined root only
                # when a strict time contradiction is certified.
                refined=actual+[(tt,actions)]+list(order[k+1:])
                if not b.possible_order(s['t'],refined):
                    pruned.append('refined return contradicts proposed weak order');valid=False;break
                ss=b.reopen(ss,tt)
            else:
                ss=b.flowing(ss,tt,ss['p']==0)
                if ss['p']==2:
                    if ss['q'].hi<b.R.lo or ss['q'].lo>D('.25'):
                        pruned.append('empty slow-phase domain');valid=False;break
                    ss['q']=ss['q'].intersect(I(b.R.lo,'.25'))
                ss=b.act(ss,actions)
            actual.append((tt,actions))
        if not valid:continue
        ss=b.flowing(ss,U,True)
        assert ss['p']==0 and ss['q'].hi<1
        conditions=tuple(('le',actual[k][0],actual[k+1][0]) for k in range(len(actual)-1))
        ss['depot']=tuple(tuple(replace(h,conditions=h.conditions+conditions) if not h.clamped else h for h in hs) for hs in ss['depot'])
        possibilities.append(ss)
        descriptions.append([dict(time=t.box().pair(),actions=[a for a,_,_ in aa]) for t,aa in actual])
    if not possibilities:raise b.v.Ambiguous('no joint recovery/input branch remained certifiable')
    assert all(x['aux']==possibilities[0]['aux'] and x['raw']==possibilities[0]['raw'] for x in possibilities)
    if b.PROFILE is not None:b.PROFILE.recovery_branch_groups.append(dict(cell=cell,batch=count,join_time=U.box().pair(),orders=descriptions,
        pruned=pruned,scope='Each branch recomputes the return from its own protected marks. Weak order labels do not contract the parameter box. A further principal firing causes refusal.'))
    return b.join_states(possibilities,dict(cell=cell,batch=count,orders=len(possibilities),kind='joint_recovery_input')),len(possibilities)
