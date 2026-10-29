"""Apply exact time-translation equivariance inside one regenerative suffix.

Caller obligations: same physical gain parameters, READY at exactly r before
each cohort, same active ports, unique heads on the admitted response branch.
The dictionary belongs to that one invocation, never to another history.
"""
from temps_symboliques_A22 import relative, exact_translation

def translated_head(active, starts, anchor, translations):
    active,starts=tuple(active),tuple(starts)
    if not active or len(active)!=len(starts) or len(set(active))!=len(active):
        raise ValueError('Expected one arrival for each distinct active port')
    pattern=(active,tuple(relative(t,anchor) for t in starts))
    if pattern not in translations:return pattern,None,None
    old_anchor,old_fire,reference=translations[pattern]
    displacement=exact_translation(anchor,old_anchor)
    if displacement is None:return pattern,None,None
    proof=dict(reference_cohort=reference,exact_translation=str(displacement),
        rule='Same physical gain parameters and exactly equal relative arrival expressions; unique threshold map is time-translation equivariant')
    return pattern,old_fire.plus(displacement),proof
