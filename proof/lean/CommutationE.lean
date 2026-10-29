import Mathlib

/-!
# A22 v4.4 — lemma E: a READY fire against a group of exterior events

This file formalizes the mathematical part of lemma E
(`sweep/v33_c7/COVERAGE_THEOREM_GENERAL_EPS_EN.txt`, section 3), which proves the
commutation macro `affine/commutation.py` at ε = 1e-3, where the fire may meet input
arrivals.

## What is modelled

All statements are for one fixed physical realization.

* `Q0` is the READY charge without the group's arrivals, `f0` its first crossing of 1.
* `Q` is the charge with the arrivals, continued without the fire reset; `F` is its first
  threshold time (`1 ≤ Q F`, `Q < 1` on `[t0, F)`).
* An arrival at `a j` with amplitude `g j ≥ 0` adds `g j * hplus (t - a j)`, where
  `hplus` is `0` before the arrival and the pulse response
  `h(u) = A/(A-K) (e^{-K u} - e^{-A u})` after it.

## What is proved (no `sorry`, see `#print axioms` at the end)

**E1** (`e1_upper`, `e1_lower`): if `Q ≥ Q0` before `f0`, the fire comes no later than
`f0`; if `Q = Q0` before the first arrival, it comes no earlier than `min(a_min, f0)`.

**E2** (`h_le_linear`, `arrivals_le`, `e2_tighten`): `h(u) ≤ A u` for every `u ≥ 0`, so the
arrivals add at most `G A (t - a_min)` with `G ≥ Σ g j`. If `Q0` stays below the line of
slope `σ > 0` through `(f0, 1)` on `[a_min, f0]`, the fire comes no earlier than
`(σ f0 + G A a_min)/(σ + G A) = f0 - κ (f0 - a_min)`, `κ = G A/(σ + G A)` (`kappa_form`).

**Enclosure** (`e_fire_enclosure`): together, `f0 - κ w ≤ F ≤ f0` for every
`w ≥ (f0 - a_min)^+`, which is the date the macro emits.

The bound `h(u) ≤ A u` is proved for every `u ≥ 0` from `1 - e^{-x} ≤ x`, without the
concavity condition the macro asserts; that assertion is therefore not needed.

## What is NOT proved here

E0 (raw_off and auxiliary actions leave the READY charge unchanged) and E3 (every order
and fire position is computed and joined) are statements about the program, not
formalized. `Q0 ≤ 1 - σ (f0 - t)` is a hypothesis: it follows from `Q0' ≥ σ` on the
window (`below_line_of_monotone`), and the program obtains `σ` from a derivative
enclosure. The soundness of the program's interval evaluations is not formalized.
-/

namespace A22.LemmaE

open Set

/-! ## E1: the fire bracket -/

/-- If the arrivals only add charge before `f0`, the fire comes no later than `f0`. -/
theorem e1_upper {Q Q0 : ℝ → ℝ} {t0 f0 F : ℝ}
    (ht0f0 : t0 ≤ f0)
    (hdom : ∀ t ∈ Icc t0 f0, Q0 t ≤ Q t)
    (hf0 : Q0 f0 = 1)
    (hfirst : ∀ t ∈ Ico t0 F, Q t < 1) :
    F ≤ f0 := by
  by_contra h
  push_neg at h
  have h1 : Q f0 < 1 := hfirst f0 ⟨ht0f0, h⟩
  have h2 : Q0 f0 ≤ Q f0 := hdom f0 ⟨ht0f0, le_rfl⟩
  linarith

/-- Before the first arrival the charge is `Q0 < 1`, so the fire comes no earlier than
`min(a_min, f0)`. -/
theorem e1_lower {Q Q0 : ℝ → ℝ} {t0 f0 amin F : ℝ}
    (hF : 1 ≤ Q F) (htF : t0 ≤ F)
    (hsame : ∀ t ∈ Ico t0 (min amin f0), Q t = Q0 t)
    (hbelow : ∀ t ∈ Ico t0 f0, Q0 t < 1) :
    min amin f0 ≤ F := by
  by_contra h
  push_neg at h
  have hQ : Q F = Q0 F := hsame F ⟨htF, h⟩
  have hb : Q0 F < 1 := hbelow F ⟨htF, lt_of_lt_of_le h (min_le_right _ _)⟩
  linarith

/-! ## E2: the contribution of the arrivals -/

/-- Pulse response of the model, `h(u) = A/(A-K) (e^{-K u} - e^{-A u})`. -/
noncomputable def h (A K u : ℝ) : ℝ :=
  A / (A - K) * (Real.exp (-K * u) - Real.exp (-A * u))

