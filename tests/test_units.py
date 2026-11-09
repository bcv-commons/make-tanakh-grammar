#!/usr/bin/env python3
"""Unit tests of the pure parts: no Bible text, no private data, no model call.

    python3 -m unittest discover -s tests -p "test_*.py" """
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import holdout  # noqa: E402
from drafting import devcheck, draft, evidence, prompt  # noqa: E402


class Holdout(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(holdout.parse("LUK:1,2,15;PHP:3"), {("LUK", 1), ("LUK", 2), ("LUK", 15), ("PHP", 3)})
        self.assertEqual(holdout.parse(""), set())

    def test_closed_list_closes_the_held_out_chapters(self):
        for b, c in holdout.HELD_OUT:
            self.assertTrue(holdout.is_closed(b, c))

    def test_shut_per_language(self):
        own = holdout.shut({"held_out": ["ROM:8"]})                      # a language of its own: only its own list
        self.assertTrue(own("ROM", 8)); self.assertFalse(own("MRK", 1))
        res = holdout.shut({"closed_list": True})                        # a research language: the closed list
        self.assertTrue(res("MRK", 1)); self.assertTrue(res("GEN", 22)); self.assertFalse(res("GEN", 2))


class Evidence(unittest.TestCase):
    def tok(self, key, cls="noun", lemma="x", ref="GEN 1:1"):
        return dict(key=key, lemma=lemma, strong="1", cls=cls, text=key, cell=None, ref=None, w=None, pos=[], ws=[], sref=ref)

    def test_merge_segments_keeps_every_word_in_text_order(self):
        a = dict(id="H:1", tokens=[self.tok("010010010051")], refs=["GEN 1:1"], lem={"a"}, skeys={"H1"}, neg=False, verb="", pn="", kind="VC", rule="", book="GEN", ch=1, lang="hbo")
        b = dict(a, tokens=[self.tok("010010010011"), self.tok("010010010021")], lem={"b"}, skeys={"H2"}, verb="qatal|qal", pn="third|singular")
        c = dict(a, id="H:2", tokens=[self.tok("010010010071")])
        out = evidence.merge_segments([a, b, c])
        self.assertEqual([q["id"] for q in out], ["H:1", "H:2"])
        self.assertEqual([t["key"] for t in out[0]["tokens"]], ["010010010011", "010010010021", "010010010051"])
        self.assertEqual(out[0]["lem"], {"a", "b"}); self.assertEqual(out[0]["verb"], "qatal|qal")

    def test_job_membership(self):
        self.assertTrue(evidence._in_job(["GEN 2:25", "GEN 3:1"], "GEN", {2}, legacy=False))     # by the first verse
        self.assertFalse(evidence._in_job(["GEN 2:25", "GEN 3:1"], "GEN", {2}, legacy=True))
        self.assertFalse(evidence._in_job([], "GEN", {2}, legacy=False))

    def test_head_word(self):
        self.assertEqual(evidence.head_word([0, 1, 3], [0, 0, 1, 1], ["p1", "stem", "stem", "s1"]), 0)   # the word with a linked stem part


class Prompt(unittest.TestCase):
    def test_parts_and_links(self):
        ws = [["a", "p1"], ["bc", "stem"], ["d", "s1"]]
        self.assertEqual(prompt.word_str(ws), "[a- bc -d]")
        self.assertEqual(prompt.link_marker(ws, [2], [[2], [2], []]), "<- g2")
        self.assertEqual(prompt.link_marker(ws, [1, 2], [[1], [2], []]), "<- a-:g1 bc:g2")
        self.assertEqual(prompt.link_marker(ws, [], [[], [], []]), "<- -")

    def test_ref_order(self):
        self.assertEqual(sorted(["GEN 10:2", "GEN 2:10", "GEN 2:9"], key=prompt.ref_key), ["GEN 2:9", "GEN 2:10", "GEN 10:2"])


class Draft(unittest.TestCase):
    def test_chapters(self):
        self.assertEqual(draft.chapters_arg("1-3,7,2"), [1, 2, 3, 7])

    def test_verse_id(self):
        self.assertEqual(draft.vid("1SA 17:4"), "1SA_17_4")


class DevCheck(unittest.TestCase):
    def test_chrf_of_identical_text_is_100(self):
        self.assertAlmostEqual(devcheck.fscore([devcheck.stats("abc defg hij", "abc defg hij")])[0], 100.0)

    def test_chrf_is_recall_weighted(self):
        short = devcheck.fscore([devcheck.stats("abcdefgh", "abcdefghijklmnop")])[0]       # half of the reference, all correct
        long = devcheck.fscore([devcheck.stats("abcdefghijklmnopqrstuvwxyzabcdef", "abcdefghijklmnop")])[0]   # all of it, and as much again
        self.assertGreater(long, short)

    def test_marks(self):
        self.assertEqual(devcheck.detone("áā", keep=("̄",)), "aā")
        self.assertEqual(devcheck.norm_word("Word,"), "word")


class Corpus(unittest.TestCase):
    def setUp(self):
        try:
            from onboard import corpus  # noqa: F401  (needs the toolkit on the path)
        except ImportError:
            self.skipTest("the toolkit is not on the path")

    def test_layer_strings(self):
        from onboard import corpus
        self.assertEqual(dict(corpus.parse("0:1-2 3:5,7 x:1")), {0: [1, 2], 3: [5, 7]})
        self.assertEqual(corpus.parse_parts("c4:14.0,14.1 f10:32"), {("c", 4): [(14, 0), (14, 1)], ("f", 10): [(32, None)]})

    def test_slots(self):
        from onboard import corpus
        rows = [(0, "a", "prefix", 2), (1, "b", "prefix", 2), (2, "cde", "stem", None), (3, "f", "suffix", 1), (4, "g", "suffix", 3)]
        self.assertEqual(corpus.slots_of(rows), ["p2.1", "p2.0", "stem", "s1.0", "s3.0"])     # k counts outward from the stem
        self.assertEqual(corpus.slots_of([(0, "abc", "whole", None)]), ["stem"])
        self.assertEqual(corpus.slots_of([(0, "a", "prefix", None), (1, "bcd", "x", None)]), ["p9.0", "stem"])   # no stem named: the longest


class Align(unittest.TestCase):
    def test_numbering(self):
        try:
            from onboard import align
            m = align.to_hebrew("JON")
        except (ImportError, OSError, KeyError):
            self.skipTest("the toolkit and its source tables are not there")
        self.assertEqual(m[(1, 17)], (2, 1)); self.assertEqual(m[(2, 10)], (2, 11)); self.assertEqual(m[(1, 1)], (1, 1))


class Alignment(unittest.TestCase):
    def test_layer_positions_become_draft_tokens(self):
        try:
            from publish import align
            import full_align as FA
            FA.index("RUT", "lexemes")
        except Exception:
            self.skipTest("the toolkit is not on the path")
        import json, tempfile
        refs = list(FA.index("RUT", "lexemes")); i = refs.index("RUT 1:1")
        with tempfile.TemporaryDirectory() as d:
            main = [""] * len(refs); main[i] = "0:0 1:1-2 2:3"          # view units 1 and 2 are the parts of token 1
            json.dump(main, open(os.path.join(d, "RUT_x.json"), "w")); json.dump({}, open(os.path.join(d, "RUT_x.meta.json"), "w"))
            units = {"RUT": {"1:1": [[0, None], [1, 0], [1, 1], [2, None]]}}
            got = align.read_layer(d, units, "RUT", 1, {1: "aa bbcc dd"})
        self.assertEqual(got[1], ("0:0 1:1 2:2", ""))

    def test_text_step_bridges_and_notes(self):
        try:
            from onboard import align
        except Exception:
            self.skipTest("the toolkit is not on the path")
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "mrk015.txt"), "w", encoding="utf-8").write("v1 aa bb.{T: a note} v2-3 cc dd v4 ee. Big heading, more 15:5–18:2\n")
            n = align.export_chapters(d, os.path.join(d, "out"))
            got = open(os.path.join(d, "out", "MRK.txt"), encoding="utf-8").read()
        self.assertEqual((n, got), (3, "15:1 aa bb.\n15:2-3 cc dd\n15:4 ee.\n"))

    def test_lexicon_ids_and_bare_forms(self):
        try:
            from onboard import lexicon
        except Exception:
            self.skipTest("the toolkit is not on the path")
        self.assertEqual([lexicon.lex_id("hbo", "0776"), lexicon.lex_id("hbo", "2050b"), lexicon.lex_id("grc", "26"), lexicon.lex_id("grc", "")],
                         ["hbo:776", "hbo:2050b", "grc:26", None])
        self.assertEqual(lexicon.bare("dèmaluéf kø̄", {"\u0304"}), "demaluef kø̄")

    def test_parts_get_the_words_marks_back(self):
        try:
            from onboard import corpus
        except Exception:
            self.skipTest("the toolkit is not on the path")
        self.assertEqual(corpus.with_marks("dèmaluéf", ["de", "maluef"]), ["dè", "maluéf"])
        self.assertEqual(corpus.with_marks("køpimat-qa", ["køpim", "at", "qa"]), ["køpim", "at", "qa"])
        self.assertEqual(corpus.with_marks("abc", ["ab", "x"]), ["ab", "x"])               # letters that do not match: as they are

    def test_kinds_of_a_bundle(self):
        from publish import align
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for p in ("RUT/RUT_001.md", ".tanakh/alternatives/nllb/RUT/RUT_001.md", ".tanakh/alternatives/nllb/RUT/RUT_002.md"):
                os.makedirs(os.path.dirname(os.path.join(d, p)), exist_ok=True); open(os.path.join(d, p), "w").close()
            k = align.kinds(d)
        self.assertEqual({x: sorted(v) for x, v in k.items()}, {"main": [("RUT", 1)], "nllb": [("RUT", 1), ("RUT", 2)]})


