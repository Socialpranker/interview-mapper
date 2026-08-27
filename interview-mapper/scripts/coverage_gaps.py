#!/usr/bin/env python3
"""
coverage_gaps.py — какие куски транскрипта не попали НИ В ОДНУ ячейку картирования.

Пропуски опаснее выдумок (omission 3.45% vs hallucination 1.47%, см. references/reliability.md),
но omission-check был единственным шагом пайплайна без инструмента: модель искала непокрытое
глазами по всему тексту — то есть тем же способом, каким его и пропустила.

Считает механически: берёт цитаты, которые verify_quotes подтвердил, находит их в тексте и
возвращает блоки реплик, которые не покрыла ни одна из них. Это не приговор («всё
непокрытое — пропуск»): интервьюер, приветствия и оффтоп в ячейку и не должны попадать.
Это список мест, где НАДО посмотреть глазами, отсортированный так, чтобы смотреть сверху.

Вход claims.json — тот же, что у verify_quotes (лучше `--emit-enriched` выход: там уже
проставлены статусы). Цитаты со статусом не verified в покрытие не идут: отклонённая цитата
ничего не подтверждает.

CLI:
  python coverage_gaps.py --transcript T_nl.txt --claims claims.json [--min-block 3]
                          [--skip-speaker "Интервьюер|Модератор"] [--out gaps.json]
"""

import argparse
import importlib.util
import json
import os
import re
import sys

_VQ_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_quotes.py")


def _load_verify_quotes():
    """Грузит соседний verify_quotes.py: нормализация и индекс строк должны быть ОДНИ и те же."""
    spec = importlib.util.spec_from_file_location("_vq_for_coverage_gaps", _VQ_PATH)
    if spec is None or spec.loader is None:
        sys.exit(f"error: не найден {_VQ_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_text(path):
    """Читает текстовый файл или завершает работу с внятной ошибкой."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        sys.exit(f"error: {path}: {e.strerror or e}")
    except UnicodeDecodeError as e:
        sys.exit(f"error: {path}: не UTF-8 ({e.reason})")


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
        sys.exit(
            f"error: {path}: invalid JSON — строка {e.lineno}, колонка {e.colno} ({e.msg})"
        )


def covered_lines(vq, claims, norm_full, index, threshold=88.0, min_cov=0.6):
    """Множество номеров строк, покрытых подтверждёнными цитатами.

    Fuzzy-совпадение засчитывается по тем же порогам, что и в verify_quotes: без них любая
    выдумка «покрывала» бы случайные строки и маскировала ровно тот пропуск, который ищем.
    """
    covered, unlocated = set(), []
    for c in claims:
        status = str(c.get("status") or c.get("verify_status") or "").lower()
        if status and not status.startswith("verified"):
            continue  # отклонённая цитата ничего не подтверждает
        qn = vq.normalize(c.get("quote") or "")
        if not qn:
            continue
        pos = norm_full.find(qn)
        span = len(qn)
        if pos == -1:
            score, matched = vq.fuzzy_score(qn, norm_full)
            cov = vq.lcs_coverage(qn, matched) if matched else 0.0
            if score < threshold or cov < min_cov:
                matched = ""
            pos = norm_full.find(matched) if matched else -1
            span = len(matched) if matched else 0
        if pos == -1:
            unlocated.append(c.get("cell"))
            continue
        for p in range(pos, pos + max(span, 1)):
            ln = vq.locate_line(p, index)
            if ln is not None:
                covered.add(ln)
    return covered, unlocated


def find_gaps(lines, covered, min_block, skip_re):
    """Блоки непокрытых реплик длиной >= min_block, от самого длинного к короткому.

    Блок рвёт только ПОКРЫТАЯ строка. Пустые строки и реплики интервьюера в блок не входят,
    но и не разрывают его: в диалоге ответы респондента идут через одну, и если считать
    интервьюера разрывом, блок физически не бывает длиннее одной строки — счётчик всегда ноль.
    """
    gaps, current = [], []
    for ln, txt in lines:
        if ln in covered:
            if len(current) >= min_block:
                gaps.append(current)
            current = []
            continue
        if not txt.strip() or (skip_re and skip_re.search(txt)):
            continue
        current.append((ln, txt))
    if len(current) >= min_block:
        gaps.append(current)
    gaps.sort(key=len, reverse=True)
    return gaps


def main():
    """CLI: считает непокрытые блоки транскрипта и печатает их сверху вниз по величине."""
    ap = argparse.ArgumentParser(
        description="Найти куски транскрипта, не покрытые ни одной подтверждённой цитатой."
    )
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--claims", required=True)
    ap.add_argument(
        "--min-block",
        type=int,
        default=3,
        help="Минимум непокрытых реплик подряд, чтобы считать это пропуском",
    )
    ap.add_argument(
        "--skip-speaker",
        default=None,
        help="Regex реплик, которые в ячейку и не должны попадать (напр. 'Интервьюер|Модератор')",
    )
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    vq = _load_verify_quotes()
    lines = vq.parse_lines(_read_text(a.transcript))
    if not lines:
        sys.exit(f"error: {a.transcript}: пустой транскрипт")
    norm_full, index = vq.build_index(lines)
    claims = _read_json(a.claims)
    skip_re = re.compile(a.skip_speaker, re.IGNORECASE) if a.skip_speaker else None

    covered, unlocated = covered_lines(vq, claims, norm_full, index)
    gaps = find_gaps(lines, covered, a.min_block, skip_re)

    total = len(lines)
    gap_lines = sum(len(g) for g in gaps)
    out = {
        "summary": {
            "transcript_lines": total,
            "covered_lines": len(covered),
            "coverage_share": round(len(covered) / total, 3) if total else 0.0,
            "gap_blocks": len(gaps),
            "gap_lines": gap_lines,
            "unlocated_claims": unlocated,
            "note": (
                "Непокрытый блок — не приговор, а место, куда надо посмотреть глазами: "
                "оффтоп и реплики интервьюера в ячейку и не должны попадать (--skip-speaker). "
                "Пропуск опаснее выдумки: выдумку ловит verify_quotes, пропуск — только этот шаг. "
                "unlocated_claims — цитаты, которых нет в этом транскрипте: не то интервью или "
                "текст подменили после картирования (напр. обезличили — см. references/ethics.md)."
            ),
        },
        "gaps": [
            {
                "from_line": g[0][0],
                "to_line": g[-1][0],
                "lines": len(g),
                "text": " ".join(t for _, t in g)[:400],
            }
            for g in gaps
        ],
    }
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)


if __name__ == "__main__":
    main()
