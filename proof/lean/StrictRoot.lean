import Mathlib

/-!
# A22 — strict-root lemma: the abstract mathematical core

This file formalizes the mathematical argument of Task 1 of `REVIEW.md`:
`proof/kernel_soundness/output/STRICT_ROOT_LEMMA_EN.txt` and Sections 4–6 of
`proof/learning_justification/output/LEARNING_COVERAGE_THEOREM_EN.txt`.

## What is modelled

* A *plain enclosure* is a pair of real bounds `Ival` (exact real arithmetic:
  outward floating-point rounding is not modelled, it is a hypothesis below).
* A *representable set* `S : Set ℝ` is the set of values an affine form can take
  when every OLD noise coordinate and every other operand is frozen, and only
  the freedom created during the current calculation (center, remainder, fresh
  coordinates) varies.
* `Encloses I S` is the soundness contract of the arithmetic: every
  representable value lies in the returned plain bounds.
* `Straddles S x`: `S` contains one value strictly below `x` and one strictly
  above. This is all that strictness needs. The manuscript's open-image lemma
  (an open interval about `x`) implies it (`OpenAbout.straddles`).

## What is proved (no `sorry`, see `#print axioms` at the end)

1. `strict_of_encloses`   : sound enclosure of a straddling set ⇒ strict enclosure.
2. `straddles_affine`, `straddles_image_strict*` : the open-image lemma, in its
   two-point form, for affine uses with nonzero coefficient and for strictly
   monotone uses (rules (a), (b), (c) of the strict-root note).
3. `AForm.straddles_of_strict_center` : a strict center witness gives straddling.
4. `accepted_bracket_strict` : an accepted bracket `f(l).hi ≤ 0`, `f(h).lo ≥ 0`
   has the root strictly inside (Section 6, first paragraph).
5. `newton_step_strict`, `newton_step_strict_slope` : the Newton image
   `m - f(m)/s` strictly contains the root, using freedom in `f(m)` (general
   case) or in the slope `s` (the rounded-midpoint-zero case).
6. `refine_strict` : every retained output of a finite refinement (Newton image,
   intersection with the previous bracket, or the previous bracket) strictly
   contains the root and is non-point.
7. `order_strict_after`, `order_strict_before`, `coincidence_never_passes` :
   the event-order consequence: a weak test `lower(x - date) ≥ 0` against a
   root date proves STRICT physical order, so an exact simultaneity can pass
   neither ordinary test.
8. `point_duration_countermodel` : without strictness (point duration), the
   weak test accepts an exact coincidence. The hypothesis is necessary.

## What is NOT proved here (the bridge to the code)

Every hypothesis of the form `Encloses N (g '' S)` or `Straddles S v` is a claim
about `engine/affine/*.py` and the effective sources. In particular:
freshness of the perturbed coordinates (the use `g` really is a function of the
perturbed value alone, every other operand frozen), absence of exact shortcuts
in exp/ln (`_unary`), the evaluation order `S = deriv(T)` before `fun(I(m))`,
and the fresh time atom of `temporal.shift`. See `GUIDE_VERIFICATION_FR.md`.
-/

namespace A22

/-! ## Plain enclosures -/

/-- A plain enclosure `[lo, hi]` (exact real bounds). -/
structure Ival where
  lo : ℝ
  hi : ℝ

namespace Ival

/-- `x ∈ [lo, hi]`. -/
def Mem (I : Ival) (x : ℝ) : Prop := I.lo ≤ x ∧ x ≤ I.hi

/-- `x ∈ (lo, hi)`: strict enclosure. -/
def Strict (I : Ival) (x : ℝ) : Prop := I.lo < x ∧ x < I.hi

/-- Intersection of two plain enclosures. -/
def inter (I J : Ival) : Ival := ⟨max I.lo J.lo, min I.hi J.hi⟩

/-- Hull (union) of two plain enclosures. -/
def hull (I J : Ival) : Ival := ⟨min I.lo J.lo, max I.hi J.hi⟩

/-- Rule (f): intersecting two enclosures in which `x` is strictly interior
keeps `x` strictly interior. -/
theorem strict_inter {I J : Ival} {x : ℝ} (hI : I.Strict x) (hJ : J.Strict x) :
    (I.inter J).Strict x :=
  ⟨max_lt hI.1 hJ.1, lt_min hI.2 hJ.2⟩

/-- Rule (e), plain version: a hull keeps strict containment of a constituent. -/
theorem strict_hull_left {I : Ival} {x : ℝ} (hI : I.Strict x) (J : Ival) :
    (I.hull J).Strict x :=
  ⟨lt_of_le_of_lt (min_le_left _ _) hI.1, lt_of_lt_of_le hI.2 (le_max_left _ _)⟩