/-- `h(u) ≤ A u` for every `u ≥ 0`. -/
theorem h_le_linear {A K u : ℝ} (hK : 0 ≤ K) (hKA : K < A) (hu : 0 ≤ u) :
    h A K u ≤ A * u := by
  have hAK : 0 < A - K := sub_pos.mpr hKA
  have hA : 0 < A := lt_of_le_of_lt hK hKA
  have hne : A - K ≠ 0 := ne_of_gt hAK
  have hsplit : Real.exp (-A * u) = Real.exp (-K * u) * Real.exp (-((A - K) * u)) := by
    rw [← Real.exp_add]
    congr 1
    ring
  have he1 : Real.exp (-K * u) ≤ 1 := by
    have h0 : Real.exp (-K * u) ≤ Real.exp 0 :=
      Real.exp_le_exp.mpr (by nlinarith [mul_nonneg hK hu])
    rwa [Real.exp_zero] at h0
  have hlin : 1 - (A - K) * u ≤ Real.exp (-((A - K) * u)) := by
    have h0 := Real.add_one_le_exp (-((A - K) * u))
    linarith
  have hle1 : Real.exp (-((A - K) * u)) ≤ 1 := by
    have h0 : Real.exp (-((A - K) * u)) ≤ Real.exp 0 :=
      Real.exp_le_exp.mpr (by nlinarith [mul_nonneg hAK.le hu])
    rwa [Real.exp_zero] at h0
  have h1x : 0 ≤ 1 - Real.exp (-((A - K) * u)) := by linarith
  have hkey : Real.exp (-K * u) * (1 - Real.exp (-((A - K) * u)))
      ≤ 1 * (1 - Real.exp (-((A - K) * u))) := mul_le_mul_of_nonneg_right he1 h1x
  have hdiff : Real.exp (-K * u) - Real.exp (-A * u) ≤ (A - K) * u := by
    rw [hsplit]
    nlinarith [hkey, hlin]
  have hcoef : 0 ≤ A / (A - K) := div_nonneg hA.le hAK.le
  have hcancel : A / (A - K) * ((A - K) * u) = A * u := by
    field_simp <;> ring
  unfold h
  calc A / (A - K) * (Real.exp (-K * u) - Real.exp (-A * u))
      ≤ A / (A - K) * ((A - K) * u) := mul_le_mul_of_nonneg_left hdiff hcoef
    _ = A * u := hcancel

/-- Admitted response of one arrival: `0` before it, `h` after it. -/
noncomputable def hplus (A K v : ℝ) : ℝ := if v ≤ 0 then 0 else h A K v

theorem hplus_le {A K v : ℝ} (hK : 0 ≤ K) (hKA : K < A) :
    hplus A K v ≤ A * max v 0 := by
  have hA : 0 < A := lt_of_le_of_lt hK hKA
  unfold hplus
  split_ifs with hv
  · exact mul_nonneg hA.le (le_max_right _ _)
  · push_neg at hv
    rw [max_eq_left hv.le]
    exact h_le_linear hK hKA hv.le

/-- The arrivals of the group, all at or after `a_min`, add at most `(Σ g) A (t - a_min)`. -/
theorem arrivals_le {ι : Type*} (s : Finset ι) (g a : ι → ℝ) {A K amin t : ℝ}
    (hK : 0 ≤ K) (hKA : K < A) (hg : ∀ j ∈ s, 0 ≤ g j) (ha : ∀ j ∈ s, amin ≤ a j)
    (ht : amin ≤ t) :
    ∑ j ∈ s, g j * hplus A K (t - a j) ≤ (∑ j ∈ s, g j) * A * (t - amin) := by
  have hA : 0 < A := lt_of_le_of_lt hK hKA
  rw [Finset.sum_mul, Finset.sum_mul]
  apply Finset.sum_le_sum
  intro j hj
  have h1 : hplus A K (t - a j) ≤ A * max (t - a j) 0 := hplus_le hK hKA
  have h2 : max (t - a j) 0 ≤ t - amin :=
    max_le (by linarith [ha j hj]) (by linarith)
  calc g j * hplus A K (t - a j) ≤ g j * (A * max (t - a j) 0) :=
        mul_le_mul_of_nonneg_left h1 (hg j hj)
    _ ≤ g j * (A * (t - amin)) :=
        mul_le_mul_of_nonneg_left (mul_le_mul_of_nonneg_left h2 hA.le) (hg j hj)
    _ = g j * A * (t - amin) := by ring

/-- If `t ↦ Q0 t - σ t` is nondecreasing on `[a_min, f0]` (that is, `Q0' ≥ σ`) and
`Q0 f0 = 1`, then `Q0` stays below the line of slope `σ` through `(f0, 1)`. -/
theorem below_line_of_monotone {Q0 : ℝ → ℝ} {σ amin f0 : ℝ}
    (hmono : MonotoneOn (fun t => Q0 t - σ * t) (Icc amin f0)) (hf0 : Q0 f0 = 1)
    {t : ℝ} (ht : t ∈ Icc amin f0) :
    Q0 t ≤ 1 - σ * (f0 - t) := by
  have h1 : Q0 t - σ * t ≤ Q0 f0 - σ * f0 :=
    hmono ht ⟨le_trans ht.1 ht.2, le_rfl⟩ ht.2
  linarith

