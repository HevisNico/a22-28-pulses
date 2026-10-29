"""Independent finite inequalities for the initial section and auxiliary cycles,
for a relative parameter half-width eps.

Same as proof/final_entry_audit/certify_initial_section.py (kept byte-identical,
its hash is cited), except that the parameter factor is [1-eps, 1+eps] instead
of the fixed [.9999, 1.0001]. With eps = 1e-4 it reproduces that script's output.
Imports only our directed-integer certificate arithmetic, never A22 engine code.
Usage: python3 certify_initial_section_eps.py <output.json> <eps>
"""
import sys,json,hashlib
from decimal import Decimal
from pathlib import Path
from fractions import Fraction as F
sys.path.insert(0,str(Path(__file__).resolve().parent))
from certify_future_v33 import I,S,A,K,R,RM,h,exp,log_rational,bisect_threshold

def main(dest,eps):
 e=Decimal(eps);assert 0<e<Decimal('0.01')
 delta=I('1e-5');factor=I(str(1-e),str(1+e));C=4*factor
 LM=log_rational(F(5,4))/I('.02')*factor
 LS=3*log_rational(2)/I('1.06')*factor
 LE=A/I('.15')*factor
 M=I('.975')/h(I('.02'))*factor
 U=(2*delta/(LE*RM)).high()
 atten=exp(-A*U)
 def charge(t,initial,m,attenuation=I(1)):
  u=I(t,t,raw=True);return RM+initial*exp(-K*u)+m*attenuation*h(u)
 d0lo=bisect_threshold(lambda t:charge(t,I(0),M.high()),0,S//10)[0]
 d0hi=bisect_threshold(lambda t:charge(t,I(0),M.low()),0,S//10)[1]
 d1lo=bisect_threshold(lambda t:charge(t,delta,M.high()),0,S//10)[0]
 d1hi=bisect_threshold(lambda t:charge(t,-delta,M.low(),atten.low()),0,S//10)[1]
 D0=I(d0lo,d0hi,raw=True);D1=I(d1lo,(U+I(d1hi,d1hi,raw=True)).hi,raw=True)
 DM=I('.02')/factor;DS=I('1.06')/factor;DE=I('.15')/factor
 q_upper=R+delta+3*C*A*U;m_upper=RM+delta+M*A*U
 derivative=M.low()*atten.low()*A/(A-K)*(A*exp(-A*I('.1'))-K)-K*delta
 W=(3*C+3*M+1)*A+I('1.1')+I('4.5')*LM+I('2.4')*LE
 checks={
 'initial_errors_end_before_U0':U-delta/(LE.low()*RM),
 'no_main_fire_before_U0':I('.2')-q_upper,
 'no_aux_fire_before_U0':I(1)-m_upper,
 'first_aux_fire_after_U0':D1.low()-U,
 'first_aux_fire_before_point_1':I('.1')-D1.high(),
 'aux_charge_increasing_through_first_root':derivative,
 'first_error_starts_after_raw_ends':D1.low()+DM.low()+DS.low()-1,
 'later_error_starts_after_raw_ends':D0.low()+DM.low()+DS.low()-1,
 'first_aux_cycle_ends_before_1_point_3':I('1.3')-D1.high()-DM.high()-DS.high()-DE.high(),
 'later_aux_cycle_ends_before_1_point_3':I('1.3')-D0.high()-DM.high()-DS.high()-DE.high(),
 'mark_current_dominates_silent_current':LM.low()-I('.8')*LS.high(),
 'mark_current_dominates_error_current':LM.low()-I('.1')*LE.high(),
 'energy_lower_boundary_points_inward':I(500)-W,
 'initial_b_positive':I('.08')-delta,
 'minimum_principal_interfire_exceeds_1_point_3':1+log_rational(F(5,2))/I('1.1')-I('1.3'),
 }
 assert all(v.lo>0 for v in checks.values()),{k:v.pair() for k,v in checks.items() if v.lo<=0}
 output=dict(status='PASS',scope='Independent finite inequalities for the stated physical model, not training simulation',arithmetic='Directed integers at scale 10^90; explicit exp/log series tails',delta=delta.pair(),relative_parameter_factor=factor.pair(),initial_section_time=U.pair(),first_aux_delay=D1.pair(),subsequent_aux_delay=D0.pair(),mark_duration=DM.pair(),silent_duration=DS.pair(),error_duration=DE.pair(),initial_main_upper=q_upper.pair(),initial_aux_upper=m_upper.pair(),first_root_uniform_derivative_lower=derivative.pair(),work_upper=W.pair(),initial_log_gain_offset=['-0.00001','0.00009'],positive_margins={k:v.pair() for k,v in checks.items()},premises=['Exact physical laws and initial set of the supplied reference, including no hidden past pulses.','Each source pulse has canonical shape; later cell inputs have principal refractory separation.','This certificate proves scalar inequalities; the accompanying argument connects them to the hybrid initial state.'])
 Path(dest).write_text(json.dumps(output,indent=2)+'\n');print(json.dumps({k:output[k] for k in ['status','initial_section_time','first_aux_delay','initial_main_upper','initial_aux_upper','work_upper']}))
if __name__=='__main__':
 if not __debug__:raise RuntimeError('Run without -O')
 main(sys.argv[1],sys.argv[2])
