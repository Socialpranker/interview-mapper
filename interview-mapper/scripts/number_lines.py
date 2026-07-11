#!/usr/bin/env python3
"""
number_lines.py — пронумеровать транскрипт построчно для трассируемости цитат.

Каждая цитата в картировании должна ссылаться на номер строки; verify_quotes.py потом
сверяет попадание. LLM плохо оперируют номерами строк «в уме» — поэтому нумеруем скриптом.

Поддерживает .txt и .docx (парсинг stdlib, без внешних зависимостей).

CLI:  python number_lines.py вход.txt [--out выход.txt]
Выход: строки вида 'L1: ...', 'L2: ...'
"""
import argparse, sys, os, zipfile
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
    """Читает .txt или .docx (парсинг stdlib); ошибки → внятное сообщение, exit 1."""
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

def main():
    """CLI: нумерует строки транскрипта и пишет результат в *_nl.txt."""
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    text = read_text(a.input)
    lines = text.splitlines()
    numbered = "\n".join(f"L{i}: {ln}" for i, ln in enumerate(lines, 1))
    out = a.out or (os.path.splitext(a.input)[0] + "_nl.txt")
    open(out, "w", encoding="utf-8").write(numbered)
    print(f"Пронумеровано строк: {len(lines)} → {out}")

if __name__ == "__main__":
    main()
