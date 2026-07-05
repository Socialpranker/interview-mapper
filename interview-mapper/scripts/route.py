#!/usr/bin/env python3
"""
route.py — детерминированный роутер пайплайна: ответы интейка → линза + выход + шаги.

Замыкает пайплайн: по цели/респонденту/выходу/числу интервью выдаёт план (какую линзу читать,
какой выход строить, какие стадии применимы). Модель не гадает маршрут — он зафиксирован.

CLI (флаги или интерактивно):
  python route.py --goal org --respondent employee --output insights --n 6 [--baseline yes]
Значения:
  goal:       discovery|org|experience|brand|prioritization|usability|expert|personas|exit|winloss|retro|
              intercept|conflict|ethnography|changereadiness
  respondent: employee|customer|expert|visitor|stakeholder|candidate|group|conflictparty
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
    "candidate": "templates/candidate.md",
    "group": "templates/focus-group.md",   # уточняется целью ниже (retro → team-retro)
    "conflictparty": "templates/conflict-mediation.md",
}
LENS_BY_GOAL = {  # цель переопределяет линзу, когда важнее цель, чем «кто»
    "discovery": "templates/custdev.md",
    "brand": "templates/brand-positioning.md",
    "experience": "templates/visitor-experience.md",
    "expert": "templates/expert.md",
    "usability": "templates/usability.md",
    "exit": "templates/exit.md",
    "winloss": "templates/winloss.md",
    "retro": "templates/team-retro.md",
    "intercept": "templates/intercept.md",
    "conflict": "templates/conflict-mediation.md",
    "ethnography": "templates/ethnographic.md",
    "changereadiness": "templates/change-readiness.md",
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
    """Выбирает файл линзы по цели и типу респондента (цель обычно сильнее «кто»)."""
    # респондент сильнее цели там, где сам тип респондента однозначно задаёт линзу
    # (кандидат — собеседование не "экспертная валидация"; сторона конфликта — не путать с expert/stakeholder)
    if respondent in ("candidate", "conflictparty"):
        return LENS[respondent]
    # цель-переопределение сильнее, кроме орг/сотрудника
    if goal in LENS_BY_GOAL and not (goal == "org"):
        return LENS_BY_GOAL[goal]
    if goal == "brand":
        return "templates/brand-positioning.md"
    return LENS.get(respondent, "templates/org-mapping-vmdi.md")

def main():
    """CLI: строит детерминированный план пайплайна по интейку (цель/респондент/выход/N)."""
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
                   "expert": "memo", "usability": "insights", "exit": "insights",
                   "winloss": "memo", "retro": "insights", "intercept": "insights",
                   "conflict": "memo", "ethnography": "insights",
                   "changereadiness": "memo"}.get(a.goal, "insights")
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

    caveats = [
        "Латентные ячейки (eNPS, признание, прогноз) — всегда кандидаты на человека.",
        "Пороги калиброваны на синтетике — валидируй на своих данных (references/validation.md).",
    ]
    if a.respondent == "group":
        caveats.append("Групповой формат: единица кодирования — реплика+говорящий, не изолированное высказывание. Расшифровка ДОЛЖНА быть диаризована (говорящие подписаны) — иначе блокер S1, не докодировать на глаз.")
    if a.respondent == "conflictparty" or a.goal == "conflict":
        caveats.append("Конфликт/медиация: каждая сторона — ОТДЕЛЬНЫЙ файл картирования, не смешивать. Ячейка «совместимость интересов» (A2) — high-stakes, обязательна проверка человеком-медиатором перед использованием в переговорах.")
    if a.goal == "changereadiness":
        caveats.append("Change readiness: гипотезы о скрытом личном интересе (A1) НЕЛЬЗЯ передавать респондентам без анонимизации и нельзя использовать как единственное основание кадровых решений без проверки человеком.")

    plan = {
        "goal": a.goal, "respondent": a.respondent, "n_interviews": a.n,
        "lens": lens, "output": out_file, "output_kind": out_key,
        "can_synthesize_patterns": can_synthesize, "k_triangulation": K,
        "pipeline": steps,
        "caveats": caveats,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
