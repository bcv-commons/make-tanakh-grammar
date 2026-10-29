#!/usr/bin/env python3
"""E6: the lexicon split in two, as TBTA's lexicon + synthesis grammar do.
  choice  Greek lemma (+ voice for verbs) -> English lexeme (the stem of the head word, by the corpus vocabulary) and its other
          core words ("went" + out); person, number, tense and case play no part here
  pre     the function words before the word: the cell pattern (class, morph features, context), shared by all lemmas
  form    the head word's form: the English lexeme's own form in that cell and pre (seen anywhere in the corpus, whichever Greek
          lemma it rendered: the irregular memory), else the cell's regular suffix applied to the stem
Everything else (other classes) as E3's context lexicon. Run through engine.py: stage e6."""
import collections, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cells as CL  # noqa: E402


def cellkey(t):
    if t["class"] == "verb":
        return ("verb", t["tense"], t["voice"], t["mood"], t["person"], t["number"])
    return ("noun", t["gcase"], t["number"])


def rolekey(t, cx):
    """FORM_ROLE: a noun's form cell with its role in the clause and a construct before it (a case language: subject ->
    nominative, object -> accusative, after a construct -> genitive); None where off or not a noun"""
    if not os.environ.get("FORM_ROLE") or t["class"] != "noun":
        return None
    return cellkey(t) + (t.get("role"), (cx or {}).get("after_cstr"), (cx or {}).get("gov"))


def coarse(t):
    if t["class"] == "verb":
        return ("verb", t["tense"], t["voice"], t["mood"])
    return ("noun", t["number"])


