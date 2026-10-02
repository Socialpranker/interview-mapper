#!/usr/bin/env python3
"""
make_adjudication.py — карточки для человека по спорным ячейкам (из consensus.py).

Совет не решает спорное сам — он флагует. Этот скрипт готовит человеку удобную развилку:
по каждой флагнутой ячейке показывает варианты РАЗНЫХ прогонов бок о бок, чтобы человек выбрал вслепую.

Карточки слепые: варианты перемешаны (отдельно на каждой карточке) и подписаны А/Б/В…, без номеров
прогонов, имён файлов, голосов и уровня согласия — иначе человек якорится на «за этот вариант проголосовало
больше прогонов». Соответствие буква → прогон лежит в отдельном ключе; открывай его только после решения.

Вход: выход consensus.py + те же run*.json.
Выход: adjudication.md (человеку) + adjudication.json + adjudication.key.json (ключ, НЕ показывать до решения).

CLI: python make_adjudication.py consensus.json run1.json run2.json [run3.json ...]
                                 [--out adjudication.md] [--seed N] [--key adjudication.key.json]
"""
import argparse, json, os, random, re, sys

LETTERS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЭЮЯ"


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
    ap.add_argument("--seed", type=int, default=None, help="Сид перемешивания вариантов (по умолчанию случайный)")
    ap.add_argument("--key", default=None, help="Куда писать ключ буква → прогон (по умолчанию <out>.key.json)")
    a = ap.parse_args()
    if len(a.runs) > len(LETTERS):
        sys.exit(f"error: слишком много прогонов ({len(a.runs)} > {len(LETTERS)})")
    seed = a.seed if a.seed is not None else random.SystemRandom().randrange(2**32)
    rng = random.Random(seed)
    key_path = a.key or os.path.splitext(a.out)[0] + ".key.json"

    cons = _read_json(a.consensus)
    flagged = cons.get("summary", {}).get("flagged", [])
    runs = [load_run(p) for p in a.runs]

    md = ["# Адъюдикация спорных ячеек (решает человек, вслепую)\n",
          f"Флагнуто советом: {len(flagged)}. По каждой — варианты. Выбери или напиши свой.\n"]
    cards = []
    key = {"seed": seed, "cells": {}}
    for cell in flagged:
        md.append(f"\n## {cell}\n")
        info = cons.get("cells", {}).get(cell, {})
        order = list(range(len(runs)))
        rng.shuffle(order)
        options, letters = [], {}
        # Labels stay off the options: identical labels on several options would reveal the vote split.
        candidates = sorted({runs[i].get(cell, {}).get("label") for i in order} - {None})
        if candidates:
            md.append(f"_Ярлыки-кандидаты (по алфавиту, без счёта голосов): {', '.join(candidates)}_\n")
        for pos, i in enumerate(order):
            letter = LETTERS[pos]
            e = runs[i].get(cell, {})
            lab = e.get("label")
            txt = (e.get("text") or "").strip()
            md.append(f"- **Вариант {letter}**: {txt}")
            options.append({"option": letter, "text": txt})
            letters[letter] = {"run": i + 1, "file": a.runs[i], "label": lab}
        md.append("\n**Решение человека:** _______  · **Почему:** _______\n")
        cards.append({"cell": cell, "options": options, "decision": None, "rationale": None})
        key["cells"][cell] = {"letters": letters,
                              **{k: info[k] for k in ("labels", "agreement", "label_share") if k in info}}

    open(a.out, "w", encoding="utf-8").write("\n".join(md))
    open(re.sub(r"\.md$", ".json", a.out), "w", encoding="utf-8").write(
        json.dumps({"cards": cards}, ensure_ascii=False, indent=2))
    open(key_path, "w", encoding="utf-8").write(json.dumps(key, ensure_ascii=False, indent=2))
    print(f"Карточек адъюдикации: {len(cards)} → {a.out}; ключ → {key_path} (открыть после решения)")

if __name__ == "__main__":
    main()
