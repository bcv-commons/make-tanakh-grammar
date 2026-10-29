#!/usr/bin/env python3
"""The rules engine, rung 1 (Greek NT -> English, BSB), and its component measures. No LLM anywhere.

Pieces (each a data table learned or written, applied deterministically):
  tree      MACULA's tree per verse (orig/grc.sqlite nodes + tokens): children of a node = sub-nodes and tokens, by first key
  lexicon   per Greek token: (lemma, morph) -> English rendering (word list), backing off to (lemma); learned from the BSB tables
  order     per tree node: (rule, child labels) -> the English order of the children; learned from the aligned positions
  cells     (E1b/E2) per morph cell: a template over the lemma's base form (contrast tables)
Measures (against the BSB's own alignment, never against an LLM): coverage, word choice, form, function words, order (Kendall
tau), and chrF as a summary only.
    /usr/bin/python3 lab/rules/engine/engine.py e1|e2 [dev|test]"""
import collections, itertools, json, math, os, re, sqlite3, sys
# eng_v9 defaults (the same block as cells.py; set here too: the corpus path is read when this module is imported)
for _k, _v in (("MID_KEYS", "3"), ("CTX_EXTRA", "pron.gov,noun.after_cstr,det.poss"), ("HEB_SFX", "1"), ("LEX_ART", "1"),
               ("CHOICE_CTX", "1"), ("PRE_LEX", "3"), ("ENDINGS", "hybrid"), ("FORM_ROLE", "1"), ("GOV_KEY", "1"), ("POST_CELL", "noun"), ("PREFIXES", "auto"), ("PRE_FN", "auto"), ("ART", "learn"), ("CORPUS_DB", "data/nt_la.db"), ("OT_DB", "data/ot_la.db")):
    os.environ.setdefault(_k, _v)
R = os.environ["MAKE_TANAKH_WORK"]
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE)
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
NT = os.path.join(PRIV, os.environ.get("CORPUS_DB", "data/nt.db")); G = os.path.join(R, "orig/grc.sqlite")

FUNC = set("""the a an of to in on at by for with from into upon about through over under and but or nor so yet if that which who
whom whose what when where why how not no is are was were be been being am do does did have has had will would shall should may
might can could must he she it they we you i me him her them us his its their our your my mine yours this these those there here
as than then also even all any some one ones because while until before after since though although let lets""".split())
if os.environ.get("FUNC_FILE"):
    # another target language: its function words (parts) from a derived list, replacing the English one
    FUNC = set(open(os.path.join(PRIV, os.environ["FUNC_FILE"]), encoding="utf-8").read().split())
if os.environ.get("FUNC_KJV"):
    # rung 1c: the KJV's own function words (pronouns, verb forms, prepositions it uses where the BSB does not)
    FUNC |= set("""thou thee thy thine ye art hast hath dost doth didst wast wert shalt wilt canst couldest wouldest shouldest
mayest mightest unto lest whither whence thither hither wherefore therefore yea nay""".split())
CONTENT = {"noun", "verb", "adj", "adv"}


