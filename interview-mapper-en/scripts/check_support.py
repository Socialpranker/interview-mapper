#!/usr/bin/env python3
"""
check_support.py — entailment accounting: makes the «quote ⊨ claim» check MANDATORY and logged.

Why: verbatim != support. A quote can be verbatim in the source yet the conclusion may not follow from it
(research: a system with perfect quotes scored 0.033 on entailment; up to 57% of quotes are post-rationalization).
Right now the model does this check «by eye». The script turns it into an auditable step:
for each quote the model issues a verdict support ∈ {yes, partial, no} + why, and the script aggregates,
CROSS-CHECKS against verbatim-ness and catches the dangerous class «verbatim, but does NOT support».

Input support.json — claims with fields from verify_quotes (verify_status) and from the model (support, support_why):
  [{"cell":"A1","quote":"...","verify_status":"verified_exact","support":"yes","support_why":"..."}]

The second judge asks the OPPOSITE question, not the same one. Repeating one prompt with one model
buys agreement with itself at the price of two runs: disagreements are suppressed, and the gate looks
functional while staying silent. Judge 1 asks "does the quote support the claim?", judge 2 asks
"show that it does NOT". Prompt text for judge 2: `--judge2-prompt`.

CLI:
  python check_support.py support.json [--second support2.json] [--out support_report.json]
  python check_support.py --judge2-prompt
"""
import argparse, json, sys

VALID = {"yes", "partial", "no"}

JUDGE2_PROMPT = """You are judge 2 in a grounding check. Judge 1 has already ruled; you do NOT see
their verdict and you do not repeat their work.

Your task is to try to REFUTE that the quote supports the claim. For each claim↔quote pair, look for
grounds to say "no": the quote is about something adjacent but not about this; it supports part of the
claim while the generalization was made on the respondent's behalf; the conclusion rests on domain
knowledge rather than on the words in the quote; the respondent speaks hypothetically and the claim
reads it as fact.

Only when you find no such grounds do you answer yes. Torn between partial and yes — answer partial.
The job is not to agree, it is to stress-test.

Response format — the same support.json:
[{"cell":"A1","quote":"verbatim","support":"yes|partial|no","support_why":"what the verdict rests on"}]
"""


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


def norm(s):
    """Normalizes a support verdict: lowercased string, or 'missing' if None."""
    return (str(s).strip().lower() if s is not None else "missing")

def main():
    """CLI: aggregates support verdicts, catches the dangerous verbatim-but-unsupported class."""
    ap = argparse.ArgumentParser()
    ap.add_argument("support", nargs="?")
    ap.add_argument("--second", default=None, help="Second independent run of verdicts — using the REFUTING prompt (--judge2-prompt)")
    ap.add_argument("--judge2-prompt", action="store_true",
                    help="Print the judge-2 prompt and exit")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if a.judge2_prompt:
        print(JUDGE2_PROMPT)
        return

    if not a.support:
        sys.exit("error: support.json is required (or --judge2-prompt)")

    items = _read_json(a.support)
    second = {}
    if a.second:
        for x in _read_json(a.second):
            second[(x.get("cell"), x.get("quote"))] = norm(x.get("support"))

    rows, missing, unsupported, dangerous, judge_split = [], [], [], [], []
    for x in items:
        sup = norm(x.get("support"))
        vs = x.get("verify_status", "unknown")
        key = (x.get("cell"), x.get("quote"))
        rec = {"cell": x.get("cell"), "quote": (x.get("quote") or "")[:60],
               "verify_status": vs, "support": sup, "why": x.get("support_why", "")}
        if sup not in VALID:
            missing.append(x.get("cell")); rec["issue"] = "no support verdict"
        if sup == "no":
            unsupported.append(x.get("cell"))
        # DANGEROUS class: quote is verbatim, but the claim is not supported by it
        if vs.startswith("verified") and sup in ("no", "partial"):
            dangerous.append(x.get("cell"))
            rec["flag"] = "verbatim, but support " + sup + " → the claim doesn't rest on the quote"
        if a.second:
            s2 = second.get(key, "missing")
            rec["support_2"] = s2
            if s2 in VALID and sup in VALID and s2 != sup:
                judge_split.append(x.get("cell"))
                rec["judge_split"] = True
        rows.append(rec)

    n = len(rows)
    # Judges with different lenses must diverge somewhere on a sizable sample.
    suspicious = bool(a.second) and n >= 8 and not judge_split
    supported = sum(1 for r in rows if r["support"] == "yes")
    summary = {
        "total": n,
        "supported_yes": supported,
        "partial": sum(1 for r in rows if r["support"] == "partial"),
        "unsupported_no": len(unsupported),
        "missing_verdict": missing,
        "dangerous_verbatim_unsupported": dangerous,
        "judge_disagreements": judge_split,
        "judge_agreement_suspicious": suspicious,
        "supported_share": round(supported / n, 3) if n else 0.0,
        "note": ("dangerous = quote is verbatim, but does NOT confirm the claim (the main hidden risk). "
                 "judge_disagreements and missing_verdict → to a human. "
                 "judge_agreement_suspicious = the judges never diverged once on a sizable sample: "
                 "judge 2 most likely echoed judge 1 instead of refuting (--judge2-prompt). "
                 "The support check cannot be skipped: verbatim-ness does not replace it."),
    }
    out = {"summary": summary, "results": rows}
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)

if __name__ == "__main__":
    main()
