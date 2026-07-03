#!/usr/bin/env python3
"""
build_provenance.py — единый аудит-след: инсайт → кластер → наггет → цитата → строка → интервью.

Полная прослеживаемость каждого вывода — фича, которой нет у закрытых продуктов.
Джойнит выход score_insights.py с (опц.) вердиктами поддержки check_support.py и статусом
дословности verify_quotes.py, чтобы каждое доказательство несло: verified? support?

Вход:
  --insights  выход score_insights.py (clusters с evidence)
  --support   (опц.) выход check_support.py — добавит support к цитатам
  --verify    (опц.) выход verify_quotes.py — добавит verify_status, если нет в evidence
Выход: provenance.json (машиночитаемый граф) + краткая консоль.

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
            # ключ по цитате без cell (evidence из score не всегда несёт cell)
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
            "note": "Каждое доказательство прослеживаемо: interview→quote→line, со статусом verified и support.",
        },
        "provenance": graph,
    }
    open(a.out, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Provenance-граф: {len(graph)} кластеров → {a.out}")
    for g in graph:
        ev = g["evidence"]
        unver = sum(1 for e in ev if not e["verified"])
        print(f"  {g['cluster']} [{g['status']}] {g['prevalence']} инт | доказательств {len(ev)}"
              + (f" | НЕ verified: {unver}" if unver else ""))

if __name__ == "__main__":
    main()
