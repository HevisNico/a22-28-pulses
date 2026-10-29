A22 — CLEAN FRESH-LAUNCH PACKAGE, v3.3 (per-port parameters)

Purpose
=======
Run the research program from layer 1 through layer 18 in a NEW output
directory, with one program identity throughout. This archive contains
sources and instructions only: no campaign output, receipt, checkpoint or
precompiled extension.

v3.3 replaces the previous fresh-launch package, whose campaign stopped at
layer 18 (cells 1 and 11: "recovery guard overlaps external boundary").
Do not resume that campaign with this code: start a new one.

Quick start (Linux / POSIX)
===========================
Use Python 3.12, a C compiler, Python/OpenSSL development headers and the
OpenSSL libcrypto library. Extract this archive, enter its
A22_fresh_launch_v3_3_EN directory, then run YOURSELF:

  python3.12 -m venv .venv
  . .venv/bin/activate
  python -m pip install -r requirements.txt
  python build_all_native.py
  python -B -m unittest discover -s tests        # 77 tests, a few seconds
  python launch_fresh.py --out results/A22_v33_001

The dependency versions are numpy 2.3.5 and scipy 1.17.0. Build the extensions
on the target machine BEFORE starting. The build starts no campaign.

The last command starts a fresh 18-layer campaign. Its output directory must
not already exist. Defaults: 8 workers, 1536 MiB address-space budget per
worker, 14400 CPU-seconds per cell (--cpu-seconds 0 disables the limit).
Eight workers need roughly 12 GiB of free RAM; use --workers 4 otherwise.
A refusal or an exhausted budget stops acceptance.

Watch progress
==============
CELL messages report completed cells. VERIFIED reports a separate artifact
verification. LAYER ... RESEARCH COMPLETE records an accepted layer.
Long cells are not failures; refusal.json and stopped.json record failures.

Resume only an unchanged program and environment
================================================
After an environmental interruption, restore the SAME program, binaries and
dependency versions, then in this same directory:

  python -B run.py --out results/A22_v33_001 --through 18

A changed program/environment is refused with
  changed kernel/environment: use a new output directory
If ANY program source or built extension changes, start from layer 1 in a NEW
directory. Never copy old receipts or edit campaign.json.

What the program does (cumulative)
==================================
Unchanged physics kernel (kernel/), affine overlay (affine/), fixes A, B, C,
E, K, H, S of v3.2, plus:

1. Fresh-launch package (previous revision)
   - plain parameter boxes for C, LM, LS, LE, M wherever no port is known;
   - strict no-fire cover (affine/nofire_cover.py): a refused READY window
     is accepted as "no fire" only if charge < 1 is proved on every piece;
   - frozen program identity, checked by workers and at acceptance.

2. Fix P, per-port symbols (affine/port_symbols.py)          NEW in v3.3
   The model gives each port i of a cell its own constants LM_i, LS_i, LE_i,
   M_i. Each now has ONE affine symbol per (cell, port), used only where the
   kernel evaluates a quantity of that port:
     - event timing of port j (monitor delay D0_j, mark DM_j, silent DS_j,
       error DE_j);
     - the mark current (LM_j) and error-deposit current (LE_j) of port j;
     - recovery actuation: each mark segment uses its own port's LM;
     - deposits: the history of port j uses LE_j.
   Everything else keeps the plain box; C stays a plain box.
   Why: plain boxes forget that a port's constant is the same at every pulse.
   The enclosures grew 4-10x by layer 17 (worst date width 0.057 vs 0.0074
   in v3.2), which made a return-to-READY straddle an arrival at layer 18.
   Soundness: a symbol never stands for two different physical quantities;
   a plain box occurrence only adds freedom.

3. Fix R, recovery return against an event group (affine/recovery_group.py)
                                                              NEW in v3.3
   The kernel already resolves a slow-recovery return that cannot be ordered
   against ONE exterior event with its certified local-cycle resolver
   (cycle_local_A20.pending_window: every admissible order, at most one
   extra fire, window shorter than the fast phase). The path for a GROUP of
   overlapping events had no such fallback and refused. Fix R applies the
   SAME resolver and the SAME join rule (all branches READY, no emission).
   Otherwise the original refusal is raised unchanged.

Checks after the campaign
=========================
  python -B tools/verif_h1h2.py --campaign results/A22_v33_001 --layer 18 --lane 4 --out h1h2_18_4.json
  python -B tools/verif_h1h2.py --campaign results/A22_v33_001 --layer 18 --lane 8 --out h1h2_18_8.json
  python -B tools/bilan_campagne.py --campaign results/A22_v33_001 --reference domaine_A14_reference.json --out bilan.json
(--out files must be outside the campaign directory.)

Scientific status
=================
Research candidate, not a qualified all-trajectories verifier. Artifact
integrity and fresh/disk equality establish recorded calculation integrity;
they do not by themselves prove every hybrid enclosure sound.
reference/full_model_reference.md is the user's original model, unchanged.
VALIDATION_EN.txt records the checks made on this exact package.
