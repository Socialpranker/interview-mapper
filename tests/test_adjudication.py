"""Слепая адъюдикация: на карточках нет прогонов/согласия, ключ раскрывает буквы, сид воспроизводим."""

import json
import tempfile
import unittest
from pathlib import Path

from helpers import LANGS, run_script

CELLS = [f"A{j}" for j in range(1, 9)]
LABELS = ["НЕЙТРАЛ", "ПРОМОУТЕР", "КРИТИК"]  # все разные → каждая ячейка флагнута
RUN_FILES = ["alpha_first.json", "beta_second.json", "gamma_third.json"]
LEAKS = [
    "split",
    "majority",
    "unanimous",
    "agreement",
    "согласие",
    "прогон",
    "run",
    "seed",
    "key",
]


def _setup(d):
    """3 прогона × 8 ячеек, consensus.json получен настоящим consensus.py."""
    paths = []
    for i, (name, lab) in enumerate(zip(RUN_FILES, LABELS), 1):
        cells = {c: {"label": lab, "text": f"txt-r{i}-{c}"} for c in CELLS}
        p = Path(d) / name
        p.write_text(json.dumps(cells, ensure_ascii=False), encoding="utf-8")
        paths.append(p)
    cons = Path(d) / "consensus.json"
    cons.write_text(run_script("ru", "consensus", *paths).stdout, encoding="utf-8")
    return cons, paths


def _adjudicate(lang, d, cons, paths, *extra, out="adj.md"):
    p = run_script(
        lang, "make_adjudication", cons, *paths, "--out", Path(d) / out, *extra
    )
    assert p.returncode == 0, p.stderr
    return p


def _orders(d, out="adj.json"):
    cards = json.loads((Path(d) / out).read_text(encoding="utf-8"))["cards"]
    return [[o["text"] for o in c["options"]] for c in cards]


class TestBlindCards(unittest.TestCase):
    def test_cards_do_not_reveal_runs_or_agreement(self):
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                cons, paths = _setup(d)
                _adjudicate(lang, d, cons, paths, "--seed", "1")
                for f in ("adj.md", "adj.json"):
                    text = (Path(d) / f).read_text(encoding="utf-8")
                    for name in RUN_FILES:
                        self.assertNotIn(name, text)
                    for word in LEAKS:
                        self.assertNotIn(word, text.lower(), f"{f} leaks {word!r}")
                    self.assertNotIn(".key", text)

    def test_options_are_neutral_letters(self):
        for lang, expected in (("ru", ["А", "Б", "В"]), ("en", ["A", "B", "C"])):
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                cons, paths = _setup(d)
                _adjudicate(lang, d, cons, paths, "--seed", "1")
                cards = json.loads((Path(d) / "adj.json").read_text(encoding="utf-8"))[
                    "cards"
                ]
                self.assertEqual(len(cards), len(CELLS))
                for c in cards:
                    self.assertEqual([o["option"] for o in c["options"]], expected)


class TestKey(unittest.TestCase):
    def test_key_maps_every_letter_back_to_its_run(self):
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                cons, paths = _setup(d)
                _adjudicate(lang, d, cons, paths, "--seed", "7")
                key = json.loads((Path(d) / "adj.key.json").read_text(encoding="utf-8"))
                cards = json.loads((Path(d) / "adj.json").read_text(encoding="utf-8"))[
                    "cards"
                ]
                self.assertEqual(key["seed"], 7)
                for c in cards:
                    k = key["cells"][c["cell"]]
                    self.assertEqual(k["agreement"], "split")
                    self.assertEqual(
                        k["labels"], [l.lower() for l in LABELS]
                    )  # consensus.py lower-cases
                    self.assertEqual(
                        sorted(k["letters"]), sorted(o["option"] for o in c["options"])
                    )
                    for o in c["options"]:
                        run = k["letters"][o["option"]]
                        self.assertEqual(o["text"], f"txt-r{run['run']}-{c['cell']}")
                        self.assertNotIn("label", o)
                        self.assertEqual(run["label"], LABELS[run["run"] - 1])
                        self.assertEqual(run["file"], str(paths[run["run"] - 1]))

    def test_key_path_can_be_overridden(self):
        with tempfile.TemporaryDirectory() as d:
            cons, paths = _setup(d)
            _adjudicate("ru", d, cons, paths, "--key", Path(d) / "secret.json")
            self.assertTrue((Path(d) / "secret.json").exists())
            self.assertFalse((Path(d) / "adj.key.json").exists())


class TestSeed(unittest.TestCase):
    def test_same_seed_same_order(self):
        with tempfile.TemporaryDirectory() as d:
            cons, paths = _setup(d)
            _adjudicate("ru", d, cons, paths, "--seed", "42", out="a.md")
            _adjudicate("en", d, cons, paths, "--seed", "42", out="b.md")
            self.assertEqual(_orders(d, "a.json"), _orders(d, "b.json"))

    def test_different_seeds_change_order(self):
        # 8 карточек × 3! перестановок: совпадение порядка на всех карточках у разных сидов исключено
        with tempfile.TemporaryDirectory() as d:
            cons, paths = _setup(d)
            _adjudicate("ru", d, cons, paths, "--seed", "1", out="a.md")
            _adjudicate("ru", d, cons, paths, "--seed", "2", out="b.md")
            self.assertNotEqual(_orders(d, "a.json"), _orders(d, "b.json"))

    def test_order_is_shuffled_per_card(self):
        with tempfile.TemporaryDirectory() as d:
            cons, paths = _setup(d)
            _adjudicate("ru", d, cons, paths, "--seed", "3")
            runs_order = [tuple(t.split("-")[1] for t in o) for o in _orders(d)]
            self.assertGreater(len(set(runs_order)), 1)


if __name__ == "__main__":
    unittest.main()


class TestDuplicateLabels(unittest.TestCase):
    def test_vote_split_not_visible_through_labels(self):
        # 2-vs-1 split: labels attached to options would show the majority.
        labels = ["ПРОМОУТЕР", "ПРОМОУТЕР", "НЕЙТРАЛ"]
        for lang in LANGS:
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as d:
                paths = []
                for i, (name, lab) in enumerate(zip(RUN_FILES, labels), 1):
                    p = Path(d) / name
                    p.write_text(
                        json.dumps({"A1": {"label": lab, "text": f"txt-r{i}"}}, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    paths.append(p)
                cons = Path(d) / "consensus.json"
                cons.write_text(
                    json.dumps({"summary": {"flagged": ["A1"]}, "cells": {}}), encoding="utf-8"
                )
                _adjudicate(lang, d, cons, paths, "--seed", "3")
                md = (Path(d) / "adj.md").read_text(encoding="utf-8")
                self.assertEqual(md.count("ПРОМОУТЕР"), 1)
                self.assertEqual(md.count("НЕЙТРАЛ"), 1)
                cards = json.loads((Path(d) / "adj.json").read_text(encoding="utf-8"))
                self.assertNotIn("ПРОМОУТЕР", json.dumps(cards, ensure_ascii=False))
