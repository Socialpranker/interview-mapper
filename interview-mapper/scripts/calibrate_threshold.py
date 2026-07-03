#!/usr/bin/env python3
"""
calibrate_threshold.py — калибровка порога дословности по gold-set.

Проблема: порог fuzzy (88) и покрытие (0.6) в verify_quotes.py — угаданы. Их нужно калибровать
на РАЗМЕЧЕННЫХ данных, а не брать из туториалов (единственный документированный порог — difflib 0.6).

Вход gold.json — список размеченных вручную примеров:
  [{"quote":"...", "is_verbatim": true},   # цитата реально есть в источнике (пусть и с шумом ASR)
   {"quote":"...", "is_verbatim": false}]  # выдумка/сильный перифраз, которого в источнике нет
Плюс транскрипт. Скрипт прогоняет verify_quotes на разных порогах и считает precision/recall/F1,
предлагает порог, максимизирующий F1 (или precision при --prefer-precision).

CLI:
  python calibrate_threshold.py --transcript T.txt --gold gold.json
        [--min 70 --max 98 --step 2] [--min-coverage 0.6] [--prefer-precision]
"""
import argparse, json, subprocess, sys, os, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = os.path.join(HERE, "verify_quotes.py")

def run_verify(transcript, claims, threshold, min_cov):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(claims, f, ensure_ascii=False)
        cpath = f.name
    try:
        out = subprocess.run(
            [sys.executable, VERIFY, "--transcript", transcript, "--claims", cpath,
             "--threshold", str(threshold), "--min-coverage", str(min_cov)],
            capture_output=True, text=True, check=True).stdout
        return json.loads(out)["results"]
    finally:
        os.unlink(cpath)

def prf(gold, results):
    tp = fp = tn = fn = 0
    for g, r in zip(gold, results):
        pred = r["status"].startswith("verified")
        truth = bool(g["is_verbatim"])
        if pred and truth: tp += 1
        elif pred and not truth: fp += 1
        elif not pred and not truth: tn += 1
        else: fn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return dict(tp=tp, fp=fp, tn=tn, fn=fn, precision=round(prec, 3),
               recall=round(rec, 3), f1=round(f1, 3))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--min", type=float, default=70)
    ap.add_argument("--max", type=float, default=98)
    ap.add_argument("--step", type=float, default=2)
    ap.add_argument("--min-coverage", type=float, default=0.6)
    ap.add_argument("--prefer-precision", action="store_true",
                    help="Выбирать порог по precision (меньше ложных цитат), не по F1")
    a = ap.parse_args()

    gold = json.load(open(a.gold, encoding="utf-8"))
    claims = [{"cell": "gold", "claim": "", "quote": g["quote"]} for g in gold]

    rows, best = [], None
    t = a.min
    while t <= a.max + 1e-9:
        res = run_verify(a.transcript, claims, t, a.min_coverage)
        m = prf(gold, res); m["threshold"] = t
        rows.append(m)
        key = (m["precision"], m["f1"]) if a.prefer_precision else (m["f1"], m["precision"])
        if best is None or key > best[0]:
            best = (key, m)
        t += a.step

    print("порог  P     R     F1    (tp/fp/fn)")
    for m in rows:
        print(f"{m['threshold']:5.0f}  {m['precision']:.2f}  {m['recall']:.2f}  {m['f1']:.2f}"
              f"   ({m['tp']}/{m['fp']}/{m['fn']})")
    b = best[1]
    print(f"\nРЕКОМЕНДУЕМЫЙ порог: {b['threshold']:.0f}  "
          f"(P={b['precision']} R={b['recall']} F1={b['f1']}; "
          f"критерий: {'precision' if a.prefer_precision else 'F1'})")
    print("N gold:", len(gold), "| мало примеров → порог ориентировочный, добери gold-set.")

if __name__ == "__main__":
    main()
