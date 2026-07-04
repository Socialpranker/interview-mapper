"""Smoke-тесты route/score_insights/check_support/extract_claims + зеркальность RU/EN."""
import json
import tempfile
import unittest
from pathlib import Path

from helpers import LANGS, run_script, strip_localized

NUGGETS = [
    # C1: 3 разных verified-интервью, 2 роли с конфликтом валентности → insight + tension
    {"id": 1, "interview": "i1", "role": "ops", "cell": "К1", "observation": "",
     "quote": "q1", "line": 1, "verified": True, "severity": 4, "valence": "-", "cluster": "C1"},
    {"id": 2, "interview": "i2", "role": "mgmt", "cell": "К1", "observation": "",
     "quote": "q2", "line": 2, "verified": True, "severity": 5, "valence": "+", "cluster": "C1"},
    {"id": 3, "interview": "i3", "role": "ops", "cell": "К1", "observation": "",
     "quote": "q3", "line": 3, "verified": True, "severity": 4, "valence": "-", "cluster": "C1"},
    # C2: один источник, но критичный → watchlist
    {"id": 4, "interview": "i1", "role": "ops", "cell": "К2", "observation": "",
     "quote": "q4", "line": 4, "verified": True, "severity": 5, "valence": "-", "cluster": "C2"},
    # C3: один источник, низкая критичность → weak
    {"id": 5, "interview": "i2", "role": "mgmt", "cell": "К3", "observation": "",
     "quote": "q5", "line": 5, "verified": False, "severity": 2, "valence": "0", "cluster": "C3"},
]

SUPPORT = [
    {"cell": "А1", "quote": "цитата раз", "verify_status": "verified_exact",
     "support": "yes", "support_why": "прямо об этом"},
    {"cell": "А2", "quote": "цитата два", "verify_status": "verified_fuzzy",
     "support": "no", "support_why": "о другом"},
    {"cell": "А3", "quote": "цитата три", "verify_status": "rejected",
     "support": None, "support_why": ""},
]

MAPPING_MD = (
    "**К5 | Системы и данные**\n"
    "Отчёты собираются вручную, автоматизации нет.\n"
    "_Цитата: «Отчет я собираю руками» (L12)_\n"
)


class TestRoute(unittest.TestCase):
    def test_deterministic_and_structured(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                a1 = run_script(lang, "route", "--goal", "org",
                                "--respondent", "employee", "--n", 3)
                a2 = run_script(lang, "route", "--goal", "org",
                                "--respondent", "employee", "--n", 3)
                self.assertEqual(a1.returncode, 0, a1.stderr)
                self.assertEqual(a1.stdout, a2.stdout)  # детерминизм
                out = json.loads(a1.stdout)
                for key in ("lens", "output", "pipeline", "k_triangulation"):
                    self.assertIn(key, out)
                self.assertEqual(out["k_triangulation"], 3)
                self.assertTrue(out["lens"].endswith(".md"))


class TestScoreInsights(unittest.TestCase):
    def test_triangulation_watchlist_weak_tension(self):
        with tempfile.TemporaryDirectory() as td:
            np = Path(td) / "nuggets.json"
            np.write_text(json.dumps(NUGGETS, ensure_ascii=False), encoding="utf-8")
            for lang in LANGS:
                with self.subTest(lang=lang):
                    p = run_script(lang, "score_insights", np, "--k", 3)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    out = json.loads(p.stdout)
                    s = out["summary"]
                    self.assertEqual(s["total_interviews"], 3)
                    self.assertEqual((s["insights"], s["watchlist"], s["weak"]), (1, 1, 1))
                    self.assertEqual(s["tensions"], ["C1"])
                    c1 = out["clusters"][0]  # insight сортируется первым
                    self.assertEqual(c1["cluster"], "C1")
                    self.assertIs(c1["triangulated"], True)
                    self.assertIs(c1["tension"], True)


class TestCheckSupport(unittest.TestCase):
    def test_dangerous_and_missing(self):
        with tempfile.TemporaryDirectory() as td:
            sp = Path(td) / "support.json"
            sp.write_text(json.dumps(SUPPORT, ensure_ascii=False), encoding="utf-8")
            for lang in LANGS:
                with self.subTest(lang=lang):
                    p = run_script(lang, "check_support", sp)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    s = json.loads(p.stdout)["summary"]
                    self.assertEqual(s["total"], 3)
                    self.assertEqual(s["supported_yes"], 1)
                    self.assertEqual(s["unsupported_no"], 1)
                    self.assertEqual(s["dangerous_verbatim_unsupported"], ["А2"])
                    self.assertEqual(s["missing_verdict"], ["А3"])


class TestExtractClaims(unittest.TestCase):
    def test_cells_quotes_lines(self):
        with tempfile.TemporaryDirectory() as td:
            mp = Path(td) / "mapping.md"
            op = Path(td) / "claims.json"
            mp.write_text(MAPPING_MD, encoding="utf-8")
            for lang in LANGS:
                with self.subTest(lang=lang):
                    p = run_script(lang, "extract_claims", mp,
                                   "--interview", "Дарья", "--out", op)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    claims = json.loads(op.read_text(encoding="utf-8"))
                    self.assertEqual(len(claims), 1)
                    c = claims[0]
                    self.assertEqual(c["cell"], "К5")
                    self.assertEqual(c["quote"], "Отчет я собираю руками")
                    self.assertEqual(c["line"], 12)
                    self.assertEqual(c["interview"], "Дарья")


class TestMirrorBehavior(unittest.TestCase):
    """Одинаковый вход → одинаковый выход у RU- и EN-копий (минус локализованные поля)."""

    def test_score_insights_mirror(self):
        with tempfile.TemporaryDirectory() as td:
            np = Path(td) / "nuggets.json"
            np.write_text(json.dumps(NUGGETS, ensure_ascii=False), encoding="utf-8")
            procs = [run_script(lang, "score_insights", np) for lang in LANGS]
            for lang, p in zip(LANGS, procs):
                self.assertEqual(p.returncode, 0, f"{lang}: {p.stderr}")
            outs = [json.loads(p.stdout) for p in procs]
            self.assertEqual(strip_localized(outs[0]), strip_localized(outs[1]))

    def test_route_mirror(self):
        procs = [run_script(lang, "route", "--goal", "org",
                             "--respondent", "employee", "--n", 3) for lang in LANGS]
        for lang, p in zip(LANGS, procs):
            self.assertEqual(p.returncode, 0, f"{lang}: {p.stderr}")
        outs = [json.loads(p.stdout) for p in procs]
        self.assertEqual(strip_localized(outs[0]), strip_localized(outs[1]))
        # pipeline — локализованный текст, исключён из strip_localized целиком (включая длину).
        # Число шагов не должно расходиться RU/EN, даже если формулировки — да.
        self.assertEqual(len(outs[0]["pipeline"]), len(outs[1]["pipeline"]))

    def test_check_support_mirror(self):
        with tempfile.TemporaryDirectory() as td:
            sp = Path(td) / "support.json"
            sp.write_text(json.dumps(SUPPORT, ensure_ascii=False), encoding="utf-8")
            outs = []
            for lang in LANGS:
                p = run_script(lang, "check_support", sp)
                self.assertEqual(p.returncode, 0, f"{lang}: {p.stderr}")
                raw = json.loads(p.stdout)
                # flag-строки в results локализованы → сравниваем только summary без note
                outs.append(strip_localized(raw["summary"]))
            self.assertEqual(outs[0], outs[1])


if __name__ == "__main__":
    unittest.main()
