# Call for review

This repository contains one result, its campaign and a **manual proof** that the campaign covers
every admissible trajectory, under stated execution assumptions. The proof has **not yet been reviewed
by an independent expert**. The fastest way to check it is to take small, self-contained pieces. Each
task below can be read in **one to three hours** without knowing the rest.

**What helps most:** one of three answers, given as a GitHub issue titled `Review: <task>`:
- "the argument holds";
- "there is a gap at <file:section or file:line>, because ...";
- "here is a counterexample".

Partial reviews are welcome. Tasks are listed **most important first**.

Background: the [README](README.md), the reading order in [proof/README.md](proof/README.md) and the
review guide [proof/base/REVIEW_GUIDE_EN.txt](proof/base/REVIEW_GUIDE_EN.txt). *Affine form* means
*c + Σ dₖ εₖ + [−e, e]*, valid for every ε in [−1, 1]^N; "the theorem" means
`proof/base/LEARNING_COVERAGE_THEOREM_EN.txt`, written for the first version of the result (box ±1e-4,
128 pulses, T = 1116) and extended to this one by the documents of `proof/extensions/`.

The engine rewrites some functions when it is loaded; the final text of those of the first version is in
`proof/base/effective_source_v33/`. Line numbers cited below refer to that first engine; the functions
have the same names in `engine/`.

---

## Task 1 — Open-image lemma and strict root order (most load-bearing)

**Claim.** Every computed threshold root is enclosed *strictly*: with the old parameters and dates
fixed, the computed enclosure contains an open interval around the true root (theorem, Sections 4–6;
also `proof/base/STRICT_ROOT_LEMMA_EN.txt`). Consequently, when the engine accepts
an order from a weak test *x − t ≥ 0*, the physical order is strict, and an exact simultaneity between a
spike and an event can never pass the ordinary order test.

**Where:** `engine/affine/engine.py` (`affine_refine`, `root`, `ready_root`), the effective `advance`
(`proof/base/effective_source_v33/advance_inner.txt`), `engine/affine/temporal.py`
(`minus`, `shift`), `engine/affine/affine_iv.py` (`_unary`, exp/ln).

**Questions.**
1. Is the open-image lemma correct as stated, for the operations actually used after the fresh
   exponential (products, sums, hulls, truncation, error promotion)?
2. In `affine_refine`, does every retained output (not only the last bracket) keep the true root
   strictly inside, including the case where the rounded midpoint is 0?
3. Is there any exp/ln evaluation on these paths whose result is exact (no adjacent-number expansion)
   and would remove the strict margin?
   (Known case: `exp` returns 1 exactly for the exact point argument 0, that is at elapsed time zero,
   where q0 < 1 excludes a root; the wording of Section 5.1 on this is clarified at the end of
   `proof/extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt`.)

**Machine-checked part.** The abstract argument behind questions 1 and 2 (open-image lemma in
two-point form, accepted brackets, Newton steps including the rounded-midpoint-zero case, every
retained refinement output, strict event order) is formalized in Lean 4 with Mathlib:
[`proof/lean/StrictRoot.lean`](proof/lean/StrictRoot.lean), no `sorry`. What remains to review is
the bridge: that the code satisfies its hypotheses (`Encloses …`, `Straddles …`), which is
question 3 together with freshness of the perturbed coordinates and the evaluation order.

## Task 2 — Event coverage and every successful exit (theorem, Section 8)

**Claim.** For every physical order of events, including equal times, the program keeps a branch that
covers it, through every successful path: ordinary advance, external groups, protected FAST/SLOW
groups, recovery/auxiliary groups, the local-cycle resolver, and the recorded fire/event commutations
(including the fallback `_first_crossing_cover`). Entry into event groups is always forward in time
(`proof/base/GROUP_ENTRY_CLOCK_LEMMA_EN.txt`). This campaign records 6 commutations, all in layer 18:
2 against an input arrival with its mark (four orders), 2 against an input cut and 2 against an error
onset (two orders each); all are covered by lemma E of
[`proof/extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt`](proof/extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt)
(`terminal/commutation_usage.json`, `tools/audit_commutations.py`).

**Where:** effective `unit` (`proof/base/effective_source_v33/unit.txt`),
`validation_A15.py` (`admissible_orders`, `protected_section_cluster`, `recovery_auxiliary_cluster`),
`cycle_local_A20.py`, `engine/affine/commutation.py`.

**Questions.**
1. Can a physical branch be lost at a group boundary, an equal-time order, or a FAST/SLOW boundary of
   zero duration?
2. Is the first-crossing property (unimodality of the READY charge between events, Section 7) used
   correctly at every place a spike is accepted?
   (A point to check: `_first_crossing_cover` encloses the first *contact* Q ≥ 1, tangency
   included, not by itself an upward crossing. On the path where it is used, Q0 receives no new
   arrival, its derivative does not turn positive again after becoming negative (Section 7), and the
   accepted upper guard at a positive time has the open enclosure of Section 5, so `f(hi).lo ≥ 0`
   gives a physical `f(hi) > 0`: a maximum tangent to 1 is not accepted on that path.)

## Task 3 — Unions: memory anchors and the fields kept from the first branch (theorem, Section 9)

**Claim.** `join_states` keeps the discrete fields (current mark and error origins, fire date, raw
inputs) of its first branch, and `dep.join` keeps the first branch's memory anchor. At every reachable
successful caller, these are common to all branches, or the memory is dropped (which is conservative).

