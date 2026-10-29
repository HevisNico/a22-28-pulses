import Mathlib
import StrictRoot

/-!
# A22 v4.4 — lemmas C7, C6 and remark P

This file formalizes the mathematical content of the three additions that let the
v3.3 program cover the box ε = 1e-3 (`sweep/v33_c7/LEMMAS_C7_C6_EN.txt`).

## What is modelled

* The READY charge without new input, from charge `q` and current amplitude `J`:
  `Q A K R q J u = R + (q - R) e^{-K u} + J (e^{-K u} - e^{-A u}) / (A - K)`,
  with `0 < K < A` (in the model `A = ln 4`, `K = 1/2`, `R = 1/10`).
* Plain enclosures `Ival`, strict enclosure and `OpenAbout` from `StrictRoot.lean`.

## What is proved (no `sorry`, see `#print axioms` at the end)

**Lemma C7** (`c7_no_fire`): the charge is nondecreasing in `q` and in `J` for `u ≥ 0`
(`Q_mono_q`, `Q_mono_J`), so one bound at the corner `(q.hi, J.hi)` that stays below 1 on
`[0, H]` excludes a fire for every admissible `(q, J)`. `Q_le_peak` shows where the corner
charge is largest: with `a = q - R + J/(A-K) > 0` and `J > 0` it rises up to the
stationary point `u*`, `(A-K) u* = log(A J/(A-K) / (K a))`, then falls, so its maximum on
`[0, H]` is at `0`, at `H` or at `u*` clamped to `[0, H]` (the points the kernel's
`peak_upper` evaluates); with `a ≤ 0` (`Q_mono_time`) it is nondecreasing, so `H` suffices.

**Lemma C6** (`c6_cover`, `bisect_cover`): if pieces cover `[0, H]` and the charge is
below a bound `< 1` on each piece, it is below 1 on `[0, H]`; bisection keeps a cover.

**Remark P** (`convex_comb_strict`, `hull_strict`, `remarkP_newton_strict`): if the mean
slope is a convex combination of derivative values, each enclosed strictly by one piece,
and the hull dominates every piece, the hull is open about the mean slope; then the
Newton step of `StrictRoot.newton_step_strict_slope` keeps the root strictly inside.

## What is NOT proved here

That the program's interval evaluations are sound enclosures (`dep.evaluate`,
`v.ready`, outward rounding), that `peak_upper` evaluates the points named above, and,
for remark P, that the integral mean slope across raw cuts is covered: the file treats a
mean slope given as a finite convex combination (the mean value theorem gives a single
derivative value in the smooth case).
-/

namespace A22.V44

open Set

/-! ## The READY charge -/

/-- READY charge at elapsed time `u`, from charge `q` and current amplitude `J`. -/
noncomputable def Q (A K R q J u : ℝ) : ℝ :=
  R + (q - R) * Real.exp (-K * u) + J * ((Real.exp (-K * u) - Real.exp (-A * u)) / (A - K))

variable {A K R : ℝ}

theorem gap_nonneg (hKA : K < A) {u : ℝ} (hu : 0 ≤ u) :
    0 ≤ (Real.exp (-K * u) - Real.exp (-A * u)) / (A - K) := by
  apply div_nonneg
  · rw [sub_nonneg]
    apply Real.exp_le_exp.mpr
    nlinarith
  · linarith

/-! ## Lemma C7: monotonicity and the corner bound -/

