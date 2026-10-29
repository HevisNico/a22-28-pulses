"""Candidate conservative parameter abstraction for independent physical ports.

The original model specifies independent C_i,LM_i,LS_i,LE_i,M_i. The old
affine overlay gave each of these one shared cell symbol. This adapter uses
ordinary interval boxes for physical constants, retaining affine state/time
enclosures but dropping physical-parameter correlations. It is a research
candidate; it is not a qualification of the whole hybrid implementation.
"""
from experiment_parameters import PHYSICAL_EPSILON

def install(engine):
    b,I,D,iv=engine.b,engine.I,engine.D,engine.iv
    def settings(cell):
        b.settings('1e-5',PHYSICAL_EPSILON)
        delay=b.D1.plain();mid=delay.mid()
        radius=max(iv.UP.subtract(delay.hi,mid),iv.UP.subtract(mid,delay.lo))
        b.D1_PORTS=tuple(I(mid)+I.symbol(f'{cell}:D1:{j}',radius) for j in range(3))
        b.INIT=dict(q=I.symbol(f'{cell}:q0','1e-5'),
            z=[I('4e-5')+I.symbol(f'{cell}:z{j}','5e-5') for j in range(3)],
            b=I.symbol(f'{cell}:b0','1e-5'))
        for x in (b.C,b.LM,b.LS,b.LE,b.M,b.DM,b.DS,b.DE,b.D0):
            if x.symbolic():raise RuntimeError('Physical parameter box unexpectedly carries a shared symbol')
    engine.settings_cell=settings
    return dict(abstraction='uncorrelated physical parameter boxes',
        scope='Allows independent port realizations and forgets additional within-port correlations conservatively',
        qualified=False)

MODEL_REFERENCE_SHA256 = '6f8462431cd43714af99d2181d5d017b2de910381690665ba7875659c061fecf'