class Publish(unittest.TestCase):
    def test_gate_is_same_verse_and_exact(self):
        from publish import verbatim
        team = {"GEN 1:1": "a b c d e f g h i j k l"}; g = verbatim.Gate(team)
        self.assertEqual(g.check("x a b c d e f g h i j y", ["GEN 1:1"])["longest run"], 10)
        self.assertIsNone(g.check("a b c x d e f", ["GEN 1:1"]))                    # short runs are the language's own usage
        self.assertIsNone(g.check("a b c d e f g h i j k l", ["GEN 1:2"]))          # another verse is never the measure
        self.assertEqual(verbatim.norm("Ab-cd, E'f!"), ["ab", "cd", "e'f"])

    def test_proposal_keeps_units_of_unchanged_verses(self):
        try:
            from publish import push
        except ImportError:
            self.skipTest("the toolkit is not on the path")
        old_md = "---\nDate: a\n---\n1:1\told one\n1:2\tsame\n"; new_md = "---\nDate: b\n---\n1:1\tnew one\n1:2\tsame\n"
        old_u = "# text aaa\n1:1\tk1:0-1\n1:2\tk2:0 k3:=\n"; new_u = "# text bbb\n1:1\tk1:0 k9:1\n1:2\tk2:=\n"
        self.assertEqual(push.merge_units(old_u, new_u, old_md, new_md), "# text bbb\n1:1\tk1:0 k9:1\n1:2\tk2:0 k3:=\n")
        self.assertEqual(push.body(old_md.replace("old", "new")), push.body(new_md))       # the front matter is not the text

    def test_ranges(self):
        try:
            from publish import chapter_format as CF                                # needs the toolkit on the path
        except ImportError:
            self.skipTest("the toolkit is not on the path")
        self.assertEqual(CF.ranges([3, 1, 2, 7]), "1-3,7")


