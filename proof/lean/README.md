# Lean formalization

Five files, all without `sorry`; their `#print axioms` list only `propext`, `Classical.choice` and
`Quot.sound`.

## Strict-root core

[`StrictRoot.lean`](StrictRoot.lean) formalizes, in Lean 4 with Mathlib, the abstract mathematical
argument of Task 1 of [`REVIEW.md`](../../REVIEW.md): the strict-root lemma
(`proof/base/STRICT_ROOT_LEMMA_EN.txt`) and Sections 4–6 of
`proof/base/LEARNING_COVERAGE_THEOREM_EN.txt`.

| Result | Statement |
|---|---|
| `strict_of_encloses` | a sound enclosure of a set that straddles a value contains it strictly |
| `straddles_affine`, `straddles_image_strict*` | open-image lemma, two-point form: affine uses with nonzero coefficient, strictly monotone uses |
| `accepted_bracket_strict` | an accepted bracket (`f(l).hi ≤ 0`, `f(h).lo ≥ 0`) contains the root strictly |
| `newton_step_strict`, `newton_step_strict_slope` | the Newton image contains the root strictly, with freedom in `f(m)` or, when the rounded midpoint is zero and `f(0) < 0`, in the slope |
| `refine_strict` | every retained output of a finite refinement contains the root strictly and is not a point |
| `order_strict_after`, `order_strict_before`, `coincidence_never_passes` | a weak order test against a root date proves strict physical order; an exact coincidence passes neither test |
| `point_duration_countermodel` | without the fresh freedom, the weak test accepts a coincidence: the hypothesis is necessary |

**Scope.** Exact real arithmetic; outward rounding is a hypothesis. Every hypothesis of the form
`Encloses N (g '' S)` or `Straddles S v` is a claim about the code (fresh coordinates, no exact
shortcut in `exp`/`ln`, the slope evaluated before the guard, the fresh time atom of
`temporal.shift`). That bridge is not formalized; it is what remains of Task 1 for a reviewer.

## Lemmas C7, C6 and remark P

[`PeakBounds.lean`](PeakBounds.lean) proves the mathematical content of
[`proof/extensions/LEMMAS_C7_C6_EN.txt`](../extensions/LEMMAS_C7_C6_EN.txt), for the READY charge
`Q(u) = R + (q − R)e^{−Ku} + J(e^{−Ku} − e^{−Au})/(A − K)` with general `0 < K < A`.

| Result | Statement |
|---|---|
| `Q_mono_q`, `Q_mono_J`, `Q_le_corner` | C7, step 1: Q is monotone in the initial charge and in the current amplitude (`u ≥ 0`) |
| `c7_no_fire` | C7: a bound `B < 1` on the corner trajectory over `[0, H]` excludes a fire for every admissible device |
| `Q_le_peak` | C7, step 4: on `[0, H]`, Q is bounded by its values at 0, at H and at the stationary point clipped to `[0, H]` |
| `Q_mono_time` | C7, case `aa ≤ 0`: Q is nondecreasing in time, so its value at H bounds it on `[0, H]` |
| `c6_cover`, `bisect_cover` | C6: pieces covering `[0, H]`, each with an upper bound `< 1`, exclude a fire on `[0, H]`; bisection keeps a cover |
| `convex_comb_strict`, `hull_strict`, `remarkP_newton_strict` | remark P: a weighted average of values each strictly inside a piece enclosure is strictly inside the hull, so `newton_step_strict_slope` applies (rounded-midpoint-zero case) |

Same scope as above: that `peak_upper`, `dep.evaluate` and the derivative enclosures meet these
hypotheses is a claim about the code, not formalized.

## Lemma E (commutations at ε = 1e-3)

[`CommutationE.lean`](CommutationE.lean) proves the mathematical part of lemma E
([`proof/extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt`](../extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt),
section 3): a READY fire against a group of exterior events that includes input arrivals.

