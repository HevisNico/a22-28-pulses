"""One command for every check of this repository.

    python3 -I tools/verify.py                 # from the committed records (also run by CI)
    python3 -I tools/verify.py <campaign dir>  # also re-extract everything from the full outputs
                                               # (release asset campaign28_T230_eps1e-3)
    python3 -I tools/verify.py [<campaign dir>] --engine <engine dir>
        # also check that the as-run engine (release asset, with its native binaries) has the
        # sources of engine/ and recompute the campaign kernel_id from it; this step imports the
        # engine and needs the interpreter it was built for (CPython 3.13, numpy 2.3.5, scipy 1.17.0)

Without a campaign directory: the initial section is recomputed and compared byte for byte; the
future certificate and its independent check are regenerated from terminal/all_terminal_exact.json
and compared (the certificate by content, since a few margins are listed in set order); Q28 is
rebuilt and compared.

With a campaign directory: first every output file is checked against campaign/RUN_MANIFEST.json,
then the terminal extraction, the lineage and clock audit and the commutation audit are rerun and
compared byte for byte with terminal/, before the checks above.

Standard library only; no engine import. Each check prints PASS or FAIL; exit code 1 on any FAIL.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / 'tools'
TERMINAL = REPO / 'terminal'
RESULTS = []


def report(name, ok, detail=''):
    RESULTS.append(ok)
    print(f'[{"PASS" if ok else "FAIL"}] {name}' + (f': {detail}' if detail else ''), flush=True)


def run(script, *args):
    out = subprocess.run([sys.executable, '-I', str(TOOLS / script)] + [str(a) for a in args],
                         capture_output=True, text=True, cwd=REPO)
    if out.returncode != 0:
        raise RuntimeError(f'{script} exited {out.returncode}: ' + (out.stderr.strip().splitlines() or ['?'])[-1][:300])
    return out.stdout


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same_bytes(a, b):
    return Path(a).read_bytes() == Path(b).read_bytes()


def check(name, fn):
    try:
        fn()
    except Exception as exc:
        report(name, False, f'{type(exc).__name__}: {exc}')


def outputs_checks(campaign, tmp):
    def manifest():
        files = json.loads((REPO / 'campaign' / 'RUN_MANIFEST.json').read_text())['files']
        bad = [k for k, v in files.items() if not (campaign / k).is_file() or sha(campaign / k) != v['sha256']]
        extra = [str(p.relative_to(campaign)) for p in campaign.rglob('*') if p.is_file() and str(p.relative_to(campaign)) not in files]
        report('campaign outputs against RUN_MANIFEST.json', not bad and not extra,
               f'{len(files)} files, {len(bad)} mismatched, {len(extra)} unlisted')
    check('campaign outputs against RUN_MANIFEST.json', manifest)

    def extraction():
        run('extract_terminal.py', campaign, tmp)
        for name in ('all_terminal_exact.json', 'all_layers_audit.json'):
            report(f'terminal extraction: {name}', same_bytes(tmp / name, TERMINAL / name))
    check('terminal extraction', extraction)

    def lineage():
        run('audit_lineage.py', campaign, tmp / 'lineage_and_clocks.json')
        report('lineage and clock audit', same_bytes(tmp / 'lineage_and_clocks.json', TERMINAL / 'lineage_and_clocks.json'))
    check('lineage and clock audit', lineage)

    def commutations():
        run('audit_commutations.py', campaign, tmp / 'commutation_usage.json')
        report('commutation audit', same_bytes(tmp / 'commutation_usage.json', TERMINAL / 'commutation_usage.json'))
    check('commutation audit', commutations)


def engine_checks(engine):
    top = {'run.py', 'build_native.py', 'build_all_native.py', 'launch_fresh.py', 'reference/full_model_reference.md'}

    def identity_files(base):
        return {str(p.relative_to(base)) for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                and (str(p.relative_to(base)) in top or p.relative_to(base).parts[0] in ('affine', 'kernel'))}

    def contents():
        a, b = identity_files(engine), identity_files(REPO / 'engine')
        binaries = {x for x in a - b if x.endswith('.so')}
        differ = sorted(x for x in a & b if sha(engine / x) != sha(REPO / 'engine' / x))
        extra = sorted(a - b - binaries) + sorted(b - a)
        campaign = json.loads((REPO / 'campaign' / 'campaign.json').read_text())
        natives = [x for x in binaries if x.startswith('affine/_rounding_native')]
        native_ok = len(natives) == 1 and sha(engine / natives[0]) == campaign['environment']['native_sha256']
        report('as-run engine sources and binaries', not differ and not extra and len(binaries) == 2 and native_ok,
               f'{len(a & b)} sources identical to engine/, {len(binaries)} binaries, rounding binary '
               + ('matches campaign.json' if native_ok else 'DOES NOT match campaign.json'))
    check('as-run engine sources and binaries', contents)

    def identity():
        campaign_file = REPO / 'campaign' / 'campaign.json'
        campaign = json.loads(campaign_file.read_text())
        code = ("import json,run;from pathlib import Path;"
                "cfg=json.loads(Path(%r).read_text());"
                "e,a,t=run.initialize(Path(%r));"
                "print(a.canonical_hash({'sources':run.identity(),'environment':cfg['environment'],"
                "'parameters':cfg['parameters'],'precision':160,'symbols':run.affine_iv_kmax()}))"
                % (str(campaign_file), str(Path(tempfile.gettempdir()) / 'a22_identity_diagnostics')))
        env = dict(os.environ, A22_PHYSICAL_EPSILON=campaign['parameters']['epsilon_relative'])
        out = subprocess.run([sys.executable, '-B', '-c', code], cwd=engine, env=env, capture_output=True,
                             text=True, timeout=600)
        if out.returncode != 0:
            raise RuntimeError('engine not importable here: ' + (out.stderr.strip().splitlines() or ['?'])[-1][:200])
        got = out.stdout.strip().splitlines()[-1]
        report('campaign kernel_id recomputed from the as-run engine', got == campaign['kernel_id'],
               f'{got[:16]}... vs {campaign["kernel_id"][:16]}...')
    check('campaign kernel_id recomputed from the as-run engine', identity)


def record_checks(tmp):
    def initial():
        run('certify_initial_section.py', tmp / 'initial.json', '1e-3')
        report('initial section at eps = 1e-3', same_bytes(tmp / 'initial.json', TERMINAL / 'initial_section_eps1e-3.json'))
    check('initial section at eps = 1e-3', initial)

    def future():
        terminal = TERMINAL / 'all_terminal_exact.json'
        cert, ind = tmp / 'future_certificate.json', tmp / 'independent_check.json'
        run('certify_future.py', terminal, cert, '1e-3')
        run('verify_future.py', terminal, cert, ind, '1e-3')
        c, i = json.loads(cert.read_text()), json.loads(ind.read_text())
        rc = json.loads((TERMINAL / 'future_certificate.json').read_text())
        ri = json.loads((TERMINAL / 'independent_check.json').read_text())
        strip = lambda d: {k: v for k, v in d.items() if k != 'certificate_sha256'}
        report('future certificate (directed integers)', c == rc and c['status'].startswith('PASS'),
               f"return before {c['global_quiescent_by'][:10]}, {c['active']} active cells, {c['masked_count']} masked ports")
        report('independent future check (directed decimals)',
               strip(i) == strip(ri) and i['status'] == 'PASS' and i['certificate_sha256'] == sha(cert))
        run('build_q_domain.py', terminal, TERMINAL / 'future_certificate.json', tmp / 'q.json')
        report('Q28 domain', same_bytes(tmp / 'q.json', TERMINAL / 'invariant_domain_Q28.json'))
    check('future certificates', future)


def main():
    if not __debug__:
        raise RuntimeError('Run without -O')
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        args = sys.argv[1:]
        if '--engine' in args:
            k = args.index('--engine')
            engine_checks(Path(args[k + 1]).resolve())
            del args[k:k + 2]
        if args:
            outputs_checks(Path(args[0]).resolve(), tmp)
        record_checks(tmp)
    failed = RESULTS.count(False)
    print(f'\n{RESULTS.count(True)} PASS, {failed} FAIL')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
