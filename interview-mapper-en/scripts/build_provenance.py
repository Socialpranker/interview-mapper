#!/usr/bin/env python3
"""
build_provenance.py — a single audit trail: insight → cluster → nugget → quote → line → interview.

Full traceability of every conclusion — a feature closed products lack.
Joins the output of score_insights.py with (opt.) support verdicts from check_support.py and the
verbatim status from verify_quotes.py, so every piece of evidence carries: verified? support?

Input:
  --insights  output of score_insights.py (clusters with evidence)
  --support   (opt.) output of check_support.py — adds support to quotes
  --verify    (opt.) output of verify_quotes.py — adds verify_status if absent from evidence
Output: provenance.json (machine-readable graph) + brief console.

CLI: python build_provenance.py --insights scored.json [--support sup.json] [--verify q.json] [--out provenance.json]
"""
import argparse, json

def index_by_quote(path, field_map):
    d = {}
    if not path:
        return d
    data = json.load(open(path, encoding="utf-8"))
    rows = data.get("results", data) if isinstance(data, dict) else data
    for r in rows:
        key = (r.get("cell"), (r.get("quote") or "")[:60])
        d[key] = {k: r.get(v) for k, v in field_map.items()}
    return d

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--insights", required=True)
    ap.add_argument("--support", default=None)
    ap.add_argument("--verify", default=None)
    ap.add_argument("--out", default="provenance.json")
    a = ap.parse_args()

    scored = json.load(open(a.insights, encoding="utf-8"))
    sup = index_by_quote(a.support, {"support": "support"})
    ver = index_by_quote(a.verify, {"verify_status": "status", "line_found": "line_found"})

    graph = []
    for c in scored.get("clusters", []):
        insight = {
            "cluster": c["cluster"], "status": c["status"],
            "prevalence": c["prevalence"], "roles": c["roles"],
            "severity": c["severity"], "triangulated": c["triangulated"],
            "tension": c["tension"], "score": c["score_combined"],
            "evidence": [],
        }
        for e in c["evidence"]:
            key = (None, (e.get("quote") or "")[:60])
            # key by quote without cell (evidence from score doesn't always carry cell)
            skey = next((k for k in sup if k[1] == key[1]), None)
            vkey = next((k for k in ver if k[1] == key[1]), None)
            insight["evidence"].append({
                "interview": e.get("interview"), "role": e.get("role"),
                "quote": e.get("quote"), "line": e.get("line"),
                "verified": e.get("verified"),
                "verify_status": (ver.get(vkey, {}) or {}).get("verify_status") if vkey else None,
                "support": (sup.get(skey, {}) or {}).get("support") if skey else None,
            })
        graph.append(insight)

    out = {
        "summary": {
            "insights": scored.get("summary", {}),
            "note": "Every piece of evidence is traceable: interview→quote→line, with verified and support status.",
        },
        "provenance": graph,
    }
    open(a.out, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Provenance graph: {len(graph)} clusters → {a.out}")
    for g in graph:
        ev = g["evidence"]
        unver = sum(1 for e in ev if not e["verified"])
        print(f"  {g['cluster']} [{g['status']}] {g['prevalence']} int | evidence {len(ev)}"
              + (f" | NOT verified: {unver}" if unver else ""))

if __name__ == "__main__":
    main()
