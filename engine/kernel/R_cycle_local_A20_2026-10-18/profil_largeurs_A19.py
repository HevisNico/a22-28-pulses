"""Enclosure diagnostics, not a decomposition of true physical sensitivity."""
from intervalles_decimaux import I,D
class Profile:
    def __init__(self,inputs):
        self.inputs=dict(maximum_arrival_width=str(max((t.box().width() for tr in inputs for t in tr),default=D(0))))
        self.categories={};self.top=[];self.max_histories=1;self.max_deposit_histories=1;self.cap_observations=[];self.gain_cap_observations=[];self.guards={};self.relative_order_proofs=[];self.recovery_branch_groups=[];self.pruned_recovery_orders=[]
    def guard(self,kind,tt):
        g=self.guards.setdefault(kind,dict(count=0,maximum_time_width=D(0)))
        g['count']+=1;g['maximum_time_width']=max(g['maximum_time_width'],tt.box().width())
    def observe(self,kind,before,after,context=None):
        r=self.categories.setdefault(kind,dict(count=0,max_b_width=D(0),max_q_width=D(0),max_log_gain_width=D(0),max_b_increase=D(0),max_q_increase=D(0),max_log_gain_increase=D(0)))
        r['count']+=1
        bw=after['b'].width();qw=after['q'].width()
        bi=(I(bw)-I(before['b'].width())).hi;qi=(I(qw)-I(before['q'].width())).hi
        r['max_b_width']=max(r['max_b_width'],bw);r['max_q_width']=max(r['max_q_width'],qw)
        r['max_b_increase']=max(r['max_b_increase'],bi);r['max_q_increase']=max(r['max_q_increase'],qi)
        zw=max(z.width() for z in after['z']);oldzw=max(z.width() for z in before['z']);zi=(I(zw)-I(oldzw)).hi
        r['max_log_gain_width']=max(r['max_log_gain_width'],zw);r['max_log_gain_increase']=max(r['max_log_gain_increase'],zi)
        self.max_histories=max(self.max_histories,len(after.get('actuation',())))
        self.max_deposit_histories=max(self.max_deposit_histories,max((len(hs) for hs in after.get('depot',())),default=1))
        if bi>0 or qi>0 or zi>0:
            self.top.append(dict(category=kind,time=after['t'].box().pair(),phase=after['p'],b_width=str(bw),q_width=str(qw),log_gain_width=str(zw),b_increase=str(bi),q_increase=str(qi),log_gain_increase=str(zi),context=context))
            self.top=sorted(self.top,key=lambda x:max(D(x['b_increase']),D(x['q_increase']),D(x['log_gain_increase'])),reverse=True)[:12]
        if not before.get('bstop',False) and after.get('bstop',False):
            self.cap_observations.append(dict(last_nonuniform_observation=before['t'].box().pair(),uniform_saturation_by=after['t'].box().pair(),b=after['b'].pair()))
        for j in range(3):
            if not before['caps'][j] and after['caps'][j]:self.gain_cap_observations.append(dict(port=j,last_nonuniform_observation=before['t'].box().pair(),uniform_saturation_by=after['t'].box().pair()))
    def export(self):
        return dict(inputs=self.inputs,categories={k:{a:str(b) if isinstance(b,D) else b for a,b in x.items()} for k,x in self.categories.items()},largest_increases=self.top,
                    guard_dates={k:dict(count=v['count'],maximum_time_width=str(v['maximum_time_width'])) for k,v in self.guards.items()},
                    relative_order_proofs=self.relative_order_proofs,
                    recovery_branch_groups=self.recovery_branch_groups,
                    pruned_recovery_orders=self.pruned_recovery_orders,
                    maximum_distinct_actuation_histories=self.max_histories,maximum_distinct_deposit_histories=self.max_deposit_histories,
                    recovery_saturation_observations=self.cap_observations,gain_saturation_observations=self.gain_cap_observations,
                    saturation_observation_scope='Last nonuniform observations are not lower bounds on individual contact times; some histories may have reached the cap earlier.',
                    interpretation='Widths and increases are enclosure diagnostics. Continuous growth, branch spread and input width do not separately prove physical sensitivity or numerical wrapping.')
