# S0 — Intake "Goal survey" (adaptive, before choosing the lens)

Goal: don't guess, route. The pipeline depends on the GOAL and WHO was interviewed — these two axes
set the lens (how to extract) and the output (what to build). Ask the MINIMUM, then more only as needed.

## Adaptive survey (not a long questionnaire)
**Always (2 questions — in 90% of cases they already determine the lens):**
1. **Goal/decision:** problem discovery · org mapping · experience evaluation · positioning/brand · prioritization-roadmap · usability evaluation · expert validation · personas/segments.
2. **Who was interviewed:** employee · customer/user · expert · visitor · stakeholder · candidate.

**As needed (only if ambiguous or required for synthesis):**
3. **The output:** mapping · insight cards · job map · personas · journey · decision memo · opportunities. (If not stated — use the default by goal.)
4. **How many interviews:** 1 / 2–4 / 5+ (determines whether we can talk about patterns: `k=3`).
5. **Is there a human baseline** to compare against (enables comparison by Δ 1–5).

Ask the user these questions (in Cowork — via option selection). Don't start mapping until axis-1 and axis-2 are clear.

## Routing matrix (goal × respondent → lens)
| Goal \ Who | employee | visitor | expert | customer |
|---|---|---|---|---|
| org mapping | org-mapping-vmdi | — | expert | — |
| problem discovery | custdev | custdev | — | custdev |
| "job"/choice (JTBD) | — | — | — | jtbd |
| experience evaluation | — | visitor-experience | — | visitor-experience |
| positioning/brand | brand-positioning | brand-positioning | brand-positioning | brand-positioning |
| expert validation | — | — | expert | — |

## Goal → default output
- org mapping → insight cards · experience evaluation → journey · positioning → decision memo ·
  prioritization → opportunities · personas → personas · expert → decision memo.

## Check the route with the script
`python scripts/route.py --goal org --respondent employee --output insights --n 6 [--baseline yes]`
→ returns the lens, output, applicable pipeline steps and warnings (including "n<k → watchlist only").

## Principle
Few artifacts, smart routing: `N lenses × M outputs` cover `N×M` tasks. Don't breed duplicate templates —
for a new task, first check whether it's covered by (lens + output), and only then add one.
