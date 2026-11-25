"""render_board: цитата с </script> не должна выходить из блока данных борда."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from helpers import LANGS, run_script

HOSTILE = '</script><script>alert(1)</script><!-- & -->'
CLUSTERS = [{"cluster": "C1", "title": "T " + HOSTILE, "status": "insight",
             "evidence": [{"quote": HOSTILE, "interview": "i1", "line": 1}]}]


class TestRenderBoardEscaping(unittest.TestCase):
    def test_hostile_quote_stays_in_data(self):
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                src, out = Path(d) / "scored.json", Path(d) / "board.html"
                src.write_text(json.dumps({"clusters": CLUSTERS}), encoding="utf-8")
                run_script(lang, "render_board", src, "--out", out, check=True)
                page = out.read_text(encoding="utf-8")
                self.assertEqual(page.count("</script>"), 1)
                self.assertNotIn("<!--", page)
                data = re.search(r"const DATA=(.*?);\n", page).group(1)
                self.assertEqual(json.loads(data), CLUSTERS)


if __name__ == "__main__":
    unittest.main()
