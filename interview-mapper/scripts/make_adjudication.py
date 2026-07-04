#!/usr/bin/env python3
"""
make_adjudication.py — карточки для человека по спорным ячейкам (из consensus.py).

Совет не решает спорное сам — он флагует. Этот скрипт готовит человеку удобную развилку:
по каждой флагнутой ячейке показывает варианты РАЗНЫХ прогонов бок о бок, чтобы человек выбрал вслепую.

Вход: выход consensus.py + те же run*.json.
Выход: adjudication.md (человеку) + adjudication.json.

CLI: python make_adjudication.py consensus.json run1.json run2.json [run3.json ...] [--out adjudication.md]
"""
import argparse, json, re, sys


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


def load_run(path):
    """Загружает один прогон картирования (json) в вид {cell: {label, text}}."""
    d = _read_json(path)
    out = {}
    for cell, v in d.items():
        out[cell] = v if isinstance(v, dict) else {"label": None, "text": str(v)}
    return out

def main():
    """CLI: готовит карточки адъюдикации по флагнутым ячейкам из consensus.py."""
    ap = argparse.ArgumentParser()
    ap.add_argument("consensus")
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", default="adjudication.md")
    a = ap.parse_args()

    cons = _read_json(a.consensus)
    flagged = cons.get("summary", {}).get("flagged", [])
    runs = [load_run(p) for p in a.runs]

    md = ["# Адъюдикация спорных ячеек (решает человек, вслепую)\n",
          f"Флагнуто советом: {len(flagged)}. По каждой — варианты прогонов. Выбери или напиши свой.\n"]
    cards = []
    for cell in flagged:
        md.append(f"\n## {cell}\n")
        info = cons.get("cells", {}).get(cell, {})
        if "labels" in info:
            md.append(f"_Ярлыки прогонов: {info.get('labels')} · согласие: {info.get('agreement')}_\n")
        options = []
        for i, r in enumerate(runs, 1):
            e = r.get(cell, {})
            lab = e.get("label")
            txt = (e.get("text") or "").strip()
            md.append(f"- **Вариант {i}**" + (f" [{lab}]" if lab else "") + f": {txt}")
            options.append({"run": i, "label": lab, "text": txt})
        md.append("\n**Решение человека:** _______  · **Почему:** _______\n")
        cards.append({"cell": cell, "options": options, "decision": None, "rationale": None})

    open(a.out, "w", encoding="utf-8").write("\n".join(md))
    open(re.sub(r"\.md$", ".json", a.out), "w", encoding="utf-8").write(
        json.dumps({"cards": cards}, ensure_ascii=False, indent=2))
    print(f"Карточек адъюдикации: {len(cards)} → {a.out}")

if __name__ == "__main__":
    main()
