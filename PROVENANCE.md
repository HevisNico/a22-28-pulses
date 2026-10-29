# Provenance

## Engine (`engine/`)

The v3.3 + C7 package of [a22-interval-replay](https://github.com/HevisNico/a22-interval-replay)
(`sweep/v33_c7/A22_fresh_launch_v3_3_C7.zip`, release v4.4), with three changes:

1. `calendar28_T230.patch` (release v4.6 of a22-interval-replay): in `run.py` the source emits 28 pulses
   and the schedule and terminal time enter the campaign identity; in
   `kernel/R_cycle_local_A20_2026-10-18/validation_A15.py` the terminal end event is at 230 and the silent
   auxiliary relaxation is evaluated at 230. Test: `tests/test_calendar28.py`.
2. The outward rounding of the lemma-E widening in `affine/commutation.py`
   ([`proof/extensions/lemma_e_outward_rounding/`](proof/extensions/lemma_e_outward_rounding/README.md)).
   Test: `tests/test_commutation_rounding.py`.
3. Nothing else. The native extensions are not committed; those of the run are in the release asset
   `A22_28_engine_as_run.zip` (built with CPython 3.13.17, numpy 2.3.5, scipy 1.17.0).

## Campaign (`campaign/`, `terminal/`)

Run once with the engine above: `run.py --through 18 --epsilon 1e-3 --workers 4 --memory-mib 3000`,
kernel `b49dca10167d09511d6933d3ca1dbc50ebce16664cb872395f707ab689fa89ae`, run
`25e6fa5fa78d4ed7afa804f780a0d92c`, 2026-10-29, 7 min 46 s. `campaign/` keeps the identity, the per-layer
completion and verification records, the console log and the manifest of all 488 output files; the outputs
themselves are the release asset `A22_28_campaign28_T230_eps1e-3.zip`. `terminal/` was produced from those
outputs by the tools of this repository.

The same schedule had been run before with the uncorrected engine (kernel `886d1c5c…`, release v4.6 of
a22-interval-replay). The terminal enclosures, the terminal domain and the future certificates of the two
runs are identical; only identity hashes differ.

## Proof documents and tools

Copied from a22-interval-replay at commit `100e5852f94fdeeaa97cd856ab6f7e3b7d8ee261`:

| Here | There |
|---|---|
| `proof/base/LEARNING_COVERAGE_THEOREM_EN.txt`, `GROUP_ENTRY_CLOCK_LEMMA_EN.txt`, `REVIEW_GUIDE_EN.txt` | `proof/learning_justification/output/` |
| `proof/base/TRAINING_ENTRY_REVIEW_EN.txt`, `FUTURE_INVARIANCE_PROOF_EN.txt`, `GLOBAL_THEOREM_AND_WORD_PRESERVATION_EN.txt` | `proof/` |
| `proof/base/STRICT_ROOT_LEMMA_EN.txt`, `proof/base/effective_source_v33/` | `proof/kernel_soundness/output/` |
| `proof/base/PROOF_WALKTHROUGH.md` | `PROOF_WALKTHROUGH.md` |
| `proof/extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt`, `FUTURE_INVARIANCE_GENERAL_EPS_EN.txt`, `LEMMAS_C7_C6_EN.txt` | `sweep/v33_c7/` |
| `proof/extensions/CALENDAR_COVERAGE_BRIDGE.md` | `sweep/schedule28_T230/` |
| `proof/lean/` | `proof/lean/` |
| `model/full_model_reference.md` | `engine/reference/` |
| `tools/audit_provenance.py`, `tools/certify_future_v33.py` | `proof/provenance_audit/` (`certify_future.py`) |
| `tools/certify_future.py`, `tools/verify_future.py` | `sweep/v23/eps_1em3/future/` (`certify_future_eps.py`, `verify_future_certificate_eps.py`) |
| `tools/certify_initial_section.py`, `tools/extract_terminal.py`, `tools/audit_commutations.py` | `sweep/v33_c7/` (`certify_initial_section_eps.py`, `audit_campaign_dir.py`, `audit_commutations.py`) |
| `tools/audit_lineage.py` | the v4.6 delivery (`audit_lineage_and_clocks.py`) |

Changes to the tools: import paths; the extractor reads the terminal time from the campaign identity;
`tools/verify_future.py` also checks the premises of every silent cell (the original skipped silent cells;
the numerical results are unchanged on all published domains). `tools/build_q_domain.py` and `tools/verify.py` are new.
The documents are unchanged; their figures for the first version (±1e-4, 128 pulses, T = 1116) are carried
to this result by the extension documents.

## Current documentation clarifications

`model/CURRENT_SPEC.md` is a current reading guide to the archived equations and the
28-pulse/T = 230 extensions. The README and proof index link to it and state the exact
parameter and initial-state scope. The introductory docstring of
`tools/audit_commutations.py` describes its diagnostic output and the general lemma E.
These clarifications leave the historical model documents, engine sources, proof archives,
campaign records, certificates and release-asset checksums unchanged. They do not extend
the proved family or supply a formal verification of the engine.

## Verification corrections

The future-certificate generator, independent checker and Q28 builder now require exact agreement
between the terminal campaign's ε, the certificate's ε and any explicit command-line value. Omitting
the argument uses the campaign value. `certificate_parameters.py` shares only metadata validation;
the two numerical implementations remain separate. The independent Decimal checker constructs the
parameter factors with its directed interval operations and records `eps` in its report.
`terminal/independent_check.json` is regenerated with that additional field; its numerical values are unchanged.

`tools/verify.py --engine` now reconstructs the archived identity statically from the files and recorded
environment. The optional `--check-runtime` separately verifies the interpreter, dependency versions,
arithmetic backend and actually loaded native binaries. Failed static checks prevent runtime loading.
Regression tests for these behaviors are in `tools/tests/` and run in CI.

These changes do not modify engine sources, the campaign identity, release assets, terminal enclosures,
the directed-integer future certificate, Q28 or the proof documents.
