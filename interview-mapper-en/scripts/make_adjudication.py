#!/usr/bin/env python3
"""
make_adjudication.py — cards for a human on contested cells (from consensus.py).

The council doesn't resolve contested cells itself — it flags them. This script prepares a convenient fork for the human:
for each flagged cell it shows the options from DIFFERENT runs side by side, so the human chooses blind.

Input: output of consensus.py + the same run*.json.
Output: adjudication.md (for the human) + adjudication.json.

CLI: python make_adjudication.py consensus.json run1.json run2.json [run3.json ...] [--out adjudication.md]
"""
import argparse, json, re, sys


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
    a = ap.parse_args()

    cons = _read_json(a.consensus)
    flagged = cons.get("summary", {}).get("flagged", [])
    runs = [load_run(p) for p in a.runs]

    md = ["# Adjudication of contested cells (decided by a human, blind)\n",
          f"Flagged by the council: {len(flagged)}. For each — the run options. Choose one or write your own.\n"]
    cards = []
    for cell in flagged:
        md.append(f"\n## {cell}\n")
        info = cons.get("cells", {}).get(cell, {})
        if "labels" in info:
            md.append(f"_Run labels: {info.get('labels')} · agreement: {info.get('agreement')}_\n")
        options = []
        for i, r in enumerate(runs, 1):
            e = r.get(cell, {})
            lab = e.get("label")
            txt = (e.get("text") or "").strip()
            md.append(f"- **Option {i}**" + (f" [{lab}]" if lab else "") + f": {txt}")
            options.append({"run": i, "label": lab, "text": txt})
        md.append("\n**Human decision:** _______  · **Why:** _______\n")
        cards.append({"cell": cell, "options": options, "decision": None, "rationale": None})

    open(a.out, "w", encoding="utf-8").write("\n".join(md))
    open(re.sub(r"\.md$", ".json", a.out), "w", encoding="utf-8").write(
        json.dumps({"cards": cards}, ensure_ascii=False, indent=2))
    print(f"Adjudication cards: {len(cards)} → {a.out}")

if __name__ == "__main__":
    main()
