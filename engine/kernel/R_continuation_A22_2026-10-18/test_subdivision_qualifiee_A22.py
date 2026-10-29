"""Fresh ledger fixture for rate splitting; never imports a legacy pickle."""
from dataclasses import replace
from pathlib import Path
import json
import campagne_A22
import histoires_A21 as h
import cycle_local_A20 as cyc
import validation_A15 as b
import dependances_A17 as dep
import actuations_A19 as ac
import subdivision_recuperation_A22 as split
import intervalles_decimaux as iv
from intervalles_decimaux import I,D

def check(value,label):
    if not value:raise RuntimeError('Check failed: '+label)

def main():
    iv.configure(160);b.settings('0','0');b.PROFILE=None
    fire=dep.Time('fresh-common-fire',I(10,'10.001'))
    early_origin=fire.plus('.02');early_end=b.shift(early_origin,b.DM,'fresh-early-end')
    later_origin=fire.plus('.99');later_end=b.shift(later_origin,b.DM,'fresh-later-end')
    early=ac.Segment(0,early_origin,early_origin,True,early_end,True)
    later=ac.Segment(1,later_origin,later_origin,True,later_end,True)
    old=ac.History(I('.07999','.08001'),fire=fire,marks=(early,later))
    now=fire.plus('1.4');charge=b.R*ac.ell(old,now).exp()
    state=dict(t=now,p=2,q=charge,fire=fire,b=ac.rate(old,now),bstop=False,
        actuation=(old,),raw=[None,fire.plus('.97'),None],aux=[2,2,0],
        mark=[early_origin,later_origin,None],err=[None]*3)
    past=(fire,)
    parent=h.History(cyc.Branch(state,emissions=past),7,11,('fixture',))
    children=split.split(parent,'fresh-rate-split')
    check(len(children)==2,'both baseline halves retained')
    intervals=sorted((x.branch.state['actuation'][0].initial for x in children),key=lambda x:x.lo)
    full=(old.initial+I('.1'))
    check(intervals[0].lo==full.lo and intervals[1].hi==full.hi and intervals[0].hi==intervals[1].lo,'closed halves cover whole baseline')
    for child in children:
        ledger=child.branch.state['actuation'][0]
        check(ledger.marks==(later,),'only completed pre-section mark folded')
        check(child.branch.emissions==past and child.index==parent.index,'emissions and cursor preserved')
        check(child.branch.state['q'].lo>=b.R.lo and child.branch.state['q'].hi<=D('.25'),'slow domain retained')
        for base in (ledger.initial.lo,ledger.initial.mid(),ledger.initial.hi):
            true_initial=I(base)-I('.1')
            reference=replace(old,initial=true_initial)
            truth=b.R*ac.ell(reference,now).exp()
            envelope=child.branch.state['q']
            check(envelope.lo<=truth.lo and truth.hi<=envelope.hi,'anchored dose includes reference at baseline sample')
    result=dict(status='pass',fresh_ledger=True,closed_halves_cover_parent=True,
        completed_mark_folded=True,later_mark_retained=True,anchored_reference_charges_included=True,
        emission_prefix_and_cursor_preserved=True,no_saved_history_loaded=True)
    (Path(__file__).resolve().parent/'test_subdivision_qualifiee_A22.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