def stem(w):
    w = w.lower()
    for suf in ("ing", "eth", "est", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


# ---------- data ----------

class Corpus:
    def __init__(self):
        self.n = sqlite3.connect(NT); self.g = sqlite3.connect(G)
        self.verses = {r[0]: dict(ref=r[0], book=r[1], ch=r[2], v=r[3], split=r[4], words=json.loads(r[5]))
                       for r in self.n.execute("select ref, book, ch, v, split, words from verse")}
        self.link = {k: (json.loads(p), set(json.loads(s)), c) for k, p, s, c in self.n.execute("select key, positions, supplied, chunk from link")}
        cols = [r[1] for r in self.g.execute("pragma table_info(tokens)")]
        self.tok = collections.defaultdict(list)
        for r in self.g.execute("select * from tokens order by key"):
            t = dict(zip(cols, r)); self.tok[f"{t['book']} {t['ch']}:{t['v']}"].append(t)
        ncols = [r[1] for r in self.g.execute("pragma table_info(nodes)")]
        self.nodes = collections.defaultdict(list)
        for r in self.g.execute("select * from nodes"):
            d = dict(zip(ncols, r)); self.nodes[f"{d['book']} {d['ch']}:{d['v']}"].append(d)

    def split(self, name):
        return [r for r, v in self.verses.items() if v["split"] == name]

    def rendering(self, ref, t):
        """the BSB words of token t (in verse order), or None when the token has no link"""
        l = self.link.get(t["key"])
        if not l:
            return None
        w = self.verses[ref]["words"]
        return [w[i] for i in l[0]]

    def tree(self, ref):
        """roots (list) of nested dicts: node = {id, rule, role, cls, kids}; leaf = {tok}; kids in source order"""
        nodes = {n["id"]: dict(id=n["id"], rule=n["rule"], role=n["role"], cls=n["class"], kids=[], first=n["first"]) for n in self.nodes.get(ref, [])}
        roots = []
        for n in self.nodes.get(ref, []):
            (nodes[n["parent"]]["kids"] if n["parent"] in nodes else roots).append(nodes[n["id"]])
        loose = []
        for t in self.tok[ref]:
            leaf = dict(tok=t, first=t["key"])
            (nodes[t["node"]]["kids"] if t["node"] in nodes else loose).append(leaf)
        for n in nodes.values():
            n["kids"].sort(key=lambda k: k["first"])
        roots = sorted(roots + loose, key=lambda k: k["first"])
        return roots


def leaves(n):
    if "tok" in n:
        yield n["tok"]
    else:
        for k in n["kids"]:
            yield from leaves(k)


def label(n):
    if "tok" in n:
        return f"{n['tok']['role'] or ''}:{n['tok']['class']}"
    return f"{n['role'] or ''}:{n['cls'] or n['rule']}"


# ---------- learning ----------

def learn_lexicon(C, refs):
    lex = collections.defaultdict(collections.Counter); lem = collections.defaultdict(collections.Counter)
    for ref in refs:
        for t in C.tok[ref]:
            r = C.rendering(ref, t)
            if r is None:
                continue
            w = tuple(x.lower() for x in r)
            lex[(t["lemma"], t["morph"])][w] += 1; lem[t["lemma"]][w] += 1
    return lex, lem


def learn_order(C, refs, min_n=3):
    """(rule, labels) -> permutation; the English order of a node's children by the first aligned position under each child"""
    perm = collections.defaultdict(collections.Counter)
    for ref in refs:
        def anchor(n):
            ps = [p for t in leaves(n) for p in (C.link.get(t["key"], ([], set(), ""))[0])]
            return min(ps) if ps else None
        def walk(n):
            if "tok" in n:
                return
            kids = n["kids"]
            if len(kids) >= 2:
                a = [anchor(k) for k in kids]
                if all(x is not None for x in a):
                    p = tuple(sorted(range(len(kids)), key=lambda i: (a[i], i)))
                    perm[(n["rule"], tuple(label(k) for k in kids))][p] += 1
            for k in kids:
                walk(k)
        for r in C.tree(ref):
            walk(r)
    rules = {}
    for key, c in perm.items():
        p, k = c.most_common(1)[0]
        tot = sum(c.values())
        if k >= min_n and k / tot >= 0.5 and p != tuple(range(len(p))):
            rules[key] = dict(perm=p, n=k, of=tot)
    return rules


class CtxLex:
    """E3: the lexicon as a decision list over context (most specific key seen at least twice wins):
    (lemma, morph, ctx) -> (lemma, morph) -> (lemma, ctx) -> (lemma). ctx per class: verb (explicit subject, negation, question),
    noun (article, case), article (its head noun's lemma, a demonstrative in the phrase), pronoun (case, the clause's subject)."""
    def __init__(self, C, refs, min_n=2):
        import cells as CL
        self.C, self.CL, self.min_n = C, CL, min_n
        self.cx = {}
        self.tab = [collections.defaultdict(collections.Counter) for _ in range(4)]
        self.mid = collections.defaultdict(collections.Counter)   # MID_KEYS: steps between (lemma, morph, ctx) and (lemma, morph)
        for ref in refs:
            cx = self.contexts(ref)
            for t in C.tok[ref]:
                r = C.rendering(ref, t)
                if r is None:
                    continue
                w = tuple(x.lower() for x in r)
                for i, k in enumerate(self.keys(t, cx[t["key"]])):
                    self.tab[i][k][w] += 1
                for k in self.mid_keys(t, cx[t["key"]]):
                    self.mid[k][w] += 1

    def contexts(self, ref):
        if ref in self.cx:
            return self.cx[ref]
        cx = self.CL.contexts(self.C, ref)
        toks = self.C.tok[ref]
        by_node = collections.defaultdict(list)
        for t in toks:
            by_node[t["node"]].append(t)
        self.CL.add_pre_fn(cx, toks)
        for t in toks:
            c = cx[t["key"]]
            if t["class"] == "det":
                nn = [x for x in by_node[t["node"]] if x["class"] == "noun"]
                c["head"] = nn[0]["lemma"] if nn else None
                c["head_ref"] = cx[nn[0]["key"]].get("p_ref") if nn else None   # the head noun's referent seen before (parts.py)
                c["head_type"] = nn[0].get("type") if nn else None             # proper / common: "Jesus", not "the Jesus"
                i = toks.index(t)
                c["poss"] = any(x["class"] == "pron" and x["gcase"] == "genitive" and x.get("type") == "personal"
                                for x in toks[i + 1:i + 4])                       # ὁ πατήρ μου: "my father", no "the"
                c["demo"] = any(x["morph"].startswith("D-") for x in toks if x["node"] in (t["node"],))
        self.cx[ref] = cx
        return cx

    @staticmethod
    def ctx(t, c):
        import cells as CL
        return CtxLex.ctx0(t, c) + CL.extra(t["class"], c)

    @staticmethod
    def ctx0(t, c):
        k = t["class"]
        if k == "verb":
            return (c["subj"], c["neg"], c["q"])
        if k == "noun":
            return (c["art"], t["gcase"])
        if k == "det":
            return (c.get("head"), c.get("demo"), c.get("next_class"))
        if k == "pron":
            return (t["gcase"], c["subj"])
        if k == "conj":
            return (c.get("first"),)
        if k in ("adv", "prep"):
            return (c.get("next_class"),)
        return ()

    def keys(self, t, c):
        x = self.ctx(t, c)
        return [(t["lemma"], t["morph"], x), (t["lemma"], t["morph"]), (t["lemma"], x), (t["lemma"],)]

    @staticmethod
    def mid_keys(t, c):
        """env MID_KEYS=1: intermediate steps for the article, each one feature of its context kept: its head noun (English
        keeps or drops "the" by the noun: "the Sanhedrin", "God"), and its case with the phrase's tree rule (a dependent
        genitive's "of the", none under a preposition)"""
        if not os.environ.get("MID_KEYS") or t["class"] != "det":
            return []
        ks = [("m1", t["lemma"], t["gcase"], c.get("head"), c.get("prule")), ("m2", t["lemma"], t["gcase"], c.get("head")),
              ("m3", t["lemma"], t["gcase"], c.get("prule"))]
        if os.environ.get("MID_KEYS") == "3":   # a possessive pronoun after it, the head noun proper or common
            ks = [("q1", t["lemma"], t["gcase"], c.get("head"), c.get("poss")),
                  ("q2", t["lemma"], t["gcase"], c.get("poss"), c.get("head_type"), c.get("prule"))] + ks + \
                 [("q3", t["lemma"], t["gcase"], c.get("poss"), c.get("head_type"))]
        if os.environ.get("MID_KEYS") == "2":   # the head noun's referent: mentioned before ("the") or new
            ks = [("r1", t["lemma"], t["gcase"], c.get("head"), c.get("head_ref"))] + ks + [("r2", t["lemma"], t["gcase"], c.get("prule"), c.get("head_ref"))]
        return ks

    def render(self, t):
        ref = f"{t['book']} {t['ch']}:{t['v']}"
        c = self.contexts(ref)[t["key"]]
        ks = self.keys(t, c)
        steps = [(self.tab[0], ks[0], "ctx0")] + [(self.mid, k, k[0]) for k in self.mid_keys(t, c)] + \
            [(self.tab[i], ks[i], f"ctx{i}") for i in (1, 2, 3)]
        for tab, k, how in steps:
            cnt = tab.get(k)
            if cnt and (sum(cnt.values()) >= self.min_n or how == "ctx3"):
                return list(cnt.most_common(1)[0][0]), how
        return None


class Factored:
    """E4: verbs and nouns rendered in two parts. core + post: the lemma's own (lemma, morph) -> (lemma) commonest core;
    pre: the cell's pattern (class, morph features, context) shared by all lemmas, from the grid of cells.py, with backoff.
    A lemma keeps its own pre only where it is clearly lemma-bound (seen >= 5 times, >= 70% the same, and unlike the cell)."""
    def __init__(self, C, refs, ctxlex):
        import cells as CL
        self.CL, self.ctxlex = CL, ctxlex
        self.cells = CL.Cells(C, refs)
        self.core = [collections.defaultdict(collections.Counter) for _ in range(2)]
        self.pre_l = collections.defaultdict(collections.Counter)
        for t, pre, core, post, cx in self.cells.rows:
            self.core[0][(t["lemma"], t["morph"])][core + post] += 1
            self.core[1][t["lemma"]][core + post] += 1
            self.pre_l[(t["lemma"], t["morph"])][pre] += 1

    def render(self, t):
        if t["class"] not in ("verb", "noun"):
            return None
        ref = f"{t['book']} {t['ch']}:{t['v']}"
        cx = self.ctxlex.contexts(ref)[t["key"]]
        c = self.core[0].get((t["lemma"], t["morph"])) or self.core[1].get(t["lemma"])
        if not c:
            return None
        core = list(c.most_common(1)[0][0])
        p = self.cells.pattern(self.cells.key(t, cx))
        pre = list(p[0]) if p else []
        pl = self.pre_l.get((t["lemma"], t["morph"]))
        if pl:
            top, n = pl.most_common(1)[0]
            if n >= 5 and n / sum(pl.values()) >= 0.7 and list(top) != pre:
                pre = list(top)
        return pre + core, "factored"


# ---------- generation ----------

class Engine:
    def __init__(self, lex, lem, order=None, cells=None):
        self.lex, self.lem, self.order, self.cells = lex, lem, order or {}, cells
        self.trace = []

    def consistent(self, t, mem, r6):
        """E8 (memory_mode "pre" / "lex"): the memory's rendering is used only when its function words are E6's (the cell
        rule), and for "lex" also its head is a form of E6's English word (any form of that stem seen in the corpus)"""
        import cells as CL
        mp, mc, _ = CL.split_rendering(mem); rp, rc, _ = CL.split_rendering(r6)
        if mp != rp or not mc or not rc:
            return False
        if self.memory_mode == "pre":
            return True
        if not hasattr(self, "_stem_heads"):
            self._stem_heads = collections.defaultdict(set)
            for (stem, _, _), c in self.gen6.form.items():
                self._stem_heads[stem].update(c)
        stem6 = CL.lemmatize(CL.head(t, rc))[0]
        h = CL.head(t, mc)
        return CL.lemmatize(h)[0] == stem6 or h in self._stem_heads.get(stem6, ())

    def render(self, t):
        if getattr(self, "gen6", None):
            mem = None
            if getattr(self, "memory_first", False) or getattr(self, "memory_mode", None):
                ref = f"{t['book']} {t['ch']}:{t['v']}"
                k = self.ctxlex.keys(t, self.ctxlex.contexts(ref)[t["key"]])[0]
                cnt = self.ctxlex.tab[0].get(k)
                if cnt and sum(cnt.values()) >= 2:
                    mem = list(cnt.most_common(1)[0][0])
                    if not getattr(self, "memory_mode", None):
                        return mem, "ctx0"
            r = self.gen6.render(t)
            if mem is not None and r and self.consistent(t, mem, r[0]):
                return mem, "ctx0 (agrees with e6)"
            if r:
                return r
        if getattr(self, "factored", None):
            if getattr(self, "ctx_first", False) and self.ctxlex:
                ref = f"{t['book']} {t['ch']}:{t['v']}"
                k = self.ctxlex.keys(t, self.ctxlex.contexts(ref)[t["key"]])[0]
                cnt = self.ctxlex.tab[0].get(k)
                if cnt and sum(cnt.values()) >= 2:
                    return list(cnt.most_common(1)[0][0]), "ctx0"
            r = self.factored.render(t)
            if r:
                return r
        if getattr(self, "ctxlex", None):
            r = self.ctxlex.render(t)
            if r:
                return r
        c = self.lex.get((t["lemma"], t["morph"]))
        if c:
            return list(c.most_common(1)[0][0]), "lex"
        if self.cells:
            r = self.cells(t)
            if r is not None:
                return r, "cell"
        c = self.lem.get(t["lemma"])
        if c:
            return list(c.most_common(1)[0][0]), "lemma"
        return [f"<{t['lemma']}>"], "unk"

    def linear(self, n):
        if "tok" in n:
            return [n["tok"]]
        kids = n["kids"]
        r = self.order.get((n["rule"], tuple(label(k) for k in kids)))
        if r and len(r["perm"]) == len(kids):
            kids = [kids[i] for i in r["perm"]]
            self.trace.append(("order", n["rule"]))
        return [t for k in kids for t in self.linear(k)]

    def verse(self, C, ref):
        toks = [t for r in C.tree(ref) for t in self.linear(r)]
        out, at = [], {}
        for t in toks:
            w, how = self.render(t)
            at[t["key"]] = (len(out), len(w), how)
            out += [x for x in w if x != "-"]
        return out, at


# ---------- measures ----------

def kendall(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    c = d = 0
    for i, j in itertools.combinations(range(n), 2):
        s = (xs[i] - xs[j]) * (ys[i] - ys[j])
        c += s > 0; d += s < 0
    return (c - d) / (c + d) if c + d else None


def measure(C, eng, refs):
    M = collections.Counter(); taus = []; hyps, refs_txt = [], []
    for ref in refs:
        out, at = eng.verse(C, ref)
        words = C.verses[ref]["words"]
        hyps.append(" ".join(out)); refs_txt.append(" ".join(words))
        # tokens
        xs, ys = [], []
        for t in C.tok[ref]:
            r = C.rendering(ref, t)
            pos, n, how = at[t["key"]]
            M["tokens"] += 1; M[f"how {how}"] += 1
            if r is None:
                continue
            gw = [w.lower() for w in r]
            ew = [w.lower() for w in out[pos:pos + n]] if n else []
            if t["class"] in CONTENT:
                gc = [w for w in gw if w not in FUNC]; ec = [w for w in ew if w not in FUNC]
                if gc:
                    M["content"] += 1
                    M["choice"] += bool({stem(w) for w in gc} & {stem(w) for w in ec})
                    M["form"] += gc == ec
            M["rendering exact"] += gw == ew
            l = C.link.get(t["key"])
            if l and l[0] and n:
                xs.append(pos); ys.append(min(l[0]))
        k = kendall(xs, ys)
        if k is not None:
            taus.append(k)
        fe = collections.Counter(w.lower() for w in out if w.lower() in FUNC)
        fr = collections.Counter(w.lower() for w in words if w.lower() in FUNC)
        M["func tp"] += sum((fe & fr).values()); M["func e"] += sum(fe.values()); M["func r"] += sum(fr.values())
    res = {"verses": len(refs), "tokens": M["tokens"],
           "coverage (lemma known)": round(1 - M["how unk"] / M["tokens"], 4),
           "word choice (content, stem)": round(M["choice"] / M["content"], 4),
           "form (content, exact)": round(M["form"] / M["content"], 4),
           "rendering exact (all tokens)": round(M["rendering exact"] / M["tokens"], 4),
           "function words P": round(M["func tp"] / max(1, M["func e"]), 4),
           "function words R": round(M["func tp"] / max(1, M["func r"]), 4),
           "order tau (mean per verse)": round(sum(taus) / len(taus), 4),
           "how": {k[4:]: v for k, v in M.items() if k.startswith("how ")}}
    try:
        import sacrebleu
        res["chrF (summary)"] = round(sacrebleu.corpus_chrf(hyps, [refs_txt]).score, 2)
    except ImportError:
        pass
    return res, hyps


def main():
    stage = sys.argv[1]; part = sys.argv[2] if len(sys.argv) > 2 else "dev"
    C = Corpus()
    train = C.split("train")
    pool = os.environ.get("TRAIN", "nt")
    books = {"mrk": {"MRK"}, "gospels": {"MRK", "MAT", "LUK", "JHN"}, "nogospels": None, "nt": None}[pool]
    if pool == "nogospels":
        train = [r for r in train if C.verses[r]["book"] not in {"MAT", "LUK", "JHN"}]
    elif books:
        train = [r for r in train if C.verses[r]["book"] in books]
    lex, lem = learn_lexicon(C, train)
    order = learn_order(C, train) if stage in ("e2", "e2c", "e3", "e4", "e5", "e6", "e7") else None
    cells = None
    if stage == "e2c":
        sys.path.insert(0, HERE); import cells as CL
        cells = CL.Cells(C, train).render
    sys.path.insert(0, HERE)
    eng = Engine(lex, lem, order, cells)
    if stage in ("e3", "e4", "e5", "e6", "e7"):
        eng.ctxlex = CtxLex(C, train)
    if stage in ("e4", "e5", "e6", "e7"):
        eng.factored = Factored(C, train, eng.ctxlex)
        eng.ctx_first = stage in ("e5", "e6", "e7")
    if stage in ("e6", "e7"):
        import gen6
        eng.gen6 = gen6.Gen6(C, train, eng.ctxlex, eng.factored)
        eng.memory_first = stage == "e7"
    res, hyps = measure(C, eng, C.split(part))
    if order is not None:
        res["order rules"] = len(order)
    out = os.path.join(PRIV, "results"); os.makedirs(out, exist_ok=True)
    tag = f"{stage}_{part}" + ("" if pool == "nt" else f"_{pool}")
    res["train verses"] = len(train)
    json.dump(res, open(os.path.join(out, f"{tag}.json"), "w"), indent=1, ensure_ascii=False)
    with open(os.path.join(out, f"{tag}.txt"), "w", encoding="utf-8") as f:
        for ref, h in zip(C.split(part), hyps):
            f.write(f"{ref}\t{h}\n")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
