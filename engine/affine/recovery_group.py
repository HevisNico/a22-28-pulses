"""Fix R (v3.3): protected recovery return overlapping an exterior event group.

unit() resolves a slow-recovery (p=2) refusal against a SINGLE exterior event
with the kernel's local-cycle resolver (cycle_local_A20.pending_window): it
encloses every admissible order of the return and the pending events, and
joins the forest only when every branch ends READY with no emission. The
group path (several overlapping events) had no such fallback and refused.
This module applies the SAME resolver and the SAME join rule to that path.

Preconditions (otherwise None, and the caller re-raises the original refusal):
  * the state is in slow recovery (p == 2);
  * the resolver certifies the window (its own checks: at most one additional
    fire, window shorter than the fast phase, no terminal event, branch budget);
  * every branch of the forest is READY with no emission.
No kernel map is modified and no branch is discarded.
"""
STATS = {'recovery_groups': 0}


def resolve(b, s, pending, idx, cell, count):
    if s['p'] != 2:
        return None
    from cycle_local_A20 import pending_window
    try:
        forest, nextidx, handled = pending_window(s, pending, idx, cell, count)
    except b.v.Ambiguous:
        return None
    if not forest.branches or not all(not x.emissions and x.state['p'] == 0 for x in forest.branches):
        return None
    joined = b.join_states([x.state for x in forest.branches],
                           dict(cell=cell, batch=count, kind='local_cycle_no_emission_group'))
    if b.PROFILE is not None:
        b.PROFILE.relative_order_proofs.append(dict(cell=cell, batch=count, guard='recovery_group_local_cycle',
            events=len(handled), branches=len(forest.branches), certificate=str(forest.certificate)[:2000]))
    STATS['recovery_groups'] += 1
    return joined, nextidx, len(handled) + 1, len(forest.branches)
