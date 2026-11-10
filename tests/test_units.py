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


class Scratch(unittest.TestCase):
    def test_tmp_runs_go_to_the_scratch(self):
        from shared import paths
        old = os.environ.get("MAKE_TANAKH_PRIVATE"); os.environ["MAKE_TANAKH_PRIVATE"] = "/p"
        try:
            self.assertEqual(paths.run_dir("xx", "draft", "JHN", "tmp-a", "answers", make=False), "/p/scratch/runs/xx/draft/JHN/tmp-a/answers")
            self.assertEqual(paths.run_dir("xx", "draft", "JHN", "dev", make=False), "/p/runs/xx/draft/JHN/dev")
        finally:
            os.environ.pop("MAKE_TANAKH_PRIVATE") if old is None else os.environ.__setitem__("MAKE_TANAKH_PRIVATE", old)


class Register(unittest.TestCase):
    def reg(self):
        from shared import register as RG
        a = RG.entry("answer", "T1", "we use abc", "decided", "team", "team:abc", "2026-10-26", text="we use abc for this")
        t = RG.entry("term", "H1234.team", "abc", "decided", "team", "team:abc", "2026-10-26", source="H1234",
                     renderings=[{"form": "abc", "status": "preferred"}], origin="store:x/decisions.json#term:H1234.team", **{"from": ["answer:T1"]})
        m = RG.entry("morph", "ka-:verb", "PST", "proposed", "derived", "script:x", "2026-10-27", form="ka-", slot="prefix", host="verb")
        return RG, [a, t, m]

    def test_a_seeded_register_passes(self):
        RG, E = self.reg()
        self.assertEqual(RG.check(E, params={})[0], [])
        self.assertEqual(RG.team_terms(E), [("term:H1234.team", "abc")])

    def test_rules(self):
        RG, E = self.reg()
        bad = RG.entry("term", "H1234.agent", "abd", "proposed", "model", "agent:x", "2026-11-01", supersedes="term:H1234.team")
        err = RG.check(E + [bad, dict(E[2])], params={})[0]
        self.assertTrue(any("only the team may supersede" in x for x in err))
        self.assertTrue(any("id used twice" in x for x in err))
        ev = RG.entry("word", "abc", "WORD", "proposed", "derived", "script:x", "2026-11-01", evidence=[{"ref": "RUT 1:1", "form": "abc abd abe abf abg"}])
        self.assertTrue(RG.check(E + [ev], params={}, protected=True)[0])
        self.assertFalse(RG.check(E + [ev], params={}, protected=False)[0])
        with self.assertRaises(ValueError):
            RG.entry("morph", "x", "y", "proposed", "derived", "script:x", "2026-11-01", colour="red")


class RegisterFiles(unittest.TestCase):
    def test_file_of(self):
        from shared import register as RG
        f = RG.file_of("morph:ni-:verb")
        self.assertRegex(f, r"^morph/ni--verb-[0-9a-f]{6}\.json$")
        self.assertNotEqual(RG.file_of("term:Ab"), RG.file_of("term:ab"))       # same slug, the hash tells them apart
        self.assertTrue(RG.file_of("word:" + "x" * 80).startswith("word/" + "x" * 40 + "-"))

    def test_write_load(self):
        import tempfile
        from shared import register as RG
        E = [RG.entry("word", "abc", "abc", "proposed", "derived", "script:t", "2026-11-10", form="abc"),
             RG.entry("morph", "ni-:verb", "ni-", "decided", "team", "team:t", "2026-11-10", slot="prefix")]
        with tempfile.TemporaryDirectory() as d:
            RG.write(d, E, {"revision": "t"}); self.assertEqual(sorted(e["id"] for e in RG.load(d)), sorted(e["id"] for e in E))
            RG.write(d, E[:1], {"revision": "t2"}); self.assertEqual([e["id"] for e in RG.load(d)], ["word:abc"])
            self.assertEqual(RG.check_files(d), [])