theorem Q_mono_q {q q' J u : ℝ} (hq : q ≤ q') : Q A K R q J u ≤ Q A K R q' J u := by
  unfold Q
  have h : (q - R) * Real.exp (-K * u) ≤ (q' - R) * Real.exp (-K * u) :=
    mul_le_mul_of_nonneg_right (by linarith) (Real.exp_pos _).le
  linarith

theorem Q_mono_J (hKA : K < A) {q J J' u : ℝ} (hu : 0 ≤ u) (hJ : J ≤ J') :
    Q A K R q J u ≤ Q A K R q J' u := by
  unfold Q
  have h := mul_le_mul_of_nonneg_right hJ (gap_nonneg hKA hu)
  linarith

theorem Q_le_corner (hKA : K < A) {q qhi J Jhi u : ℝ} (hu : 0 ≤ u) (hq : q ≤ qhi)
    (hJ : J ≤ Jhi) : Q A K R q J u ≤ Q A K R qhi Jhi u :=
  le_trans (Q_mono_q hq) (Q_mono_J hKA hu hJ)

/-- **Lemma C7.** A bound below 1 for the corner charge on `[0, H]` excludes a fire on
`[0, H]` for every admissible charge `q ≤ q.hi` and amplitude `J ≤ J.hi`. -/
theorem c7_no_fire (hKA : K < A) {qhi Jhi H B : ℝ}
    (hB : ∀ u ∈ Icc (0 : ℝ) H, Q A K R qhi Jhi u ≤ B) (hB1 : B < 1)
    {q J u : ℝ} (hq : q ≤ qhi) (hJ : J ≤ Jhi) (hu : u ∈ Icc (0 : ℝ) H) :
    Q A K R q J u < 1 :=
  lt_of_le_of_lt (le_trans (Q_le_corner hKA hu.1 hq hJ) (hB u hu)) hB1

/-! ## Where the corner charge is largest -/

/-- The charge as `R + a e^{-K u} - b e^{-A u}`. -/
theorem Q_eq (hKA : K < A) (q J u : ℝ) :
    Q A K R q J u = R + (q - R + J / (A - K)) * Real.exp (-K * u)
      - J / (A - K) * Real.exp (-A * u) := by
  unfold Q
  ring

theorem hasDerivAt_expmul (c u : ℝ) :
    HasDerivAt (fun x => Real.exp (c * x)) (Real.exp (c * u) * c) u := by
  have h := ((hasDerivAt_id u).const_mul c).exp
  simp only [id, mul_one] at h
  exact h

/-- Derivative of `R + a e^{-K u} - b e^{-A u}`. -/
theorem hasDerivAt_form (a b u : ℝ) :
    HasDerivAt (fun x => R + a * Real.exp (-K * x) - b * Real.exp (-A * x))
      (a * (Real.exp (-K * u) * -K) - b * (Real.exp (-A * u) * -A)) u :=
  (((hasDerivAt_expmul (-K) u).const_mul a).const_add R).sub
    ((hasDerivAt_expmul (-A) u).const_mul b)

theorem exp_split (x : ℝ) :
    Real.exp (-K * x) = Real.exp (-A * x) * Real.exp ((A - K) * x) := by
  rw [← Real.exp_add]
  congr 1
  ring

/-- Sign of the derivative, written as `e^{-A x} (A b - K a e^{(A-K) x})`. -/
theorem deriv_form_eq (a b x : ℝ) :
    a * (Real.exp (-K * x) * -K) - b * (Real.exp (-A * x) * -A)
      = Real.exp (-A * x) * (A * b - K * a * Real.exp ((A - K) * x)) := by
  rw [exp_split (A := A) (K := K) x]
  ring

theorem form_cont (a b : ℝ) :
    Continuous (fun x => R + a * Real.exp (-K * x) - b * Real.exp (-A * x)) := by
  fun_prop

/-- With `a > 0`, `b > 0`, the form rises up to the stationary point `u*`. -/
theorem form_mono_before (hK : 0 < K) (hKA : K < A) {a b ustar : ℝ} (ha : 0 < a) (hb : 0 < b)
    (hstar : (A - K) * ustar = Real.log (A * b / (K * a))) :
    MonotoneOn (fun x => R + a * Real.exp (-K * x) - b * Real.exp (-A * x)) (Iic ustar) := by
  have hratio : 0 < A * b / (K * a) := by
    apply div_pos <;> nlinarith
  apply monotoneOn_of_hasDerivWithinAt_nonneg (convex_Iic ustar)
    (form_cont (R := R) (K := K) (A := A) a b).continuousOn
    (fun x _ => (hasDerivAt_form (R := R) (K := K) (A := A) a b x).hasDerivWithinAt)
  intro x hx
  rw [interior_Iic] at hx
  show 0 ≤ a * (Real.exp (-K * x) * -K) - b * (Real.exp (-A * x) * -A)
  rw [deriv_form_eq]
  apply mul_nonneg (Real.exp_pos _).le
  have hexp : Real.exp ((A - K) * x) ≤ A * b / (K * a) := by
    calc Real.exp ((A - K) * x) ≤ Real.exp ((A - K) * ustar) :=
          Real.exp_le_exp.mpr (mul_le_mul_of_nonneg_left (le_of_lt hx) (by linarith))
      _ = A * b / (K * a) := by rw [hstar, Real.exp_log hratio]
  have hKa : 0 < K * a := mul_pos hK ha
  have h2 : K * a * Real.exp ((A - K) * x) ≤ K * a * (A * b / (K * a)) :=
    mul_le_mul_of_nonneg_left hexp hKa.le
  have hK0 : K ≠ 0 := ne_of_gt hK
  have ha0 : a ≠ 0 := ne_of_gt ha
  have h3 : K * a * (A * b / (K * a)) = A * b := by
    field_simp
  linarith

/-- With `a > 0`, `b > 0`, the form falls after the stationary point `u*`. -/
theorem form_anti_after (hK : 0 < K) (hKA : K < A) {a b ustar : ℝ} (ha : 0 < a) (hb : 0 < b)
    (hstar : (A - K) * ustar = Real.log (A * b / (K * a))) :
    AntitoneOn (fun x => R + a * Real.exp (-K * x) - b * Real.exp (-A * x)) (Ici ustar) := by
  have hratio : 0 < A * b / (K * a) := by
    apply div_pos <;> nlinarith
  apply antitoneOn_of_hasDerivWithinAt_nonpos (convex_Ici ustar)
    (form_cont (R := R) (K := K) (A := A) a b).continuousOn
    (fun x _ => (hasDerivAt_form (R := R) (K := K) (A := A) a b x).hasDerivWithinAt)
  intro x hx
  rw [interior_Ici] at hx
  show a * (Real.exp (-K * x) * -K) - b * (Real.exp (-A * x) * -A) ≤ 0
  rw [deriv_form_eq]
  apply mul_nonpos_of_nonneg_of_nonpos (Real.exp_pos _).le
  have hexp : A * b / (K * a) ≤ Real.exp ((A - K) * x) := by
    calc A * b / (K * a) = Real.exp ((A - K) * ustar) := by rw [hstar, Real.exp_log hratio]
      _ ≤ Real.exp ((A - K) * x) :=
          Real.exp_le_exp.mpr (mul_le_mul_of_nonneg_left (le_of_lt hx) (by linarith))
  have hKa : 0 < K * a := mul_pos hK ha
  have h2 : K * a * (A * b / (K * a)) ≤ K * a * Real.exp ((A - K) * x) :=
    mul_le_mul_of_nonneg_left hexp hKa.le
  have hK0 : K ≠ 0 := ne_of_gt hK
  have ha0 : a ≠ 0 := ne_of_gt ha
  have h3 : K * a * (A * b / (K * a)) = A * b := by
    field_simp
  linarith

/-- With `a ≤ 0`, `b ≥ 0`, the form is nondecreasing for all times. -/
theorem form_mono_all (hK : 0 < K) (hKA : K < A) {a b : ℝ} (ha : a ≤ 0) (hb : 0 ≤ b) :
    MonotoneOn (fun x => R + a * Real.exp (-K * x) - b * Real.exp (-A * x)) univ := by
  apply monotoneOn_of_hasDerivWithinAt_nonneg convex_univ
    (form_cont (R := R) (K := K) (A := A) a b).continuousOn
    (fun x _ => (hasDerivAt_form (R := R) (K := K) (A := A) a b x).hasDerivWithinAt)
  intro x _
  show 0 ≤ a * (Real.exp (-K * x) * -K) - b * (Real.exp (-A * x) * -A)
  rw [deriv_form_eq]
  apply mul_nonneg (Real.exp_pos _).le
  have h1 : K * a * Real.exp ((A - K) * x) ≤ 0 :=
    mul_nonpos_of_nonpos_of_nonneg (mul_nonpos_of_nonneg_of_nonpos hK.le ha) (Real.exp_pos _).le
  have h2 : 0 ≤ A * b := mul_nonneg (by linarith) hb
  linarith

/-- **Where the corner charge peaks** (`a > 0`, `J > 0`): on `[0, H]` it is at most its
value at `0`, at `H`, or at the stationary point clamped to `[0, H]`. -/
theorem Q_le_peak (hK : 0 < K) (hKA : K < A) {q J H ustar u : ℝ}
    (ha : 0 < q - R + J / (A - K)) (hJ : 0 < J)
    (hstar : (A - K) * ustar = Real.log (A * (J / (A - K)) / (K * (q - R + J / (A - K)))))
    (hu : u ∈ Icc (0 : ℝ) H) :
    Q A K R q J u ≤ max (Q A K R q J 0)
      (max (Q A K R q J H) (Q A K R q J (max 0 (min ustar H)))) := by
  have hb : 0 < J / (A - K) := div_pos hJ (by linarith)
  have hQ : ∀ x, Q A K R q J x = R + (q - R + J / (A - K)) * Real.exp (-K * x)
      - J / (A - K) * Real.exp (-A * x) := fun x => Q_eq hKA q J x
  have hmono := form_mono_before (R := R) hK hKA ha hb hstar
  have hanti := form_anti_after (R := R) hK hKA ha hb hstar
  simp only [hQ]
  obtain ⟨hu0, huH⟩ := hu
  rcases le_total u ustar with hus | hus
  · rcases le_total ustar H with hsH | hsH
    · -- 0 ≤ u ≤ u* ≤ H: the clamp is u*
      have hc : max 0 (min ustar H) = ustar := by
        rw [min_eq_left hsH, max_eq_right (le_trans hu0 hus)]
      rw [hc]
      exact le_max_of_le_right (le_max_of_le_right
        (hmono (mem_Iic.mpr hus) (mem_Iic.mpr le_rfl) hus))
    · -- u ≤ H ≤ u*: the function still rises, H is the largest point
      exact le_max_of_le_right (le_max_of_le_left
        (hmono (mem_Iic.mpr hus) (mem_Iic.mpr hsH) huH))
  · rcases le_total 0 ustar with h0s | h0s
    · -- 0 ≤ u* ≤ u ≤ H: the clamp is u*
      have hc : max 0 (min ustar H) = ustar := by
        rw [min_eq_left (le_trans hus huH), max_eq_right h0s]
      rw [hc]
      exact le_max_of_le_right (le_max_of_le_right
        (hanti (mem_Ici.mpr le_rfl) (mem_Ici.mpr hus) hus))
    · -- u* ≤ 0 ≤ u: the function already falls, 0 is the largest point
      exact le_max_of_le_left (hanti (mem_Ici.mpr h0s) (mem_Ici.mpr hus) hu0)

/-- With `a ≤ 0` and `J ≥ 0` the charge is nondecreasing: `H` is the largest point. -/
theorem Q_mono_time (hK : 0 < K) (hKA : K < A) {q J u H : ℝ}
    (ha : q - R + J / (A - K) ≤ 0) (hJ : 0 ≤ J) (huH : u ≤ H) :
    Q A K R q J u ≤ Q A K R q J H := by
  have hb : 0 ≤ J / (A - K) := div_nonneg hJ (by linarith)
  rw [Q_eq hKA, Q_eq hKA]
  exact form_mono_all (R := R) hK hKA ha hb (mem_univ u) (mem_univ H) huH

/-! ## Lemma C6: piecewise cover -/

/-- **Lemma C6.** Pieces covering `[0, H]`, each with a bound below 1, exclude a fire. -/
theorem c6_cover {f : ℝ → ℝ} {H : ℝ} {n : ℕ} (lo hi c : Fin n → ℝ)
    (hcover : ∀ u ∈ Icc (0 : ℝ) H, ∃ k, u ∈ Icc (lo k) (hi k))
    (hbound : ∀ k, ∀ u ∈ Icc (lo k) (hi k), f u ≤ c k) (hc : ∀ k, c k < 1) :
    ∀ u ∈ Icc (0 : ℝ) H, f u < 1 := by
  intro u hu
  obtain ⟨k, hk⟩ := hcover u hu
  exact lt_of_le_of_lt (hbound k u hk) (hc k)

/-- Bisection keeps a cover: both halves together cover the parent piece. -/
theorem bisect_cover {lo mid hi u : ℝ} (hu : u ∈ Icc lo hi) :
    u ∈ Icc lo mid ∨ u ∈ Icc mid hi := by
  rcases le_total u mid with h | h
  · exact Or.inl ⟨hu.1, h⟩
  · exact Or.inr ⟨h, hu.2⟩

/-! ## Remark P: slope on a partition -/

/-- A convex combination of values strictly inside `(lo, hi)` is strictly inside. -/
theorem convex_comb_strict {ι : Type*} (s : Finset ι) (w v : ι → ℝ) {lo hi : ℝ}
    (hw : ∀ i ∈ s, 0 ≤ w i) (hsum : ∑ i ∈ s, w i = 1)
    (hv : ∀ i ∈ s, lo < v i ∧ v i < hi) :
    lo < ∑ i ∈ s, w i * v i ∧ ∑ i ∈ s, w i * v i < hi := by
  obtain ⟨j, hj, hwj⟩ : ∃ j ∈ s, w j ≠ 0 :=
    Finset.exists_ne_zero_of_sum_ne_zero (by rw [hsum]; norm_num)
  have hwj' : 0 < w j := lt_of_le_of_ne (hw j hj) (Ne.symm hwj)
  have hlo : lo = ∑ i ∈ s, w i * lo := by rw [← Finset.sum_mul, hsum, one_mul]
  have hhi : hi = ∑ i ∈ s, w i * hi := by rw [← Finset.sum_mul, hsum, one_mul]
  constructor
  · have hpos : 0 < ∑ i ∈ s, w i * (v i - lo) :=
      Finset.sum_pos' (fun i hi' => mul_nonneg (hw i hi') (by linarith [(hv i hi').1]))
        ⟨j, hj, mul_pos hwj' (by linarith [(hv j hj).1])⟩
    have hexp : ∑ i ∈ s, w i * (v i - lo) = ∑ i ∈ s, w i * v i - ∑ i ∈ s, w i * lo := by
      rw [← Finset.sum_sub_distrib]
      apply Finset.sum_congr rfl
      intro i _
      ring
    linarith
  · have hpos : 0 < ∑ i ∈ s, w i * (hi - v i) :=
      Finset.sum_pos' (fun i hi' => mul_nonneg (hw i hi') (by linarith [(hv i hi').2]))
        ⟨j, hj, mul_pos hwj' (by linarith [(hv j hj).2])⟩
    have hexp : ∑ i ∈ s, w i * (hi - v i) = ∑ i ∈ s, w i * hi - ∑ i ∈ s, w i * v i := by
      rw [← Finset.sum_sub_distrib]
      apply Finset.sum_congr rfl
      intro i _
      ring
    linarith

