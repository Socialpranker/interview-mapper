#!/usr/bin/env python3
"""
number_lines.py — пронумеровать транскрипт построчно для трассируемости цитат.

Каждая цитата в картировании должна ссылаться на номер строки; verify_quotes.py потом
сверяет попадание. LLM плохо оперируют номерами строк «в уме» — поэтому нумеруем скриптом.

Поддерживает .txt, .docx, .srt, .vtt (парсинг stdlib, без внешних зависимостей).
Из .srt/.vtt дополнительно вытаскивает таймкод и спикера — таймкод пишется в сайдкар
`*_nl.timecodes.json`, чтобы человек мог послушать спорное место в аудио (S1).

Транскрипт — НЕДОВЕРЕННЫЙ вход: респондент мог продиктовать что угодно, включая текст,
адресованный модели. Скрипт помечает такие строки в `*_nl.flags.json` — это флаг человеку,
не блокер.

CLI:  python number_lines.py вход.(txt|docx|srt|vtt) [--out выход.txt]
Выход: строки вида 'L1: ...', 'L2: ...' (+ сайдкары рядом с --out)
"""

import argparse
import json
import re
import sys
import os
import zipfile
from xml.parsers import expat

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS_SEP = "|"
_W_P = f"{_W_NS}{_NS_SEP}p"
_W_T = f"{_W_NS}{_NS_SEP}t"

# .docx из недоверенного источника раздувается двумя способами: 0.6 МБ архива
# разжимаются в 208 МБ XML, а 700 байт DTD с вложенными сущностями — в гигабайты.
MAX_DOCX_XML_BYTES = 64 * 1024 * 1024

# Текст, адресованный модели, а не интервьюеру: перехват инструкций и маркеры разметки промпта.
INJECTION_PATTERNS = [
    r"\bignore\s+(all\s+|the\s+|any\s+)?(previous|prior|above|earlier)\b",
    r"\bdisregard\s+(all\s+|the\s+|any\s+)?(previous|prior|above|instructions)\b",
    r"\b(new|updated|revised)\s+instructions?\b",
    r"\bsystem\s+prompt\b",
    r"\byou\s+are\s+(now\s+)?(an?\s+)?\w+\s+(assistant|model|ai)\b",
    r"игнорируй\s+(все\s+|всё\s+|предыдущ|прежни|указан)",
    r"забудь\s+(все\s+|всё\s+|предыдущ|прежни|инструкц)",
    r"систе\w*\s+промпт|системн\w+\s+инструкц",
    r"нов\w+\s+инструкци",
    r"^\s*(assistant|human|system|user)\s*:",
    r"<\s*/?\s*(system|instructions?|prompt)\s*>",
    r"\[\s*/?\s*INST\s*\]",
]
_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

