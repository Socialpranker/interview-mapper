#!/usr/bin/env python3
"""
make_adjudication.py — cards for a human on contested cells (from consensus.py).

The council doesn't resolve contested cells itself — it flags them. This script prepares a convenient fork for the human:
for each flagged cell it shows the options from DIFFERENT runs side by side, so the human chooses blind.

The cards are blind: options are shuffled (separately on each card) and labelled A/B/C…, with no run
numbers, file names, votes or agreement level — otherwise the human anchors on "more runs backed this one".
The letter → run mapping lives in a separate key; open it only after the decision.

Input: output of consensus.py + the same run*.json.
Output: adjudication.md (for the human) + adjudication.json + adjudication.key.json (the key, do NOT show before the decision).

CLI: python make_adjudication.py consensus.json run1.json run2.json [run3.json ...]
                                 [--out adjudication.md] [--seed N] [--key adjudication.key.json]
"""
import argparse, json, os, random, re, string, sys

LETTERS = string.ascii_uppercase


def _read_json(path):
    """Read a JSON file; broken JSON or a missing file → a clear error, exit 1."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        sys.exit(f"error: {path}: {e.strerror or e}")
    except UnicodeDecodeError as e:
        sys.exit(f"error: {path}: not UTF-8 ({e.reason})")
    except json.JSONDecodeError as e:
        sys.exit(f"error: {path}: invalid JSON — line {e.lineno}, column {e.colno} ({e.msg})")


def load_run(path):
    """Loads one mapping run (json) into the shape {cell: {label, text}}."""
    d = _read_json(path)
    out = {}
    for cell, v in d.items():
        out[cell] = v if isinstance(v, dict) else {"label": None, "text": str(v)}
    return out

def main():
    """CLI: prepares adjudication cards for the cells flagged by consensus.py."""
    ap = argparse.ArgumentParser()
    ap.add_argument("consensus")
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", default="adjudication.md")
    ap.add_argument("--seed", type=int, default=None, help="Shuffle seed for the options (default: random)")
    ap.add_argument("--key", default=None, help="Where to write the letter → run key (default: <out>.key.json)")
    a = ap.parse_args()
    if len(a.runs) > len(LETTERS):
        sys.exit(f"error: too many runs ({len(a.runs)} > {len(LETTERS)})")
    seed = a.seed if a.seed is not None else random.SystemRandom().randrange(2**32)
    rng = random.Random(seed)
    key_path = a.key or os.path.splitext(a.out)[0] + ".key.json"

    cons = _read_json(a.consensus)
    flagged = cons.get("summary", {}).get("flagged", [])
    runs = [load_run(p) for p in a.runs]

    md = ["# Adjudication of contested cells (decided by a human, blind)\n",
          f"Flagged by the council: {len(flagged)}. For each — the options. Choose one or write your own.\n"]
    cards = []
    key = {"seed": seed, "cells": {}}
    for cell in flagged:
        md.append(f"\n## {cell}\n")
        info = cons.get("cells", {}).get(cell, {})
        order = list(range(len(runs)))
        rng.shuffle(order)
        options, letters = [], {}
        # Labels stay off the options: identical labels on several options would reveal the vote split.
        candidates = sorted({runs[i].get(cell, {}).get("label") for i in order} - {None})
        if candidates:
            md.append(f"_Candidate labels (alphabetical, vote counts hidden): {', '.join(candidates)}_\n")
        for pos, i in enumerate(order):
            letter = LETTERS[pos]
            e = runs[i].get(cell, {})
            lab = e.get("label")
            txt = (e.get("text") or "").strip()
            md.append(f"- **Option {letter}**: {txt}")
            options.append({"option": letter, "text": txt})
            letters[letter] = {"run": i + 1, "file": a.runs[i], "label": lab}
        md.append("\n**Human decision:** _______  · **Why:** _______\n")
        cards.append({"cell": cell, "options": options, "decision": None, "rationale": None})
        key["cells"][cell] = {"letters": letters,
                              **{k: info[k] for k in ("labels", "agreement", "label_share") if k in info}}

    open(a.out, "w", encoding="utf-8").write("\n".join(md))
    open(re.sub(r"\.md$", ".json", a.out), "w", encoding="utf-8").write(
        json.dumps({"cards": cards}, ensure_ascii=False, indent=2))
    open(key_path, "w", encoding="utf-8").write(json.dumps(key, ensure_ascii=False, indent=2))
    print(f"Adjudication cards: {len(cards)} → {a.out}; key → {key_path} (open after the decision)")

if __name__ == "__main__":
    main()
