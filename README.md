# A22 — certified exact transmission after 28 training pulses

**Result.** A learning spiking network of 216 coupled hybrid cells (18 layers × 12 lanes) is trained
by **28 source pulses** on lane 0 (times 0, 8, …, 216). For **every fixed device** whose five
per-port parameters **C_i, L_m,i, L_s,i, L_e,i and M_i** lie independently within **±0.1 %** of nominal,
and for every state in the [specified initial family](model/CURRENT_SPEC.md#initial-family)
(with δ = 1e-5 on the specified coordinates, restricted initial modes and E in [50,100]):

1. **Training.** At **t = 230** the network is in an explicit quiescent domain **Q28**
   ([`terminal/invariant_domain_Q28.json`](terminal/invariant_domain_Q28.json)).
2. **Afterwards, forever.** From Q28, for every future sequence of source pulses spaced by at least 20,
   each of the **191 active cells fires exactly once** per pulse, the network is back at rest within
   12.791 time units, and it returns to Q28.
3. **Exact transmission.** Each active cell answers with a fixed latency, so the intervals between pulses
   are transmitted **exactly** through all 18 layers. The latencies depend on the device and on the learned
   gains; they are not claimed to be equal across devices.

The [current specification](model/CURRENT_SPEC.md) lists the fixed constants, initial-state
restrictions and source protocol. In particular, a, κ, r, r_m, the thresholds, actuation factors,
energy-pump constants and b_max are fixed; the parameter box does not include time-varying drift.

The proof combines a computer-assisted enclosure of every admissible trajectory of the training with a
written argument that the enclosure covers them, and with finite certificates for the future regime.
It holds under explicit execution assumptions (A1–A4: authentic execution of the recorded program, correct
arithmetic runtime and native binaries, fail-closed assertions, namespace discipline). It has **not yet been
reviewed by an independent expert**. Some of its mathematical lemmas are machine-checked in Lean 4 (the
abstract core of the strict-root lemma, lemmas C7, C6 and P, the mathematical part of lemma E, the
first-crossing facts and the number-free steps of the future proof; list in [`proof/README.md`](proof/README.md));
the rest of the argument, the program and its arithmetic are not. Review is welcome: [`REVIEW.md`](REVIEW.md).

> **Made with AI.** The code, the diagnostics and the written proof were produced with Claude
> (Anthropic) and ChatGPT (OpenAI) under the direction of Nicolas Breuillaud.

## The campaign

| | |
|---|---|
| Physical parameters | ±1e-3 relative on C_i, L_m,i, L_s,i, L_e,i and M_i; fixed independently per port |
| Parameter representation | Separate per-port symbols for LM/LS/LE/M; C kept as an interval box |
| Initial family | δ = 1e-5 on the specified coordinates; restricted modes; E in [50,100] ([details](model/CURRENT_SPEC.md#initial-family)) |
| Training source | 28 canonical pulses, lane 0, times 8k for k = 0…27 |
| Terminal cut | exact time 230, checked for every cell (no uncertain term) |
| Layers accepted | 18 / 18, each layer re-read by a separate verifier process |
| Active cells; silent cells | 191; 25 (all active cells at exact rest at 230) |
| Network emissions during training | 2 202 |
| Fire/event commutations (lemma E) | 6 |
| Future regime from Q28 | at rest before 12.7907; idle margin 7.209 before the next pulse; smallest strict margin 0.0489 |
| Campaign identity | `kernel_id` `b49dca10…`, run `25e6fa5f…` ([`campaign/campaign.json`](campaign/campaign.json)) |

The engine is the exact program that ran ([`engine/`](engine/), 101 tests). Its origin and the few changes
from the first version are listed in [`PROVENANCE.md`](PROVENANCE.md).

## What proves what

| Part | Argument | Checked by |
|---|---|---|
| Model and current protocol | [`model/CURRENT_SPEC.md`](model/CURRENT_SPEC.md), with the archived equations linked there | — |
| Training covers every trajectory | coverage theorem and its extensions ([`proof/README.md`](proof/README.md), steps 2–4) | the campaign; extraction, lineage and commutation audits |
| Entry into Q28 at 230 | same | [`terminal/`](terminal/) |
| Future regime from Q28 | future invariance proof (step 5) | two independent programs (directed integers, directed decimals) |
| Exact transmission | word-preservation theorem (step 6) | — |
| Selected mathematical lemmas | strict-root core, C7/C6/P, mathematical part of lemma E, first crossings, number-free future-wave steps | Lean 4, no `sorry` ([`proof/lean/`](proof/lean/README.md)) |

## Check it

```sh
python3 -I tools/verify.py
```
recomputes the initial section, the future certificate, its independent check and Q28 from the committed
records, and compares them (standard library only; also run by CI). This default command does not
rerun training or validate the release campaign payloads. With the release assets of `v1.0`
(their SHA-256 are in [`RELEASE_ASSETS_SHA256.json`](RELEASE_ASSETS_SHA256.json)):

```sh
unzip A22_28_campaign28_T230_eps1e-3.zip && unzip A22_28_engine_as_run.zip
python3 -I tools/verify.py campaign28_T230_eps1e-3 --engine A22_28_engine_as_run
```
also checks every output file against [`campaign/RUN_MANIFEST.json`](campaign/RUN_MANIFEST.json), re-extracts
the terminal state and reruns the lineage and commutation audits byte for byte, and recomputes the
archived `kernel_id` from the engine files and the recorded environment. These are static checks:
they do not import the archived engine or require its original interpreter. Expected: `11 PASS, 0 FAIL`.

To additionally check the **loaded runtime**, use:
```sh
python3 -I tools/verify.py campaign28_T230_eps1e-3 --engine A22_28_engine_as_run --check-runtime
```
This requires the recorded CPython **3.13.17**, numpy **2.3.5**, scipy **1.17.0**, and both archived
native extensions. A Python fallback, a different interpreter or different loaded binaries fail this
additional check. Expected with a matching runtime: `12 PASS, 0 FAIL`.

The future-certificate tools read ε from the terminal campaign metadata. An optional explicit ε must
match it exactly; the independent checker and Q28 builder also check the certificate's ε. The independent
report records the checked value as `eps`. For example, the standalone check uses ε = 1e-3 automatically:
```sh
python3 -I tools/verify_future.py terminal/all_terminal_exact.json terminal/future_certificate.json check.json
python3 -B -m unittest discover -s tools/tests
```

To rerun the campaign itself (about 10 minutes with 4 workers):
```sh
cd engine && python3 build_all_native.py && python3 -B -m unittest discover -s tests
python3 -u -B run.py --out ../new_campaign --through 18 --epsilon 1e-3 --workers 4 --memory-mib 3000
```
A rebuild on another machine gives another engine identity, hence another `kernel_id` and other identity
hashes; the enclosed values can then be compared with those of [`terminal/`](terminal/).

## What it does not say

- **Not a minimum.** 28 pulses and t = 230 come from a sampled point-simulation search; fewer pulses or an
  earlier cut are not excluded.
- **Not the box of real components.** ±0.1 % is far tighter than the variability of physical devices.
- **Not a qualification of the program.** The assumptions A1–A4 are explicit; the native binaries, the
  compiler and the Python runtime are trusted, not verified.

## Learning comparison

For a paired finite experiment comparing adaptive gains with gains frozen at their
initial values, see [`experiments/README.md`](experiments/README.md). Recovery remains
adaptive in both variants; the experiment has its own outputs and does not extend
the published certificate.

## History

This result is the outcome of the development recorded in
[a22-interval-replay](https://github.com/HevisNico/a22-interval-replay): the first complete version (±1e-4,
128 pulses), the extension to ±1e-3, the 32-pulse schedule, arbitrary depth and the box-width sweeps.
