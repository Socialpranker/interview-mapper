#!/usr/bin/env python3
"""
score_insights.py — надёжностный учёт кластеров наггетов для синтеза инсайтов (S6.5).

Кластеризацию (какой наггет к какой теме) и формулировки делает МОДЕЛЬ — это семантика.
Этот скрипт делает ДЕТЕРМИНИРОВАННЫЙ учёт, который нельзя выдумать:
  - сколько РАЗНЫХ интервью в кластере (не цитат! один человек ≠ паттерн),
  - триангуляция: паттерн засчитан, только если ≥K разных интервью, каждое с verified-цитатой,
  - частота × критичность (две оси, плюс дорожка «редкое, но высокоставочное» = watchlist),
  - напряжение: в кластере есть разные роли с конфликтующей валентностью (+/−),
  - статус: insight / watchlist / weak (одиночный источник — анекдот, не паттерн).

Вход nuggets.json — список:
  {"id","interview","role","cell","observation","quote","line",
   "verified": true/false, "severity": 1..5 (опц.), "valence": "+"/"-"/"0" (опц.),
   "cluster": "C1"}

CLI: python score_insights.py nuggets.json [--k 3] [--out insights_scored.json]
"""
import argparse, json, sys
from collections import defaultdict


def _read_json(path):
    """Читает JSON-файл; битый JSON или отсутствие файла → внятная ошибка, exit 1."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        sys.exit(f"error: {path}: {e.strerror or e}")
    except UnicodeDecodeError as e:
        sys.exit(f"error: {path}: не UTF-8 ({e.reason})")
    except json.JSONDecodeError as e:
        sys.exit(f"error: {path}: invalid JSON — строка {e.lineno}, колонка {e.colno} ({e.msg})")


def main():
    """CLI: считает триангуляцию/критичность/напряжения по кластерам наггетов и печатает summary."""
    ap = argparse.ArgumentParser()
    ap.add_argument("nuggets")
    ap.add_argument("--k", type=int, default=3, help="Порог триангуляции: мин. разных интервью с verified-цитатой")
    ap.add_argument("--severe", type=float, default=4.0, help="Порог критичности для watchlist (1..5)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    nuggets = _read_json(a.nuggets)
    all_interviews = sorted({n.get("interview") for n in nuggets if n.get("interview")})
    N = len(all_interviews)

    clusters = defaultdict(list)
    for n in nuggets:
        clusters[n.get("cluster", "UNCLUSTERED")].append(n)

    out = []
    for cid, items in clusters.items():
        interviews = sorted({i.get("interview") for i in items if i.get("interview")})
        roles = sorted({i.get("role") for i in items if i.get("role")})
        verified_interviews = sorted({i.get("interview") for i in items
                                      if i.get("verified") and i.get("interview")})
        severities = [float(i["severity"]) for i in items if i.get("severity") is not None]
        valences = {i.get("valence") for i in items if i.get("valence")}
        # напряжение: >=2 ролей и одновременно + и −
        role_valence = defaultdict(set)
        for i in items:
            if i.get("role") and i.get("valence"):
                role_valence[i["role"]].add(i["valence"])
        cross_role = len(roles) >= 2
        valence_conflict = ("+" in valences and "-" in valences)
        tension = cross_role and valence_conflict

        distinct_iv = len(interviews)
        distinct_verified = len(verified_interviews)
        prevalence = round(distinct_iv / N, 3) if N else 0.0
        severity = round(max(severities), 1) if severities else None
        triangulated = distinct_verified >= a.k

        # частота×критичность: обе нормированы 0..1, честно раздельно + combined для сортировки
        prev_norm = distinct_iv / N if N else 0.0
        sev_norm = ((severity - 1) / 4) if severity is not None else 0.0
        combined = round(0.5 * prev_norm + 0.5 * sev_norm, 3)

        # статус
        if triangulated:
            status = "insight"
        elif severity is not None and severity >= a.severe:
            status = "watchlist"   # редкое, но критичное — не хоронить
        elif tension:
            status = "watchlist"   # межролевое противоречие интересно даже при средней критичности
        else:
            status = "weak"        # одиночный источник, низкая критичность — анекдот

        out.append({
            "cluster": cid,
            "status": status,
            "prevalence": f"{distinct_iv}/{N}",
            "prevalence_ratio": prevalence,
            "distinct_interviews": distinct_iv,
            "verified_interviews": distinct_verified,
            "triangulated": triangulated,
            "roles": roles,
            "severity": severity,
            "score_combined": combined,
            "tension": tension,
            "tension_detail": ({r: sorted(v) for r, v in role_valence.items()} if tension else None),
            "n_nuggets": len(items),
            "evidence": [{"interview": i.get("interview"), "role": i.get("role"),
                          "quote": i.get("quote"), "line": i.get("line"),
                          "verified": bool(i.get("verified"))} for i in items],
        })

    # сортировка: insight'ы по combined desc, потом watchlist по severity, потом weak
    order = {"insight": 0, "watchlist": 1, "weak": 2}
    out.sort(key=lambda c: (order[c["status"]], -c["score_combined"], -(c["severity"] or 0)))

    summary = {
        "total_interviews": N,
        "interviews": all_interviews,
        "clusters": len(out),
        "insights": sum(1 for c in out if c["status"] == "insight"),
        "watchlist": sum(1 for c in out if c["status"] == "watchlist"),
        "weak": sum(1 for c in out if c["status"] == "weak"),
        "tensions": [c["cluster"] for c in out if c["tension"]],
        "k_triangulation": a.k,
        "note": ("insight = ≥k разных интервью с verified-цитатой; "
                 "watchlist = редкое, но критичное (severity≥%.1f); "
                 "weak = одиночный источник, не паттерн. "
                 "Малое N интервью → паттерны ненадёжны." % a.severe),
    }
    result = {"summary": summary, "clusters": out}
    js = json.dumps(result, ensure_ascii=False, indent=2)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)

if __name__ == "__main__":
    main()