class Shape(unittest.TestCase):
    def test_realise(self):
        from alternatives import shape
        ev = [{"id": "G:1", "lang": "grc", "tokens": [{"ref": "MAT 1:1", "w": 0, "ws": [0], "pos": [0]}, {"ref": "MAT 1:1", "w": 1, "ws": [1], "pos": [1, 2]}],
               "words": {"MAT 1:1": {"w0": 0, "words": [[["Na", "stem"]], [["ba-", "p1.0"], ["genda", "stem"]]], "pos": [[0], [1, 2]]}}}]
        got = shape.realise([{"for": 1, "ref": [1, 2]}, {"for": 1, "ref": [1, 2], "lex": 1}, {"for": None, "ref": [1, 1]}, {"none": "x", "for": 2},
                             {"for": 1, "lex": 1}, {"for": 1, "ref": [9, 9]}], {"id": "q"}, ev, {1: [("soma", {"text": 3})]})
        self.assertEqual([w for w, _ in got], ["ba-genda", "ba-soma", "na", "soma"])       # the verse-initial capital goes; a bad reference yields nothing
        self.assertEqual([t for _, t in got], ["ref:G:1#2", "ref:G:1#2+lex", "ref:G:1#1", "lex"])


class Nllb(unittest.TestCase):
    def test_words_and_cut(self):
        try:
            from alternatives import nllb
        except ImportError:
            self.skipTest("the toolkit is not on the path")
        self.assertEqual(nllb.words_of("ni@@ ba@@ kuu Na."), ["nibakuu", "Na."])
        q = {"tokens": [{"sref": "JHN 1:1", "key": "k3"}, {"sref": "JHN 1:1", "key": "k4"}]}
        self.assertEqual(nllb.cut(q, {"JHN 1:1": ["a", "b", "c", "d", "e", "f", "g", "h"]}, {"JHN 1:1": ["k1", "k2", "k3", "k4"]}), "e f g h")


if __name__ == "__main__":
    unittest.main()
