#!/usr/bin/env python3
"""
number_lines.py — number a transcript line by line for quote traceability.

Every quote in a mapping must reference a line number; verify_quotes.py then
checks the match. LLMs handle line numbers poorly «in their head» — so we number by script.

Supports .txt and .docx (stdlib parsing, no external dependencies).

CLI:  python number_lines.py input.txt [--out output.txt]
Output: lines of the form 'L1: ...', 'L2: ...'
"""
import argparse, sys, os, zipfile
from xml.etree import ElementTree as ET

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def read_docx(path):
    """Reads .docx text via stdlib (zipfile + XML): paragraphs from word/document.xml, text from <w:t>."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs = []
    for p in root.iter(f"{_W_NS}p"):
        text = "".join(t.text or "" for t in p.iter(f"{_W_NS}t"))
        paragraphs.append(text)
    return "\n".join(paragraphs)

def read_text(path):
    """Reads .txt or .docx (stdlib parsing); errors → a clear message, exit 1."""
    if path.lower().endswith(".docx"):
        try:
            return read_docx(path)
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
            sys.exit(f"error: {path}: failed to read .docx ({e})")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        sys.exit(f"error: {path}: {e.strerror or e}")
    except UnicodeDecodeError as e:
        sys.exit(f"error: {path}: not UTF-8 ({e.reason})")

def main():
    """CLI: numbers the transcript's lines and writes the result to *_nl.txt."""
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    text = read_text(a.input)
    lines = text.splitlines()
    numbered = "\n".join(f"L{i}: {ln}" for i, ln in enumerate(lines, 1))
    out = a.out or (os.path.splitext(a.input)[0] + "_nl.txt")
    open(out, "w", encoding="utf-8").write(numbered)
    print(f"Lines numbered: {len(lines)} → {out}")

if __name__ == "__main__":
    main()
