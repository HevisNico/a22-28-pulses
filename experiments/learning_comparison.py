"""Paired finite-horizon experiment: adaptive versus initially frozen log-gains.

Uses the existing interval engine in separate processes. This is an experimental
variant, not the archived campaign or a future-invariance certificate.
"""
import argparse
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('adaptive', 'frozen_gains')


def protocol(future_gaps):
    gaps = [Decimal(x) for x in future_gaps]
    if any(not x.is_finite() or x < 20 for x in gaps):
        raise ValueError('future gaps must be finite and at least 20')
    training = [Decimal(8 * k) for k in range(28)]
    future = [Decimal(230)]
    for gap in gaps:
        future.append(future[-1] + gap)
    return training, future, future[-1] + 20


def install_variant(engine, arm, horizon):
    """Modify only this process; leave all shipped engine files untouched."""
    b, I = engine.b, engine.I
    source = engine._src
    # The stored, fully patched unit source has three fixed-horizon sites.
    if (source.count('D(230)') != 1 or source.count('I(230)') != 1
            or source.count("('clock','2.3E+2')") != 1):
        raise RuntimeError('unsupported engine unit source; horizon sites changed')
    b.COMPARISON_HORIZON = Decimal(horizon)
    b.COMPARISON_END_TOKEN = ('clock', str(b.COMPARISON_HORIZON.normalize()))
    source = source.replace('D(230)', 'COMPARISON_HORIZON')
    source = source.replace('I(230)', 'I(COMPARISON_HORIZON)')
    source = source.replace("('clock','2.3E+2')", 'COMPARISON_END_TOKEN')
    exec(compile(source, '<learning-comparison-unit>', 'exec'), b.__dict__)
    if arm == 'adaptive':
        return
    if arm != 'frozen_gains':
        raise ValueError('unknown comparison arm')
    # No gain-current accumulation, gate histories or cap events. Recovery
    # actuation, auxiliary events, charge dynamics and input gains stay intact.
    dz = b.dz
    dz.offered = lambda h, t: h.initial
    dz.value = lambda h, t: h.initial
    dz.certain_cap = lambda h, t: False
    dz.open_gate = lambda h, *args: h
    dz.close_gate = lambda h, *args: h
    dz.refresh = lambda h, t: h
    coefficients = b.coefficients

    def frozen_coefficients(state):
        current, _, recovery = coefficients(state)
        return current, [I(0) for _ in range(3)], recovery

    b.coefficients = frozen_coefficients


def measure(outputs, future, horizon, expected_response=True):
    """Associate only emissions contained wholly inside a source-response window.

    A window is [source pulse, next source pulse), with the last ending at the
    horizon. Border overlaps are ambiguous. A complete train is also required
    before any interval-error bound is reported.
    """
    windows = list(zip(future, future[1:] + [horizon]))
    assigned = [[] for _ in windows]
    ambiguous = 0
    for emission in outputs:
        box = emission.box()
        if box.hi < future[0]:
            continue
        matches = [i for i, (lo, hi) in enumerate(windows) if box.lo >= lo and box.hi < hi]
        if len(matches) == 1:
            assigned[matches[0]].append(emission)
        else:
            ambiguous += 1
    counts = [len(row) for row in assigned]
    expected = int(expected_response)
    result = dict(response_counts=counts, ambiguous_emissions=ambiguous,
                  expected_response_per_window=expected,
                  empty_windows=sum(n == 0 for n in counts),
                  missing_responses=sum(max(0, expected - n) for n in counts),
                  extra_emissions=sum(max(0, n - expected) for n in counts),
                  reference_pattern_matched=not ambiguous and all(n == expected for n in counts),
                  complete_one_per_window=not ambiguous and all(n == 1 for n in counts))
    if result['complete_one_per_window']:
        train = [row[0] for row in assigned]
        latencies = [t.plus(-f).box() for t, f in zip(train, future)]
        errors = [train[k + 1].minus(train[k]) - (future[k + 1] - future[k])
                  for k in range(len(train) - 1)]
        result['latency_boxes'] = [[str(x.lo), str(x.hi)] for x in latencies]
        result['interval_error_boxes'] = [[str(x.lo), str(x.hi)] for x in errors]
        result['max_abs_interval_error_upper'] = str(max(
            (max(x.lo.copy_abs(), x.hi.copy_abs()) for x in errors), default=Decimal(0)))
    return result


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def run_arm(args):
    """The private worker runs once in a fresh interpreter for each arm."""
    output = args.out / args.arm
    output.mkdir()
    training, future, horizon = protocol(args.future_gaps)
    os.environ['A22_PHYSICAL_EPSILON'] = args.epsilon
    sys.path.insert(0, str(ROOT / 'engine'))
    import run
    engine, artifacts, temporal = run.initialize(output / 'diagnostics')
    import platform
    import numpy
    import scipy
    import rounding
    install_variant(engine, args.arm, horizon)
    certificate = json.loads((ROOT / 'terminal' / 'future_certificate.json').read_text())
    active_reference = {(row['layer'], row['lane']) for row in certificate['cells']}
    silent_reference = {(row['layer'], row['lane']) for row in certificate['inactive_cells']}
    expected_cells = {(layer, lane) for layer in range(1, 19) for lane in range(12)}
    if active_reference & silent_reference or active_reference | silent_reference != expected_cells:
        raise RuntimeError('reference active/silent partition is incomplete or conflicting')
    temporal.begin_producer('comparison/source')
    clock = temporal.Time('canonical-initial-clock', engine.I(0))
    source = tuple(clock.plus(t) for t in training + future)
    previous = [source] + [()] * 11
    report = dict(arm=args.arm, status='running', layers_completed=0, cells=[],
                  environment=dict(python=platform.python_version(), numpy=numpy.__version__,
                                   scipy=scipy.__version__, arithmetic_backend=rounding.BACKEND),
                  boundary='finite interval-engine experiment; no infinite-horizon claim')
    try:
        for layer in range(1, args.layers + 1):
            current = []
            for lane in range(12):
                namespace = f'comparison/cell/{layer}/{lane}'
                result = engine.compute_cell(layer, lane, previous, namespace)
                # Check every ledger, including latent histories, rather than only
                # comparing the final marginal gain boxes.
                if args.arm == 'frozen_gains':
                    for histories in result['state']['terminal_affine']['depot']:
                        for history in histories:
                            if history.full or history.partial or history.active is not None or history.clamped:
                                raise RuntimeError('frozen gain history accumulated learning')
                payload = output / f'cell_{layer:02d}_{lane:02d}.json'
                digest, _ = artifacts.write_checked(payload, result)
                reread = artifacts.read(payload, digest)
                current.append(tuple(reread['outputs']))
                row = dict(layer=layer, lane=lane, payload_sha256=digest,
                           training_emissions=sum(t.box().hi < future[0] for t in current[-1]),
                           terminal_gains=result['state']['g'], terminal_b=result['state']['b'],
                           metrics=result['metrics'],
                           future=measure(current[-1], future, horizon, (layer, lane) in active_reference))
                report['cells'].append(row)
                print(f'{args.arm}: layer {layer}, lane {lane}: {row["future"]["response_counts"]}', flush=True)
                write_json(output / 'summary.json', report)
            previous = current
            report['layers_completed'] = layer
        report['status'] = 'completed'
    except Exception as exc:
        report.update(status='unresolved', error_type=type(exc).__name__, error=str(exc),
                      traceback=traceback.format_exc(), next_cell=dict(layer=layer, lane=lane))
    write_json(output / 'summary.json', report)
    return 0 if report['status'] == 'completed' else 1


