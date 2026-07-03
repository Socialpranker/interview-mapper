#!/usr/bin/env python3
"""
number_lines.py — пронумеровать транскрипт построчно для трассируемости цитат.

Каждая цитата в картировании должна ссылаться на номер строки; verify_quotes.py потом
сверяет попадание. LLM плохо оперируют номерами строк «в уме» — поэтому нумеруем скриптом.

Поддерживает .txt и .docx (если установлен python-docx; иначе просит сконвертировать).

CLI:  python number_lines.py вход.txt [--out выход.txt]
Выход: строки вида 'L1: ...', 'L2: ...'
"""
import argparse, sys, os

def read_text(path):
    if path.lower().endswith(".docx"):
        try:
            import docx
        except Exception:
            sys.exit("Нужен python-docx для .docx: pip install python-docx --break-system-packages")
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
    print(f"Пронумеровано строк: {len(lines)} → {out}")

if __name__ == "__main__":
    main()