/-- A value strictly inside a piece is strictly inside any hull that dominates the piece. -/
theorem hull_strict {P Hl : Ival} {v : ℝ} (hlo : Hl.lo ≤ P.lo) (hhi : P.hi ≤ Hl.hi)
    (hv : P.Strict v) : Hl.Strict v :=
  ⟨lt_of_le_of_lt hlo hv.1, lt_of_lt_of_le hv.2 hhi⟩

/-- A plain interval strictly containing `s` is open about `s`. -/
theorem openAbout_Ioo {lo hi s : ℝ} (h : lo < s ∧ s < hi) : OpenAbout (Ioo lo hi) s := by
  refine ⟨min (s - lo) (hi - s), lt_min (by linarith [h.1]) (by linarith [h.2]), ?_⟩
  intro y hy
  have h1 := min_le_left (s - lo) (hi - s)
  have h2 := min_le_right (s - lo) (hi - s)
  exact ⟨by linarith [hy.1], by linarith [hy.2]⟩

/-- **Remark P.** The mean slope `s` is a convex combination of derivative values, each
strictly inside one piece enclosure dominated by the hull `Hl`. Then the hull is open
about `s`, and the Newton step driven by the slope keeps the root strictly inside
(`StrictRoot.newton_step_strict_slope`). -/
theorem remarkP_newton_strict {ι : Type*} (s : Finset ι) (w v : ι → ℝ)
    (piece : ι → Ival) (Hl : Ival)
    (hw : ∀ i ∈ s, 0 ≤ w i) (hsum : ∑ i ∈ s, w i = 1)
    (hv : ∀ i ∈ s, (piece i).Strict (v i))
    (hdom : ∀ i ∈ s, Hl.lo ≤ (piece i).lo ∧ (piece i).hi ≤ Hl.hi)
    {m r fm : ℝ} {N : Ival} (hs : 0 < ∑ i ∈ s, w i * v i) (hfm : fm < 0)
    (hr : r = m - fm / ∑ i ∈ s, w i * v i)
    (hN : Encloses N ((fun t => m - fm / t) '' (Ioo Hl.lo Hl.hi ∩ Ioi 0))) :
    N.Strict r := by
  have hstrict : ∀ i ∈ s, Hl.lo < v i ∧ v i < Hl.hi := fun i hi' =>
    hull_strict (hdom i hi').1 (hdom i hi').2 (hv i hi')
  exact newton_step_strict_slope hs hfm hr
    (openAbout_Ioo (convex_comb_strict s w v hw hsum hstrict)) hN

end A22.V44

-- Must list only `propext`, `Classical.choice`, `Quot.sound`: no `sorryAx`.
#print axioms A22.V44.c7_no_fire
#print axioms A22.V44.Q_le_peak
#print axioms A22.V44.Q_mono_time
#print axioms A22.V44.c6_cover
#print axioms A22.V44.bisect_cover
#print axioms A22.V44.remarkP_newton_strict
