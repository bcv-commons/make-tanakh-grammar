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
        for t, pre, core, post, cx in rows:
            h = CL.head(t, core); stem, suf = CL.lemmatize(h)
            rest = CL.rest(t, core) + tuple(post)
            v = t["voice"] if t["class"] == "verb" else None
            self.choice_t[(t["lemma"], v, t["tense"], t["mood"])][(stem, rest)] += 1
            self.choice[(t["lemma"], v)][(stem, rest)] += 1; self.choice_l[t["lemma"]][(stem, rest)] += 1
            self.form[(stem, cellkey(t), pre)][h] += 1; self.form_c[(stem, coarse(t), pre)][h] += 1
            self.suf[(cellkey(t), pre)][suf] += 1; self.suf_c[(coarse(t), pre)][suf] += 1

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
        ct = self.choice_t.get((t["lemma"], v, t["tense"], t["mood"]))
        c = (ct if ct and sum(ct.values()) >= 3 else None) or self.choice.get((t["lemma"], v)) or self.choice_l.get(t["lemma"])
        if not c:
            return None
        (stem, rest), _ = c.most_common(1)[0]
        ref = f"{t['book']} {t['ch']}:{t['v']}"
        cx = self.ctxlex.contexts(ref)[t["key"]]
        p = self.fac.cells.pattern(self.fac.cells.key(t, cx))
        pre = tuple(p[0]) if p else ()
        f = self.form.get((stem, cellkey(t), pre))
        s = self.suf.get((cellkey(t), pre))
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
        core = [head] + list(rest) if t["class"] == "verb" else list(rest) + [head]
        return list(pre) + core, how