/-- **E2.** With `Q0` below the line of slope `σ > 0` and the arrivals bounded by
`G A (t - a_min)`, the fire comes no earlier than `(σ f0 + G A a_min)/(σ + G A)`. -/
theorem e2_tighten {Q Q0 : ℝ → ℝ} {σ G A amin f0 F : ℝ}
    (hσ : 0 < σ) (hG : 0 ≤ G) (hA : 0 < A)
    (hF : 1 ≤ Q F) (hFlo : amin ≤ F) (hFhi : F ≤ f0)
    (hline : ∀ t ∈ Icc amin f0, Q0 t ≤ 1 - σ * (f0 - t))
    (hadd : ∀ t ∈ Icc amin f0, Q t ≤ Q0 t + G * A * (t - amin)) :
    (σ * f0 + G * A * amin) / (σ + G * A) ≤ F := by
  have hGA : 0 ≤ G * A := mul_nonneg hG hA.le
  have hpos : 0 < σ + G * A := by linarith
  have hne : σ + G * A ≠ 0 := ne_of_gt hpos
  have hT : (σ * f0 + G * A * amin) / (σ + G * A) * (σ + G * A)
      = σ * f0 + G * A * amin := by
    field_simp <;> ring
  by_contra hlt
  push_neg at hlt
  have hmul : F * (σ + G * A) < (σ * f0 + G * A * amin) / (σ + G * A) * (σ + G * A) :=
    mul_lt_mul_of_pos_right hlt hpos
  rw [hT] at hmul
  have h1 : Q F ≤ Q0 F + G * A * (F - amin) := hadd F ⟨hFlo, hFhi⟩
  have h2 : Q0 F ≤ 1 - σ * (f0 - F) := hline F ⟨hFlo, hFhi⟩
  nlinarith [hmul, h1, h2, hF]

/-- The same bound written with `κ = G A/(σ + G A)`. -/
theorem kappa_form {σ G A amin f0 : ℝ} (hpos : 0 < σ + G * A) :
    (σ * f0 + G * A * amin) / (σ + G * A) = f0 - G * A / (σ + G * A) * (f0 - amin) := by
  have hne : σ + G * A ≠ 0 := ne_of_gt hpos
  field_simp <;> ring

/-! ## The emitted date encloses the fire -/

/-- **Lemma E, enclosure.** For every `w ≥ (f0 - a_min)^+`, the fire date `F` lies in
`[f0 - κ w, f0]` with `κ = G A/(σ + G A)`. -/
theorem e_fire_enclosure {Q Q0 : ℝ → ℝ} {t0 f0 amin F σ G A w : ℝ}
    (hσ : 0 < σ) (hG : 0 ≤ G) (hA : 0 < A)
    (ht0f0 : t0 ≤ f0) (htF : t0 ≤ F)
    (hF : 1 ≤ Q F) (hfirst : ∀ t ∈ Ico t0 F, Q t < 1)
    (hdom : ∀ t ∈ Icc t0 f0, Q0 t ≤ Q t) (hf0 : Q0 f0 = 1)
    (hsame : ∀ t ∈ Ico t0 (min amin f0), Q t = Q0 t)
    (hbelow : ∀ t ∈ Ico t0 f0, Q0 t < 1)
    (hline : ∀ t ∈ Icc amin f0, Q0 t ≤ 1 - σ * (f0 - t))
    (hadd : ∀ t ∈ Icc amin f0, Q t ≤ Q0 t + G * A * (t - amin))
    (hw : max (f0 - amin) 0 ≤ w) :
    f0 - G * A / (σ + G * A) * w ≤ F ∧ F ≤ f0 := by
  have hup : F ≤ f0 := e1_upper ht0f0 hdom hf0 hfirst
  have hlow : min amin f0 ≤ F := e1_lower hF htF hsame hbelow
  have hGA : 0 ≤ G * A := mul_nonneg hG hA.le
  have hpos : 0 < σ + G * A := by linarith
  have hκ : 0 ≤ G * A / (σ + G * A) := div_nonneg hGA hpos.le
  have hw0 : 0 ≤ w := le_trans (le_max_right _ _) hw
  refine ⟨?_, hup⟩
  rcases le_total amin f0 with hle | hle
  · have hFlo : amin ≤ F := by rwa [min_eq_left hle] at hlow
    have hT := e2_tighten hσ hG hA hF hFlo hup hline hadd
    rw [kappa_form hpos] at hT
    have hww : G * A / (σ + G * A) * (f0 - amin) ≤ G * A / (σ + G * A) * w :=
      mul_le_mul_of_nonneg_left (le_trans (le_max_left _ _) hw) hκ
    linarith
  · have hFlo : f0 ≤ F := by rwa [min_eq_right hle] at hlow
    have hkw : 0 ≤ G * A / (σ + G * A) * w := mul_nonneg hκ hw0
    linarith

end A22.LemmaE

-- Must list only `propext`, `Classical.choice`, `Quot.sound`: no `sorryAx`.
#print axioms A22.LemmaE.e1_upper
#print axioms A22.LemmaE.e1_lower
#print axioms A22.LemmaE.h_le_linear
#print axioms A22.LemmaE.arrivals_le
#print axioms A22.LemmaE.e2_tighten
#print axioms A22.LemmaE.e_fire_enclosure
