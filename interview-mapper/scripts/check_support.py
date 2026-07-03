#!/usr/bin/env python3
"""
check_support.py — учёт entailment: делает проверку «цитата ⊨ тезис» ОБЯЗАТЕЛЬНОЙ и логируемой.

Зачем: дословность != поддержка. Цитата может быть в источнике дословно, но вывод из неё не следовать
(ресёрч: система с идеальными цитатами дала 0.033 по entailment; до 57% цитат — post-rationalization).
Сейчас эту проверку модель делает «на глаз». Скрипт превращает её в аудируемый шаг:
модель для каждой цитаты выносит вердикт support ∈ {yes, partial, no} + why, а скрипт агрегирует,
СВЕРЯЕТ с дословностью и ловит опасный класс «verbatim, но НЕ поддерживает».

Вход support.json — claims с полями от verify_quotes (verify_status) и от модели (support, support_why):
  [{"cell":"А1","quote":"...","verify_status":"verified_exact","support":"yes","support_why":"..."}]

Второй судья: прогони entailment-вердикт ДВАЖДЫ независимо, подай оба файла (--second),
скрипт пометит расхождения судей → на человека.

CLI:
  python check_support.py support.json [--second support2.json] [--out support_report.json]
"""
import argparse, json, sys

VALID = {"yes", "partial", "no"}

def norm(s):
    return (str(s).strip().lower() if s is not None else "missing")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("support")
    ap.add_argument("--second", default=None, help="Второй независимый прогон вердиктов (для судьи-2)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    items = json.load(open(a.support, encoding="utf-8"))
    second = {}
    if a.second:
        for x in json.load(open(a.second, encoding="utf-8")):
            second[(x.get("cell"), x.get("quote"))] = norm(x.get("support"))

    rows, missing, unsupported, dangerous, judge_split = [], [], [], [], []
    for x in items:
        sup = norm(x.get("support"))
        vs = x.get("verify_status", "unknown")
        key = (x.get("cell"), x.get("quote"))
        rec = {"cell": x.get("cell"), "quote": (x.get("quote") or "")[:60],
               "verify_status": vs, "support": sup, "why": x.get("support_why", "")}
        if sup not in VALID:
            missing.append(x.get("cell")); rec["issue"] = "нет вердикта поддержки"
        if sup == "no":
            unsupported.append(x.get("cell"))
        # ОПАСНЫЙ класс: цитата дословная, но тезис ею не поддержан
        if vs.startswith("verified") and sup in ("no", "partial"):
            dangerous.append(x.get("cell"))
            rec["flag"] = "verbatim, но поддержка " + sup + " → тезис держится не на цитате"
        if a.second:
            s2 = second.get(key, "missing")
            rec["support_2"] = s2
            if s2 in VALID and sup in VALID and s2 != sup:
                judge_split.append(x.get("cell"))
                rec["judge_split"] = True
        rows.append(rec)

    n = len(rows)
    supported = sum(1 for r in rows if r["support"] == "yes")
    summary = {
        "total": n,
        "supported_yes": supported,
        "partial": sum(1 for r in rows if r["support"] == "partial"),
        "unsupported_no": len(unsupported),
        "missing_verdict": missing,
        "dangerous_verbatim_unsupported": dangerous,
        "judge_disagreements": judge_split,
        "supported_share": round(supported / n, 3) if n else 0.0,
        "note": ("dangerous = цитата дословная, но НЕ подтверждает тезис (главный скрытый риск). "
                 "judge_disagreements и missing_verdict → на человека. "
                 "Проверку поддержки нельзя пропускать: дословность её не заменяет."),
    }
    out = {"summary": summary, "results": rows}
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)

if __name__ == "__main__":
    main()
