#!/usr/bin/env python3
"""
verify_quotes.py — verbatim verification of mapping quotes WITHOUT external APIs.

Cascade (cheap → expensive), inspired by LLMCode / DeTAILS + fuzzy practices:
  1) normalization (case, punctuation, fillers, spaces) + exact match → verified_exact
  2) fuzzy substring (rapidfuzz.partial_ratio_alignment, else difflib) → verified_fuzzy (+coordinates, line)
  3) coverage check via LCS share (guard against the leniency of token metrics)
  4) otherwise → rejected  (or paraphrase, if --semantic-hint is given)

Verbatim != support. This script checks ONLY verbatim-ness.
The «quote ⊨ claim» (entailment) check is done by the model as a separate step (see SKILL.md).

Dependencies: stdlib only. rapidfuzz is used IF installed (more accurate and faster),
otherwise it automatically falls back to difflib.

CLI:
  python verify_quotes.py --transcript T.txt --claims claims.json [--threshold 88]
                          [--min-coverage 0.6] [--window 6] [--out result.json]

Formats:
  transcript: plain text. If lines start with "L12: " or "12\t", the line number is recognized.
  claims.json: [{"cell":"К5","claim":"...","quote":"...","line":61}]  (line — optional)
Output: JSON with a status for each quote.
"""
import argparse, json, re, sys, unicodedata

# ---------- fuzzy backend (rapidfuzz optional, difflib fallback) ----------
try:
    from rapidfuzz import fuzz as _rf_fuzz
    from rapidfuzz.distance import LCSseq as _rf_lcs
    _HAS_RF = True
except Exception:
    _HAS_RF = False
from difflib import SequenceMatcher

