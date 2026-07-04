#!/usr/bin/env python3
"""
extract_claims.py — вытащить цитаты из готового картирования (.md) в claims.json.

Убирает ручную клейку: парсит наш формат картирования и собирает список цитат для verify_quotes.py.
Распознаёт:
  - заголовки ячеек: **К5 | Системы...**, **А1 | eNPS...**, ### СЛОЙ ...
  - цитаты в «ёлочках»: «...» (в любых строках, чаще в _курсивных_ «Цитата: «...»» или _«...» (L61)_)
  - опциональный номер строки в цитате: (L61) / (61)

Номер строки НЕ обязателен — verify_quotes сам найдёт (см. --emit-enriched).

CLI: python extract_claims.py mapping.md [--interview "Дарья"] [--role "операции"] [--out claims.json]
"""
import argparse, json, re, sys

# Ловит коды: С3.2, С2.П (ВМДИ), а также К5/К10, А1, J1, C1, E1
CELL_RE = re.compile(r"\*\*\s*([A-Za-zА-Яа-я]{1,2}\d{1,2}(?:\.[\wА-Яа-я]+)?)\s*[|｜]\s*([^*]+)\*\*")
QUOTE_RE = re.compile(r"«([^»]{4,})»")
LINE_RE = re.compile(r"\(L?(\d{1,4})\)")


def _read_text(path):
    """Читает текстовый файл или завершает работу с внятной ошибкой."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        sys.exit(f"error: {path}: {e.strerror or e}")
    except UnicodeDecodeError as e:
        sys.exit(f"error: {path}: не UTF-8 ({e.reason})")


def main():
    """CLI: парсит .md-картирование и извлекает список цитат в claims.json."""
    ap = argparse.ArgumentParser()
    ap.add_argument("mapping")
    ap.add_argument("--interview", default=None)
    ap.add_argument("--role", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    text = _read_text(a.mapping)
    lines = text.splitlines()
    cur_cell, cur_title, cur_claimtext = None, None, ""
    claims = []
    for ln in lines:
        mcell = CELL_RE.search(ln)
        if mcell:
            cur_cell = mcell.group(1).strip()
            cur_title = mcell.group(2).strip()
            cur_claimtext = ""
            continue
        # накапливаем текст ячейки как «тезис» (без цитатных строк)
        if cur_cell and "«" not in ln and ln.strip() and not ln.startswith(("#", "---", "**", "_Цитата")):
            if len(cur_claimtext) < 160:
                cur_claimtext = (cur_claimtext + " " + ln.strip()).strip()
        for mq in QUOTE_RE.finditer(ln):
            quote = mq.group(1).strip()
            mline = LINE_RE.search(ln)
            claim = {"cell": cur_cell or "?", "title": cur_title or "",
                     "claim": cur_claimtext[:160], "quote": quote}
            if mline:
                claim["line"] = int(mline.group(1))
            if a.interview:
                claim["interview"] = a.interview
            if a.role:
                claim["role"] = a.role
            claims.append(claim)

    out = a.out or (re.sub(r"\.md$", "", a.mapping) + "_claims.json")
    open(out, "w", encoding="utf-8").write(json.dumps(claims, ensure_ascii=False, indent=2))
    print(f"Извлечено цитат: {len(claims)} из {a.mapping} → {out}")
    # краткая сводка по ячейкам
    from collections import Counter
    c = Counter(x["cell"] for x in claims)
    print("по ячейкам:", dict(c))

if __name__ == "__main__":
    main()