class SegBundle(unittest.TestCase):
    def test_store_entry(self):
        from shared import register as RG
        from onboard import segbundle as SB
        e = RG.entry("morph", "ni-:verb", "1SG", "proposed", "model", "agent:t", "2026-11-10", slot="prefix", form="ni-", host="verb",
                     origin="store:x/observations.json#m:ni-:verb")
        x = SB.store_entry(e)
        self.assertEqual((x["id"], x["status"], x["slot"], x["form"]), ("m:ni-:verb", "observed", "prefix", "ni-"))
        self.assertEqual(SB.store_entry(dict(e, origin=None, status="open"))["id"], "m:ni-:verb")


class Intake(unittest.TestCase):
    class Seg:                                   # a splitter that knows ni- and -a around the stem lamul
        def split(self, w):
            out = []
            if w.startswith("ni"):
                out.append({"slot": "prefix", "text": "ni"}); w = w[2:]
            if w.startswith("lamul"):
                out.append({"slot": "stem", "text": "lamul"}); w = w[5:]
                return out + ([{"slot": "suffix", "text": w}] if w else [])
            return out + [{"slot": "stem", "text": w}]

    def test_merge(self):
        from onboard import intake as IN
        E, st = IN.merge([{"id": "a", "v": 1}, {"id": "b", "v": 1}], [{"id": "b", "v": 2}, {"id": "c", "v": 1}])
        self.assertEqual({e["id"]: e["v"] for e in E}, {"a": 1, "b": 2, "c": 1})
        self.assertEqual(st, {"changed in the repository": 1, "new from the repository": 1, "ours only (kept)": 1})

    def test_affix(self):
        from onboard import intake as IN
        self.assertEqual(IN.affix_of(self.Seg(), "lamula", "nilamula")[1:3], ([("suffix", "a")], [("prefix", "ni"), ("suffix", "a")]))
        self.assertEqual(IN.affix_of(self.Seg(), "kaba", "xekaba")[3], "xe-")           # unknown to the splitter: a candidate
        self.assertIsNone(IN.affix_of(self.Seg(), "kaba", "toto"))
        rows = [{"cat": "WORD", "old": "kaba", "new": "xekaba", "chapter": "RUT_001", "ref": "1:2"},
                {"cat": "FUNC", "old": "na", "new": "ne", "chapter": "RUT_001", "ref": "1:2"}]
        prop = IN.classify(rows, self.Seg(), [])
        self.assertEqual([r["intake_cat"] for r in rows], ["AFFIX", "FUNC"])
        self.assertEqual((prop[0]["form"], prop[0]["status"]), ("xe-", "open"))

    def test_edit_rows(self):
        import tempfile
        from onboard import intake as IN
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ".tanakh", "edits", "RUT", "RUT_001"); os.makedirs(p)
            open(os.path.join(p, "x.jsonl"), "w").write('{"ref": "1:1", "who": "t", "when": "w", "op": "R", "cat": "WORD"}\n'
                                                       '{"ref": "1:1", "op": "Q", "cat": "WORD"}\nnot json\n')
            rows, bad = IN.read_edits(d)
        self.assertEqual((len(rows), len(bad), rows[0]["chapter"]), (1, 2, "RUT_001"))

    def test_splitter_takes_decisions_only(self):
        from onboard import segbundle as SB
        self.assertTrue(SB.splits({"origin": "store:x#m:a", "status": "proposed"}))
        self.assertTrue(SB.splits({"status": "decided"}))
        self.assertFalse(SB.splits({"status": "open", "by": "script:intake"}))

    def test_term_value_and_team_rules(self):
        import tempfile
        from shared import register as RG
        from alternatives import rules as RU
        t = RG.entry("term", "x", "Naomi", "decided", "team", "t", "2026-11-10", renderings=[{"form": "Nawomi", "status": "preferred"}])
        self.assertTrue(any("preferred" in m for m in RG.check([t], params={})[0]))
        t["value"] = "Nawomi"; t["renderings"].append({"form": "Naomi", "status": "deprecated"})
        self.assertEqual(RG.team_terms([t]), [("term:x", "Nawomi (not Naomi)")])
        r = RG.entry("rule", "y", "keep a-", "decided", "team", "t", "2026-11-10", table="R2.V.p2.0", conditions={"subj_pn": "Third.Singular"}, do={"value": "a"})
        with tempfile.TemporaryDirectory() as d:
            RG.write(d, [t, r], {"revision": "t"}); ov = RU.team_overrides(d)
        self.assertEqual((ov[0][0], ov[0][1]["when"], ov[0][1]["source"]), ("R2.V.p2.0", {"subj_pn": "Third.Singular"}, "team:rule:y"))


