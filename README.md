# A22 — certified exact transmission after 28 training pulses

**Result.** A learning spiking network of 216 coupled hybrid cells (18 layers × 12 lanes) is trained
by **28 source pulses** (times 0, 8, …, 216). For **every device** whose physical constants lie within
**±0.1 %** of nominal, independently for each input port of each cell, and for every initial state
within ±1e-5, a computer-assisted enclosure shows that at **t = 230** the network is in an explicit
quiescent domain Q28. A written proof then shows that from Q28, **for every future sequence of source
pulses spaced by at least 20**, each of the 191 active cells fires exactly once per pulse, the network
returns to rest, and the intervals between pulses are transmitted **exactly** through all 18 layers.

**Status.** This repository is being assembled. It will contain the model, the exact engine that ran,
the campaign records, the terminal domain, all proof documents, the machine-checked parts (Lean 4),
the two independent future checkers, and a single command that rechecks everything from the outputs.

The proof is a computer-assisted manual argument under explicit execution assumptions (authentic
execution of the recorded program, correct arithmetic runtime and native binaries, fail-closed
assertions, namespace discipline). It has not yet been reviewed by an independent expert, and only
its purely mathematical steps are machine-checked.

The development history (earlier versions, the 128- and 32-pulse campaigns, arbitrary depth, box-width
sweeps) is in [a22-interval-replay](https://github.com/HevisNico/a22-interval-replay).

> **Made with AI.** The code, the diagnostics and the written proof were produced with Claude
> (Anthropic) and ChatGPT (OpenAI) under the direction of Nicolas Breuillaud.
> 
