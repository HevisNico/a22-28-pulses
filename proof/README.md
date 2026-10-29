# The proof, in reading order

The argument is organized into six steps. Each step names the document that argues it and the program or certificate
that checks its finite part.

| Step | Statement | Argument | Finite checks |
|---|---|---|---|
| 1. Model | the hybrid cell, its parameters, the network and the source | [`model/CURRENT_SPEC.md`](../model/CURRENT_SPEC.md), with the archived equations linked there | — |
| 2. Initial section | from every admissible initial state, the first source pulse is admitted from known invariants | [`base/LEARNING_COVERAGE_THEOREM_EN.txt`](base/LEARNING_COVERAGE_THEOREM_EN.txt), [`extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt`](extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt) | `tools/certify_initial_section.py` → `terminal/initial_section_eps1e-3.json` |
| 3. Training coverage | the enclosure computed by the engine contains every trajectory, up to the cut at T = 230 | [`base/LEARNING_COVERAGE_THEOREM_EN.txt`](base/LEARNING_COVERAGE_THEOREM_EN.txt), [`base/GROUP_ENTRY_CLOCK_LEMMA_EN.txt`](base/GROUP_ENTRY_CLOCK_LEMMA_EN.txt), [`base/STRICT_ROOT_LEMMA_EN.txt`](base/STRICT_ROOT_LEMMA_EN.txt); at ±1e-3: [`extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt`](extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt) (lemma E), [`extensions/LEMMAS_C7_C6_EN.txt`](extensions/LEMMAS_C7_C6_EN.txt) (C7, C6, P), [`extensions/lemma_e_outward_rounding/`](extensions/lemma_e_outward_rounding/README.md); for 28 pulses and T = 230: [`extensions/CALENDAR_COVERAGE_BRIDGE.md`](extensions/CALENDAR_COVERAGE_BRIDGE.md) | the campaign (`campaign/`), `tools/extract_terminal.py`, `tools/audit_lineage.py`, `tools/audit_commutations.py` |
| 4. Entry into Q28 | at T = 230 every trajectory is in the explicit domain Q28 | the same documents | `terminal/all_terminal_exact.json`, `tools/build_q_domain.py` → `terminal/invariant_domain_Q28.json` |
| 5. Future regime | from Q28, for every source sequence with gaps ≥ 20, each of the 191 active cells fires exactly once per pulse and the network returns to Q28 | [`base/FUTURE_INVARIANCE_PROOF_EN.txt`](base/FUTURE_INVARIANCE_PROOF_EN.txt), [`extensions/FUTURE_INVARIANCE_GENERAL_EPS_EN.txt`](extensions/FUTURE_INVARIANCE_GENERAL_EPS_EN.txt) | `tools/certify_future.py`, `tools/verify_future.py` → `terminal/future_certificate.json`, `terminal/independent_check.json` |
| 6. Exact transmission | each active cell has a fixed latency, so intervals between pulses are preserved through all 18 layers | [`base/GLOBAL_THEOREM_AND_WORD_PRESERVATION_EN.txt`](base/GLOBAL_THEOREM_AND_WORD_PRESERVATION_EN.txt) | — |

A guided tour of the first version of the argument (five propositions, the three most delicate points)
is [`base/PROOF_WALKTHROUGH.md`](base/PROOF_WALKTHROUGH.md); the review guide of that version is
[`base/REVIEW_GUIDE_EN.txt`](base/REVIEW_GUIDE_EN.txt), and [`base/TRAINING_ENTRY_REVIEW_EN.txt`](base/TRAINING_ENTRY_REVIEW_EN.txt)
is its critical review of the training entry.

## Current model and historical references

[`model/CURRENT_SPEC.md`](../model/CURRENT_SPEC.md) specifies the current parameter family,
initial states and 28-pulse/T = 230 protocol. `model/full_model_reference.md` and its copy inside
`engine/reference/` preserve the historical reference and status text. Read their 128-pulse/T = 1116
figures with the explicit substitutions in the current specification and calendar bridge below.

## The two layers of documents

`base/` holds the proof of the first complete version (box ±1e-4, 128 training pulses, T = 1116), copied
unchanged. `extensions/` holds what carries it to this result: general ε (initial section, lemma E, future
proof), lemmas C7, C6 and remark P, the outward rounding of lemma E, and the bridge to 28 pulses with the
cut at 230. Where a base document states a figure of the first version (±1e-4, 128 pulses, 1116), the
extension documents give the corresponding statement here. Some base files state that the training entry
is open; the coverage theorem supersedes them.

## Machine-checked parts (Lean 4, Mathlib, no `sorry`)

[`lean/`](lean/README.md): the abstract core of the strict-root lemma (`StrictRoot.lean`), lemmas C7, C6
and P (`PeakBounds.lean`), the mathematical part of lemma E (`CommutationE.lean`), the first-crossing facts
used by the coverage theorem (`FirstCrossing.lean`), and the number-free steps of the future proof and of
exact transmission (`FutureWave.lean`). Not machine-checked: the program, its arithmetic, the campaign, and
the bridge between the code and these statements.

## Assumptions

The coverage argument holds under A1–A4, stated in the theorem: authentic execution of the recorded program,
correct arithmetic runtime and native binaries, fail-closed assertions, and namespace discipline.
