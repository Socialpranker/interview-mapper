#!/usr/bin/env python3
"""
compare_to_gold.py — леса для human-in-the-loop сравнения «ИИ-картирование vs gold.md».

НЕ автоматический оценщик. Скрипт не ставит баллы и не судит расхождения — он
готовит бланк, куда человек ВСЛЕПУЮ проставляет балл покрытия (1-5) и код расхождения
([Ф]/[П]/[И]/[Р], см. references/rubric.md), сверяя формулировки, а не зная заранее,
где какой источник.

Парсинг gold.md — по заголовкам ячеек `### <код> — <название>` и блокам `Цитата: ... (строка N)`
внутри каждой ячейки. Формат читается «как есть»: gold.md остаётся обычным markdown,
не переписывается в отдельный JSON-формат.

AI-картирование подаётся тем же способом: markdown-файл с теми же заголовками ячеек
`### <код> — <название>`, полученный реальным прогоном пайплайна скилла (S1→S4) на том
же transcript.txt, каким пользуется скилл. Этот скрипт LLM не вызывает.

CLI:
  python compare_to_gold.py --gold gold.md --ai ai_mapping.md [--lens templates/candidate.md] [--out review.md]
"""
import argparse, re, sys

CELL_HEADER_RE = re.compile(r"^###\s+(?P<code>\S+)\s+—\s+(?P<title>.+?)\s*$", re.MULTILINE)
SECTION_HEADER_RE = re.compile(r"^##\s+(?!#).+$", re.MULTILINE)


def _read_text(path):
    """Читает текстовый файл или завершает работу с внятной ошибкой."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        sys.exit(f"error: {path}: {e.strerror or e}")
    except UnicodeDecodeError as e:
        sys.exit(f"error: {path}: не UTF-8 ({e.reason})")


def parse_cells(text):
    """Режет markdown-картирование на ячейки по заголовкам `### <код> — <название>`.

    Возвращает список (code, title, body) в порядке появления в тексте.
    body — сырой текст ячейки между её заголовком и следующим `###` (или концом файла/
    следующего `##`-раздела).
    """
    headers = list(CELL_HEADER_RE.finditer(text))
    sections = [m.start() for m in SECTION_HEADER_RE.finditer(text)]
    cells = []
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        next_section = next((s for s in sections if s > start and s < end), None)
        if next_section is not None:
            end = next_section
        body = text[start:end].strip("\n")
        cells.append((m.group("code"), m.group("title").strip(), body))
    return cells


def lens_cell_order(lens_text):
    """Извлекает порядок и названия ячеек из шаблона линзы (templates/<линза>.md), если задан.

    Строки шаблона вида `- **K1 Название** — описание`. Используется только для сортировки/
    сверки полноты набора ячеек — не обязателен для построения бланка.
    """
    order = []
    for m in re.finditer(r"^\s*-\s+\*\*(?P<code>\S+)\s+(?P<title>[^*]+?)\*\*", lens_text, re.MULTILINE):
        order.append((m.group("code"), m.group("title").strip()))
    return order


def render_review(gold_cells, ai_cells, lens_order=None):
    """Строит markdown-бланк: по каждой ячейке gold-версия и ИИ-версия рядом + пустые поля для человека."""
    ai_by_code = {code: (title, body) for code, title, body in ai_cells}
    gold_codes = [code for code, _, _ in gold_cells]

    order = gold_codes
    if lens_order:
        lens_codes = [code for code, _ in lens_order]
        order = [c for c in lens_codes if c in gold_codes] + [c for c in gold_codes if c not in lens_codes]

    gold_by_code = {code: (title, body) for code, title, body in gold_cells}

    lines = ["# Human↔AI review blank", ""]
    missing_in_ai = [c for c in order if c not in ai_by_code]
    if missing_in_ai:
        lines.append(f"**Внимание:** нет в ИИ-картировании: {', '.join(missing_in_ai)}")
        lines.append("")

    for code in order:
        gold_title, gold_body = gold_by_code[code]
        lines.append(f"## {code} — {gold_title}")
        lines.append("")
        lines.append("### Gold")
        lines.append(gold_body if gold_body else "_(пусто)_")
        lines.append("")
        lines.append("### AI")
        if code in ai_by_code:
            _, ai_body = ai_by_code[code]
            lines.append(ai_body if ai_body else "_(пусто)_")
        else:
            lines.append("_(ячейка отсутствует в ИИ-картировании)_")
        lines.append("")
        lines.append("Балл покрытия (1-5): ___")
        lines.append("Код расхождения (если есть): ___")
        lines.append("")
        lines.append("---")
        lines.append("")

    extra_in_ai = [code for code, _, _ in ai_cells if code not in gold_by_code]
    if extra_in_ai:
        lines.append(f"**Есть в ИИ, нет в gold:** {', '.join(extra_in_ai)}")
        lines.append("")

    return "\n".join(lines)


def main():
    """CLI: строит human↔AI review-бланк из gold.md и ИИ-картирования той же линзы."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", help="transcript.txt фикстуры (для справки в шапке бланка)")
    ap.add_argument("--gold", required=True, help="gold.md фикстуры")
    ap.add_argument("--ai", required=True, help="ИИ-картирование той же линзы (markdown, те же заголовки ячеек)")
    ap.add_argument("--lens", help="templates/<линза>.md — опционально, для порядка ячеек")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    gold_text = _read_text(a.gold)
    ai_text = _read_text(a.ai)
    lens_order = lens_cell_order(_read_text(a.lens)) if a.lens else None

    gold_cells = parse_cells(gold_text)
    ai_cells = parse_cells(ai_text)
    if not gold_cells:
        sys.exit(f"error: {a.gold}: не найдено ни одной ячейки `### <код> — <название>`")

    out = render_review(gold_cells, ai_cells, lens_order)
    if a.transcript:
        out = f"**Транскрипт:** {a.transcript}\n\n" + out

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out)


if __name__ == "__main__":
    main()