class Gen6:
    def __init__(self, C, refs, ctxlex, factored):
        self.ctxlex, self.fac = ctxlex, factored
        rows = factored.cells.rows
        self.choice = collections.defaultdict(collections.Counter)      # (lemma, voice) -> (stem, rest)
        self.choice_t = collections.defaultdict(collections.Counter)    # (lemma, voice, tense, mood) -> (stem, rest)
        self.choice_l = collections.defaultdict(collections.Counter)    # lemma -> (stem, rest)
        self.form = collections.defaultdict(collections.Counter)        # (stem, cell, pre) -> head
        self.form_c = collections.defaultdict(collections.Counter)      # (stem, coarse, pre) -> head
        self.suf = collections.defaultdict(collections.Counter)         # (cell, pre) -> suffix
        self.suf_c = collections.defaultdict(collections.Counter)       # (coarse, pre) -> suffix
        self.art = collections.defaultdict(collections.Counter)         # noun lemma -> pre ends in "the" or not (LEX_ART)
        self.choice_g = collections.defaultdict(collections.Counter)    # (lemma, voice, gcase) -> (stem, rest) | None (CHOICE_CTX)
        self.pre_l = collections.defaultdict(collections.Counter)       # (lemma, cell key) -> pre (PRE_LEX)
        self.post_l = collections.defaultdict(collections.Counter)      # (lemma, cell key) -> post (PRE_LEX + POST_CELL)
        post_cell = os.environ.get("POST_CELL")
        for t, pre, core, post, cx in rows:
            if os.environ.get("PRE_LEX"):
                self.pre_l[(t["lemma"], factored.cells.key(t, cx))][tuple(pre)] += 1
                if post_cell and (post_cell != "noun" or t["class"] == "noun"):
                    self.post_l[(t["lemma"], factored.cells.key(t, cx))][tuple(post)] += 1
            if post_cell and (post_cell != "noun" or t["class"] == "noun"):
                post = ()   # POST_CELL: the function words after the word come from the cell, as those before it do
            if os.environ.get("CHOICE_CTX"):
                # the word's own case / prefixes / suffix in the choice (בְּיַד "through", לְאִשָּׁה "in marriage"), and the
                # empty choice: a word the reference leaves unrendered here (merged into a neighbour's words)
                g = (t["lemma"], t["voice"] if t["class"] == "verb" else None, t["gcase"])
                if not core and not pre and not post:
                    self.choice_g[g][None] += 1
                elif core:
                    self.choice_g[g][(CL.lemmatize(CL.head(t, core))[0], CL.rest(t, core) + tuple(post))] += 1
            if t["class"] == "noun":
                self.art[t["lemma"]][bool(pre) and pre[-1] == "the"] += 1
            h = CL.head(t, core); stem, suf = CL.lemmatize(h)
            rest = CL.rest(t, core) + tuple(post)
            v = t["voice"] if t["class"] == "verb" else None
            self.choice_t[(t["lemma"], v, t["tense"], t["mood"])][(stem, rest)] += 1
            self.choice[(t["lemma"], v)][(stem, rest)] += 1; self.choice_l[t["lemma"]][(stem, rest)] += 1
            self.form[(stem, cellkey(t), pre)][h] += 1; self.form_c[(stem, coarse(t), pre)][h] += 1
            rk = rolekey(t, cx)
            if rk:
                self.form[(stem, rk, pre)][h] += 1; self.suf[(rk, pre)][suf] += 1
            self.suf[(cellkey(t), pre)][suf] += 1; self.suf_c[(coarse(t), pre)][suf] += 1
            if os.environ.get("ENDCLASS"):   # the regular rule per paradigm class (the stem's commonest ending)
                k = CL.stem_class(stem)
                self.suf[(cellkey(t), pre, k)][suf] += 1; self.suf_c[(coarse(t), pre, k)][suf] += 1

    def func_only(self, t):
        """a lemma the reference renders with function words only in this cell (εἰμί "is", δεῖ "must", ἔχω "has"):
        the commonest such rendering, when they are at least half of the lemma's renderings in the cell (else of the lemma)"""
        import engine as E
        for i, k in ((1, (t["lemma"], t["morph"])), (3, (t["lemma"],))):
            c = self.ctxlex.tab[i].get(k)
            if not c or sum(c.values()) < 3:
                continue
            fo = collections.Counter({w: n for w, n in c.items() if all(x in E.FUNC for x in w)})
            if sum(fo.values()) * 2 >= sum(c.values()):
                return list(fo.most_common(1)[0][0])
            return None
        return None

    def render(self, t):
        if t["class"] not in ("verb", "noun"):
            return None
        fo = self.func_only(t)
        if fo is not None:
            return fo, "function words only"
        v = t["voice"] if t["class"] == "verb" else None
        cg = self.choice_g.get((t["lemma"], v, t["gcase"])) if os.environ.get("CHOICE_CTX") else None
        if cg and sum(cg.values()) >= 3 and cg.most_common(1)[0][1] * 2 > sum(cg.values()):
            if cg.most_common(1)[0][0] is None:
                return [], "choice: none in this case"
            cg = collections.Counter({k: n for k, n in cg.items() if k is not None})
        else:
            cg = None
        ct = self.choice_t.get((t["lemma"], v, t["tense"], t["mood"]))
        c = cg or (ct if ct and sum(ct.values()) >= 3 else None) or self.choice.get((t["lemma"], v)) or self.choice_l.get(t["lemma"])
        if not c:
            return None
        (stem, rest), _ = c.most_common(1)[0]
        ref = f"{t['book']} {t['ch']}:{t['v']}"
        cx = self.ctxlex.contexts(ref)[t["key"]]
        p = self.fac.cells.pattern(self.fac.cells.key(t, cx))
        pre = tuple(p[0]) if p else ()
        pc = os.environ.get("POST_CELL")
        pc = pc if pc and (pc != "noun" or t["class"] == "noun") else None   # POST_CELL=noun: nouns only
        post = tuple(p[2]) if p and pc else ()
        if os.environ.get("PRE_LEX"):
            # a lexical exception to the cell's function words (TBTA's lexicon features in general): the lemma's own words in
            # this cell, when it has been seen there at least PRE_LEX times and one pattern holds 60% of them
            pl = self.pre_l.get((t["lemma"], self.fac.cells.key(t, cx)))
            if pl and sum(pl.values()) >= int(os.environ["PRE_LEX"]):
                w, n = pl.most_common(1)[0]
                if n >= 0.6 * sum(pl.values()):
                    pre = w
            ql = self.post_l.get((t["lemma"], self.fac.cells.key(t, cx))) if pc else None
            if ql and sum(ql.values()) >= int(os.environ["PRE_LEX"]):
                w, n = ql.most_common(1)[0]
                if n >= 0.6 * sum(ql.values()):
                    post = w
        if os.environ.get("LEX_ART") and t["class"] == "noun":
            # the lexicon's article feature (TBTA's "takes the article"): a noun that has "the" in >= 80% of its renderings
            # gets it after the cell's words, one that has it in <= 5% loses it ("the LORD", "God")
            a = self.art.get(t["lemma"])
            n = sum(a.values()) if a else 0
            if n >= 5 and a[True] / n >= 0.8 and (not pre or pre[-1] != "the"):
                pre = pre + ("the",)
            elif n >= 5 and a[True] / n <= 0.05 and pre and pre[-1] == "the":
                pre = pre[:-1]
        f = self.form.get((stem, cellkey(t), pre))
        s = self.suf.get((cellkey(t), pre))
        rk = rolekey(t, cx)
        if rk:
            fr, sr = self.form.get((stem, rk, pre)), self.suf.get((rk, pre))
            if fr:
                f = fr
            elif sr and sum(sr.values()) >= 3 and not f:
                s = sr
        if os.environ.get("ENDCLASS"):
            sk = self.suf.get((cellkey(t), pre, CL.stem_class(stem)))
            s = sk if sk and sum(sk.values()) >= 3 else s
        if f:
            head = f.most_common(1)[0][0]; how = "form seen"
        elif s and sum(s.values()) >= 3:  # the cell's regular rule before any coarser memory: person and number decide the form
            suf = s.most_common(1)[0][0]
            head = CL.apply_suffix(stem, suf) if suf != "Ø" else stem; how = "form by rule"
        else:
            f = self.form_c.get((stem, coarse(t), pre))
            if f:
                head = f.most_common(1)[0][0]; how = "form seen (coarse)"
            else:
                s = self.suf_c.get((coarse(t), pre))
                suf = s.most_common(1)[0][0] if s else "Ø"
                head = CL.apply_suffix(stem, suf) if suf != "Ø" else stem; how = "form by rule (coarse)"
        if how.startswith("form by rule") and CL.VOCAB.get(head, 0) < 2:
            # capability 6 (round 2): a regular suffix must give a word the corpus has ("writtened", "mans" do not occur);
            # else the Greek lemma's own commonest head in this cell, else the stem
            alt = collections.Counter()
            for w, n in (self.ctxlex.tab[1].get((t["lemma"], t["morph"])) or {}).items():
                _, cc, _ = CL.split_rendering(list(w))
                if cc:
                    alt[CL.head(t, cc)] += n
            head = alt.most_common(1)[0][0] if alt else stem
            how = "form by rule, corpus-checked"
        core = [head] + list(rest) if t["class"] == "verb" else list(rest) + [head]
        return list(pre) + core + list(post), how
