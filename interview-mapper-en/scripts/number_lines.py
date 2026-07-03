#!/usr/bin/env python3
"""
number_lines.py — number a transcript line by line for quote traceability.

Every quote in a mapping must reference a line number; verify_quotes.py then
checks the match. LLMs handle line numbers poorly «in their head» — so we number by script.

Supports .txt and .docx (if python-docx is installed; otherwise asks you to convert).

CLI:  python number_lines.py input.txt [--out output.txt]
Output: lines of the form 'L1: ...', 'L2: ...'
"""
import argparse, sys, os

def read_text(path):
    if path.lower().endswith(".docx"):
        try:
            import docx
        except Exception:
            sys.exit("python-docx is required for .docx: pip install python-docx --break-system-packages")
        return "\n".join(p.text for p in docx.Document(path).paragraphs)
    return open(path, encoding="utf-8").read()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    text = read_text(a.input)
    lines = [ln for ln in text.splitlines()]
    numbered = "\n".join(f"L{i}: {ln}" for i, ln in enumerate(lines, 1) if ln.strip() != "" or True)
    out = a.out or (os.path.splitext(a.input)[0] + "_nl.txt")
    open(out, "w", encoding="utf-8").write(numbered)
    print(f"Lines numbered: {len(lines)} → {out}")

if __name__ == "__main__":
    main()