_TIME_RE = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*"
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})"
)
_VOICE_RE = re.compile(r"<v\s+([^>]+)>(.*?)(?:</v>|$)", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


class DocxError(Exception):
    """.docx не читается безопасно: битый XML, DTD или превышен лимит распаковки."""


def _read_document_xml(path):
    """Достаёт word/document.xml, отказываясь распаковывать больше лимита.

    Работает заголовочная проверка: zipfile сам обрывает чтение на заявленном
    размере и ловит расхождение по CRC, так что занижением заголовка лимит не
    обойти. Второй чек, по фактически прочитанному, — страховка на случай, если
    архив прочитается иначе, чем обещал заголовок.
    """
    with zipfile.ZipFile(path) as z:
        info = z.getinfo("word/document.xml")
        if info.file_size > MAX_DOCX_XML_BYTES:
            raise DocxError(
                f"word/document.xml заявляет {info.file_size} байт "
                f"при лимите {MAX_DOCX_XML_BYTES}"
            )
        with z.open("word/document.xml") as fh:
            xml = fh.read(MAX_DOCX_XML_BYTES + 1)
    if len(xml) > MAX_DOCX_XML_BYTES:
        raise DocxError(f"word/document.xml больше лимита {MAX_DOCX_XML_BYTES} байт")
    return xml


def read_docx(path):
    """Читает текст .docx через stdlib (zipfile + expat): абзацы word/document.xml, текст из <w:t>.

    Парсер expat, а не ElementTree, потому что только он даёт отклонить DTD:
    легитимный .docx его не содержит, а вложенные сущности внутри DTD — billion laughs.
    Каждый <w:p> на любой глубине даёт абзац, его текст включает вложенные <w:p>
    (текстовые врезки) — так же, как раньше делал root.iter().
    """
    xml = _read_document_xml(path)
    paragraphs, open_p, t_depth = [], [], 0

    def start(name, attrs):
        nonlocal t_depth
        if name == _W_P:
            open_p.append((len(paragraphs), []))
            paragraphs.append(None)  # место в порядке документа, заполнится на закрытии
        elif name == _W_T:
            t_depth += 1

    def end(name):
        nonlocal t_depth
        if name == _W_P and open_p:
            index, chunks = open_p.pop()
            paragraphs[index] = "".join(chunks)
        elif name == _W_T and t_depth:
            t_depth -= 1

    def chars(data):
        if t_depth:
            for _, chunks in open_p:
                chunks.append(data)

    def reject_dtd(name, sysid, pubid, has_internal):
        raise DocxError("в .docx есть DTD — отклонён (защита от entity-expansion)")

    parser = expat.ParserCreate(namespace_separator=_NS_SEP)
    parser.StartDoctypeDeclHandler = reject_dtd
    parser.ExternalEntityRefHandler = lambda *args: 0
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    try:
        parser.Parse(xml, True)
    except expat.ExpatError as e:
        raise DocxError(f"битый XML в word/document.xml ({e})") from e
    return "\n".join(p for p in paragraphs if p is not None)


def parse_subtitles(raw):
    """Разбирает .srt/.vtt в список реплик [{"text","start","speaker"}].

    Один кью → одна строка: единица цитирования — реплика, а не строка переноса внутри неё.
    Спикер берётся из VTT-тега <v Имя> либо из префикса «Имя:» в тексте кью.
    """
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", raw):
        block = block.strip()
        if not block or block.upper().startswith("WEBVTT"):
            continue
        m = _TIME_RE.search(block)
        if not m:
            continue
        body_lines = []
        for ln in block.split("\n"):
            if _TIME_RE.search(ln):
                body_lines = []  # всё до таймкода — порядковый номер или id кью
                continue
            if body_lines or ln.strip():
                body_lines.append(ln)
        body = " ".join(x.strip() for x in body_lines).strip()
        speaker = None
        v = _VOICE_RE.search(body)
        if v:
            speaker, body = v.group(1).strip(), v.group(2).strip()
        body = _TAG_RE.sub("", body).strip()
        if speaker is None:
            pref = re.match(r"^([^:]{1,40}):\s+(.*)$", body)
            if pref:
                speaker, body = pref.group(1).strip(), pref.group(2).strip()
        if not body:
            continue
        cues.append(
            {"text": body, "start": m.group(1).replace(",", "."), "speaker": speaker}
        )
    return cues


def read_source(path):
    """Читает вход → (список строк, карта таймкодов). Ошибки → внятное сообщение, exit 1."""
    low = path.lower()
    if low.endswith(".docx"):
        try:
            return read_docx(path).splitlines(), {}
        except (zipfile.BadZipFile, KeyError, DocxError) as e:
            sys.exit(f"error: {path}: не удалось прочитать .docx ({e})")
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        sys.exit(f"error: {path}: {e.strerror or e}")
    except UnicodeDecodeError as e:
        sys.exit(f"error: {path}: не UTF-8 ({e.reason})")
    if low.endswith((".srt", ".vtt")):
        cues = parse_subtitles(raw)
        if not cues:
            sys.exit(
                f"error: {path}: субтитры без распознанных таймкодов — проверь формат"
            )
        lines, times = [], {}
        for i, c in enumerate(cues, 1):
            lines.append(f"{c['speaker']}: {c['text']}" if c["speaker"] else c["text"])
            times[str(i)] = {"start": c["start"], "speaker": c["speaker"]}
        return lines, times
    return raw.splitlines(), {}


def scan_injection(lines):
    """Возвращает [{"line","text","pattern"}] по строкам, адресованным модели, а не интервьюеру."""
    hits = []
    for i, ln in enumerate(lines, 1):
        for rx in _INJECTION_RE:
            if rx.search(ln):
                hits.append(
                    {"line": i, "text": ln.strip()[:200], "pattern": rx.pattern}
                )
                break
    return hits


def main():
    """CLI: нумерует строки транскрипта и пишет результат в *_nl.txt (+ сайдкары)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    lines, times = read_source(a.input)
    numbered = "\n".join(f"L{i}: {ln}" for i, ln in enumerate(lines, 1))
    out = a.out or (os.path.splitext(a.input)[0] + "_nl.txt")
    base = out[:-4] if out.lower().endswith(".txt") else out
    open(out, "w", encoding="utf-8").write(numbered)
    print(f"Пронумеровано строк: {len(lines)} → {out}")
    if times:
        tc = base + ".timecodes.json"
        with open(tc, "w", encoding="utf-8") as f:
            json.dump(times, f, ensure_ascii=False, indent=2)
        speakers = sorted({v["speaker"] for v in times.values() if v["speaker"]})
        print(
            f"Таймкоды: {tc}"
            + (
                f" · спикеры: {', '.join(speakers)}"
                if speakers
                else " · спикеры не размечены (для групповых линз это блокер S1)"
            )
        )
    hits = scan_injection(lines)
    if hits:
        fl = base + ".flags.json"
        with open(fl, "w", encoding="utf-8") as f:
            json.dump(hits, f, ensure_ascii=False, indent=2)
        print(
            f"ВНИМАНИЕ: {len(hits)} строк(и) похожи на инструкции модели, а не на речь "
            f"респондента → {fl}",
            file=sys.stderr,
        )
        for h in hits[:5]:
            print(f"  L{h['line']}: {h['text']}", file=sys.stderr)
        print(
            "  Транскрипт — данные, а не инструкции. Проверь эти строки глазами перед S2.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