FILLERS = {
    # ru
    "ну", "вот", "как бы", "типа", "короче", "это самое", "в общем", "эээ", "ээ",
    "мм", "ммм", "то есть", "так сказать", "знаете", "понимаете", "скажем так",
    # en
    "um", "uh", "erm", "you know", "like", "sort of", "kind of", "i mean",
    "as you know", "basically", "actually",
}

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def normalize(s: str) -> str:
    """lowercase, ё→е, strip punctuation, fillers, collapse spaces."""
    s = s.lower().replace("ё", "е")
    s = strip_accents(s)
    s = re.sub(r"[«»\"'`”“„.,;:!?()\[\]{}\-—–…/\\|]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s:
        # remove fillers as standalone tokens/bigrams
        for f in sorted(FILLERS, key=len, reverse=True):
            s = re.sub(rf"(?<!\w){re.escape(f)}(?!\w)", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
    return s

def parse_lines(text: str):
    """Returns a list of (line_no, original_line). Recognizes prefixes 'L12: ' and '12\\t'."""
    out = []
    for i, raw in enumerate(text.splitlines(), 1):
        m = re.match(r"^\s*L?(\d+)[:\t]\s?(.*)$", raw)
        if m:
            out.append((int(m.group(1)), m.group(2)))
        else:
            out.append((i, raw))
    return out

def fuzzy_score(needle: str, hay: str):
    """Returns (score 0..100, matched_substring_in_hay)."""
    if not needle or not hay:
        return 0.0, ""
    if _HAS_RF:
        al = _rf_fuzz.partial_ratio_alignment(needle, hay)
        if al is None:
            return 0.0, ""
        return _rf_fuzz.partial_ratio(needle, hay), hay[al.dest_start:al.dest_end]
    # difflib fallback: best block
    sm = SequenceMatcher(None, needle, hay)
    blocks = sm.get_matching_blocks()
    best = max(blocks, key=lambda b: b.size) if blocks else None
    if not best or best.size == 0:
        return 0.0, ""
    start = max(0, best.b - 2)
    end = min(len(hay), best.b + best.size + 2)
    window = hay[start:end]
    score = SequenceMatcher(None, needle, window).ratio() * 100
    return score, window

def lcs_coverage(needle: str, hay: str) -> float:
    """Share of the quote covered by the longest common fragment (0..1)."""
    if not needle:
        return 0.0
    if _HAS_RF:
        # LCSseq distance -> LCS length
        d = _rf_lcs.distance(needle, hay)
        lcs_len = (len(needle) + len(hay) - d) / 2  # not quite exact for seq, but a lower bound
        # safer via SequenceMatcher longest block:
    sm = SequenceMatcher(None, needle, hay)
    total = sum(b.size for b in sm.get_matching_blocks())
    return min(1.0, total / max(1, len(needle)))

def verify_one(quote, lines, norm_full, line_index, threshold, min_cov, window, claimed_line):
    qn = normalize(quote)
    if not qn:
        return {"status": "empty", "score": 0}
    # 1) exact normalized
    pos = norm_full.find(qn)
    if pos != -1:
        ln = locate_line(pos, line_index)
        return {"status": "verified_exact", "score": 100, "line_found": ln,
                "matched": quote.strip(), "coverage": 1.0,
                "line_ok": line_ok(ln, claimed_line, window)}
    # 2) fuzzy — over a window around the claimed line if present, otherwise over the whole text
    hay = norm_full
    if claimed_line is not None:
        hay = window_text(lines, claimed_line, window)
        hay_n = normalize(hay)
        score, matched = fuzzy_score(qn, hay_n)
        if score < threshold:  # window didn't match — try the whole text
            score, matched = fuzzy_score(qn, norm_full)
            hay_n = norm_full
    else:
        score, matched = fuzzy_score(qn, norm_full)
        hay_n = norm_full
    cov = lcs_coverage(qn, matched) if matched else 0.0
    if score >= threshold and cov >= min_cov:
        pos2 = norm_full.find(matched) if matched else -1
        ln = locate_line(pos2, line_index) if pos2 != -1 else None
        return {"status": "verified_fuzzy", "score": round(score, 1), "coverage": round(cov, 2),
                "line_found": ln, "matched": matched,
                "line_ok": line_ok(ln, claimed_line, window)}
    return {"status": "rejected", "score": round(score, 1), "coverage": round(cov, 2),
            "line_found": None, "matched": matched}

def window_text(lines, center_line, k):
    nums = [ln for ln, _ in lines]
    if center_line not in nums:
        return " ".join(t for _, t in lines)
    idx = nums.index(center_line)
    lo, hi = max(0, idx - k), min(len(lines), idx + k + 1)
    return " ".join(t for _, t in lines[lo:hi])

def build_index(lines):
    """Builds the normalized full text and a position->line-number map."""
    parts, index = [], []
    cursor = 0
    for ln, txt in lines:
        nt = normalize(txt)
        if not nt:
            continue
        parts.append(nt)
        index.append((cursor, cursor + len(nt), ln))
        cursor += len(nt) + 1  # +1 for the space separator
    return " ".join(parts), index

def locate_line(pos, index):
    for start, end, ln in index:
        if start <= pos <= end:
            return ln
    return index[-1][2] if index else None

def line_ok(found, claimed, k):
    if claimed is None or found is None:
        return None
    return abs(found - claimed) <= k

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--claims", required=True, help="JSON: list of {cell,claim,quote,line?}")
    ap.add_argument("--threshold", type=float, default=88.0,
                    help="Fuzzy threshold (calibrate! rapidfuzz partial_ratio 0..100)")
    ap.add_argument("--min-coverage", type=float, default=0.6,
                    help="Min. share of the quote covered by a verbatim fragment")
    ap.add_argument("--window", type=int, default=6, help="±lines around the claimed line")
    ap.add_argument("--out", default=None)
    ap.add_argument("--emit-enriched", default=None,
                    help="Path: write claims with the line filled in (line_found). "
                         "The model must NOT guess the line number — the script sets it.")
    a = ap.parse_args()

    text = open(a.transcript, encoding="utf-8").read()
    claims = json.load(open(a.claims, encoding="utf-8"))
    lines = parse_lines(text)
    norm_full, index = build_index(lines)

    results = []
    for c in claims:
        r = verify_one(c.get("quote", ""), lines, norm_full, index,
                       a.threshold, a.min_coverage, a.window, c.get("line"))
        r["cell"] = c.get("cell")
        r["claim"] = (c.get("claim", "") or "")[:120]
        r["quote"] = c.get("quote", "")
        results.append(r)

    n = len(results)
    ok = sum(1 for r in results if r["status"].startswith("verified"))
    summary = {
        "backend": "rapidfuzz" if _HAS_RF else "difflib",
        "total": n, "verified": ok, "rejected": n - ok,
        "verified_share": round(ok / n, 3) if n else 0.0,
        "rejected_cells": [r["cell"] for r in results if r["status"] == "rejected"],
        "line_mismatches": [r["cell"] for r in results if r.get("line_ok") is False],
    }
    out = {"summary": summary, "results": results}
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    if a.emit_enriched:
        enriched = []
        for c, r in zip(claims, results):
            e = dict(c)
            e["line"] = r.get("line_found")          # authority is the script, not the model
            e["verify_status"] = r["status"]
            enriched.append(e)
        open(a.emit_enriched, "w", encoding="utf-8").write(
            json.dumps(enriched, ensure_ascii=False, indent=2))
    print(js)

if __name__ == "__main__":
    main()
