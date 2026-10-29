"""Conservative fallback: cover a refused READY window by strict subthreshold boxes.

No new arrival is processed before the requested external boundary. Admitted
pulse amplitudes are constant; the pulse-memory evaluator includes raw cuts.
If its outward enclosure is below1 on every closed piece of[0,H], no first
threshold crossing exists before that boundary. This permits flowing to it.
An undecided piece, finite budget failure, or other refusal propagates the
original exception. This is an experimental kernel addition, not qualification.
"""
def install(engine):
    b,I,D,iv=engine.b,engine.I,engine.D,engine.iv
    original=b.advance
    def advance(s,boundary,cell,count):
        try:return original(s,boundary,cell,count)
        except b.v.Ambiguous as error:
            if (str(error)!='ready guard still overlaps external boundary or possible tangency'
                    or s['p']!=0 or s.get('memory') is None):raise
            H=boundary.minus(s['t']).nonnegative().hi
            stack=[(D(0),H,0)];leaves=[]
            while stack:
                lo,hi,depth=stack.pop()
                t=b.shift(s['t'],I(lo,hi),f'{cell}:{count}:nofire-cover')
                charge=b.dep.evaluate(s['memory'],t)
                if charge.hi<1:
                    leaves.append((lo,hi,charge.hi));continue
                if depth==16 or len(leaves)+len(stack)>65536:raise error
                mid=iv.NEAR.divide(iv.NEAR.add(lo,hi),D(2))
                if not lo<mid<hi:raise error
                stack.append((mid,hi,depth+1));stack.append((lo,mid,depth+1))
            if not leaves or leaves[0][0]!=0 or leaves[-1][1]!=H:raise error
            if any(x[1]!=y[0] for x,y in zip(leaves,leaves[1:])):raise error
            if b.PROFILE is not None:
                b.PROFILE.relative_order_proofs.append(dict(cell=cell,batch=count,guard='no_fire_cover',
                    start=s['t'].box().pair(),boundary=boundary.box().pair(),horizon=str(H),
                    cover=[[str(x) for x in leaf] for leaf in leaves],
                    predicate='Every closed cover piece has memory charge upper bound strictly below1'))
            return b.flowing(s,boundary),'external'
    b.advance=advance
