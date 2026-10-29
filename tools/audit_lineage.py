"""Passive campaign audit. Standard library only; never imports the engine.

Checks every payload, receipt, completed-layer decision, parent lineage and
retained time-atom definition. Does not establish physical soundness itself.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_provenance import DAG, canonical, sha

def main(root, dest):
    if not __debug__:
        raise RuntimeError('Run without -O')
    root, dest = Path(root), Path(dest)
    cfg = json.loads((root / 'campaign.json').read_text())
    assert cfg['parameters'] == {
        'epsilon_relative': '0.001', 'initial_delta': '1e-5',
        'training_calendar': {'count': 28, 'first': '0', 'gap': '8',
                              'last': '216', 'source_lane': 0,
                              'terminal_time': '230'}}
    atoms = {}
    categories = Counter()
    guards = Counter()
    occurrences = time_nodes = 0
    rows = []
    parents = []
    for layer in range(1, 19):
        base = root / f'layer_{layer:02d}'
        complete = json.loads((base / 'complete.json').read_text())
        verify = json.loads((base / 'verification.json').read_text())
        assert complete['status'] == 'research_layer_complete'
        assert complete['layer'] == verify['layer'] == layer
        assert (verify['run_id'], verify['kernel_id']) == (cfg['run_id'], cfg['kernel_id'])
        receipts = []
        payloads = []
        for lane in range(12):
            folder = base / f'cell_{lane:02d}'
            rb = (folder / 'receipt.json').read_bytes()
            r = json.loads(rb)
            raw = (folder / 'result.json').read_bytes()
            assert sha(raw) == r['payload_sha256']
            assert r['status'] == 'research_cell_complete'
            expected = dict(run_id=cfg['run_id'], kernel_id=cfg['kernel_id'],
                            layer=layer, lane=lane, parent_receipts=parents)
            assert r['case'] == expected
            assert set(r['comparisons']) == {'state', 'emissions', 'time_dependencies', 'provenance', 'complete'}
            assert all(v['equal'] is True and v['fresh'] == v['disk'] for v in r['comparisons'].values())
            doc = json.loads(raw)
            assert sha(canonical(doc)) == r['check']['typed_content_sha256']
            d = DAG(doc)
            rt = d.fields(doc['root'])
            assert d.simple(rt['case']) == expected
            for view, key in [('state', 'state'), ('emissions', 'outputs'), ('provenance', 'case')]:
                assert sha(canonical(d.subgraph(rt[key]))) == r['comparisons'][view]['disk']
            for node in d.ns:
                if node[0] != 'time':
                    continue
                time_nodes += 1
                terms = d.ns[node[4]]
                assert terms[0] == 'tuple'
                for ti in terms[1]:
                    term = d.ns[ti]
                    assert term[0] == 'tuple' and len(term[1]) == 3
                    ai, ni, vi = term[1]
                    atom, multiplier, value = d.simple(ai), d.simple(ni), d.ns[vi]
                    assert isinstance(atom, str) and type(multiplier) is int and value[0] == 'affine'
                    definition = sha(canonical(value))
                    assert atoms.setdefault(atom, definition) == definition, (layer, lane, atom)
                    occurrences += 1
            profile = d.simple(d.fields(rt['state'])['width_profile'])
            categories.update({k: v['count'] for k, v in profile['categories'].items()})
            guards.update({k: v['count'] for k, v in profile['guard_dates'].items()})
            receipts.append(sha(rb))
            payloads.append(sha(raw))
            rows.append(dict(layer=layer, lane=lane, payload_sha256=sha(raw)))
        assert receipts == verify['receipts'] == complete['receipts']
        assert payloads == verify['payloads']
        parents = receipts
        print('Lineage and retained clocks checked through layer', layer, flush=True)
    assert len(rows) == 216
    report = dict(status='PASS', campaign=cfg, cells=216, time_nodes=time_nodes,
                  time_atom_occurrences=occurrences, distinct_time_atoms=len(atoms),
                  conflicting_definitions=0, profile_categories=dict(categories),
                  profile_guard_counts=dict(guards), per_cell=rows,
                  scope='All saved payloads and parent chains; equality of retained time-atom definitions.',
                  limitations=['Discarded intermediate expressions are not available.',
                               'Atom equality and successful checks alone do not prove physical soundness.'])
    dest.write_text(json.dumps(report, indent=2) + '\n')

if __name__ == '__main__':
    main(*sys.argv[1:])
