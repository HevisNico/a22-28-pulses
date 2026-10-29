import Mathlib
import PeakBounds

/-!
# A22 — first threshold crossings

This file formalizes the facts about first crossings of the threshold 1 that the
learning-coverage theorem (`proof/learning_justification/output/LEARNING_COVERAGE_THEOREM_EN.txt`)
uses when it accepts a fire.

## What is proved (no `sorry`, see `#print axioms` at the end)

* `first_crossing_unique`, `first_crossing_exists`: a continuous charge that reaches 1 on
  `[a, b]` has exactly one first crossing.
* `cover_encloses` (Section 8(vi), `_first_crossing_cover`): if the charge is below 1 on
  `[a, lower)` and reaches 1 at `upper`, the first crossing lies in `[lower, upper]`,
  without any slope assumption.
* `comparison_bracket`, `ready_root_bracket` (Section 6, `ready_root`): the READY charge
  is monotone in the initial charge and the current amplitude (`PeakBounds.lean`), so the
  first crossing lies between those of the two corner trajectories.
* `deriv_stays_nonpos`, `ascending_root_is_first` (Section 7): between arrivals the
  derivative `d` of the charge satisfies `d' = -K d - A J` with `J ≥ 0`, so once `d ≤ 0`
  it stays `≤ 0`; a root where the charge rises is therefore its first crossing.

## What is NOT proved here

The raw ends ("cuts") are handled in prose: there the current drops, so `d` only
decreases, and `ascending_root_is_first` takes the resulting property `hstay` as a
hypothesis. That the program's enclosures meet these hypotheses is not formalized.
-/

namespace A22.Crossing

open Set

/-- `F` is the first time from `a` at which `f` reaches 1. -/
def IsFirstCrossing (f : ℝ → ℝ) (a F : ℝ) : Prop :=
  a ≤ F ∧ 1 ≤ f F ∧ ∀ t ∈ Ico a F, f t < 1

theorem first_crossing_unique {f : ℝ → ℝ} {a F1 F2 : ℝ}
    (h1 : IsFirstCrossing f a F1) (h2 : IsFirstCrossing f a F2) : F1 = F2 := by
  rcases lt_trichotomy F1 F2 with h | h | h
  · have h3 := h2.2.2 F1 ⟨h1.1, h⟩
    linarith [h1.2.1]
  · exact h
  · have h3 := h1.2.2 F2 ⟨h2.1, h⟩
    linarith [h2.2.1]

