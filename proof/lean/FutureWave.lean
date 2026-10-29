import Mathlib
import PeakBounds
import CommutationE
import FirstCrossing

/-!
# A22 — one future wave: monotone head response, protection, exact word

This file formalizes the mathematical steps of `proof/FUTURE_INVARIANCE_PROOF_EN.txt`
(sections C–D) and `proof/GLOBAL_THEOREM_AND_WORD_PRESERVATION_EN.txt` that do not depend
on the certified numbers.

## What is proved (no `sorry`, see `#print axioms` at the end)

* `h_strictMonoOn` (section C): if `K e^{-K} < A e^{-A}` (the checker verifies
  `a e^{-a} > κ e^{-κ}`), the pulse response `h` is strictly increasing on `[0, 1]`.
* `protection_duration` (section D): if `ℓ' = -b` with `β ≤ b ≤ 1.1` and `ℓ` falls from `L`
  to 0 in time `T`, then `L ≤ 1.1 T` and `β T ≤ L`, that is `T ∈ [L/1.1, L/β]`.
* `first_crossing_shift`, `head_charge_shift`, `latency_fixed` (word preservation): a cell
  at rest whose influential parents fire at `s + d i` has the charge
  `r + Σ G i h₊(t - s - d i)`, a fixed function of `t - s`, so its first crossing is
  `s + d` with `d` independent of `s`.
* `word_preserved`: hence two waves give firing times whose difference is the difference
  of the source times. Applied layer by layer (the source has latency 0), this is the
  induction of the global theorem.

## What is NOT proved here

The certified inequalities themselves (crossing brackets, margins, the global settling
bound), computed by the two independent checkers, and the facts that make the head formula
valid (gains fixed before the crossing, all heads at `r`, masked ports absent before the
crossing): these are the finite checks of the future proof, not formalized.
-/

namespace A22.Future

open Set A22.Crossing

/-- **Monotone head response.** `h` is strictly increasing on `[0, 1]`. -/
theorem h_strictMonoOn {A K : ℝ} (hK : 0 < K) (hKA : K < A)
    (hcond : K * Real.exp (-K) < A * Real.exp (-A)) :
    StrictMonoOn (A22.LemmaE.h A K) (Icc 0 1) := by
  have hAK : 0 < A - K := sub_pos.mpr hKA
  have hA : 0 < A := lt_trans hK hKA
  have hderiv : ∀ x, HasDerivAt (A22.LemmaE.h A K)
      (A / (A - K) * (Real.exp (-K * x) * -K - Real.exp (-A * x) * -A)) x := by
    intro x
    exact ((A22.V44.hasDerivAt_expmul (-K) x).sub
      (A22.V44.hasDerivAt_expmul (-A) x)).const_mul (A / (A - K))
  have hsplitA : ∀ x, Real.exp (-A * x) = Real.exp (-K * x) * Real.exp (-((A - K) * x)) := by
    intro x
    rw [← Real.exp_add]
    congr 1
    ring
  have hsplit1 : Real.exp (-A) = Real.exp (-K) * Real.exp (-(A - K)) := by
    rw [← Real.exp_add]
    congr 1
    ring
  have hKlt : K < A * Real.exp (-(A - K)) := by
    have he := Real.exp_pos (-K)
    rw [hsplit1] at hcond
    by_contra hc
    push_neg at hc
    have h1 := mul_le_mul_of_nonneg_right hc he.le
    linarith
  apply strictMonoOn_of_hasDerivWithinAt_pos (convex_Icc 0 1)
    (fun x _ => (hderiv x).continuousAt.continuousWithinAt)
    (fun x _ => (hderiv x).hasDerivWithinAt)
  intro x hx
  rw [interior_Icc] at hx
  have hx1 : x ≤ 1 := hx.2.le
  have he2 : Real.exp (-(A - K)) ≤ Real.exp (-((A - K) * x)) :=
    Real.exp_le_exp.mpr (by nlinarith [mul_nonneg hAK.le (sub_nonneg.mpr hx1)])
  have heK := Real.exp_pos (-K * x)
  have hmain : K * Real.exp (-K * x) < A * Real.exp (-A * x) := by
    rw [hsplitA x]
    have h1 : K * Real.exp (-K * x) < A * Real.exp (-(A - K)) * Real.exp (-K * x) :=
      mul_lt_mul_of_pos_right hKlt heK
    have h2 : A * Real.exp (-(A - K)) * Real.exp (-K * x)
        ≤ A * Real.exp (-((A - K) * x)) * Real.exp (-K * x) :=
      mul_le_mul_of_nonneg_right (mul_le_mul_of_nonneg_left he2 hA.le) heK.le
    linarith
  have hc : 0 < A / (A - K) := div_pos hA hAK
  show 0 < A / (A - K) * (Real.exp (-K * x) * -K - Real.exp (-A * x) * -A)
  apply mul_pos hc
  linarith

