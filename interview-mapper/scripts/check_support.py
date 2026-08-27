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

Второй судья задаёт ОБРАТНЫЙ вопрос, а не тот же самый. Повтор одного промпта одной моделью даёт
согласие с самим собой по цене двух прогонов: расхождения занижены, гейт выглядит рабочим и молчит.
Судья-1 спрашивает «поддерживает ли цитата тезис?», судья-2 — «покажи, что НЕ поддерживает».
Текст промпта для судьи-2: `--judge2-prompt`.

CLI:
  python check_support.py support.json [--second support2.json] [--out support_report.json]
  python check_support.py --judge2-prompt
"""
import argparse, json, sys

VALID = {"yes", "partial", "no"}

JUDGE2_PROMPT = """Ты судья-2 в проверке заземлённости. Судья-1 уже вынес вердикт; ты его НЕ видишь
и не повторяешь его работу.

Твоя задача — попытаться ОПРОВЕРГНУТЬ, что цитата поддерживает тезис. Для каждой пары
тезис↔цитата ищи основание сказать «нет»: цитата про смежное, но не про это; она подтверждает
часть тезиса, а обобщение сделано за респондента; вывод держится на знании о предметной области,
а не на словах в цитате; респондент говорит гипотетически, а тезис читает это как факт.

Не нашёл такого основания — только тогда ставь yes. Сомневаешься между partial и yes — ставь partial.
Задача не в том, чтобы согласиться, а в том, чтобы проверить на прочность.

Формат ответа — тот же support.json:
[{"cell":"А1","quote":"дословно","support":"yes|partial|no","support_why":"на чём держится вердикт"}]
"""


def _read_json(path):
    """Читает JSON-файл; битый JSON или отсутствие файла → внятная ошибка, exit 1."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        sys.exit(f"error: {path}: {e.strerror or e}")
    except UnicodeDecodeError as e:
        sys.exit(f"error: {path}: не UTF-8 ({e.reason})")
    except json.JSONDecodeError as e:
        sys.exit(f"error: {path}: invalid JSON — строка {e.lineno}, колонка {e.colno} ({e.msg})")


def norm(s):
    """Нормализует вердикт поддержки: строка в нижнем регистре или 'missing', если None."""
    return (str(s).strip().lower() if s is not None else "missing")

def main():
    """CLI: агрегирует вердикты поддержки, ловит опасный класс verbatim-но-не-поддерживает."""
    ap = argparse.ArgumentParser()
    ap.add_argument("support", nargs="?")
    ap.add_argument("--second", default=None, help="Второй независимый прогон вердиктов — по ОПРОВЕРГАЮЩЕМУ промпту (--judge2-prompt)")
    ap.add_argument("--judge2-prompt", action="store_true",
                    help="Напечатать промпт для судьи-2 и выйти")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if a.judge2_prompt:
        print(JUDGE2_PROMPT)
        return

    if not a.support:
        sys.exit("error: нужен support.json (или --judge2-prompt)")

    items = _read_json(a.support)
    second = {}
    if a.second:
        for x in _read_json(a.second):
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
    # Судьи с разными линзами на заметной выборке обязаны хоть где-то разойтись.
    suspicious = bool(a.second) and n >= 8 and not judge_split
    supported = sum(1 for r in rows if r["support"] == "yes")
    summary = {
        "total": n,
        "supported_yes": supported,
        "partial": sum(1 for r in rows if r["support"] == "partial"),
        "unsupported_no": len(unsupported),
        "missing_verdict": missing,
        "dangerous_verbatim_unsupported": dangerous,
        "judge_disagreements": judge_split,
        "judge_agreement_suspicious": suspicious,
        "supported_share": round(supported / n, 3) if n else 0.0,
        "note": ("dangerous = цитата дословная, но НЕ подтверждает тезис (главный скрытый риск). "
                 "judge_disagreements и missing_verdict → на человека. "
                 "judge_agreement_suspicious = судьи не разошлись НИ РАЗУ на заметной выборке: "
                 "скорее всего судья-2 повторил судью-1 вместо опровержения (--judge2-prompt). "
                 "Проверку поддержки нельзя пропускать: дословность её не заменяет."),
    }
    out = {"summary": summary, "results": rows}
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)

if __name__ == "__main__":
    main()