def main():
    if not __debug__:
        raise RuntimeError('Run without -O')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--layers', type=int, default=1, help='1..18; start with one layer')
    parser.add_argument('--epsilon', default='1e-3')
    parser.add_argument('--future-gaps', nargs='*', default=['20', '31', '40', '25'])
    parser.add_argument('--timeout', type=int, default=1800, help='seconds per arm')
    parser.add_argument('--arm', choices=ARMS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        epsilon = Decimal(args.epsilon)
        if not epsilon.is_finite() or not 0 < epsilon < 1:
            raise ValueError('epsilon must be strictly between 0 and 1')
        if not 1 <= args.layers <= 18 or args.timeout <= 0:
            raise ValueError('layers must be 1..18 and timeout must be positive')
        if not args.future_gaps:
            raise ValueError('at least one future gap is required to measure interval errors')
        with localcontext() as context:
            context.prec = 160
            training, future, horizon = protocol(args.future_gaps)
    except (ValueError, ArithmeticError) as exc:
        parser.error(str(exc))
    args.out = args.out.resolve()
    if args.arm:
        with localcontext() as context:
            context.prec = 160
            return run_arm(args)
    args.out.mkdir(parents=True, exist_ok=False)
    # Import runner only to hash its files, without initializing the engine.
    sys.path.insert(0, str(ROOT / 'engine'))
    import run
    manifest = dict(schema='A22-learning-comparison-1', layers=args.layers, epsilon=str(epsilon),
                    training=[str(x) for x in training], future=[str(x) for x in future],
                    horizon=str(horizon), engine_identity=run.identity(),
                    experiment_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    reference_pattern='active/silent cells from published epsilon=1e-3 certificate; a comparison target, not a guarantee at other epsilon values',
                    reference_sha256=hashlib.sha256((ROOT / 'terminal' / 'future_certificate.json').read_bytes()).hexdigest(),
                    frozen_scope='z_i fixed at engine initial-section values; recovery b remains adaptive in both arms',
                    arms={})
    write_json(args.out / 'comparison.json', manifest)
    for arm in ARMS:
        command = [sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                   '--out', str(args.out), '--layers', str(args.layers), '--epsilon', args.epsilon,
                   '--arm', arm, '--future-gaps', *args.future_gaps]
        with (args.out / f'{arm}.log').open('w') as log:
            try:
                process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout)
                code = process.returncode
            except subprocess.TimeoutExpired:
                code = None
        summary = args.out / arm / 'summary.json'
        result = json.loads(summary.read_text()) if summary.exists() else {}
        if code != 0:
            result['status'] = 'unresolved'
        manifest['arms'][arm] = dict(status=result.get('status', 'unresolved'),
                                    returncode=code, layers_completed=result.get('layers_completed', 0))
        cells = result.get('cells', [])
        manifest['arms'][arm]['measured_cells'] = len(cells)
        for key in ('missing_responses', 'extra_emissions', 'ambiguous_emissions'):
            manifest['arms'][arm][key] = sum(c['future'][key] for c in cells)
        manifest['arms'][arm]['reference_pattern_matched_cells'] = sum(
            c['future']['reference_pattern_matched'] for c in cells)
        write_json(args.out / 'comparison.json', manifest)
    print(json.dumps(manifest, indent=2))
    return 0 if all(v['status'] == 'completed' for v in manifest['arms'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