class Tune(unittest.TestCase):
    def test_patch(self):
        from onboard import tune as TU
        S = {"r2_base": {"V": ["tgroup"]}, "r6_fields": ["person"], "r3_min_share": 0.5}
        self.assertEqual(TU.patch(S, {"r2_base_add": "sperson"})["r2_base"]["V"], ["tgroup", "sperson"])
        self.assertEqual(TU.patch(S, {"src_trig_add": "sneg"})["src_trig"], ["sneg"])
        self.assertEqual(TU.patch(S, {"r2_extra_add": ["V.p2.0", "subj_pnc"]})["r2_extra"], {"V.p2.0": ["subj_pnc"]})
        self.assertFalse(TU.applies(S, {"r3_min_share": 0.5})); self.assertTrue(TU.applies(S, {"r3_min_share": 0.4}))
        self.assertEqual(S["r2_base"]["V"], ["tgroup"])                              # S itself unchanged

    def test_guard(self):
        from onboard import tune as TU
        c = lambda w, p: {"chrF3 (words)": (0, 0, w), "chrF3 (parts)": (0, 0, p)}
        self.assertTrue(TU.passes(c([0.5, 0.1, 0.9], [0.0, -0.3, 0.3])))
        self.assertTrue(TU.passes(c([0.3, -0.1, 0.7], [0.1, -0.2, 0.4])))
        self.assertFalse(TU.passes(c([0.3, -0.3, 0.7], [0.1, -0.2, 0.4])))           # words: lower bound too low
        self.assertFalse(TU.passes(c([0.5, 0.1, 0.9], [-0.5, -0.9, -0.1])))          # parts fall


