"""Тесты сигналов надёжности: omission-покрытие, опровергающий судья-2, вырожденный совет."""

import json
import tempfile
import unittest
from pathlib import Path

from helpers import LANGS, load_script, run_script

TRANSCRIPT = "\n".join(
    [
        "L1: Интервьюер: Расскажите про отчёты",
        "L2: Респондент: Отчет я собираю руками каждую пятницу вечером",
        "L3: Интервьюер: А что с заявками",
        "L4: Респондент: Мы теряем заявки каждый день",
        "L5: Интервьюер: Что ещё мешает",
        "L6: Респондент: Никто не знает где лежат актуальные данные",
        "L7: Респондент: Согласования тянутся неделями без объяснений",
        "L8: Респондент: Половина работы уходит на переписку в почте",
    ]
)


def _cg(lang):
    return load_script(lang, "coverage_gaps")


class TestCoverageGaps(unittest.TestCase):
    def _run(self, lang, claims, min_block=2):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "t_nl.txt"
            t.write_text(TRANSCRIPT, encoding="utf-8")
            c = Path(d) / "claims.json"
            c.write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")
            r = run_script(
                lang,
                "coverage_gaps",
                "--transcript",
                t,
                "--claims",
                c,
                "--min-block",
                min_block,
                "--skip-speaker",
                "Интервьюер",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout)

    def test_full_coverage_reports_no_gaps(self):
        claims = [
            {"cell": "K1", "quote": "Отчет я собираю руками каждую пятницу вечером"},
            {"cell": "K2", "quote": "Мы теряем заявки каждый день"},
            {"cell": "K3", "quote": "Никто не знает где лежат актуальные данные"},
            {"cell": "K4", "quote": "Согласования тянутся неделями без объяснений"},
            {"cell": "K5", "quote": "Половина работы уходит на переписку в почте"},
        ]
        out = self._run(LANGS[0], claims)
        self.assertEqual(out["summary"]["gap_blocks"], 0, out["gaps"])

    def test_missing_tail_is_reported_as_a_gap(self):
        """Контроль в обратную сторону: убрали три цитаты — блок обязан появиться."""
        for lang in LANGS:
            with self.subTest(lang=lang):
                claims = [
                    {
                        "cell": "K1",
                        "quote": "Отчет я собираю руками каждую пятницу вечером",
                    }
                ]
                out = self._run(lang, claims)
                self.assertGreaterEqual(out["summary"]["gap_blocks"], 1)
                self.assertIn(
                    "Согласования", json.dumps(out["gaps"], ensure_ascii=False)
                )

    def test_rejected_quote_does_not_count_as_coverage(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                claims = [
                    {
                        "cell": "K1",
                        "quote": "Отчет я собираю руками каждую пятницу вечером",
                    },
                    {
                        "cell": "K2",
                        "quote": "Мы теряем заявки каждый день",
                        "status": "rejected",
                    },
                    {
                        "cell": "K3",
                        "quote": "Никто не знает где лежат актуальные данные",
                        "status": "rejected",
                    },
                    {
                        "cell": "K4",
                        "quote": "Согласования тянутся неделями без объяснений",
                        "status": "rejected",
                    },
                ]
                out = self._run(lang, claims)
                self.assertGreaterEqual(out["summary"]["gap_blocks"], 1)

    def test_interviewer_turns_do_not_break_a_block(self):
        """В диалоге ответы идут через одну: если интервьюер рвёт блок, счётчик всегда ноль."""
        for lang in LANGS:
            with self.subTest(lang=lang):
                out = self._run(lang, [], min_block=3)
                self.assertEqual(out["summary"]["gap_blocks"], 1, out["gaps"])
                self.assertEqual(out["gaps"][0]["lines"], 5)

    def test_quote_absent_from_transcript_is_unlocated(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                out = self._run(
                    lang,
                    [{"cell": "X1", "quote": "Мы внедрили новую CRM и все довольны"}],
                )
                self.assertEqual(out["summary"]["unlocated_claims"], ["X1"])


class TestJudgeTwo(unittest.TestCase):
    def test_judge2_prompt_is_refuting_and_needs_no_input_file(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                r = run_script(lang, "check_support", "--judge2-prompt")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("support_why", r.stdout)
                self.assertTrue(len(r.stdout) > 200)

    def test_agreement_on_a_sizable_sample_is_flagged_as_suspicious(self):
        rows = [
            {
                "cell": f"A{i}",
                "quote": f"q{i}",
                "verify_status": "verified_exact",
                "support": "yes",
                "support_why": "ok",
            }
            for i in range(10)
        ]
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                p1, p2 = Path(d) / "s1.json", Path(d) / "s2.json"
                p1.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
                p2.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
                r = run_script(lang, "check_support", p1, "--second", p2)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertTrue(
                    json.loads(r.stdout)["summary"]["judge_agreement_suspicious"]
                )

    def test_one_disagreement_clears_the_suspicion(self):
        rows = [
            {
                "cell": f"A{i}",
                "quote": f"q{i}",
                "verify_status": "verified_exact",
                "support": "yes",
                "support_why": "ok",
            }
            for i in range(10)
        ]
        rows2 = [dict(x) for x in rows]
        rows2[4]["support"] = "no"
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                p1, p2 = Path(d) / "s1.json", Path(d) / "s2.json"
                p1.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
                p2.write_text(json.dumps(rows2, ensure_ascii=False), encoding="utf-8")
                out = json.loads(
                    run_script(lang, "check_support", p1, "--second", p2).stdout
                )
                self.assertFalse(out["summary"]["judge_agreement_suspicious"])
                self.assertEqual(out["summary"]["judge_disagreements"], ["A4"])

    def test_single_judge_never_raises_the_suspicion(self):
        rows = [
            {
                "cell": f"A{i}",
                "quote": f"q{i}",
                "verify_status": "verified_exact",
                "support": "yes",
                "support_why": "ok",
            }
            for i in range(10)
        ]
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                p1 = Path(d) / "s1.json"
                p1.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
                out = json.loads(run_script(lang, "check_support", p1).stdout)
                self.assertFalse(out["summary"]["judge_agreement_suspicious"])


class TestConsensusDegeneracy(unittest.TestCase):
    def _runs(self, d, diverge=False):
        paths = []
        for i in range(3):
            cells = {
                f"A{j}": {"label": "НЕЙТРАЛ", "text": f"вывод {j} прогон {i}"}
                for j in range(1, 7)
            }
            if diverge and i == 2:
                cells["A3"]["label"] = "ПРОМОУТЕР"
            p = Path(d) / f"run{i}.json"
            p.write_text(json.dumps(cells, ensure_ascii=False), encoding="utf-8")
            paths.append(p)
        return paths

    def test_unanimous_but_poorly_grounded_is_marked(self):
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                runs = self._runs(d)
                out = json.loads(
                    run_script(
                        lang, "consensus", *runs, "--weights", "0.4,0.5,0.45"
                    ).stdout
                )
                self.assertEqual(len(out["summary"]["unanimous_but_ungrounded"]), 6)

    def test_well_grounded_unanimity_is_not_marked(self):
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                runs = self._runs(d)
                out = json.loads(
                    run_script(
                        lang, "consensus", *runs, "--weights", "0.9,0.95,0.9"
                    ).stdout
                )
                self.assertEqual(out["summary"]["unanimous_but_ungrounded"], [])

    def test_total_agreement_reads_as_a_degenerate_council(self):
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                out = json.loads(run_script(lang, "consensus", *self._runs(d)).stdout)
                self.assertTrue(out["summary"]["council_degenerate"])

    def test_a_single_divergence_clears_degeneracy(self):
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                out = json.loads(
                    run_script(lang, "consensus", *self._runs(d, diverge=True)).stdout
                )
                self.assertFalse(out["summary"]["council_degenerate"])


class TestRouteCost(unittest.TestCase):
    def test_council_runs_drive_the_estimate(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                base = json.loads(
                    run_script(
                        lang,
                        "route",
                        "--goal",
                        "org",
                        "--respondent",
                        "employee",
                        "--n",
                        6,
                    ).stdout
                )["cost"]
                cheap = json.loads(
                    run_script(
                        lang,
                        "route",
                        "--goal",
                        "org",
                        "--respondent",
                        "employee",
                        "--n",
                        6,
                        "--council-runs",
                        1,
                    ).stdout
                )["cost"]
                self.assertEqual(base["per_interview_feeds"], 4)
                self.assertEqual(cheap["per_interview_feeds"], 2)
                self.assertLess(cheap["transcript_feeds"], base["transcript_feeds"])
                self.assertGreater(base["approx_input_tokens"], 0)


if __name__ == "__main__":
    unittest.main()
