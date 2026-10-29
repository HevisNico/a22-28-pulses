# Gain-learning comparison

This paired experiment asks what adaptation of the three transmission log-gains
`z_i` contributes to A22's finite response. It compares the shipped dynamics with
`z_i` held at the engine's initial-section values. Both arms retain the same
conservative initial-slab enclosure (including its small gain allowance); the
frozen arm does not tighten it to a point or a different initial family.
The recovery variable `b` **remains adaptive
in both arms**. This is a gain-learning ablation, not removal of all adaptation.

Both arms use the same physical parameter family, initial-state enclosure,
connectivity and input protocol. They run in separate fresh Python processes.
The engine source files and published campaign/certificates are untouched.

## Run

From the repository root, install `engine/requirements.txt` and build the native
extensions with `python3 engine/build_all_native.py`. Start with one layer:

```sh
python3 -I -B experiments/learning_comparison.py --out engine/results/learning_eps1e-3 --layers 1 --epsilon 1e-3
```

The output directory must be new. To compare all 18 layers at ±0.5%:

```sh
python3 -I -B experiments/learning_comparison.py --out engine/results/learning_eps5e-3 --layers 18 --epsilon 5e-3 --timeout 3600
```

Each arm has its own timeout in seconds. The default protocol is 28 training
pulses at `8k`, followed by test pulses at **230, 250, 281, 321, 346**. The final
section is at 366. There is no state reset at 230. Customize future inter-pulse
gaps, all at least 20, with `--future-gaps 20 31 40 25`.

## Read the results

`comparison.json` records the protocol, parameter width, engine identity (including
local binaries), experiment hash, reference-certificate hash and arm statuses.
Each arm contains a `summary.json`, runtime versions and typed cell artifacts
that are serialized and read back with digest checks. Logs are in the top folder.

For each cell the summary reports:

- Training emission count and final gain/recovery boxes.
- Test response counts in windows `[source pulse, next source pulse)`; the final
  window ends at the experiment horizon. Boundary-straddling emission boxes are
  explicitly ambiguous. Window assignment is an operational metric, not a proof
  of the causal origin of an emission.
- Missing/extra responses relative to the published ±0.1% active/silent pattern.
  Silent reference cells are expected to emit zero times. This pattern is a
  comparison target, **not a certified pattern at ±0.5%**.
- For complete one-response-per-window trains, latency boxes and interval-error
  enclosures computed from correlated time differences. Their maximum absolute
  upper bound measures the enclosure; a positive bound alone does not establish
  a nonzero physical timing error. Incomplete trains get no timing-error score.

`completed` means the requested finite computation completed, not that every cell
matched the reference pattern or that transmission was exact. `unresolved` means
a timeout or calculation refusal; it does **not** establish a physical failure.
Partial results and error details remain available. Exit code is 1 if either arm
is unresolved, 0 if both complete.

The adapter recompiles the engine's existing patched `unit` source in memory to
change only its three horizon sites. It refuses an unexpected source layout.
In the frozen arm it also disables gain-current coefficients, gain deposition,
history accumulation and gain-cap events, while retaining recovery dynamics.
Every successful frozen cell is checked for accumulated gain histories.

This finite interval-engine experiment supplies neither an infinite-horizon
certificate nor a comparison with another physical cell model. Existing proof
arguments are not automatically applicable to the modified dynamics or horizon.

## Regression checks

```sh
python3 -B -m unittest discover -s experiments/tests
```

These tests cover interval metrics, silent cells, missing/extra/boundary responses,
the irregular protocol and separation of gain adaptation from recovery. They
include a real-engine check: at horizon 230 the adaptive adapter must reproduce
the original cell's entire scientific payload exactly; frozen gains must equal
their initial affine expressions. Dependencies and a local native build are
required for this integration check. CI runs the suite after the engine build.