/-- A strict enclosure is never a point: noncollapse of the bracket. -/
theorem nonpoint_of_strict {I : Ival} {x : ℝ} (h : I.Strict x) : I.lo < I.hi :=
  lt_trans h.1 h.2

end Ival

/-! ## Representable sets, soundness, straddling -/

/-- Soundness contract: every representable value lies in the plain bounds. -/
def Encloses (I : Ival) (S : Set ℝ) : Prop := ∀ y ∈ S, I.Mem y

/-- `S` has a value strictly below `x` and one strictly above. -/
def Straddles (S : Set ℝ) (x : ℝ) : Prop :=
  ∃ y₁ ∈ S, ∃ y₂ ∈ S, y₁ < x ∧ x < y₂

/-- `S` contains an open interval about `x` (the manuscript's formulation). -/
def OpenAbout (S : Set ℝ) (x : ℝ) : Prop :=
  ∃ δ > 0, Set.Ioo (x - δ) (x + δ) ⊆ S

/-- The open-interval property implies the two-point property. -/
theorem OpenAbout.straddles {S : Set ℝ} {x : ℝ} (h : OpenAbout S x) : Straddles S x := by
  obtain ⟨δ, hδ, hsub⟩ := h
  exact ⟨x - δ / 2, hsub (Set.mem_Ioo.mpr ⟨by linarith, by linarith⟩),
    x + δ / 2, hsub (Set.mem_Ioo.mpr ⟨by linarith, by linarith⟩),
    by linarith, by linarith⟩

/-- Open about a positive value: straddling can be realized by positive values. -/
theorem OpenAbout.straddles_pos {S : Set ℝ} {x : ℝ} (h : OpenAbout S x) (hx : 0 < x) :
    Straddles (S ∩ Set.Ioi 0) x := by
  obtain ⟨δ, hδ, hsub⟩ := h
  have hm1 : min δ x ≤ δ := min_le_left _ _
  have hm2 : min δ x ≤ x := min_le_right _ _
  have hm0 : 0 < min δ x := lt_min hδ hx
  exact ⟨x - min δ x / 2,
    ⟨hsub (Set.mem_Ioo.mpr ⟨by linarith, by linarith⟩), Set.mem_Ioi.mpr (by linarith)⟩,
    x + min δ x / 2,
    ⟨hsub (Set.mem_Ioo.mpr ⟨by linarith, by linarith⟩), Set.mem_Ioi.mpr (by linarith)⟩,
    by linarith, by linarith⟩

/-- Rule (d)/(e): truncation, promotion and hulls never shrink the representable
set, so straddling is preserved by any enlargement. -/
theorem Straddles.mono {S T : Set ℝ} {x : ℝ} (h : Straddles S x) (hST : S ⊆ T) :
    Straddles T x := by
  obtain ⟨y₁, h₁, y₂, h₂, hy₁, hy₂⟩ := h
  exact ⟨y₁, hST h₁, y₂, hST h₂, hy₁, hy₂⟩

/-- **Key step.** A sound enclosure of a straddling set strictly contains the value. -/
theorem strict_of_encloses {I : Ival} {S : Set ℝ} {x : ℝ}
    (hI : Encloses I S) (hS : Straddles S x) : I.Strict x := by
  obtain ⟨y₁, h₁, y₂, h₂, hy₁, hy₂⟩ := hS
  exact ⟨lt_of_le_of_lt (hI y₁ h₁).1 hy₁, lt_of_lt_of_le hy₂ (hI y₂ h₂).2⟩

/-! ## Open-image lemma (two-point form) -/

theorem straddles_image_strictMono {S : Set ℝ} {x : ℝ} {g : ℝ → ℝ}
    (hS : Straddles S x) (hg : StrictMono g) : Straddles (g '' S) (g x) := by
  obtain ⟨y₁, h₁, y₂, h₂, hy₁, hy₂⟩ := hS
  exact ⟨g y₁, Set.mem_image_of_mem g h₁, g y₂, Set.mem_image_of_mem g h₂, hg hy₁, hg hy₂⟩

theorem straddles_image_strictAnti {S : Set ℝ} {x : ℝ} {g : ℝ → ℝ}
    (hS : Straddles S x) (hg : StrictAnti g) : Straddles (g '' S) (g x) := by
  obtain ⟨y₁, h₁, y₂, h₂, hy₁, hy₂⟩ := hS
  exact ⟨g y₂, Set.mem_image_of_mem g h₂, g y₁, Set.mem_image_of_mem g h₁, hg hy₂, hg hy₁⟩

/-- Local version: the use is strictly monotone only on a set `U` containing the
straddling witnesses and the actual value. -/
theorem straddles_image_strictMonoOn {S U : Set ℝ} {x : ℝ} {g : ℝ → ℝ}
    (hS : Straddles S x) (hSU : S ⊆ U) (hx : x ∈ U) (hg : StrictMonoOn g U) :
    Straddles (g '' S) (g x) := by
  obtain ⟨y₁, h₁, y₂, h₂, hy₁, hy₂⟩ := hS
  exact ⟨g y₁, Set.mem_image_of_mem g h₁, g y₂, Set.mem_image_of_mem g h₂,
    hg (hSU h₁) hx hy₁, hg hx (hSU h₂) hy₂⟩

theorem straddles_image_strictAntiOn {S U : Set ℝ} {x : ℝ} {g : ℝ → ℝ}
    (hS : Straddles S x) (hSU : S ⊆ U) (hx : x ∈ U) (hg : StrictAntiOn g U) :
    Straddles (g '' S) (g x) := by
  obtain ⟨y₁, h₁, y₂, h₂, hy₁, hy₂⟩ := hS
  exact ⟨g y₂, Set.mem_image_of_mem g h₂, g y₁, Set.mem_image_of_mem g h₁,
    hg hx (hSU h₂) hy₂, hg (hSU h₁) hx hy₁⟩

/-- **Open-image lemma, affine case** (rules (a), (b)): a remaining use that is
affine in the perturbed value with a NONZERO actual coefficient keeps straddling. -/
theorem straddles_affine {S : Set ℝ} {x a b : ℝ} (hS : Straddles S x) (ha : a ≠ 0) :
    Straddles ((fun y => a * y + b) '' S) (a * x + b) := by
  rcases lt_or_gt_of_ne ha with hneg | hpos
  · have hg : StrictAnti (fun y : ℝ => a * y + b) := fun u v h => by
      show a * v + b < a * u + b
      nlinarith
    exact straddles_image_strictAnti hS hg
  · have hg : StrictMono (fun y : ℝ => a * y + b) := fun u v h => by
      show a * u + b < a * v + b
      nlinarith
    exact straddles_image_strictMono hS hg

/-! ## Affine forms with frozen old coordinates -/

/-- An affine form `[cl, ch] + Σ a_k η_k + [-e, e]`. -/
structure AForm (n : ℕ) where
  cl : ℝ
  ch : ℝ
  a : Fin n → ℝ
  e : ℝ

/-- Values represented with the old coordinates `η` frozen. -/
def AForm.vals {n : ℕ} (X : AForm n) (η : Fin n → ℝ) : Set ℝ :=
  {v | ∃ c ρ, X.cl ≤ c ∧ c ≤ X.ch ∧ |ρ| ≤ X.e ∧ v = c + ∑ k, X.a k * η k + ρ}

/-- A strict center witness (`cl < c < ch`) gives straddling of the actual value. -/
theorem AForm.straddles_of_strict_center {n : ℕ} (X : AForm n) (η : Fin n → ℝ)
    {x c ρ : ℝ} (hc₁ : X.cl < c) (hc₂ : c < X.ch) (hρ : |ρ| ≤ X.e)
    (hx : x = c + ∑ k, X.a k * η k + ρ) : Straddles (X.vals η) x := by
  have hle : X.cl ≤ X.ch := le_of_lt (lt_trans hc₁ hc₂)
  refine ⟨X.cl + ∑ k, X.a k * η k + ρ, ⟨X.cl, ρ, le_refl _, hle, hρ, rfl⟩,
    X.ch + ∑ k, X.a k * η k + ρ, ⟨X.ch, ρ, hle, le_refl _, hρ, rfl⟩, ?_, ?_⟩ <;> linarith

/-! ## Accepted brackets (Section 6, first paragraph) -/

theorem neg_of_hi_nonpos {I : Ival} {G : Set ℝ} {v : ℝ}
    (hI : Encloses I G) (hG : Straddles G v) (hhi : I.hi ≤ 0) : v < 0 :=
  lt_of_lt_of_le (strict_of_encloses hI hG).2 hhi

theorem pos_of_lo_nonneg {I : Ival} {G : Set ℝ} {v : ℝ}
    (hI : Encloses I G) (hG : Straddles G v) (hlo : 0 ≤ I.lo) : 0 < v :=
  lt_of_le_of_lt hlo (strict_of_encloses hI hG).1

theorem root_strictly_inside {f : ℝ → ℝ} {l h r : ℝ}
    (hl : f l < 0) (hh : 0 < f h) (hr : f r = 0) (hlr : l ≤ r) (hrh : r ≤ h) :
    l < r ∧ r < h := by
  refine ⟨lt_of_le_of_ne hlr ?_, lt_of_le_of_ne hrh ?_⟩
  · intro e
    rw [e] at hl
    linarith
  · intro e
    rw [e] at hr
    linarith

/-- An accepted bracket (weak tests `f(l).hi ≤ 0`, `f(h).lo ≥ 0`) whose guard
enclosures straddle the actual guard values contains the root strictly.
At elapsed zero, replace the first two hypotheses by the live-state fact `f l < 0`
and use `root_strictly_inside` directly. -/
theorem accepted_bracket_strict {f : ℝ → ℝ} {l h r : ℝ} {Il Ih : Ival} {Gl Gh : Set ℝ}
    (hIl : Encloses Il Gl) (hGl : Straddles Gl (f l)) (hl : Il.hi ≤ 0)
    (hIh : Encloses Ih Gh) (hGh : Straddles Gh (f h)) (hh : 0 ≤ Ih.lo)
    (hr : f r = 0) (hlr : l ≤ r) (hrh : r ≤ h) : l < r ∧ r < h :=
  root_strictly_inside (neg_of_hi_nonpos hIl hGl hl) (pos_of_lo_nonneg hIh hGh hh) hr hlr hrh

/-! ## Newton steps (Section 6, second and third paragraphs) -/

/-- General case. The mean slope `s > 0` is frozen (it is evaluated BEFORE the
guard), the root satisfies the mean-value identity `r = m - f(m)/s`, and the
guard evaluation supplies fresh freedom `F` straddling `f(m)`. Then any sound
enclosure of the Newton image strictly contains `r`. -/
theorem newton_step_strict {m r s fm : ℝ} {F : Set ℝ} {N : Ival}
    (hs : 0 < s) (hr : r = m - fm / s) (hF : Straddles F fm)
    (hN : Encloses N ((fun y => m - y / s) '' F)) : N.Strict r := by
  have hfun : (fun y : ℝ => m - y / s) = (fun y => (-s⁻¹) * y + m) := by
    funext y
    ring
  have hcoef : (-s⁻¹ : ℝ) ≠ 0 := neg_ne_zero.mpr (inv_ne_zero hs.ne')
  have h := straddles_affine (b := m) hF hcoef
  have hr' : r = (-s⁻¹) * fm + m := by
    rw [hr]
    ring
  rw [hfun] at hN
  rw [hr']
  exact strict_of_encloses hN h

/-- Rounded-midpoint-zero case. The guard value `f(m) < 0` is held fixed and the
freedom comes from the enclosed mean slope `S`, open about the actual `s > 0`.
`t ↦ m - f(m)/t` is strictly antitone on `(0, ∞)`, so the image straddles `r`. -/
theorem newton_step_strict_slope {m r s fm : ℝ} {Sl : Set ℝ} {N : Ival}
    (hs : 0 < s) (hfm : fm < 0) (hr : r = m - fm / s) (hSl : OpenAbout Sl s)
    (hN : Encloses N ((fun t => m - fm / t) '' (Sl ∩ Set.Ioi 0))) : N.Strict r := by
  have hanti : StrictAntiOn (fun t : ℝ => m - fm / t) (Set.Ioi 0) := by
    intro t₁ h₁ t₂ h₂ h
    have h₁' : (0 : ℝ) < t₁ := h₁
    have h₂' : (0 : ℝ) < t₂ := h₂
    have ht₁ : t₁ ≠ 0 := h₁'.ne'
    have ht₂ : t₂ ≠ 0 := h₂'.ne'
    have k₁ : fm / t₁ * t₁ = fm := by field_simp
    have k₂ : fm / t₂ * t₂ = fm := by field_simp
    have hb : fm / t₂ < 0 := div_neg_of_neg_of_pos hfm h₂'
    have key : fm / t₁ < fm / t₂ := by
      nlinarith [mul_pos_of_neg_of_neg hb (sub_neg.mpr h), h₁']
    show m - fm / t₂ < m - fm / t₁
    linarith
  have h := straddles_image_strictAntiOn (hSl.straddles_pos hs) Set.inter_subset_right
    (Set.mem_Ioi.mpr hs) hanti
  rw [hr]
  exact strict_of_encloses hN h

/-! ## Refinement: every retained output (Task 1, question 2) -/

/-- What `affine_refine` may retain at a step. -/
inductive Choice
  | newton  -- the correlated Newton image
  | inter   -- intersection of the previous bracket with the Newton image
  | keep    -- the previous bracket / previously retained image

def stepResult (B N : Ival) : Choice → Ival
  | .newton => N
  | .inter => B.inter N
  | .keep => B

theorem step_strict {B N : Ival} {r : ℝ} (hB : B.Strict r) (hN : N.Strict r)
    (c : Choice) : (stepResult B N c).Strict r := by
  cases c
  · exact hN
  · exact Ival.strict_inter hB hN
  · exact hB

/-- Every retained output of a finite refinement strictly contains the root and
is non-point, whatever is retained at each step. -/
theorem refine_strict (B N : ℕ → Ival) (c : ℕ → Choice) (r : ℝ)
    (hstep : ∀ n, B (n + 1) = stepResult (B n) (N n) (c n))
    (h0 : (B 0).Strict r) (hN : ∀ n, (N n).Strict r) :
    ∀ n, (B n).Strict r ∧ (B n).lo < (B n).hi := by
  intro n
  have hn : (B n).Strict r := by
    induction n with
    | zero => exact h0
    | succ k ih =>
      rw [hstep k]
      exact step_strict ih (hN k) (c k)
  exact ⟨hn, Ival.nonpoint_of_strict hn⟩

/-! ## Event-order consequence (strict-root note, Section 3) -/

/-- The root date is `b + r` (absolute base shifted by the root duration). The
duration is carried by a FRESH atom whose representable set `D` straddles `r`,
while the exterior date `x` and the base `b` are old data, frozen. If the
subtraction `x - date` is soundly enclosed by `E` and the weak test
`E.lo ≥ 0` passes, the physical order is strict: `b + r < x`. -/
theorem order_strict_after {x b r : ℝ} {D : Set ℝ} {E : Ival}
    (hD : Straddles D r) (hE : Encloses E ((fun d => x - (b + d)) '' D))
    (hlo : 0 ≤ E.lo) : b + r < x := by
  have hanti : StrictAnti (fun d : ℝ => x - (b + d)) := fun u v h => by
    show x - (b + v) < x - (b + u)
    linarith
  have hs := strict_of_encloses hE (straddles_image_strictAnti hD hanti)
  have h1 : E.lo < x - (b + r) := hs.1
  linarith

/-- The reversed comparison. -/
theorem order_strict_before {x b r : ℝ} {D : Set ℝ} {E : Ival}
    (hD : Straddles D r) (hE : Encloses E ((fun d => (b + d) - x) '' D))
    (hlo : 0 ≤ E.lo) : x < b + r := by
  have hmono : StrictMono (fun d : ℝ => (b + d) - x) := fun u v h => by
    show (b + u) - x < (b + v) - x
    linarith
  have hs := strict_of_encloses hE (straddles_image_strictMono hD hmono)
  have h1 : E.lo < (b + r) - x := hs.1
  linarith

/-- An exact coincidence between the exterior date and the root date passes
neither ordinary ordering test. -/
theorem coincidence_never_passes {x b r : ℝ} {D : Set ℝ} {E E' : Ival}
    (hD : Straddles D r)
    (hE : Encloses E ((fun d => x - (b + d)) '' D))
    (hE' : Encloses E' ((fun d => (b + d) - x) '' D))
    (hx : x = b + r) : ¬ (0 ≤ E.lo) ∧ ¬ (0 ≤ E'.lo) := by
  constructor
  · intro hlo
    have := order_strict_after hD hE hlo
    linarith
  · intro hlo
    have := order_strict_before hD hE' hlo
    linarith

/-- The hypothesis is necessary: with a POINT duration (no fresh freedom), the
weak test accepts an exact coincidence. This is the toy countermodel of the
main draft. -/
theorem point_duration_countermodel :
    ∃ (x b r : ℝ) (E : Ival),
      Encloses E ((fun d => x - (b + d)) '' {r}) ∧ 0 ≤ E.lo ∧ ¬ (b + r < x) := by
  refine ⟨0, 0, 0, ⟨0, 0⟩, ?_, le_refl _, by norm_num⟩
  intro y hy
  obtain ⟨d, hd, rfl⟩ := hy
  rw [Set.mem_singleton_iff] at hd
  subst hd
  constructor <;> norm_num

end A22

-- Must list only `propext`, `Classical.choice`, `Quot.sound`: no `sorryAx`.
#print axioms A22.accepted_bracket_strict
#print axioms A22.newton_step_strict
#print axioms A22.newton_step_strict_slope
#print axioms A22.refine_strict
#print axioms A22.coincidence_never_passes
#print axioms A22.point_duration_countermodel