| Result | Statement |
|---|---|
| `e1_upper`, `e1_lower` | E1: the fire lies in `[min(a_min, f0), f0]` |
| `h_le_linear`, `arrivals_le` | E2: `h(u) ≤ A u` for every `u ≥ 0`, so the arrivals add at most `G A (t − a_min)` |
| `e2_tighten`, `kappa_form`, `below_line_of_monotone` | E2: with `Q0' ≥ σ > 0`, the fire comes no earlier than `f0 − κ (f0 − a_min)`, `κ = G A/(σ + G A)` |
| `e_fire_enclosure` | the date the macro emits, `[f0 − κ w, f0]` with `w ≥ (f0 − a_min)^+`, contains the fire |

`h(u) ≤ A u` is proved from `1 − e^{−x} ≤ x`, without the concavity condition the macro asserts.
E0 (which events leave the charge unchanged) and E3 (every order and fire position is kept) are
statements about the program and are not formalized.

## First crossings

[`FirstCrossing.lean`](FirstCrossing.lean): the facts about the first time the charge reaches 1
that the coverage theorem uses when it accepts a fire.

| Result | Statement |
|---|---|
| `first_crossing_exists`, `first_crossing_unique` | a continuous charge that reaches 1 has exactly one first crossing |
| `cover_encloses` | section 8(vi), `_first_crossing_cover`: below 1 on `[a, lower)` and at least 1 at `upper` puts the first crossing in `[lower, upper]`, with no slope assumption |
| `ready_root_bracket` | section 6, `ready_root`: the first crossing lies between those of the two corner trajectories |
| `deriv_stays_nonpos`, `ascending_root_is_first` | section 7: with `d' = −K d − A J`, `J ≥ 0`, a derivative that reaches `≤ 0` stays `≤ 0`, so a root where the charge rises is the first crossing |

The raw ends, where the current drops and `d` only decreases, are a hypothesis of
`ascending_root_is_first`.

## One future wave and the exact word

[`FutureWave.lean`](FutureWave.lean): the steps of the future proof
([`FUTURE_INVARIANCE_PROOF_EN.txt`](../base/FUTURE_INVARIANCE_PROOF_EN.txt), sections C–D) and of the
word-preservation argument
([`GLOBAL_THEOREM_AND_WORD_PRESERVATION_EN.txt`](../base/GLOBAL_THEOREM_AND_WORD_PRESERVATION_EN.txt))
that do not depend on the certified numbers.

| Result | Statement |
|---|---|
| `h_strictMonoOn` | if `K e^{−K} < A e^{−A}` (checked by the certificate), `h` is strictly increasing on `[0, 1]` |
| `protection_duration` | with `ℓ' = −b`, `β ≤ b ≤ 1.1`, the protected phase lasts between `L/1.1` and `L/β` |
| `first_crossing_shift`, `head_charge_shift`, `latency_fixed` | parents firing at `s + dᵢ` give a charge that depends on `t − s` only, so the cell fires at `s + d` with `d` independent of `s` |
| `word_preserved` | two waves fire the cell at times whose difference is that of the source pulses; applied layer by layer, this is the induction of the global theorem |

The certified inequalities (brackets, margins, the settling bound 12.791) remain those of the two
independent checkers.

## Build

Pinned to Lean `v4.35.0` and Mathlib `v4.35.0` (`lean-toolchain`, `lakefile.toml`). The GitHub
workflow `.github/workflows/lean.yml` builds the five files and fails if any `#print axioms` mentions
`sorryAx`. Locally:

```sh
cd proof/lean
lake update             # resolves Mathlib v4.35.0, writes lake-manifest.json
lake exe cache get      # prebuilt Mathlib
lake build
lake env lean StrictRoot.lean   # prints the axioms
lake env lean PeakBounds.lean
lake env lean CommutationE.lean
lake env lean FirstCrossing.lean
lake env lean FutureWave.lean
```

`StrictRoot.lean` can also be pasted into <https://live.lean-lang.org> (current Mathlib), where it checks
without errors.
