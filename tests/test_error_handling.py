"""Отсутствующий файл / битый JSON → exit 1 + внятное сообщение, БЕЗ traceback."""
import tempfile
import unittest
from pathlib import Path

from helpers import LANGS, run_script

# (скрипт, аргументы с несуществующим JSON-файлом)
MISSING_JSON_CASES = [
    ("verify_quotes", ["--transcript", "{t}", "--claims", "{missing}"]),
    ("score_insights", ["{missing}"]),
    ("check_support", ["{missing}"]),
    ("render_board", ["{missing}"]),
    ("calibrate_threshold", ["--transcript", "{t}", "--gold", "{missing}"]),
    ("build_provenance", ["--insights", "{missing}"]),
    ("make_adjudication", ["{missing}", "{c}"]),
]
MISSING_TEXT_CASES = [
    ("verify_quotes", ["--transcript", "{missing}", "--claims", "{c}"]),
    ("extract_claims", ["{missing}"]),
    ("number_lines", ["{missing}"]),
]


class TestErrors(unittest.TestCase):
    def _check(self, p, expect_json_msg=False):
        self.assertEqual(p.returncode, 1, f"stdout={p.stdout!r} stderr={p.stderr!r}")
        self.assertIn("error:", p.stderr)
        self.assertNotIn("Traceback", p.stderr)
        if expect_json_msg:
            self.assertIn("JSON", p.stderr)

    def test_missing_files(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "t.txt"; t.write_text("L1: привет", encoding="utf-8")
            c = Path(td) / "c.json"; c.write_text("[]", encoding="utf-8")
            missing = Path(td) / "no_such_file.json"
            subs = {"{t}": str(t), "{c}": str(c), "{missing}": str(missing)}
            for script, args in MISSING_JSON_CASES + MISSING_TEXT_CASES:
                real = [subs.get(a, a) for a in args]
                for lang in LANGS:
                    with self.subTest(script=script, lang=lang):
                        self._check(run_script(lang, script, *real))

    def test_broken_json(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "t.txt"; t.write_text("L1: привет", encoding="utf-8")
            bad = Path(td) / "bad.json"; bad.write_text("{oops", encoding="utf-8")
            for script, args in [
                ("verify_quotes", ["--transcript", str(t), "--claims", str(bad)]),
                ("score_insights", [str(bad)]),
                ("check_support", [str(bad)]),
                ("render_board", [str(bad)]),
                ("calibrate_threshold", ["--transcript", str(t), "--gold", str(bad)]),
            ]:
                for lang in LANGS:
                    with self.subTest(script=script, lang=lang):
                        self._check(run_script(lang, script, *args), expect_json_msg=True)

    def test_non_utf8(self):
        with tempfile.TemporaryDirectory() as td:
            bad_bytes = Path(td) / "bad_bytes.dat"
            bad_bytes.write_bytes(b"\xff\xfe\x00bad")
            for lang in LANGS:
                with self.subTest(script="extract_claims", lang=lang):
                    self._check(run_script(lang, "extract_claims", str(bad_bytes)))
                with self.subTest(script="score_insights", lang=lang):
                    self._check(run_script(lang, "score_insights", str(bad_bytes)))


if __name__ == "__main__":
    unittest.main()
