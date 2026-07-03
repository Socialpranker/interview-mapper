#!/usr/bin/env python3
"""
batch_prepare.py — prepare a folder of transcripts for bulk mapping.

For each transcript (.txt/.docx) in the folder: numbers the lines → *_nl.txt, writes a manifest.
Lets you run a pool of N interviews without manual fuss. The mappings themselves are done by the model from the manifest.

CLI: python batch_prepare.py /path/to/transcripts [--out manifest.json]
"""
import argparse, json, os, re, glob

def read_text(path):
    if path.lower().endswith(".docx"):
        try:
            import docx
        except Exception:
            return None  # mark in the manifest as requiring conversion
        return "\n".join(p.text for p in docx.Document(path).paragraphs)
    return open(path, encoding="utf-8").read()

def interview_name(path):
    base = os.path.splitext(os.path.basename(path))[0]
    base = re.sub(r"[_\-]*(расшифровка|вычитано|интервью|nl|по спикерам).*$", "", base, flags=re.I)
    return base.strip(" —_-") or base

def main():
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
        if text is None:
            entry["status"] = "needs_docx_lib"
            manifest.append(entry); continue
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
    print(f"Transcripts: {len(manifest)} | ready for mapping: {ready} → {out}")
    for m in manifest:
        print(f"  [{m.get('status')}] {m['interview']}"
              + (f" ({m.get('lines')} lines)" if m.get('lines') else ""))
    print("Next: for each ready one — the model does the mapping using the chosen lens (S0-S2).")

if __name__ == "__main__":
    main()