class Parts(unittest.TestCase):
    def test_pieces_rebuild(self):
        from publish import derived as DV
        r = [{"text": "ni", "slot": "prefix", "position": 1, "chain_id": "m:ni:verb", "label": None, "tone": None},
             {"text": "lim", "slot": "stem", "position": None, "chain_id": None, "label": None, "tone": None},
             {"text": None, "slot": "tone", "position": None, "chain_id": None, "label": "H", "tone": ["2:\u0301"]}]
        pcs = [DV.piece(x) for x in r]
        self.assertEqual(pcs[:2], ["ni:p1:m:ni:verb", "lim:stem"])
        self.assertEqual(DV.rebuild(pcs), "nilím")
        self.assertEqual(DV.parse_piece(pcs[0])["morph"], "m:ni:verb")
        self.assertEqual(DV.verse_hash(1, 2, "abc"), DV.verse_hash(1, 2, "abc")); self.assertNotEqual(DV.verse_hash(1, 2, "abc"), DV.verse_hash(1, 2, "abd"))

    def test_front_matter_kept(self):
        from publish import push
        old, new = "---\nstatus: team\n---\n# T\n1:1\told\n", "---\nstatus: machine\n---\n# T\n1:1\tnew\n"
        self.assertEqual(push.front(old)[0] + push.front(new)[1], "---\nstatus: team\n---\n# T\n1:1\tnew\n")


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

    def test_rights_no_unless_yes_and_the_publishing_hold(self):
        from shared import rights
        from publish import push
        self.assertEqual([rights.allowed({}, x) for x in ("llm", "jev", "aligner_service")], [False, False, False])
        self.assertTrue(rights.allowed({"rights": {"llm": True}}, "llm"))
        self.assertEqual([push.held({}), push.held({"publishing": {"hold": " "}}), push.held({"publishing": {"hold": "the team asked"}})],
                         [None, None, "the team asked"])

    def test_lexicon_reader_leaves_out_and_bridges(self):
        import sqlite3, tempfile
        from unittest import mock
        from drafting import lexicon
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "lexicon")); db = sqlite3.connect(os.path.join(d, "lexicon", "words.db"))
            db.executescript("create table lexeme(id, lang, strong, lemma, cls, n); create table form(id, form, plain, bare, tokens, n);"
                             "create table occ(lexeme, form, ref, src, key, positions, method); create table meta(name, value);"
                             "insert into meta values ('built', 'x'); insert into lexeme values ('grc:26', 'grc', '26', 'agape', 'noun', 4);"
                             "insert into lexeme values ('hbo:160b', 'hbo', '160b', 'ahava', 'noun', 1);"
                             "insert into form values (1, 'Abu', 'abu', 'abu', 1, 3), (2, 'abi ta', 'abi ta', 'abi ta', 2, 1), (3, 'ahu', 'ahu', 'ahu', 1, 1);")
            db.executemany("insert into occ values (?, ?, ?, '', '', '', '')", [("grc:26", 1, "JHN 3:16"), ("grc:26", 1, "ROM 5:5"),
                           ("grc:26", 1, "ROM 5:8"), ("grc:26", 2, "1JN 4:8"), ("hbo:160b", 3, "GEN 29:20")]); db.commit(); db.close()
            with mock.patch.object(lexicon.paths, "lang_dir", lambda iso, *p: os.path.join(d, *p)), \
                    mock.patch.object(lexicon.bridges, "lexemes", lambda: {"160": [("26", 0.8)]}):
                L = lexicon.Lexicon({"iso": "xxx"}, skip={("JHN", 3)}, leave_out={"1JN"})
                self.assertEqual(L.of("grc", "26"), ([("Abu", 1.0, 2)], 2))                # JHN 3 and 1JN not counted
                self.assertEqual([(lb, tot) for lb, _, tot, _ in L.renderings("hbo", {"strong": "160"})], [(None, 1), ("agape", 2)])   # few direct links: bridged
                self.assertIsNone(L.expected("grc", {"strong": "26"}))                       # fewer than 3 links
                self.assertTrue(lexicon.found("abi ta", {"abi", "ta", "x"}) and not lexicon.found("abi ta", {"abi"}))

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
        got = shape.realise([{"for": 1, "word": 2}, {"for": 1, "word": 3}, {"for": 2, "word": 1}], {"id": "q"}, ev, {}, {1: [("na", 0.5, None), ("ba-genda", 0.2, None)]})
        self.assertEqual(got, [("ba-genda", "word")])                                        # a whole word of the lexicon; a bad number yields nothing


class Nllb(unittest.TestCase):
    def test_words_and_cut(self):
        try:
            from alternatives import nllb
        except ImportError:
            self.skipTest("the toolkit is not on the path")
        self.assertEqual(nllb.words_of("ni@@ ba@@ kuu Na."), ["nibakuu", "Na."])
        q = {"tokens": [{"sref": "JHN 1:1", "key": "k3"}, {"sref": "JHN 1:1", "key": "k4"}]}
        self.assertEqual(nllb.cut(q, {"JHN 1:1": ["a", "b", "c", "d", "e", "f", "g", "h"]}, {"JHN 1:1": ["k1", "k2", "k3", "k4"]}), "e f g h")