/-- **Protection duration.** With `ℓ' = -b`, `β ≤ b ≤ 1.1`, `ℓ(0) = L` and `ℓ(T) = 0`:
`L ≤ 1.1 T` and `β T ≤ L`. -/
theorem protection_duration {ell b : ℝ → ℝ} {β L T : ℝ}
    (hd : ∀ t, HasDerivAt ell (-b t) t) (hb : ∀ t, β ≤ b t ∧ b t ≤ 1.1)
    (h0 : ell 0 = L) (hT : ell T = 0) (hT0 : 0 ≤ T) :
    L ≤ 1.1 * T ∧ β * T ≤ L := by
  have hg1 : ∀ x, HasDerivAt (fun y => ell y + 1.1 * y) (-b x + 1.1) x := by
    intro x
    have h1 := (hd x).add ((hasDerivAt_id x).const_mul (1.1 : ℝ))
    simp only [id, mul_one] at h1
    exact h1
  have hg2 : ∀ x, HasDerivAt (fun y => ell y + β * y) (-b x + β) x := by
    intro x
    have h1 := (hd x).add ((hasDerivAt_id x).const_mul β)
    simp only [id, mul_one] at h1
    exact h1
  have hmono : MonotoneOn (fun y => ell y + 1.1 * y) (Ici 0) := by
    apply monotoneOn_of_hasDerivWithinAt_nonneg (convex_Ici 0)
      (fun x _ => (hg1 x).continuousAt.continuousWithinAt)
      (fun x _ => (hg1 x).hasDerivWithinAt)
    intro x _
    linarith [(hb x).2]
  have hanti : AntitoneOn (fun y => ell y + β * y) (Ici 0) := by
    apply antitoneOn_of_hasDerivWithinAt_nonpos (convex_Ici 0)
      (fun x _ => (hg2 x).continuousAt.continuousWithinAt)
      (fun x _ => (hg2 x).hasDerivWithinAt)
    intro x _
    linarith [(hb x).1]
  have h1 : ell 0 + 1.1 * 0 ≤ ell T + 1.1 * T :=
    hmono (mem_Ici.mpr le_rfl) (mem_Ici.mpr hT0) hT0
  have h2 : ell T + β * T ≤ ell 0 + β * 0 :=
    hanti (mem_Ici.mpr le_rfl) (mem_Ici.mpr hT0) hT0
  constructor <;> linarith

/-- A first crossing of `φ` from 0 at `d` is a first crossing of `t ↦ φ (t - s)` from `s`
at `s + d`. -/
theorem first_crossing_shift {φ : ℝ → ℝ} {d s : ℝ}
    (h : IsFirstCrossing φ 0 d) :
    IsFirstCrossing (fun t => φ (t - s)) s (s + d) := by
  obtain ⟨h0, h1, h2⟩ := h
  have hsd : s + d - s = d := by ring
  refine ⟨by linarith, ?_, ?_⟩
  · show 1 ≤ φ (s + d - s)
    rw [hsd]
    exact h1
  · intro t ht
    exact h2 (t - s) ⟨by linarith [ht.1], by linarith [ht.2]⟩

/-- **Head charge.** With every head at rest `r` and parents firing at `s + d i`, the charge
is a fixed function of `t - s`. -/
theorem head_charge_shift {ι : Type*} (S : Finset ι) (G dd : ι → ℝ) (A K r s t : ℝ) :
    r + ∑ i ∈ S, G i * A22.LemmaE.hplus A K (t - (s + dd i))
      = (fun u => r + ∑ i ∈ S, G i * A22.LemmaE.hplus A K (u - dd i)) (t - s) := by
  show _ = r + ∑ i ∈ S, G i * A22.LemmaE.hplus A K (t - s - dd i)
  congr 1
  apply Finset.sum_congr rfl
  intro i _
  rw [show t - (s + dd i) = t - s - dd i by ring]

/-- **Fixed latency.** Every wave fires the cell at `s + d`, with `d` independent of `s`. -/
theorem latency_fixed {ι : Type*} (S : Finset ι) (G dd : ι → ℝ) {A K r d s F : ℝ}
    (hφ : IsFirstCrossing (fun u => r + ∑ i ∈ S, G i * A22.LemmaE.hplus A K (u - dd i)) 0 d)
    (hF : IsFirstCrossing
      (fun t => r + ∑ i ∈ S, G i * A22.LemmaE.hplus A K (t - (s + dd i))) s F) :
    F = s + d := by
  have hshift := first_crossing_shift (s := s) hφ
  have heq : (fun t => r + ∑ i ∈ S, G i * A22.LemmaE.hplus A K (t - (s + dd i)))
      = (fun t => (fun u => r + ∑ i ∈ S, G i * A22.LemmaE.hplus A K (u - dd i)) (t - s)) := by
    funext t
    exact head_charge_shift S G dd A K r s t
  rw [heq] at hF
  exact first_crossing_unique hF hshift

/-- **Exact word.** Two waves at `s1` and `s2` fire the cell at times whose difference is
`s2 - s1`. -/
theorem word_preserved {ι : Type*} (S : Finset ι) (G dd : ι → ℝ) {A K r d s1 s2 F1 F2 : ℝ}
    (hφ : IsFirstCrossing (fun u => r + ∑ i ∈ S, G i * A22.LemmaE.hplus A K (u - dd i)) 0 d)
    (h1 : IsFirstCrossing
      (fun t => r + ∑ i ∈ S, G i * A22.LemmaE.hplus A K (t - (s1 + dd i))) s1 F1)
    (h2 : IsFirstCrossing
      (fun t => r + ∑ i ∈ S, G i * A22.LemmaE.hplus A K (t - (s2 + dd i))) s2 F2) :
    F2 - F1 = s2 - s1 := by
  rw [latency_fixed S G dd hφ h1, latency_fixed S G dd hφ h2]
  ring

end A22.Future

-- Must list only `propext`, `Classical.choice`, `Quot.sound`: no `sorryAx`.
#print axioms A22.Future.h_strictMonoOn
#print axioms A22.Future.protection_duration
#print axioms A22.Future.first_crossing_shift
#print axioms A22.Future.head_charge_shift
#print axioms A22.Future.latency_fixed
#print axioms A22.Future.word_preserved
