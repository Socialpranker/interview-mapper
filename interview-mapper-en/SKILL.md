---
name: interview-mapper-en
description: >
  Map and interpret interviews (transcripts) with a chosen methodology, transcript QA,
  and reliability checks. Use WHENEVER the user wants to analyze, code, map, interpret,
  or "make sense of" an interview, transcript, depth interview, custdev/JTBD/expert
  interview, synthesize a series of interviews, or pull cross-interview insights
  (synthesis, patterns, insight cards) — even if they don't name a method. Supports
  employee org-mapping, JTBD, CustDev/discovery, expert, visitor-experience, and
  positioning/brand lenses. Specifically handles: transcription distortions, fabricated
  and "regenerated" quotes, and instability of analytic conclusions across runs.
  Not for generating new interviews and not for plain audio transcription.
---

# Interview Mapper

Turns an interview transcript into a structured mapping where **every conclusion is grounded
in a verbatim quote**, analysis is checked across **multiple runs**, and disputed cells are
**flagged for a human** rather than resolved silently. Built on an evidence base
(self-consistency, LLM-as-judge flip-rate, faithfulness ≠ verbatim; see `references/reliability.md`).

## S0 — Intake "Goal survey" (ALWAYS first)
The pipeline depends on two axes: **what you're deciding** (goal) and **who you interviewed** (respondent).
Don't start mapping until both are clear. Ask adaptively (details — `references/intake.md`):
1. **Goal:** discovery · org-mapping · experience evaluation · positioning/brand · prioritization · expert validation · personas.
2. **Who you interviewed:** employee · customer · expert · visitor · stakeholder · candidate.
3. (as needed) output · number of interviews · whether a human baseline exists.

Then lock the route with a script:
`python scripts/route.py --goal <goal> --respondent <who> [--output <output> --n <N> --baseline yes]`
→ returns the lens, output, and applicable steps (including the warning "n<k → watchlist only").

### Axis 1 — Lenses (how to extract from ONE interview)
| Lens | For whom | Template |
|---|---|---|
| Org-mapping (6 blocks · 40 codes) | employee | `templates/org-mapping-vmdi.md` |
| JTBD | customer (the "job"/choice) | `templates/jtbd.md` |
| CustDev (Mom Test) | customer (problem discovery) | `templates/custdev.md` |
| Expert | expert/stakeholder | `templates/expert.md` |
| Visitor experience | visitor | `templates/visitor-experience.md` |
| Positioning/brand | anyone (name/brand focus) | `templates/brand-positioning.md` |

### Axis 2 — Outputs (what to build from N interviews)
| Output | When | Template |
|---|---|---|
| Insight cards | synthesis default | `outputs/insight-cards.md` |
| Personas | segments (need ≥5 interviews) | `outputs/personas.md` |
| Journey map | path across stages | `outputs/journey-map.md` |
| Opportunities/prioritization | roadmap input | `outputs/opportunity-prioritization.md` |
| Decision memo | for one stakeholder decision | `outputs/decision-memo.md` |

All lenses share one backbone (Framework Method, two layers: facts + analysis). Principle: **few artifacts, smart routing** — `N lenses × M outputs` cover `N×M` tasks. Don't spawn duplicates: for a new task, first check (lens + output).

## Pipeline S0.5–S4
Details of each step — `references/pipeline.md`. In brief:

### S0.5 — Many interviews? Prepare in batch
For several interviews: `python scripts/batch_prepare.py folder/` — numbers lines for all and writes `manifest.json`. Then map by the manifest.