class Rules(unittest.TestCase):
    def test_table_overrides_and_levels(self):
        from alternatives import rules_engine as K
        T = K.learn_dl("R2.V.p1.0", "R2", "x", [({"a": 1, "b": 1}, "ka")] * 5 + [({"a": 1, "b": 2}, "")] * 5, [["a", "b"], ["a"]], 5, 0.5)
        self.assertEqual(T.lookup({"a": 1, "b": 1})["do"]["value"], "ka"); self.assertEqual(T.lookup({"a": 1, "b": 2})["do"]["value"], "")
        self.assertIsNone(T.lookup({"a": 2, "b": 1}))
        T.add({"when": {"a": [1, 2]}, "unless": {"b": 2}, "do": {"value": "mu"}, "source": "llm"})     # an override: tried first
        self.assertEqual(T.lookup({"a": 2, "b": 1})["do"]["value"], "mu"); self.assertEqual(T.lookup({"a": 1, "b": 2})["do"]["value"], "")
        self.assertEqual(T.lookup({"a": 2, "b": 1}, skip=frozenset({"a"})), None)

    def test_slots_marks_and_time(self):
        from alternatives import rules_engine as K
        self.assertEqual(sorted(["s1.0", "p2.0", "p1.0", "p1.1"], key=K.slot_order), ["p1.1", "p1.0", "p2.0", "s1.0"])
        self.assertEqual(K.marked(["ba", "gu", "ta", "ni"], [0, 0, 1, 2]), "ba@@ gu ta ni")
        self.assertEqual(K.words_of([0, 0, 1, 2, 2]), [[0, 1], [2], [3, 4]])
        self.assertEqual((K.tgroup("Historic Past"), K.tgroup("Present"), K.tgroup(None)), ("past.remote", "present", "na"))
        self.assertEqual(K.noun_class("abatu"), "ba"); self.assertTrue(K.same_word("walked", "walking"))
        self.assertEqual(K.gloss_words("[the] man of God"), ["man", "god"]); self.assertEqual(K.norm_strong("G0746"), "746")

    def test_matcher_and_order(self):
        from alternatives import rules_engine as K, rules as R
        M = K.Matcher.__new__(K.Matcher); M.smap = {"dog": {"G12"}}; M.pre = "G"; M.assoc = {}
        cons = [dict(cid="p/0", cat="N", concept="dog", sense=""), dict(cid="p/1", cat="V", concept="run", sense="")]
        toks = [dict(key="k1", lemma="x", strong="12", gloss="hound", **{"class": "noun"}), dict(key="k2", lemma="y", strong="9", gloss="go", **{"class": "verb"})]
        self.assertEqual({c: t["key"] for c, t in M.match(cons, toks).items()}, {"p/0": "k1", "p/1": "k2"})     # Strong's, then the only free verb
        rule = lambda a, b: {"do": {"value": "ba"}} if (a, b) == ("N", "V") else None
        self.assertEqual([x[0] for x in R.Drafter.order([("N", 1), ("V", 2), ("A", 3)], rule)], ["V", "N", "A"])

    def test_words_and_cut(self):
        from alternatives import rules as R
        tags = [["Ba", 0, "p1.0", "c", "k1", "R2"], ["genda", 0, "stem", "c", "k1", "R2"], ["na", 1, "stem", None, None, "R3:x"],
                ["<dog>", 2, "stem", "d", "k3", "unk"], ["soma", 3, "stem", "e", "k4", "R1"]]
        ws = R.verse_words(tags)
        self.assertEqual(ws, [("Bagenda", "k1", "R2"), ("na", None, "R3:x"), ("soma", "k4", "R1")])      # an unknown concept is dropped
        self.assertEqual(R.cut(ws, [{"k1"}, {"k4"}]), [[("Bagenda", "R2"), ("na", "R3:x")], [("soma", "R1")]])
        self.assertEqual(R.cut([("na", None, "R9")] + ws, [{"k4"}, {"k1"}]), [[("na", "R9"), ("soma", "R1")], [("Bagenda", "R2"), ("na", "R3:x")]])
        self.assertEqual(R.norm_form(["ka", [["mu", "p1.0"], "ti"]]), [[["ka", "stem"]], [["mu", "p1.0"], ["ti", "stem"]]])


if __name__ == "__main__":
    unittest.main()
