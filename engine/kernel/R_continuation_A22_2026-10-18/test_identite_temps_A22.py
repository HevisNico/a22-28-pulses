"""F02 witnesses and refusal barriers, without saved network histories."""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal
import json,pickle,subprocess,sys
import campagne_A22
import dependances_A17 as dep
import identite_temps_A22 as ids
from intervalles_decimaux import I
from temps_symboliques_A22 import exact_translation

def check(value,label):
    if not value:raise RuntimeError('Check failed: '+label)
def refuses(fn,label):
    try:fn()
    except ids.AtomIdentityRefusal:return
    raise RuntimeError('Expected identity refusal: '+label)

def main():
    ids.begin_producer('test-F02-producer-A')
    x=dep.Time('conteneur',I(0,1));y=dep.Time('conteneur',I(0,1))
    check(x.token()!=y.token(),'equal labels do not identify independent atoms')
    check(y.minus(x).pair()==I(-1,1).pair(),'annex B difference')
    check(exact_translation(y,x) is None,'annex B is not an exact translation')
    events={}
    for date,port in ((x,0),(y,1)):events.setdefault(date.token(),[date,[]])[1].append(('raw_on',port,date))
    check(len(events)==2,'annex B keeps two exterior dates')
    copied=dep.Time('another-label',x.box(),terms=x.expression())
    check(copied.token()==x.token(),'explicit expression copy shares the same quantity')
    check(x.plus(8).minus(x).pair()==I(8).pair(),'exact offset retains identity')
    a=dep.shift(x,I('.01','.02'),'same-duration-label')
    b=dep.shift(x,I('.01','.02'),'same-duration-label')
    check(a.token()!=b.token() and exact_translation(a,b) is None,'distinct duration allocations remain distinct')
    check(a.minus(b).lo<=Decimal('-.01') and a.minus(b).hi>=Decimal('.01'),'independent duration difference is covered')
    check(dep.Time('clock',I(0)).plus(1116).token()==('clock','1116'),'exact source/terminal clock compatibility')
    refuses(lambda:dep.Time('fabricated',I(0,1),terms=(('unregistered',1,I(0,1)),)),'unregistered explicit atom')
    legacy=object.__new__(dep.Time)
    for name,value in dict(key='old-key',base=I(0,1),offset=Decimal(0),terms=None).items():object.__setattr__(legacy,name,value)
    refuses(legacy.token,'legacy token')
    refuses(lambda:legacy.minus(x),'legacy difference')
    refuses(lambda:exact_translation(legacy,x),'legacy exact translation')
    data={'dates':(x,y,a,b,copied),'memory_origin':x}
    catalog=ids.atom_catalog(data)
    check(ids.validate_catalog(data,catalog),'catalogue covers all referenced atoms')
    bad=deepcopy(catalog);identity=next(iter(bad['records']));bad['records'][identity]['bounds']=['0','2']
    refuses(lambda:ids.import_catalog(bad),'conflicting imported bounds')
    short=deepcopy(catalog);short['records'].pop(next(iter(short['records'])))
    refuses(lambda:ids.validate_catalog(data,short),'missing catalogue entry')
    refuses(lambda:ids.begin_producer('test-F02-producer-A'),'producer counter cannot reset')
    temporary=dep.Time('mutable-input-test',I(5,6));temporary.terms[0][2].hi=Decimal(7)
    refuses(temporary.token,'mutated primitive bounds')
    for endpoint in (Decimal(0),Decimal(1)):
        collapsed=dep.Time('collapsed-atom',I(0,1))
        before_collapse=ids.atom_catalog(collapsed)
        bounds=collapsed.terms[0][2];bounds.lo=endpoint;bounds.hi=endpoint
        refuses(collapsed.token,'registered atom collapsed to point token')
        refuses(lambda:collapsed.minus(x),'collapsed atom difference')
        refuses(lambda:exact_translation(collapsed,x),'collapsed atom translation')
        refuses(lambda:dep.shift(collapsed,I('.01','.02'),'collapsed-shift'),'collapsed atom shift')
        refuses(lambda:ids.atom_catalog(collapsed),'collapsed atom export')
        refuses(lambda:ids.validate_catalog(collapsed,before_collapse),'pre-mutation catalogue cannot attest collapsed atom')
    zero_term=dep.Time('zero-coefficient',I(0),terms=((x.terms[0][0],0,I(0,1)),))
    zero_catalog=ids.atom_catalog(zero_term)
    check(ids.validate_catalog(zero_term,zero_catalog),'zero coefficient retains declared atom check')
    zero_term.terms[0][2].hi=Decimal(0)
    refuses(zero_term.token,'zero coefficient does not hide mutation')
    refuses(lambda:ids.validate_catalog(zero_term,zero_catalog),'zero coefficient catalogue mutation')
    collapsed_payload=pickle.dumps((collapsed,before_collapse),protocol=5)
    collapsed_program='''import sys,pickle
import campagne_A22
import identite_temps_A22 as ids
t,catalog=pickle.loads(sys.stdin.buffer.read())
try:ids.validate_catalog(t,catalog)
except ids.AtomIdentityRefusal:pass
else:raise RuntimeError('Unimported catalogue accepted collapsed atom')
try:t.token()
except ids.AtomIdentityRefusal:pass
else:raise RuntimeError('Unimported collapsed atom accepted as clock')
'''
    collapsed_child=subprocess.run([sys.executable,'-B','-c',collapsed_program],input=collapsed_payload,capture_output=True,cwd=Path(__file__).resolve().parent)
    check(collapsed_child.returncode==0,collapsed_child.stderr.decode())
    # Same source object is serialized once and supplied to all receivers.
    # In a clean interpreter it is unusable until its catalogue is imported.
    payload=pickle.dumps((data,catalog),protocol=5)
    program='''import sys,pickle
import campagne_A22
import identite_temps_A22 as ids
data,catalog=pickle.loads(sys.stdin.buffer.read())
try:data['dates'][0].token()
except ids.AtomIdentityRefusal:pass
else:raise RuntimeError('Unknown imported atom accepted')
ids.validate_catalog(data,catalog);ids.import_catalog(catalog)
x,y,a,b,copied=data['dates']
if x.token()!=copied.token() or x.token()==y.token():raise RuntimeError('Imported identities changed')
print('checked catalogue import preserved copy and independence')
'''
    child=subprocess.run([sys.executable,'-B','-c',program],input=payload,capture_output=True,cwd=Path(__file__).resolve().parent)
    check(child.returncode==0,child.stderr.decode())
    result=dict(status='pass',annex_B_exterior_groups=2,independent_equal_labels_preserved=True,
        independent_duration_labels_preserved=True,explicit_copy_preserved=True,exact_translation_preserved=True,
        legacy_and_unknown_atoms_refused=True,conflicting_or_incomplete_catalog_refused=True,
        namespace_reset_refused=True,mutated_bounds_refused=True,clean_process_catalog_import='pass',
        collapsed_atoms_refused=True,pre_mutation_catalog_rejected=True,
        zero_coefficient_mutation_refused=True,unimported_collapsed_atom_refused=True,
        no_old_artifact_migrated=True,no_global_history_loaded=True)
    (Path(__file__).resolve().parent/'test_identite_temps_A22.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