### S1 — Transcript QA (proofread by decision-relevance)
1. Number the lines: `python scripts/number_lines.py input.(txt|docx)` → `*_nl.txt`. Quotes reference lines, BUT the line number is set by the script, not by you (models are poor at line numbers — S2.3).
2. Find distortion candidates: proper names, system names, numbers, "garbage" spans.
3. For each, mark **which cell** it affects (decision-relevance). Fix only the relevant ones.
4. Split fixes into **confident** (fix, keep a log) and **uncertain** (do NOT fix, flag — can't guess without audio).
5. Save the clean version + change log. Proofreading fixes the factual layer, NOT the analysis (empirically: it changes names/systems, not tone).

### S2 — Interpretation by lens + grounding check
1. Read the lens template. Fill Layer 1 (facts, **1 run** — facts are stable) and Layer 2 (analysis).
2. **Each Layer-1 cell — a direct quote + line number. Quote VERBATIM, do not paraphrase.**
   If there's no exact quote — write "NO QUOTE", don't fabricate.
3. **Check verbatim with a script** (not by eye). Don't assign line numbers yourself — the script does:
   auto-collect quotes from the finished mapping: `python scripts/extract_claims.py mapping.md --interview NAME --role ROLE` → `claims.json`;
   then `python scripts/verify_quotes.py --transcript *_nl.txt --claims claims.json --emit-enriched claims_lines.json`.
   Statuses: `verified_exact/fuzzy` — ok; `rejected` — quote not in source (regeneration/fabrication) → fix or drop. `--emit-enriched` returns quotes with the line filled in.
4. **Check support (entailment) — a required, logged step, not "by eye".** For each quote give a verdict `support ∈ {yes,partial,no}` + why in `support.json`, run it a second time independently (judge-2), then
   `python scripts/check_support.py support.json --second support2.json`.
   The script catches `dangerous` (quote is verbatim but the thesis is NOT supported by it — verbatim ≠ support) and `judge_disagreements` → soften both / send to a human.
5. **Counterfactual pass:** "what in the data CONTRADICTS these conclusions? which fragments landed in no cell?" (omission-check — omissions are more dangerous than fabrications).

> verify/score thresholds are guessed. Before production use, calibrate: `references/validation.md` + `scripts/calibrate_threshold.py`.

### S3 — Reliability council (only for unstable Layer-2 cells)
Analysis (eNPS, culture of recognition, horizon, forces of progress, etc.) flips across runs.
1. Do **N isolated Layer-2 runs** (default 3) — each as a separate subagent with a **fresh context** (star-model), re-feeding the transcript (re-grounding), NOT the chat history. Don't re-run Layer 1.
2. Save runs as json `{ "A1": {"label":"...","text":"..."}, ... }`.
3. Aggregate: `python scripts/consensus.py run1.json run2.json run3.json --weights <by share of valid quotes>`.
   - `flagged` — runs disagreed on the label → **a human adjudicates blind**, don't pick yourself.
   - agreeing cells — consensus.
4. A run's weight ↓ if it has many `rejected` quotes (poorly grounded).
5. For flagged cells — prepare the human a fork: `python scripts/make_adjudication.py consensus.json run1.json run2.json …` → cards with options side by side.

### S4 — Output
Final mapping: per cell — conclusion + quote(line) + grounding status
(`verified/paraphrase/rejected` × `supported/unsupported`) + for Layer 2 a mark `[consensus]` or
`[⚑ disputed — human decides]`. Plus: change log, omission list, list of rejected quotes
(transparency is a feature). Format — `references/pipeline.md` §S4.

## Cross-interview insight synthesis (S5–S7)
When there are ≥2 mappings and you need cross-interview insights — switch to synthesis mode.
Details: `references/synthesis.md`. In brief:
1. **S5 Nuggets** — auto-stubs from each mapping: `python scripts/extract_nuggets.py mapping.md --interview NAME --role ROLE`. The model fills `severity/valence/cluster`, verify_quotes fills `verified`. Build up from atoms, do NOT compress summaries.
2. **S6 Clustering** — assign a `cluster` to each nugget. Count **distinct interviews, not quotes**; don't merge diverging roles — that's a TENSION.
3. **S6.5 Scoring** — `python scripts/score_insights.py nuggets.json --k 3`: triangulation, frequency×criticality, tension detection, status `insight/watchlist/weak`.
4. **S7 Cards** — for passing clusters write insight cards (statement + evidence with verified quotes + prevalence + tension + counter-evidence + confidence + implication). Scope by role.
5. **Audit and board** — `python scripts/build_provenance.py --insights scored.json --support support.json` → full trail insight→quote→line→interview; `python scripts/render_board.py provenance.json --out board.html` → standalone HTML board with filters.

Honestly: a pattern = ≥k distinct interviews with a verified quote. Too few interviews → watchlist only, don't sell as an insight. Frequency ≠ importance (keep the second axis — criticality); the gold is in tensions, not consensus.

## Human↔AI comparison (optional)
If a human version exists — compare via `references/rubric.md` (18 cells × coverage 1–5 + discrepancy types).
The score is set by a human blind, not by the AI itself.

## Script index
| Script | Purpose | Stage |
|---|---|---|
| `route.py` | intake answers → lens + output + steps | S0 |
| `batch_prepare.py` | folder of transcripts → numbering + manifest | S0.5 |
| `number_lines.py` | line numbering | S1 |
| `extract_claims.py` | mapping.md → claims.json | S2 |
| `verify_quotes.py` | verbatim (+ `--emit-enriched` sets the line) | S2 |
| `check_support.py` | entailment: quote ⊨ thesis, judge-2, catches `dangerous` | S2 |
| `calibrate_threshold.py` | threshold calibration on a gold-set | validation |
| `consensus.py` | council: agreement/flag on unstable cells | S3 |
| `make_adjudication.py` | fork cards for a human | S3 |
| `extract_nuggets.py` | mapping.md → nuggets.json | S5 |
| `score_insights.py` | triangulation, frequency×criticality, tensions | S6.5 |
| `build_provenance.py` | audit trail insight→quote→line→interview | S7 |
| `render_board.py` | standalone HTML insight board | S7 |

## Honest limits (state them to the user)
- On **latent** constructs (tone, intent, power, eNPS) LLMs are weak — these cells are always human candidates.
- Thresholds (fuzzy 88, coverage 0.6, k=3) are guessed. **Calibrate before trusting** (`references/validation.md`).
- n<k interviews — a pilot, not a measurement. Synthesis gives only watchlist, not insights.
- Verbatim ≠ support: `verify_quotes` does not replace `check_support`.

## Dependencies
Scripts — stdlib Python only; `rapidfuzz` is used if present (more accurate), otherwise auto-fallback to `difflib`.
`number_lines.py`/`batch_prepare.py` need `python-docx` for .docx. Validation — `references/validation.md`; eval prompts — `evals/evals.json`.