/-- A continuous charge that reaches 1 at `b` has a first crossing in `[a, b]`. -/
theorem first_crossing_exists {f : ℝ → ℝ} {a b : ℝ} (hab : a ≤ b)
    (hf : ContinuousOn f (Icc a b)) (hb : 1 ≤ f b) :
    ∃ F, IsFirstCrossing f a F ∧ F ≤ b := by
  have hclosed : IsClosed (Icc a b ∩ f ⁻¹' Ici 1) :=
    hf.preimage_isClosed_of_isClosed isClosed_Icc isClosed_Ici
  have hne : (Icc a b ∩ f ⁻¹' Ici 1).Nonempty := ⟨b, ⟨hab, le_rfl⟩, hb⟩
  have hbdd : BddBelow (Icc a b ∩ f ⁻¹' Ici 1) := ⟨a, fun t ht => ht.1.1⟩
  have hmem : sInf (Icc a b ∩ f ⁻¹' Ici 1) ∈ Icc a b ∩ f ⁻¹' Ici 1 :=
    hclosed.csInf_mem hne hbdd
  refine ⟨sInf (Icc a b ∩ f ⁻¹' Ici 1), ⟨hmem.1.1, hmem.2, ?_⟩, hmem.1.2⟩
  intro t ht
  by_contra hlt
  push_neg at hlt
  have htS : t ∈ Icc a b ∩ f ⁻¹' Ici 1 := ⟨⟨ht.1, le_trans ht.2.le hmem.1.2⟩, hlt⟩
  have h4 := csInf_le hbdd htS
  linarith [ht.2]

/-- **First-crossing cover.** Below 1 on `[a, lower)` and at least 1 at `upper`: the first
crossing lies in `[lower, upper]`. -/
theorem cover_encloses {f : ℝ → ℝ} {a F lower upper : ℝ}
    (hF : IsFirstCrossing f a F)
    (hleft : ∀ t ∈ Ico a lower, f t < 1)
    (hup : a ≤ upper) (hfup : 1 ≤ f upper) :
    lower ≤ F ∧ F ≤ upper := by
  constructor
  · by_contra h
    push_neg at h
    have h1 := hleft F ⟨hF.1, h⟩
    linarith [hF.2.1]
  · by_contra h
    push_neg at h
    have h1 := hF.2.2 upper ⟨hup, h⟩
    linarith

/-- Pointwise comparison orders the first crossings. -/
theorem comparison_bracket {Q Qlo Qhi : ℝ → ℝ} {a F Flo Fhi : ℝ}
    (hle : ∀ t, a ≤ t → Qlo t ≤ Q t) (hge : ∀ t, a ≤ t → Q t ≤ Qhi t)
    (hF : IsFirstCrossing Q a F) (hlo : IsFirstCrossing Qlo a Flo)
    (hhi : IsFirstCrossing Qhi a Fhi) :
    Fhi ≤ F ∧ F ≤ Flo := by
  constructor
  · by_contra h
    push_neg at h
    have h1 := hhi.2.2 F ⟨hF.1, h⟩
    have h2 := hge F hF.1
    linarith [hF.2.1]
  · by_contra h
    push_neg at h
    have h1 := hF.2.2 Flo ⟨hlo.1, h⟩
    have h2 := hle Flo hlo.1
    linarith [hlo.2.1]

/-- **Comparison roots of `ready_root`.** For `qlo ≤ q ≤ qhi` and `Jlo ≤ J ≤ Jhi`, the
first crossing of the READY charge lies between those of the corner trajectories. -/
theorem ready_root_bracket {A K R qlo q qhi Jlo J Jhi F Flo Fhi : ℝ} (hKA : K < A)
    (hq1 : qlo ≤ q) (hq2 : q ≤ qhi) (hJ1 : Jlo ≤ J) (hJ2 : J ≤ Jhi)
    (hF : IsFirstCrossing (A22.V44.Q A K R q J) 0 F)
    (hlo : IsFirstCrossing (A22.V44.Q A K R qlo Jlo) 0 Flo)
    (hhi : IsFirstCrossing (A22.V44.Q A K R qhi Jhi) 0 Fhi) :
    Fhi ≤ F ∧ F ≤ Flo :=
  comparison_bracket (fun _ ht => A22.V44.Q_le_corner hKA ht hq1 hJ1)
    (fun _ ht => A22.V44.Q_le_corner hKA ht hq2 hJ2) hF hlo hhi

/-- **Between arrivals.** If `d' = -K d - A J` with `A ≥ 0` and `J ≥ 0`, then `d ≤ 0` at `s`
implies `d ≤ 0` at every later time: `t ↦ e^{K t} d t` is nonincreasing. -/
theorem deriv_stays_nonpos {d J : ℝ → ℝ} {K A s : ℝ} (hA : 0 ≤ A)
    (hd : ∀ t, HasDerivAt d (-K * d t - A * J t) t) (hJ : ∀ t, 0 ≤ J t)
    (hs : d s ≤ 0) {t : ℝ} (hst : s ≤ t) : d t ≤ 0 := by
  have hφ : ∀ x, HasDerivAt (fun y => Real.exp (K * y) * d y)
      (Real.exp (K * x) * K * d x + Real.exp (K * x) * (-K * d x - A * J x)) x := by
    intro x
    exact (A22.V44.hasDerivAt_expmul K x).mul (hd x)
  have hanti : AntitoneOn (fun y => Real.exp (K * y) * d y) (Ici s) := by
    apply antitoneOn_of_hasDerivWithinAt_nonpos (convex_Ici s)
      (fun x _ => (hφ x).continuousAt.continuousWithinAt)
      (fun x _ => (hφ x).hasDerivWithinAt)
    intro x _
    have he := Real.exp_pos (K * x)
    nlinarith [mul_nonneg he.le (mul_nonneg hA (hJ x))]
  have h1 : Real.exp (K * t) * d t ≤ Real.exp (K * s) * d s :=
    hanti (mem_Ici.mpr le_rfl) (mem_Ici.mpr hst) hst
  have hes := Real.exp_pos (K * s)
  have het := Real.exp_pos (K * t)
  have h2 : Real.exp (K * s) * d s ≤ 0 := by nlinarith
  by_contra hpos
  push_neg at hpos
  have h3 := mul_pos het hpos
  linarith

/-- **An ascending root is the first crossing.** If the derivative never goes back from
`≤ 0` to `> 0`, a point where the charge equals 1 while rising is its first crossing. -/
theorem ascending_root_is_first {Q d : ℝ → ℝ} {a r : ℝ} (har : a ≤ r)
    (hQ : ∀ t, HasDerivAt Q (d t) t)
    (hstay : ∀ s t, s ≤ t → d s ≤ 0 → d t ≤ 0)
    (hr : Q r = 1) (hdr : 0 < d r) :
    IsFirstCrossing Q a r := by
  have hmono : StrictMonoOn Q (Icc a r) := by
    apply strictMonoOn_of_hasDerivWithinAt_pos (convex_Icc a r)
      (fun x _ => (hQ x).continuousAt.continuousWithinAt)
      (fun x _ => (hQ x).hasDerivWithinAt)
    intro x hx
    have hxr : x ≤ r := (interior_subset hx : x ∈ Icc a r).2
    by_contra hneg
    push_neg at hneg
    have h1 := hstay x r hxr hneg
    linarith
  refine ⟨har, le_of_eq hr.symm, ?_⟩
  intro t ht
  have h1 : Q t < Q r := hmono ⟨ht.1, ht.2.le⟩ ⟨har, le_rfl⟩ ht.2
  linarith

end A22.Crossing

-- Must list only `propext`, `Classical.choice`, `Quot.sound`: no `sorryAx`.
#print axioms A22.Crossing.first_crossing_unique
#print axioms A22.Crossing.first_crossing_exists
#print axioms A22.Crossing.cover_encloses
#print axioms A22.Crossing.ready_root_bracket
#print axioms A22.Crossing.deriv_stays_nonpos
#print axioms A22.Crossing.ascending_root_is_first
