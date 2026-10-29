# Current specification — 28 pulses, ε = 1e-3, T = 230

This document states the family and protocol used by this repository. The hybrid
equations and weak-order event semantics are those of the archived
[`full_model_reference.md`](full_model_reference.md). The general-epsilon and calendar
extensions listed below specialize that reference to the current result.

## Network and source

There are 18 feedforward layers of 12 periodic lanes, hence 216 cells. The three
ports of cell (n,j) receive lanes j−1, j and j+1 of layer n−1, modulo 12.
Only external source lane 0 emits. A canonical pulse emitted at F is
`p_F(t) = a exp(−a(t−F))` for `F ≤ t < F+1`, and zero otherwise, with `a = ln 4`.

Training uses 28 pulses at `8k`, `k = 0,…,27`; the last source pulse starts at 216.
The terminal section is at the exact time 230. From Q28, the first future source
pulse can occur at or after 230; successive future source pulses are separated
by at least 20. They have the same canonical shape and use source lane 0.

## Parameter family

For each cell and input port independently, choose the following five parameters
within the relative factor `[0.999, 1.001]` of their nominal values. Each chosen
parameter stays fixed throughout training and future operation.

| Parameter | Nominal value |
|---|---|
| Gain cap C_i | 4 |
| Mark rate L_m,i | ln(5/4) / (1/50) |
| Silent rate L_s,i | ln 8 / (53/50) |
| Error rate L_e,i | ln 4 / (3/20) |
| Auxiliary input gain M_i | (1−r_m) / h(1/50) |

Here `h(u) = a/(a−κ) [exp(−κu) − exp(−au)]`. The constants `a = ln 4`, `κ = 1/2`,
`r = 1/10`, `r_m = 1/40`, both thresholds 1, the actuation factors 8 and 1/2,
the pump constants in `E' = 10(100−E) − W`, and `b_max = 11/10` are fixed.
The theorem does not quantify over perturbations of these fixed constants.

The engine uses separate per-port symbols for LM, LS, LE and M. C remains an
interval box; this abstraction allows independent physical caps and does not
force them to be equal. Parameters fixed in time are different from the learned
state variables z_i and b, which evolve according to the model.

## Initial family

Set `δ = 1e-5`. Independently in each cell:

| Coordinate or mode | Allowed initial value |
|---|---|
| Main mode | READY |
| Main charge q | `[r−δ, r+δ]` |
| Log-gain z_i | `[ln(g_i,nom)−δ, ln(g_i,nom)+δ]`, with nominal gains `(0.3, 1.2, 0.3)` |
| Recovery variable b | `[0.08−δ, 0.08+δ]` |
| Reserve E | `[50,100]` |
| Each auxiliary | READY with m_i in `[r_m−δ,r_m+δ]`, or terminal ERROR with m_i in `[r_m,r_m+δ]` |

There is no hidden prior pulse or additional delayed current. Initial auxiliary
modes in the middle of arbitrary phases are not included. The radius δ applies
to the stated charge, log-gain and recovery coordinates; it is not a radius on
every state component. The initial-section enclosure covers the allowed residual
ERROR phase instead of imposing a physical reset.

## How to read the archived documents

| Archived statement | Current specialization or status |
|---|---|
| 128 pulses at 8k, terminal time 1116 | 28 pulses at 8k, terminal time 230 |
| Relative parameter half-width 1e-4 | 1e-3 on the five per-port parameters above |
| Initial perturbation 1e-5 | Same radius on the specified coordinates and same allowed modes |
| Historical status dated 18 October 2026; campaign paused | Status of the archived dossier at that date, not the current campaign execution record |
| Earlier open training-entry obligations | Addressed by the later manual coverage argument and extensions; not a formal verification of the program |

The substitutions are justified by the
[general-epsilon coverage extension](../proof/extensions/COVERAGE_THEOREM_GENERAL_EPS_EN.txt),
[C7/C6/P extension](../proof/extensions/LEMMAS_C7_C6_EN.txt),
[lemma-E outward-rounding correction](../proof/extensions/lemma_e_outward_rounding/README.md),
[calendar bridge](../proof/extensions/CALENDAR_COVERAGE_BRIDGE.md), and
[general-epsilon future extension](../proof/extensions/FUTURE_INVARIANCE_GENERAL_EPS_EN.txt).
The [proof index](../proof/README.md) gives the complete reading order.

The archived model and its copy in `engine/reference/` are retained byte for byte.
In particular, the engine copy participates in the recorded program identity.

## Result and validation boundary

Under execution assumptions A1–A4 and the manual coverage argument, every admissible
training trajectory enters Q28 at 230. From Q28, each of the 191 active cells fires
once per future source pulse, the 25 silent cells remain silent, and the network
returns to Q28 before 12.791 time units after each source pulse. Fixed influential
gains and exact resting head charges imply a fixed latency for each active cell
in a fixed device and learned state, hence exact preservation of source intervals.

| Check | What it establishes |
|---|---|
| `python3 -I tools/verify.py` | Recomputes the initial and future certificates and Q28 from committed terminal records; normally 4 PASS |
| Same command with a full campaign directory | Also checks 488 output files and reproduces terminal extraction, lineage/clocks and commutation diagnostics; normally 9 PASS |
| Same command with the campaign and `--engine` as-run directory | Adds static engine-source/binary identity and archived kernel_id checks using the recorded environment; normally 11 PASS, without importing the engine |
| Same command with `--engine` and `--check-runtime` | Also loads the engine and checks the actual interpreter, dependency versions and native binaries against the recorded environment; normally 12 PASS with the matching runtime |
| Fresh `engine/run.py` campaign | Re-executes the training enclosure algorithm with the local build |
| Lean files | Check selected mathematical lemmas under explicit hypotheses |

The ordinary CI runs engine tests and the first certificate command, plus a separate
Lean workflow and verification-tool regression tests. It does not replay training or check the full release campaign archive.
Reproduction and matching hashes support correspondence and repeatability; they do
not replace the source-level soundness argument. The code-to-lemma bridge, event-order
coverage of the full engine and arithmetic implementation are not formally verified.

The future-certificate generator derives ε from the terminal campaign. The independent checker
and Q28 builder require the certificate's ε to agree with that campaign; explicit command-line
values must also agree. The independent report includes `eps`, identifying the width actually checked.

The result does not establish that 28 pulses are minimal, or extend to arbitrary
waveforms, time-varying parameter drift, noise or unrestricted initial modes.