**Where:** `validation_A15.py` (`join_states`), `dependances_A17.py` (`join`), the callers in the
effective `unit`, `engine/affine/commutation.py`.

**Questions.**
1. Is there a reachable union whose branches differ in a mark or error origin, or in the fire date?
2. Is it true that separately recomputed returns always get distinct time atoms, so that their memories
   can never be wrongly merged under an equal token?

## Task 4 — Future invariance and exact transmission

**Claim.** From the quiescent domain Q, every source pulse spaced by at least 20 makes each of the 191
active cells fire exactly once, the network is at rest within 12.791 (Q28: before 12.7907), and the state returns to Q. Active
cells have fixed latencies, so the pulse word is transmitted exactly.

**Where:** `proof/base/FUTURE_INVARIANCE_PROOF_EN.txt`, `proof/base/GLOBAL_THEOREM_AND_WORD_PRESERVATION_EN.txt`,
the two checkers `tools/certify_future.py` and `tools/verify_future.py`.

**Questions.**
1. Is the "influential / masked / silent" classification of ports enough to keep the head response
   identical from wave to wave?
2. Are the strict margins (reopening, end of raw pulse, end of error) the right ones, and are the two
   checkers' series and tail bounds correct?

## Task 5 — Outward-rounded affine arithmetic

**Claim.** Each affine operation is valid pointwise, for arbitrary represented operand values:
- the multiplication remainder covers every term (`__mul__`, line 182);
- in the mean-value form for exp, ln and reciprocal, the slope domain includes the expansion point
  (`_unary`, line 201);
- a union keeps a common coefficient and absorbs the spread (`_dev_up` line 285, `hull` line 308);
- truncation to 256 symbols bounds the dropped mass upward (`truncate_coeff`: Python reference in
  `engine/affine/rounding.py` line 51, C in `engine/affine/rounding_native.c`).

**Where:** `engine/affine/affine_iv.py`, `engine/affine/rounding.py`, `engine/affine/rounding_native.c`,
`engine/affine/sound_lattice.py`, the theorem's Section 4.

## Task 6 — Per-port parameter symbols (fix P)

**Claim.** Each port *j* of a cell gets one symbol per constant (LM, LS, LE, M), used only where the
kernel evaluates a quantity of port *j*; every other occurrence keeps a plain interval (C is plain
everywhere). Hence every trajectory of the model is represented, and no correlation the model does not
have is imposed.

**Where:** `engine/affine/port_symbols.py` (`settings` line 49, `with_port` line 93, `raw_dose` line 107,
`with_deposit_port` line 133), `engine/affine/engine.py` (event durations line 155, coefficients
line 222), tests in `engine/tests/test_v33_ports.py`.

**Questions.**
1. Does every port-dependent use of LM, LS, LE, M receive that port's value, and every other use keep
   the plain box?
2. Is the per-mark `raw_dose` identical to the kernel's for a single-port history, and correct for a
   history that mixes ports?

## Task 7 — Lemmas C7, C6 and remark P (wider box)

**Claim.** At ±1e-3 the READY charge is bounded with the kernel's own monotone peak bound where the first
version refused (C7), a piecewise version of the same bound covers the pulse memory (C6), and the
root-bracket slope is established on a partition without changing the acceptance predicate (P).

**Where:** `proof/extensions/LEMMAS_C7_C6_EN.txt`; machine-checked mathematics in
`proof/lean/PeakBounds.lean`; code in `engine/affine/cluster_memory_cover.py` and the C7 additions listed in
`engine/ENGINE_CHANGES_FROM_V33.diff`.

## Task 8 — Lemma E: a fire against a group of events, and its outward rounding

**Claim.** In READY, a fire whose order against a group of input arrivals, input cuts and auxiliary actions
is undecided is enclosed by F ∈ [f0 − κ w, f0]; every admissible order is computed and joined.

**Where:** `proof/extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt` (lemma E), `proof/lean/CommutationE.lean`
(its mathematical part), `engine/affine/commutation.py`. The widening must be applied outward exactly:
`proof/extensions/lemma_e_outward_rounding/` documents the correction of an inward rounding of the
negated widening, with the regression test `engine/tests/test_commutation_rounding.py` and its outputs on
the uncorrected and corrected engines.

**Questions.** Are the bounds on σ and on Σ g_j valid on the whole window? Is every quantity entering the
emitted enclosure rounded outward?

## Task 9 — 28 pulses and the terminal cut at 230

**Claim.** The coverage argument does not depend on the number of source pulses, and the earlier cut at
230 is checked, not assumed: the terminal event must be last in every queue, every retained terminal time
must be exactly 230 with no uncertain term, and every cell must end READY with no active input.

**Where:** `proof/extensions/CALENDAR_COVERAGE_BRIDGE.md`; the calendar change in `engine/run.py` and
`engine/kernel/R_cycle_local_A20_2026-10-18/validation_A15.py` (terminal event and silent relaxation at
230); `engine/tests/test_calendar28.py`; the passive checks in `tools/extract_terminal.py` and
`tools/audit_lineage.py`.

## Task 10 — The two future checkers and what each one checks

**Claim.** `tools/certify_future.py` (directed integers) and `tools/verify_future.py` (directed decimals,
written separately) both check every premise of Q28 on all 216 cells, silent cells included, and every
strict inequality of the future proof.

**Where:** the two files; `terminal/future_certificate.json`, `terminal/independent_check.json`,
`terminal/invariant_domain_Q28.json`; `tools/build_q_domain.py`.

**Questions.** Is any premise of the future proof checked by only one of the two programs? Are their
series remainders and directed roundings correct?
