# Rubric for comparing mappings (human ↔ AI, run ↔ run)

A single tool. Freeze it before the runs, don't change it mid-way.

## Unit
Each cell of the chosen lens (e.g., 18 for org mapping). We score by coverage + flag divergences.

## Coverage scale (1–5)
- **5** — complete: all key facts/names/numbers + quote, no errors.
- **4** — nearly complete: 1 minor omission.
- **3** — partial: the meaning is caught, specifics lost.
- **2** — weak: only the theme, details confused/missing.
- **1** — failure: theme not covered / gross error / hallucination.

## Types of divergence
- **[F]** factual error (name, number, attribution; often — a trace of transcription distortion).
- **[O]** omission (was in the source, didn't make it into the cell).
- **[I]** reinterpretation (the conclusion doesn't rest on the respondent's words).
- **[R]** frame mismatch (theme assigned to the wrong column / different level of generalization).

## What to record
**Run↔run (Experiment 1, proofreading effect/variance):** did the cell shift, the type, did the CONCLUSION change (not the wording). Bottom line — the share of cells where the meaning moved.

**Human↔AI (Experiment 2):** for each cell, the winner (human/AI/parity) + the loser's divergence type. Separately: where the AI hallucinates, where the human didn't make the analytical conclusion.

## Per-block Δ (VMDI format)
For the VMDI codebook, aggregate Δ by block, as in your "FINAL COMPARISON" template:

| Block | Avg. Δ AI↔Human | Main divergences/agreements |
|---|---|---|
| Block 1 … Block 6 | average over the block's codes | codes with Δ≤2 — where AI and human diverged the most |

This shows in which blocks the AI is reliable (Δ≈4–5) and where a human is needed (Δ≤2 — usually latent: eNPS, recognition culture, forecast).

## Honesty rule
The score in a human↔AI comparison is set by a **human, blind** (not knowing which is AI). "Parity 5/5", assigned by the AI itself by comparing texts, is not a blind score — mark it as such.

## Separate variance from effect
A single A/B run confuses "proofreading effect" and "the model's run-to-run variance". To separate them strictly —
≥3 runs of each version, measure which cells flip with the transcript UNCHANGED (that is the variance).
