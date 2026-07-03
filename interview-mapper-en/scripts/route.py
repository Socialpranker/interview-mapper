#!/usr/bin/env python3
"""
route.py — deterministic pipeline router: intake answers → lens + output + steps.

Closes the pipeline: from goal/respondent/output/number of interviews it produces a plan (which lens to read,
which output to build, which stages apply). The model doesn't guess the route — it's fixed.

CLI (flags or interactive):
  python route.py --goal org --respondent employee --output insights --n 6 [--baseline yes]
Values:
  goal:       discovery|org|experience|brand|prioritization|usability|expert|personas
  respondent: employee|customer|expert|visitor|stakeholder|candidate
  output:     mapping|insights|jobmap|persona|journey|memo|opportunity
  n:          number of interviews (int)
"""
import argparse, json

LENS = {  # (by respondent, considering the goal) → lens file
    "employee": "templates/org-mapping-vmdi.md",
    "visitor": "templates/visitor-experience.md",
    "expert": "templates/expert.md",
    "customer": "templates/jtbd.md",       # refined by goal below
    "stakeholder": "templates/expert.md",
    "candidate": "templates/org-mapping-vmdi.md",
}
LENS_BY_GOAL = {  # goal overrides the lens when the goal matters more than «who»
    "discovery": "templates/custdev.md",
    "brand": "templates/brand-positioning.md",
    "experience": "templates/visitor-experience.md",
    "expert": "templates/expert.md",
}
OUTPUT = {
    "insights": "outputs/insight-cards.md",
    "persona": "outputs/personas.md",
    "personas": "outputs/personas.md",
    "journey": "outputs/journey-map.md",
    "memo": "outputs/decision-memo.md",
    "opportunity": "outputs/opportunity-prioritization.md",
    "prioritization": "outputs/opportunity-prioritization.md",
    "mapping": None,     # output = the mapping itself, no synthesis needed
    "jobmap": "templates/jtbd.md",
}
K = 3  # default triangulation threshold

def choose_lens(goal, respondent):
    # goal-override is stronger, except for org/employee
    if goal in LENS_BY_GOAL and not (goal == "org"):
        return LENS_BY_GOAL[goal]
    if goal == "brand":
        return "templates/brand-positioning.md"
    return LENS.get(respondent, "templates/org-mapping-vmdi.md")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", required=True)
    ap.add_argument("--respondent", required=True)
    ap.add_argument("--output", default=None, help="if not set — we'll output the one recommended by goal")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--baseline", default="no")
    a = ap.parse_args()

    lens = choose_lens(a.goal, a.respondent)
    # output by goal, if not explicitly set
    default_out = {"org": "insights", "discovery": "insights", "experience": "journey",
                   "brand": "memo", "prioritization": "opportunity", "personas": "persona",
                   "expert": "memo", "usability": "insights"}.get(a.goal, "insights")
    out_key = a.output or default_out
    out_file = OUTPUT.get(out_key)

    can_synthesize = a.n >= K
    steps = ["S1 Transcript QA (number_lines → proofreading → log)",
             f"S2 Mapping by lens ({lens}) + verify_quotes + check_support + omission",
             "S3 Reliability council on unstable cells (consensus) → flag to human"]
    if a.n >= 2 and out_key not in ("mapping",):
        if can_synthesize:
            steps += ["S5 extract_nuggets across all mappings",
                      "S6 Clustering (different interviews, not quotes)",
                      f"S6.5 score_insights --k {K} (triangulation, frequency×severity, tensions)",
                      f"S7 Output: {out_file}",
                      "S7 build_provenance + render_board (audit + board)"]
        else:
            steps += [f"⚠ n={a.n} < k={K}: synthesis yields only watchlist, NOT insights. Add interviews or mark as pilot."]
    if a.baseline.lower() in ("yes", "y", "да"):
        steps += ["Human↔AI comparison on rubric.md (Δ 1–5, per-block), scored by a human blind"]

    plan = {
        "goal": a.goal, "respondent": a.respondent, "n_interviews": a.n,
        "lens": lens, "output": out_file, "output_kind": out_key,
        "can_synthesize_patterns": can_synthesize, "k_triangulation": K,
        "pipeline": steps,
        "caveats": [
            "Latent cells (eNPS, recognition, forecast) are always candidates for a human.",
            "Thresholds are guessed — calibrate (references/validation.md).",
        ],
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
