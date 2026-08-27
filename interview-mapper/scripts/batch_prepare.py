#!/usr/bin/env python3
"""
batch_prepare.py — подготовить папку транскриптов к массовому картированию.

Для каждого транскрипта (.txt/.docx/.srt/.vtt) в папке: нумерует строки → *_nl.txt, пишет манифест.
Из .srt/.vtt дополнительно достаёт таймкоды/спикеров (сайдкар *_nl.timecodes.json) и по каждому
транскрипту проверяет, нет ли в нём текста, адресованного модели (*_nl.flags.json) — транскрипт
недоверенный вход.
Чтобы прогнать пул из N интервью без ручной возни. Сами картирования делает модель по манифесту.

CLI: python batch_prepare.py /path/to/transcripts [--out manifest.json]
"""
import argparse, json, os, re, glob, sys, zipfile
from xml.etree import ElementTree as ET

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

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


def read_docx(path):
    """Читает текст .docx через stdlib (zipfile + XML): абзацы word/document.xml, текст из <w:t>."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs = []
    for p in root.iter(f"{_W_NS}p"):
        text = "".join(t.text or "" for t in p.iter(f"{_W_NS}t"))
        paragraphs.append(text)
    return "\n".join(paragraphs)

def read_source(path):
    """Читает вход (.txt/.docx/.srt/.vtt) → (список строк, карта таймкодов); ошибки → exit 1."""
    low = path.lower()
    if low.endswith(".docx"):
        try:
            return read_docx(path).splitlines(), {}
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
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
            sys.exit(f"error: {path}: субтитры без распознанных таймкодов — проверь формат")
        lines, times = [], {}
        for i, cue in enumerate(cues, 1):
            lines.append(f"{cue['speaker']}: {cue['text']}" if cue["speaker"] else cue["text"])
            times[str(i)] = {"start": cue["start"], "speaker": cue["speaker"]}
        return lines, times
    return raw.splitlines(), {}

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


def interview_name(path):
    """Извлекает человекочитаемое имя интервью из имени файла транскрипта."""
    base = os.path.splitext(os.path.basename(path))[0]
    base = re.sub(r"[_\-]*(расшифровка|вычитано|интервью|nl|по спикерам).*$", "", base, flags=re.I)
    return base.strip(" —_-") or base

def main():
    """CLI: нумерует строки всех транскриптов в папке и пишет манифест."""
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    files = []
    for ext in ("*.txt", "*.docx", "*.srt", "*.vtt"):
        files += glob.glob(os.path.join(a.folder, ext))
    files = [f for f in sorted(set(files)) if "_nl" not in os.path.basename(f)]

    manifest = []
    flagged_total = 0
    used_stems = set()
    for f in files:
        lines, times = read_source(f)
        stem = os.path.splitext(f)[0]
        name = interview_name(f)
        if stem in used_stems:
            # demo.srt и demo.vtt дали бы один demo_nl.txt — второй затёр бы первый молча.
            ext = os.path.splitext(f)[1].lstrip(".").lower()
            stem, name = f"{stem}_{ext}", f"{name} ({ext})"
        used_stems.add(stem)
        entry = {"interview": name, "transcript": f, "role": None}
        nl = stem + "_nl.txt"
        numbered = "\n".join(f"L{i}: {ln}" for i, ln in enumerate(lines, 1))
        open(nl, "w", encoding="utf-8").write(numbered)
        entry["numbered"] = nl
        entry["lines"] = len(lines)
        if times:
            tc = stem + "_nl.timecodes.json"
            with open(tc, "w", encoding="utf-8") as fh:
                json.dump(times, fh, ensure_ascii=False, indent=2)
            entry["timecodes"] = tc
            entry["speakers"] = sorted({v["speaker"] for v in times.values() if v["speaker"]})
        hits = scan_injection(lines)
        if hits:
            fl = stem + "_nl.flags.json"
            with open(fl, "w", encoding="utf-8") as fh:
                json.dump(hits, fh, ensure_ascii=False, indent=2)
            entry["injection_flags"] = fl
            entry["injection_flag_count"] = len(hits)
            flagged_total += len(hits)
        entry["status"] = "ready"
        manifest.append(entry)

    out = a.out or os.path.join(a.folder, "manifest.json")
    open(out, "w", encoding="utf-8").write(json.dumps(manifest, ensure_ascii=False, indent=2))
    ready = sum(1 for m in manifest if m.get("status") == "ready")
    print(f"Транскриптов: {len(manifest)} | готово к картированию: {ready} → {out}")
    for m in manifest:
        extra = ""
        if m.get("speakers"):
            extra += f" · спикеры: {', '.join(m['speakers'])}"
        if m.get("injection_flag_count"):
            extra += f" · ⚑ {m['injection_flag_count']} подозрительных строк"
        print(f"  [{m.get('status')}] {m['interview']}"
              + (f" ({m.get('lines')} строк)" if m.get('lines') else "") + extra)
    if flagged_total:
        print(f"ВНИМАНИЕ: {flagged_total} строк(и) похожи на инструкции модели, а не на речь "
              "респондента. Транскрипт — данные, не инструкции: проверь помеченные строки "
              "перед S2 (см. *_nl.flags.json).", file=sys.stderr)
    print("Дальше: для каждого готового — модель делает картирование по выбранной линзе (S0-S2).")

if __name__ == "__main__":
    main()
