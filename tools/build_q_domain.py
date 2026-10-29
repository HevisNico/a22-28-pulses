"""Build the explicit quiescent domain Q28 from the terminal extraction and the future certificate.

Usage: python3 -I build_q_domain.py <all_terminal_exact.json> <future_certificate.json> <output.json>

For every cell: READY main and auxiliary modes, no pending event, no raw current, the stored q, m
and E bounds, b in [stored lower bound, 1.1]. Gains: influential and silent ports keep their stored
bounds; masked ports range from their stored lower bound up to the physical cap C_i(theta) of the
fixed device. This is the domain to which the future theorem applies (general-epsilon version).
"""
import hashlib
import json
import sys
from decimal import Decimal as D
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from certificate_parameters import resolve_epsilon


def main(terminal_path, certificate_path, output_path):
    if not __debug__:
        raise RuntimeError('Run without -O')
    terminal_path, certificate_path = Path(terminal_path), Path(certificate_path)
    terminal = json.loads(terminal_path.read_text())
    future = json.loads(certificate_path.read_text())
    resolve_epsilon(terminal, certificate=future)
    assert future['campaign'] == terminal['campaign']
    assert future['terminal_input_sha256'] == hashlib.sha256(terminal_path.read_bytes()).hexdigest()
    assert future['status'].startswith('PASS')
    classes = {(r['layer'], r['lane']): r for r in future['cells']}
    domain, counts = [], {'influential': 0, 'masked': 0, 'silent': 0}
    for c in terminal['cells']:
        row = classes.get((c['layer'], c['lane']))
        gains = []
        for p in range(3):
            kind = ('influential' if row and p in row['influential_ports']
                    else 'masked' if row and p in row['masked_ports'] else 'silent')
            counts[kind] += 1
            gains.append(dict(port=p, kind=kind, lower=c['g'][p][0],
                              upper='C_i(theta)' if kind == 'masked' else c['g'][p][1],
                              intersect_physical_cap=True))
        assert D(c['b'][1]) <= D('1.1')
        domain.append(dict(layer=c['layer'], lane=c['lane'], active=row is not None, main_mode='READY',
                           auxiliary_modes=['READY'] * 3, pending_events=[], raw_currents=[None] * 3,
                           q=c['q'], m=c['m'], E=[50, 100], b=[c['b'][0], '1.1'], gains=gains))
    calendar = terminal['campaign']['parameters']['training_calendar']
    definition = dict(
        name='Q28(theta)', terminal_time=int(calendar['terminal_time']), campaign=terminal['campaign'],
        terminal_input_sha256=hashlib.sha256(terminal_path.read_bytes()).hexdigest(),
        future_certificate_sha256=hashlib.sha256(certificate_path.read_bytes()).hexdigest(),
        port_counts=counts, cells=domain,
        interpretation='Quiescent domain built from the extracted enclosures, per the general-epsilon future '
                       'theorem. Gain bounds are intersected with each fixed device physical cap; b may grow '
                       'monotonically up to 1.1; masked gains may grow up to the cap.')
    Path(output_path).write_text(json.dumps(definition, indent=2) + '\n')
    print(json.dumps(dict(port_counts=counts, cells=len(domain))))


if __name__ == '__main__':
    main(*sys.argv[1:])
