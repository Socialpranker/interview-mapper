# Synthesizing insights from a series of interviews (S5–S7)

The "N mappings → insights" stage. Main principle: **build up from atoms, don't compress from the top**.
A summary of summaries = where hallucinations compound ("employees think X" out of thin air).

## S5 — Nuggets (atomization)
From each mapping, pull out atomic observations. A nugget is indivisible and grounded.

Schema (`nuggets.json`, a list):
```json
{"id":"n1","interview":"Daria","role":"operations","cell":"K9",
 "observation":"Learns about decisions after the fact ~40%",
 "quote":"they call me at night...","line":135,
 "verified":true, "severity":4, "valence":"-", "cluster":null}
```
- `verified` — did the quote pass through `verify_quotes.py` (use ONLY verified nuggets as evidence of a pattern).
- `severity` 1–5 — criticality/impact (set by the model, justify it).
- `valence` `+`/`-`/`0` — sign (needed for tension detection).
- `role` — mandatory: insights are scoped by role.

## Severity / valence rubric (the model sets these by this scale, not at random)
The `score_insights.py` script depends on these fields — garbage in gives garbage in scoring. Set them with justification:
- **severity 1–5** — impact on the organization's/user's goal: 5 = blocker/systemic risk; 4 = major pain; 3 = noticeable friction; 2 = inconvenience; 1 = cosmetic.
- **valence** — the sign of the attitude in the nugget: `+` (works/values/for), `-` (pain/against/broken), `0` (neutral fact).
Valence is needed for tension detection: the same cluster with `+` for one role and `-` for another = TENSION.

## S6 — Clustering (affinity, done by the model)
Group nuggets by semantic themes, assign each a `cluster`. Rules:
- **Count different interviews, not quotes.** One person who repeated a thought three times is not a pattern.
- Don't merge opposing positions into one cluster — if roles diverge, that's a TENSION (more valuable than consensus), mark it with valence.
- A cluster is not "a theme in general" but a specific regularity.

## S6.5 — Accounting for reliability (script, not by eye)
`python scripts/score_insights.py nuggets.json --k 3`
Computes per cluster: distinct interviews, triangulation (≥k different interviews with a verified quote), frequency×criticality, tension, status:
- **insight** — triangulated (≥k sources) → can be called a pattern.
- **watchlist** — rare but critical (severity≥4) OR cross-role tension → don't bury.
- **weak** — a single source, low criticality → anecdote, not a pattern.
If N interviews is small (<k) — be honest: there will be no patterns, only watchlist. Don't pass off watchlist as an insight.

## S7 — Insight cards (the model builds these from the clusters that passed)
Only for `insight` and `watchlist`. A counter-evidence pass is mandatory.

Card format:
```
### [ID] Insight title — one sentence
Statement: [observation + interpretation + implication — not a retelling]
Holds for: [roles/segments] · NOT for: [where it doesn't work]
Prevalence: X of N interviews (roles: …) · Criticality: high/medium/low
Type: CONSENSUS | TENSION ([role A] vs [role B] — on exactly what)
Evidence (verified only):
  - [Interview, role] «verbatim quote» (Lxx)
  - [Interview, role] «…» (Lxx)
Counter-evidence: [who didn't confirm / what contradicts / where there's silence]
Confidence: high/medium/low  (based on triangulation + grounding)
Implication / recommendation: [what to do; for whom]
```

Card honesty rules:
- No verified quotes from ≥k different interviews → this is NOT an insight, mark it "watchlist / needs more interviews".
- Every card goes through counter-evidence: actively look for who did NOT confirm and who contradicts.
- "Silence" (not everyone asked raised the theme) — is also a signal, record it.
- An insight is always scoped: "for collections staff", not "for employees".

## S7.5 — Synthesis stability (optional, like S3)
Run S6–S7 twice in a fresh context. Insights that didn't reproduce (appeared/disappeared between runs), mark `[⚑ unstable]` — for a human. Clustering is subjective, like eNPS.

## Ranking the output
Sort: first `insight` by (frequency×criticality), then `watchlist` (including tensions and rare-but-critical), then don't show `weak` in the main report (move it to the "raw nuggets" appendix).
