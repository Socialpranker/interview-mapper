# Validation and calibration (T1) — before trusting the conclusions

The skill is assembled from research; the thresholds are calibrated on synthetic data only (`reliability.md`) and accuracy on real data hasn't been measured. Before "production" use — run this stage. Otherwise you're building on sand.

## What we calibrate
Thresholds in the scripts are hyperparameters, not truth:
- `verify_quotes.py`: fuzzy `--threshold` (default 88), `--min-coverage` (0.6).
- `score_insights.py`: triangulation `--k` (3), watchlist `--severe` (4).
The only threshold documented in the primary sources is difflib 0.6; the rest is practice. Calibrate on your own data.

## Calibrating the verbatim threshold
1. Assemble a **gold-set** manually: 15–40 examples `{"quote":"…","is_verbatim":true/false}`.
   - true: the quote is really in the source (including with ASR noise).
   - false: a fabrication OR a heavy "regeneration" (words removed such that the meaning shifted).
   - **The most valuable are near-misses**: real quotes with fillers/punctuation removed (regenerations). On easy fabrications any threshold gives F1=1.0 and calibrates nothing.
2. `python scripts/calibrate_threshold.py --transcript T.txt --gold gold.json [--prefer-precision]`
3. Take the recommended threshold. For mapping, **precision** usually matters more (fewer false "verified" quotes) → `--prefer-precision`.

## Mini-eval skill vs baseline (qualitative)
The full eval cycle — via skill-creator. The minimum for a sanity check:
1. Take 2–3 transcripts.
2. Run the task twice: with this skill and without (baseline).
3. Compare via `references/rubric.md` (coverage 1–5 + divergence types). The score is set by a human, blind.
4. Look not only at the bottom line, but also at: the share of rejected quotes, the number of council flags, the caught omissions.
Test prompts — in `evals/evals.json`.

## Separate variance from effect (important!)
A single A/B run confuses "proofreading effect" and "the model's run-to-run variance". To separate them:
- run ONE transcript version 3–5 times, count which Layer 2 cells flip with the text unchanged — that's pure variance;
- only then compare raw vs proofread. The difference beyond variance = the proofreading effect.

## Honest status
- n<k interviews → synthesis yields no insights, only watchlist. Don't pass it off as a pattern.
- gold-set <15 examples → the threshold is approximate.
- Latent labels (eNPS, etc.) are unstable by nature — calibration doesn't fix it, only the council + a human.
