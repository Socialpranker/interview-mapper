#!/usr/bin/env python3
"""
consensus.py — «совет надёжности» БЕЗ внешних API.

Берёт N независимых прогонов картирования одного интервью и по КАЖДОЙ ячейке решает:
стабильна (все согласны) или спорна (нужна человеческая адъюдикация — флаг).

Почему так: доказательная база (self-consistency ICLR'23; multi-agent debate ICML'24;
LLM-judge flip-rate до 56%) говорит — верные выводы сходятся между прогонами, ошибки рассеяны;
одиночный авто-судья ненадёжен. Поэтому: авто-консенсус там, где согласие, и ФЛАГ ЧЕЛОВЕКУ там,
где прогоны разошлись. Модель не выбирает победителя молча.

Для ячеек с ярлыком (eNPS: ПРОМОУТЕР/НЕЙТРАЛ/ДЕТРАКТОР и т.п.) — голосование по ярлыку.
Для свободного текста — стабильность через попарную близость (difflib, stdlib).
Вес прогона можно задать по доле валидных цитат (из verify_quotes.py) — плохие прогоны весят меньше.

CLI:
  python consensus.py run1.json run2.json run3.json
       [--weights 1.0,0.8,1.0] [--stability 0.55] [--out consensus.json]

Формат прогона (json):
  { "К1": {"label": null, "text": "..."},
    "А1": {"label": "НЕЙТРАЛ", "text": "..."}, ... }
  Допускается и плоское { "К1": "текст", ... } — тогда label=None.
"""
import argparse, json, re, sys
from difflib import SequenceMatcher
from collections import Counter

LABELS = {  # известные словари ярлыков для нормализации голосования
    "enps": {"промоутер", "нейтрал", "детрактор", "promoter", "neutral", "detractor"},
}


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


def norm_label(s):
    """Нормализует ярлык: нижний регистр, первое слово, без пунктуации."""
    if not s:
        return None
    t = re.sub(r"[^\wа-яё]+", " ", str(s).lower()).strip()
    t = t.split()[0] if t else None
    return t

def load_run(path):
    """Загружает один прогон картирования (json) в вид {cell: {label, text}}."""
    d = _read_json(path)
    out = {}
    for cell, v in d.items():
        if isinstance(v, dict):
            out[cell] = {"label": norm_label(v.get("label")), "text": v.get("text", "") or ""}
        else:
            out[cell] = {"label": None, "text": str(v)}
    return out

def text_stability(texts):
    """Средняя попарная близость текстов (0..1). 1 = идентичны."""
    texts = [t for t in texts if t.strip()]
    if len(texts) < 2:
        return 1.0 if texts else 0.0
    sims, n = [], len(texts)
    for i in range(n):
        for j in range(i + 1, n):
            sims.append(SequenceMatcher(None, texts[i], texts[j]).ratio())
    return sum(sims) / len(sims) if sims else 1.0

def weighted_vote(labels, weights):
    """Взвешенное голосование по ярлыкам: возвращает (ярлык-победитель, степень согласия, доля)."""
    tally = Counter()
    for lab, w in zip(labels, weights):
        if lab:
            tally[lab] += w
    if not tally:
        return None, "n/a", 0.0
    top, top_w = tally.most_common(1)[0]
    total = sum(tally.values())
    share = top_w / total if total else 0.0
    distinct = len([l for l in labels if l])
    unique = len(set(l for l in labels if l))
    if unique <= 1:
        agree = "unanimous"
    elif share >= 0.5:
        agree = "majority"
    else:
        agree = "split"
    return top, agree, round(share, 2)

def main():
    """CLI: сравнивает N прогонов картирования и флагует расходящиеся ячейки человеку."""
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="JSON-файлы прогонов (>=2)")
    ap.add_argument("--weights", default=None, help="через запятую, по числу прогонов")
    ap.add_argument("--text-floor", type=float, default=0.35,
                    help="Жёсткий пол текстовой близости для БЕЗ-ярлычных ячеек: ниже = содержание "
                         "существенно разошлось → флаг. Разные формулировки при том же смысле сюда НЕ попадают.")
    ap.add_argument("--stability", type=float, default=None, help="deprecated alias of --text-floor")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    runs = [load_run(p) for p in a.runs]
    N = len(runs)
    if N < 2:
        print("Нужно >=2 прогонов для консенсуса.", file=sys.stderr); sys.exit(1)
    weights = [1.0] * N
    if a.weights:
        weights = [float(x) for x in a.weights.split(",")]
        assert len(weights) == N, "weights должно совпадать с числом прогонов"

    cells = []
    for r in runs:
        for c in r:
            if c not in cells:
                cells.append(c)

    text_floor = a.stability if a.stability is not None else a.text_floor
    report = {}
    flags = []
    low_stab = []
    for cell in cells:
        entries = [r.get(cell, {"label": None, "text": ""}) for r in runs]
        labels = [e["label"] for e in entries]
        texts = [e["text"] for e in entries]
        has_labels = any(labels)
        stab = text_stability(texts)
        rec = {"stability": round(stab, 2)}
        flag = False
        if has_labels:
            lab, agree, share = weighted_vote(labels, weights)
            rec.update({"label_consensus": lab, "agreement": agree, "label_share": share,
                        "labels": labels})
            # Аналитический ярлык (eNPS и т.п.) субъективен и нестабилен между прогонами.
            # Любое разногласие ярлыка → человек решает. Согласие по сути при разной формулировке — не флаг.
            if agree != "unanimous":
                flag = True
        else:
            # без ярлыка: флаг лишь при СУЩЕСТВЕННОМ расхождении содержания
            if stab < text_floor:
                flag = True
                rec["reason_content_divergence"] = True
        if stab < 0.5:
            low_stab.append(cell)  # мягкая подсказка «формулировки разошлись», не жёсткий флаг
        rec["flag_for_human"] = flag
        if flag:
            flags.append(cell)
        report[cell] = rec

    summary = {
        "runs": N,
        "weights": weights,
        "cells_total": len(cells),
        "cells_flagged": len(flags),
        "flagged": flags,
        "low_stability_hint": low_stab,
        "note": "flagged = разногласие по существу → человек адъюдицирует вслепую. "
                "low_stability_hint = согласие по сути, но разные формулировки (мягко, можно игнорировать).",
    }
    out = {"summary": summary, "cells": report}
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)

if __name__ == "__main__":
    main()
