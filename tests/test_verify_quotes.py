"""Юнит-тесты ядра verify_quotes.py — против обеих языковых копий."""
import json
import tempfile
import unittest
from pathlib import Path

from helpers import LANGS, load_script, run_script

TRANSCRIPT = (
    "L1: Мы теряем заявки каждый день\n"
    "L2: Отчет я собираю руками каждую пятницу вечером\n"
    "L3: Никто не знает, где лежат актуальные данные\n"
)


def _mods():
    return [(lang, load_script(lang, "verify_quotes")) for lang in LANGS]


class TestNormalize(unittest.TestCase):
    def test_ru_fillers_and_punctuation(self):
        for lang, m in _mods():
            with self.subTest(lang=lang):
                self.assertEqual(m.normalize("Ну, Ёжик — это КАК БЫ хорошо!"),
                                 "ежик это хорошо")

    def test_en_fillers(self):
        for lang, m in _mods():
            with self.subTest(lang=lang):
                self.assertEqual(m.normalize("Um, you know, THE report — takes hours!"),
                                 "the report takes hours")

    def test_yo_to_ye(self):
        for lang, m in _mods():
            with self.subTest(lang=lang):
                self.assertEqual(m.normalize("Отчёт"), "отчет")


class TestParseLines(unittest.TestCase):
    def test_prefixes_and_plain(self):
        for lang, m in _mods():
            with self.subTest(lang=lang):
                self.assertEqual(m.parse_lines("L12: привет"), [(12, "привет")])
                self.assertEqual(m.parse_lines("3\tтекст"), [(3, "текст")])
                self.assertEqual(m.parse_lines("а\nб"), [(1, "а"), (2, "б")])


class TestVerifyCascade(unittest.TestCase):
    def _setup(self, m):
        lines = m.parse_lines(TRANSCRIPT)
        norm_full, index = m.build_index(lines)
        return lines, norm_full, index

    def test_exact(self):
        for lang, m in _mods():
            with self.subTest(lang=lang):
                lines, nf, idx = self._setup(m)
                r = m.verify_one("Мы теряем заявки", lines, nf, idx, 88.0, 0.6, 6, None)
                self.assertEqual(r["status"], "verified_exact")
                self.assertEqual(r["line_found"], 1)

    def test_fuzzy_with_noise(self):
        # выпало слово «я» — не exact, но fuzzy должен пройти.
        # Порог 85.0 с запасом ниже ОБЕИХ веток бэкенда: difflib ≈ 86.97,
        # rapidfuzz ≈ 94.3 — тест зелёный независимо от того, установлен ли
        # rapidfuzz. (Дефолт 88.0 на difflib этот кейс режет — вход для
        # калибровки порогов, см. Task 5.)
        for lang, m in _mods():
            with self.subTest(lang=lang):
                lines, nf, idx = self._setup(m)
                r = m.verify_one("Отчет собираю руками каждую пятницу",
                                 lines, nf, idx, 85.0, 0.6, 6, None)
                self.assertTrue(r["status"].startswith("verified"), r)

    def test_hallucination_rejected(self):
        for lang, m in _mods():
            with self.subTest(lang=lang):
                lines, nf, idx = self._setup(m)
                r = m.verify_one("Мы внедрили новую CRM и все довольны",
                                 lines, nf, idx, 88.0, 0.6, 6, None)
                self.assertEqual(r["status"], "rejected")

    def test_threshold_and_coverage_wiring(self):
        # тот же fuzzy-кейс, но с запретительными порогами → rejected
        for lang, m in _mods():
            with self.subTest(lang=lang):
                lines, nf, idx = self._setup(m)
                r = m.verify_one("Отчет собираю руками каждую пятницу",
                                 lines, nf, idx, 100.0, 0.6, 6, None)
                self.assertEqual(r["status"], "rejected")
                r2 = m.verify_one("Отчет собираю руками каждую пятницу",
                                  lines, nf, idx, 88.0, 1.01, 6, None)
                self.assertEqual(r2["status"], "rejected")

    def test_empty_quote(self):
        for lang, m in _mods():
            with self.subTest(lang=lang):
                lines, nf, idx = self._setup(m)
                r = m.verify_one("   ", lines, nf, idx, 88.0, 0.6, 6, None)
                self.assertEqual(r["status"], "empty")

    def test_line_mismatch(self):
        # цитата на L3, заявлена строка 20, окно 6 → line_ok False
        for lang, m in _mods():
            with self.subTest(lang=lang):
                lines, nf, idx = self._setup(m)
                r = m.verify_one("Никто не знает, где лежат актуальные данные",
                                 lines, nf, idx, 88.0, 0.6, 6, 20)
                self.assertTrue(r["status"].startswith("verified"))
                self.assertIs(r["line_ok"], False)

    def test_line_ok_helper(self):
        for lang, m in _mods():
            with self.subTest(lang=lang):
                self.assertIs(m.line_ok(8, 3, 6), True)
                self.assertIs(m.line_ok(10, 3, 6), False)
                self.assertIsNone(m.line_ok(None, 3, 6))
                self.assertIsNone(m.line_ok(5, None, 6))


class TestDifflibFallback(unittest.TestCase):
    def test_forced_fallback(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                m = load_script(lang, "verify_quotes")  # свежий экземпляр
                m._HAS_RF = False
                score, matched = m.fuzzy_score(
                    m.normalize("Отчет собираю руками каждую пятницу"),
                    m.normalize("Отчет я собираю руками каждую пятницу вечером"))
                self.assertGreaterEqual(score, 85.0)
                self.assertTrue(matched)


class TestCli(unittest.TestCase):
    def test_end_to_end(self):
        claims = [
            {"cell": "К1", "claim": "теряем заявки", "quote": "Мы теряем заявки", "line": 1},
            {"cell": "К2", "claim": "выдумка", "quote": "Мы внедрили новую CRM и все довольны"},
        ]
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td) / "t.txt"
            cp = Path(td) / "c.json"
            tp.write_text(TRANSCRIPT, encoding="utf-8")
            cp.write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")
            for lang in LANGS:
                with self.subTest(lang=lang):
                    p = run_script(lang, "verify_quotes",
                                   "--transcript", tp, "--claims", cp)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    out = json.loads(p.stdout)
                    self.assertEqual(out["summary"]["total"], 2)
                    self.assertEqual(out["summary"]["verified"], 1)
                    self.assertEqual(out["summary"]["rejected_cells"], ["К2"])
                    self.assertIn(out["summary"]["backend"], ("rapidfuzz", "difflib"))


if __name__ == "__main__":
    unittest.main()
