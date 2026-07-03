#!/usr/bin/env python3
"""
route.py — детерминированный роутер пайплайна: ответы интейка → линза + выход + шаги.

Замыкает пайплайн: по цели/респонденту/выходу/числу интервью выдаёт план (какую линзу читать,
какой выход строить, какие стадии применимы). Модель не гадает маршрут — он зафиксирован.

CLI (флаги или интерактивно):
  python route.py --goal org --respondent employee --output insights --n 6 [--baseline yes]
Значения:
  goal:       discovery|org|experience|brand|prioritization|usability|expert|personas
  respondent: employee|customer|expert|visitor|stakeholder|candidate
  output:     mapping|insights|jobmap|persona|journey|memo|opportunity
  n:          число интервью (int)
"""
import argparse, json

LENS = {  # (по респонденту, с учётом цели) → файл линзы
    "employee": "templates/org-mapping-vmdi.md",
    "visitor": "templates/visitor-experience.md",
    "expert": "templates/expert.md",
    "customer": "templates/jtbd.md",       # уточняется целью ниже
    "stakeholder": "templates/expert.md",
    "candidate": "templates/org-mapping-vmdi.md",
}
LENS_BY_GOAL = {  # цель переопределяет линзу, когда важнее цель, чем «кто»
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
    "mapping": None,     # выход = само картирование, синтез не нужен
    "jobmap": "templates/jtbd.md",
}
K = 3  # порог триангуляции по умолчанию

def choose_lens(goal, respondent):
    # цель-переопределение сильнее, кроме орг/сотрудника
    if goal in LENS_BY_GOAL and not (goal == "org"):
        return LENS_BY_GOAL[goal]
    if goal == "brand":
        return "templates/brand-positioning.md"
    return LENS.get(respondent, "templates/org-mapping-vmdi.md")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", required=True)
    ap.add_argument("--respondent", required=True)
    ap.add_argument("--output", default=None, help="если не задан — выведем рекомендованный по цели")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--baseline", default="no")
    a = ap.parse_args()

    lens = choose_lens(a.goal, a.respondent)
    # выход по цели, если явно не задан
    default_out = {"org": "insights", "discovery": "insights", "experience": "journey",
                   "brand": "memo", "prioritization": "opportunity", "personas": "persona",
                   "expert": "memo", "usability": "insights"}.get(a.goal, "insights")
    out_key = a.output or default_out
    out_file = OUTPUT.get(out_key)

    can_synthesize = a.n >= K
    steps = ["S1 QA расшифровки (number_lines → вычитка → лог)",
             f"S2 Картирование по линзе ({lens}) + verify_quotes + check_support + omission",
             "S3 Совет надёжности на нестабильных ячейках (consensus) → флаг человеку"]
    if a.n >= 2 and out_key not in ("mapping",):
        if can_synthesize:
            steps += ["S5 extract_nuggets по всем картированиям",
                      "S6 Кластеризация (разные интервью, не цитаты)",
                      f"S6.5 score_insights --k {K} (триангуляция, частота×критичность, напряжения)",
                      f"S7 Выход: {out_file}",
                      "S7 build_provenance + render_board (аудит + борд)"]
        else:
            steps += [f"⚠ n={a.n} < k={K}: синтез даст только watchlist, НЕ инсайты. Добери интервью или помечай как пилот."]
    if a.baseline.lower() in ("yes", "y", "да"):
        steps += ["Сравнение человек↔ИИ по rubric.md (Δ 1–5, per-block), балл ставит человек вслепую"]

    plan = {
        "goal": a.goal, "respondent": a.respondent, "n_interviews": a.n,
        "lens": lens, "output": out_file, "output_kind": out_key,
        "can_synthesize_patterns": can_synthesize, "k_triangulation": K,
        "pipeline": steps,
        "caveats": [
            "Латентные ячейки (eNPS, признание, прогноз) — всегда кандидаты на человека.",
            "Пороги угаданы — калибруй (references/validation.md).",
        ],
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
