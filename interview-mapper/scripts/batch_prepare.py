#!/usr/bin/env python3
"""
batch_prepare.py — подготовить папку транскриптов к массовому картированию.

Для каждого транскрипта (.txt/.docx) в папке: нумерует строки → *_nl.txt, пишет манифест.
Чтобы прогнать пул из N интервью без ручной возни. Сами картирования делает модель по манифесту.

CLI: python batch_prepare.py /path/to/transcripts [--out manifest.json]
"""
import argparse, json, os, re, glob, sys, zipfile
from xml.etree import ElementTree as ET

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

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

def read_text(path):
    """Читает .txt или .docx (парсинг stdlib); OSError → внятная ошибка, exit 1."""
    if path.lower().endswith(".docx"):
        try:
            return read_docx(path)
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
            sys.exit(f"error: {path}: не удалось прочитать .docx ({e})")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        sys.exit(f"error: {path}: {e.strerror or e}")
    except UnicodeDecodeError as e:
        sys.exit(f"error: {path}: не UTF-8 ({e.reason})")

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
    for ext in ("*.txt", "*.docx"):
        files += glob.glob(os.path.join(a.folder, ext))
    files = [f for f in sorted(set(files)) if "_nl" not in os.path.basename(f)]

    manifest = []
    for f in files:
        text = read_text(f)
        entry = {"interview": interview_name(f), "transcript": f, "role": None}
        nl = os.path.splitext(f)[0] + "_nl.txt"
        numbered = "\n".join(f"L{i}: {ln}" for i, ln in enumerate(text.splitlines(), 1))
        open(nl, "w", encoding="utf-8").write(numbered)
        entry["numbered"] = nl
        entry["lines"] = len(text.splitlines())
        entry["status"] = "ready"
        manifest.append(entry)

    out = a.out or os.path.join(a.folder, "manifest.json")
    open(out, "w", encoding="utf-8").write(json.dumps(manifest, ensure_ascii=False, indent=2))
    ready = sum(1 for m in manifest if m.get("status") == "ready")
    print(f"Транскриптов: {len(manifest)} | готово к картированию: {ready} → {out}")
    for m in manifest:
        print(f"  [{m.get('status')}] {m['interview']}"
              + (f" ({m.get('lines')} строк)" if m.get('lines') else ""))
    print("Дальше: для каждого готового — модель делает картирование по выбранной линзе (S0-S2).")

if __name__ == "__main__":
    main()
