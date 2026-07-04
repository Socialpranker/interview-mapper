#!/usr/bin/env python3
"""
extract_nuggets.py — from a finished mapping (.md), assemble nugget stubs for synthesis (S5).

Saves the manual gluing of nuggets.json. Pulls a nugget stub for each quote:
  {interview, role, cell, observation, quote, line, verified:null, severity:null, valence:null, cluster:null}
The severity/valence/cluster fields are left null — the model MUST fill them in (it's judgment, not parsing).
verified is filled in by verify_quotes.py.

CLI: python extract_nuggets.py mapping.md --interview "Daria" --role "operations" [--out nuggets.json]
"""
import argparse, json, re, sys

# Catches codes: С3.2, С2.П (VMDI), as well as К5/К10, А1, J1, C1, E1
CELL_RE = re.compile(r"\*\*\s*([A-Za-zА-Яа-я]{1,2}\d{1,2}(?:\.[\wА-Яа-я]+)?)\s*[|｜]\s*([^*]+)\*\*")
QUOTE_RE = re.compile(r"«([^»]{4,})»")
LINE_RE = re.compile(r"\(L?(\d{1,4})\)")


def _read_text(path):
    """Read a text file, or exit with a clear error."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        sys.exit(f"error: {path}: {e.strerror or e}")
    except UnicodeDecodeError as e:
        sys.exit(f"error: {path}: not UTF-8 ({e.reason})")


def main():
    """CLI: assembles nugget stubs from an .md mapping for synthesis (S5)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("mapping")
    ap.add_argument("--interview", required=True)
    ap.add_argument("--role", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    text = _read_text(a.mapping)
    cur_cell, cur_title, obs = None, None, ""
    nuggets, idx = [], 0
    for ln in text.splitlines():
        m = CELL_RE.search(ln)
        if m:
            cur_cell, cur_title = m.group(1).strip(), m.group(2).strip()
            obs = ""
            continue
        if cur_cell and "«" not in ln and ln.strip() and not ln.startswith(("#", "---", "**", "_", ">")):
            if len(obs) < 140:
                obs = (obs + " " + ln.strip()).strip()
        for mq in QUOTE_RE.finditer(ln):
            idx += 1
            mline = LINE_RE.search(ln)
            nuggets.append({
                "id": f"{a.interview[:4]}-{idx}",
                "interview": a.interview,
                "role": a.role,
                "cell": cur_cell or "?",
                "observation": (cur_title + " — " + obs)[:180] if obs else (cur_title or ""),
                "quote": mq.group(1).strip(),
                "line": int(mline.group(1)) if mline else None,
                "verified": None,     # ← verify_quotes.py
                "severity": None,     # ← model (1..5, with rationale)
                "valence": None,      # ← model (+/-/0)
                "cluster": None,      # ← model (S6)
            })

    out = a.out or (re.sub(r"\.md$", "", a.mapping) + "_nuggets.json")
    open(out, "w", encoding="utf-8").write(json.dumps(nuggets, ensure_ascii=False, indent=2))
    print(f"Nugget stubs: {len(nuggets)} → {out}")
    print("Next: verify_quotes fills in verified; the model fills in severity/valence/cluster.")

if __name__ == "__main__":
    main()
