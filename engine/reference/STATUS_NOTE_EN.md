# Status note for `full_model_reference.md` (read this first)

`full_model_reference.md` is the author's physical model of A22, in French. It is **part of the program
identity**: its exact bytes enter `run.identity()` and therefore the campaign `kernel_id`
(`results/HASHES.md`). It is kept unchanged on purpose. Editing it, even its banner, would break the
exact provenance reconstruction of the v3.3 campaign.

**What is current.** Sections 1–6 (graph, source, parameters, states, phases, learning, resources,
initial set, event semantics) define the physical model. They are the model that the v3.3 campaign
computes and that the proof in `proof/` is about.

**What is historical.** The banner dated 18 October 2026 and section 7 describe the state of the work
*before* the v3.3 campaign. In particular:
- "La campagne principale demeure en pause": superseded. The v3.3 campaign (run_id `f29efeaf…`)
  completed all 18 layers.
- "Non acquis : la fermeture large 11–18": superseded. The wide family (δ = 1e-5, ε = 1e-4) is closed
  through layer 18 by the v3.3 campaign, with independent constants for each port.
- "Les premiers calculs A22 ne font pas partie du résultat livré ici": superseded. The v3.3 A22
  campaign is the result reported in this repository.
- The other items listed as "non acquis" (mixing over 12 layers, a common asymptotic front, a bounded
  access cost, a universal speed, necessity of the mechanism in every minimal R) **remain open**.
- "Une preuve écrite et des calculs validés ne constituent pas une vérification formelle…": still true.
  The proof in `proof/` is a manual proof under stated assumptions, not machine-checked.

**Wording in `engine/README_EN.txt`.** That file says "the user's original model"; read "the author's
original model". It is also kept byte-identical to the released engine package
(`A22_fresh_launch_v3_3_EN.zip`, listed in `engine/SHA256SUMS`), which the proof refers to.

This note is not part of the program identity and does not change any hash of the campaign.
