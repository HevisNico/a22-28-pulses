"""Rehydrate persisted branch states without losing their emission histories."""
import json
from pathlib import Path
from etat_A20 import decode
from cycle_local_A20 import Branch,Forest

def branch(record):
    x=decode(record);s=x['state']
    for key in ('raw','mark','err','aux','caps'):s[key]=list(s[key])
    return Branch(s,tuple(x['emissions']),tuple(x['conditions']),tuple(x['trace']))

def local_forest(path):
    data=json.loads(Path(path).read_text())
    return Forest(tuple(branch(x) for x in data['branches']),data['certificate'])
