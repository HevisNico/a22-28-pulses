A22 — FRESH-LAUNCH PACKAGE v3.3 + C7
=====================================

The v3.3 program (covered by the manual proof), with the box width epsilon
as a parameter (as in sweep/SOURCE_FOR_REPLAY.zip), plus three changes, all
in affine/engine.py and listed in ENGINE_CHANGES_FROM_V33.diff:

1. Lemma C7 (flowing and advance): when the READY peak-time logarithm has no
   certified positive argument, the charge is bounded with the kernel's own
   ready_general_A22.peak_upper instead of refusing.
2. Lemma C6 (flowing only, second resort): piecewise evaluation of the pulse
   memory on [t, T] (new module affine/cluster_memory_cover.py).
3. Root brackets: the strictly positive slope required on [l, h] may be
   established on 8 or 32 equal pieces of [l, h] (_piecewise_slope), in the
   bracket test and in the Newton steps. The acceptance predicate is unchanged.

Launch (Linux, Python 3.12, a C compiler, Python and OpenSSL headers)
---------------------------------------------------------------------
  python3.12 -m venv .venv
  . .venv/bin/activate
  python -m pip install -r requirements.txt      # numpy 2.3.5, scipy 1.17.0
  python build_all_native.py
  python -B -m unittest discover -s tests        # 94 tests
  python -u -B launch_fresh.py --out results/A22_v33c7_1em3 --epsilon 1e-3 --workers 4 --memory-mib 3000

Resume after an interruption, with the same program and environment:
  python -u -B run.py --out results/A22_v33c7_1em3 --through 18 --epsilon 1e-3 --workers 4 --memory-mib 3000

The reference run took 1 h 15 min with 4 workers (cells (18, 4) and (18, 8):
about 29 min each). Then, from the repository root:
  python3 -I sweep/v33_c7/audit_campaign_dir.py results/A22_v33c7_1em3 out/
  python3 -I sweep/v23/eps_1em3/future/certify_future_eps.py out/all_terminal_exact.json out/future.json 1e-3
  python3 -I sweep/v23/eps_1em3/future/verify_future_certificate_eps.py out/all_terminal_exact.json out/future.json out/independent.json 1e-3
