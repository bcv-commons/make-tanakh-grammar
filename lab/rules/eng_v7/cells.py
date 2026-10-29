#!/usr/bin/env python3
"""E1b: contrast tables and the paradigm grid, and E2's cell rules built from them.

A token's BSB rendering is split into pre (function words before the first content word), core (first to last content word)
and post. The core's head word is compared with the lemma's base form (its commonest bare head word): suffix Ø, +s, +ed, +ing,
... or irr. Per cell (class, morph features) and context (explicit subject in the clause, negation, question, article in the
phrase), the grid counts (pre, suffix). Contrasts: two cells that differ in one feature, compared on pre and suffix.
Nothing here knows English: the function-word list is the only English-specific input (it decides what "pre" is), and the
suffixes are read off the data.
    /usr/bin/python3 lab/rules/engine/cells.py   -> lab/rules/results/contrasts.md, grid.json"""
import collections, json, os, sys
# eng_v7 (2026-10-26): eng_v6 + POST_CELL=noun (a noun's words after it from its cell: Greek «η καρδία σου»), Vamvas E6 +2.11 [1.95, 2.28], BSB-OT +0.02, BSB-NT -0.00. eng_v6 (2026-10-26): eng_v5 + the case keys for case languages (FORM_ROLE: the noun's role; GOV_KEY: the word governing it), Vamvas E6 +0.98 [0.87, 1.09], BSB-OT -0.02 [-0.04, 0.01]. eng_v5 (2026-10-26): eng_v4's switches + the learned endings (ENDINGS=hybrid: the English list where it splits, else the
# stems and endings of each source lemma's renderings), on the corpus from lexeme-aligner's BSB layer v1.0 (data/nt_la.db,
# ot_la.db; decided 2026-10-26); an empty value in the environment still turns a switch off
for _k, _v in (("MID_KEYS", "3"), ("CTX_EXTRA", "pron.gov,noun.after_cstr,det.poss"), ("HEB_SFX", "1"), ("LEX_ART", "1"),
               ("CHOICE_CTX", "1"), ("PRE_LEX", "3"), ("ENDINGS", "hybrid"), ("FORM_ROLE", "1"), ("GOV_KEY", "1"), ("POST_CELL", "noun"), ("CORPUS_DB", "data/nt_la.db"), ("OT_DB", "data/ot_la.db")):
    os.environ.setdefault(_k, _v)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import engine as E  # noqa: E402

VFEAT = ("tense", "voice", "mood", "person", "number")
NFEAT = ("gcase", "number")
NEG = {"οὐ", "μή", "οὐδέ", "μηδέ", "οὐκέτι", "μηκέτι", "οὔπω", "μήπω"}


def contexts(C, ref):
    """per token key: context features from the tree"""
    toks = C.tok[ref]; nodes = {n["id"]: n for n in C.nodes.get(ref, [])}
    by_clause = collections.defaultdict(list)
    for t in toks:
        by_clause[t["clause"]].append(t)
    subj_clause = {n["parent"] for n in nodes.values() if n["role"] == "s"} | {t["clause"] for t in toks if t["role"] == "s"}
    # a sentence: tokens up to a final punctuation mark
    sent, cur = {}, []
    for t in toks:
        cur.append(t)
        a = t["after"] or ""
        if any(p in a for p in ".;;·") or t is toks[-1]:
            q = any(p in a for p in ";;")
            for x in cur:
                sent[x["key"]] = q
            cur = []
    art_np = set()
    for t in toks:
        if t["class"] == "det":
            art_np.add(t["node"])
    out = {}
    first_of = {c: min(x["key"] for x in ts) for c, ts in by_clause.items()}
    nodes = {n["id"]: n for n in C.nodes.get(ref, [])}
    P = parts_of(C)
    for i, t in enumerate(toks):
        neg = any(x["lemma"] in NEG for x in by_clause[t["clause"]])
        nxt = toks[i + 1]["class"] if i + 1 < len(toks) else None
        prv = toks[i - 1] if i > 0 else None
        out[t["key"]] = dict(subj=t["clause"] in subj_clause, neg=neg, q=sent.get(t["key"], False), art=t["node"] in art_np,
                             first="verse" if i == 0 else "clause" if first_of[t["clause"]] == t["key"] else "no", next_class=nxt,
                             prev_class=prv["class"] if prv else None, prev_lemma=prv["lemma"] if prv else None,
                             gov=gov(t, toks, nodes), nrule=(nodes.get(t["node"]) or {}).get("rule"),
                             prule=(nodes.get((nodes.get(t["node"]) or {}).get("parent")) or {}).get("rule"))
        if P:
            out[t["key"]].update(P.get(t["key"], {}))
    if P:
        # clause_subj: the participant continuity of the token's clause (its first verb with a subject id): conjunctions
        # (δέ "but" / "and" / none) and others read the switch of subject from it
        cs = {}
        for t in toks:
            if t["class"] == "verb" and P.get(t["key"], {}).get("p_subj") and t["clause"] not in cs:
                cs[t["clause"]] = P[t["key"]]["p_subj"]
        for t in toks:
            out[t["key"]]["clause_subj"] = cs.get(t["clause"])
    return out


def gov(t, toks, nodes):
    """the word's governor in the tree: "prep" (its node, or the node above, is a prepositional phrase), "np" (a noun in the
    same phrase), else other"""
    n = nodes.get(t["node"]) or {}
    if n.get("rule") == "PrepNp" or (nodes.get(n.get("parent")) or {}).get("rule") == "PrepNp":
        return "prep"
    if any(x["node"] == t["node"] and x["class"] == "noun" and x is not t for x in toks):
        return "np"
    return "other"


# EXTRA (env CTX_EXTRA, comma-separated class.field, e.g. "pron.gov,verb.p_subj"): context fields added to the lexicon's
# and the cells' keys; participant fields (engine/parts.py) are loaded only when one is named
EXTRA = [tuple(x.split(".")) for x in os.environ.get("CTX_EXTRA", "").split(",") if x]
_P = []


def parts_of(C):
    if not any(f.startswith("p_") or f in ("clause_subj", "head_ref") for _, f in EXTRA) and os.environ.get("MID_KEYS") != "2":
        return None
    if not _P:
        import parts
        _P.append(parts.load(C))
    return _P[0]


def extra(cls, c):
    return tuple(c.get(f) for k, f in EXTRA if k == cls)


def split_rendering(words):
    w = [x.lower() for x in words]
    idx = [i for i, x in enumerate(w) if x not in E.FUNC]
    if not idx:
        return tuple(w), (), ()
    a, b = idx[0], idx[-1]
    return tuple(w[:a]), tuple(w[a:b + 1]), tuple(w[b + 1:])


def head(t, core):
    """the inflected word of a core: a verb's first content word ("went" out), a noun's last ("unclean" spirit)"""
    return core[0] if t["class"] == "verb" else core[-1]


def rest(t, core):
    return tuple(core[1:]) if t["class"] == "verb" else tuple(core[:-1])


VOCAB = None
ENDS = None        # ENDINGS=learn: the target's endings, learned from its vocabulary (learn_endings), longest first
_LEM = {}
MIN_STEM = int(os.environ.get("MIN_STEM", "2"))
_LISTBASE = None   # ENDINGS=hybrid: the words the hand list gives as bases
STEM_END = None    # stem -> Counter of its endings in the vocabulary (tokens); the stem's commonest ending is its class


def learn_endings(vocab, max_len=4, min_stems=None, top=60):
    """the target's endings from its vocabulary alone, no list for any language: a split w = stem + ending counts when the stem
    (>= 3 letters) occurs with at least two different endings among the corpus words ("" for the bare stem when it is a word
    itself). An ending's score is the number of such stems; the `top` endings with at least `min_stems` stems are kept.
    Sets ENDS and STEM_END (both used by lemmatize)."""
    global ENDS, STEM_END
    _LEM.clear()
    words = [w for w, n in vocab.items() if n >= 2 and len(w) >= 4 and w.isalpha()]
    ends_of = collections.defaultdict(set)
    for w in words:
        for k in range(0, max_len + 1):
            if len(w) - k >= 3:
                ends_of[w[: len(w) - k]].add(w[len(w) - k:])
    score = collections.Counter()
    for st, es in ends_of.items():
        if len(es) >= 2:
            for e in es:
                score[e] += 1
    min_stems = min_stems or max(20, len(words) // 2000)
    ENDS = sorted([e for e, n in score.most_common(top + 1) if e and n >= min_stems], key=len, reverse=True)
    STEM_END = collections.defaultdict(collections.Counter)
    for w in words:
        st, suf = lemmatize(w)
        STEM_END[st][suf] += vocab[w]
    return ENDS, score


STEM_OF = {}       # ENDINGS=learn: target head word -> (stem, ending), from the renderings of one source lemma


def learn_families(heads, base, max_end=4):
    """the target's stems and endings from the parallel data, with no list for any language: the head words that render one
    source lemma and share at least 3 first letters with its base form (both remainders <= max_end letters) are one family;
    the family's stem is the shortest common beginning of its words (love / loved / loving -> lov + e / ed / ing; λόγος /
    λόγου -> λόγ + ος / ου). ENDS = the endings found in at least 5 families, longest first (for words never seen as a head)."""
    global ENDS, STEM_END
    global _LISTBASE
    _LEM.clear(); STEM_OF.clear(); _LISTBASE = None
    STEM_END = collections.defaultdict(collections.Counter)
    fam_ends = collections.Counter(); by_word = collections.defaultdict(collections.Counter)
    import unicodedata
    def bare(w):   # letter by letter without marks, same length (άνθρωπος / ανθρώπου share ανθρωπ)
        return "".join(unicodedata.normalize("NFD", c)[0] for c in w)
    lcp = lambda a, b: len(os.path.commonprefix([bare(a), bare(b)]))
    for lem, hc in heads.items():
        b = base.get(lem)
        if not b:
            continue
        fam = []
        for h, n in hc.items():
            k = lcp(h, b)
            if k >= MIN_STEM and len(h) - k <= max_end and len(b) - k <= max_end and h.isalpha():
                fam.append((h, n))
        if len(fam) < 2:
            continue
        k = min(lcp(h, b) for h, _ in fam)
        st = b[:k]
        for e in {h[k:] for h, _ in fam}:
            fam_ends[e] += 1
        for h, n in fam:
            by_word[h][(st, "+" + h[k:] if h[k:] else "Ø")] += n
            STEM_END[st]["+" + h[k:] if h[k:] else "Ø"] += n
    for h, c in by_word.items():
        STEM_OF[h] = c.most_common(1)[0][0]
    ENDS = sorted([e for e, n in fam_ends.items() if e and n >= 5], key=len, reverse=True)
    return ENDS, fam_ends


def stem_class(stem):
    """a stem's paradigm class for the regular rule: its commonest ending in the corpus (λόγ -> +ος, ημέρ -> +ας)"""
    c = STEM_END.get(stem) if STEM_END else None
    return c.most_common(1)[0][0] if c else None


def lemmatize(w):
    """English word -> (stem, suffix) by the corpus vocabulary only: a suffix is stripped when the rest is itself a BSB word.
    With ENDINGS=learn: the word's family split (learn_families), else the split whose stem has the largest learned paradigm.
    With ENDINGS=hybrid: the hand list where it splits the word or the word is one of its bases, else the family split
    (on a language the list does not fit, e.g. Greek letters, that is the family split alone)"""
    if ENDS is not None and os.environ.get("ENDINGS") == "hybrid":
        global _LISTBASE
        r = _list_lemmatize(w)
        if r[1] != "Ø":
            return r
        if _LISTBASE is None:
            _LISTBASE = {r[0] for r in map(_list_lemmatize, VOCAB) if r[1] != "Ø"}
        if w in _LISTBASE:
            return w, "Ø"
        return STEM_OF.get(w, (w, "Ø"))
    if ENDS is not None:
        if w in STEM_OF:
            return STEM_OF[w]
        if w in _LEM:
            return _LEM[w]
        best, bp = (w, "Ø"), 1
        for e in ENDS:
            if w.endswith(e) and len(w) - len(e) >= 3:
                st = w[: -len(e)]
                # the split whose stem has the largest paradigm (the learned endings it occurs with); a tie keeps the shorter ending
                par = (VOCAB.get(st, 0) >= 2) + sum(VOCAB.get(st + e2, 0) >= 2 for e2 in ENDS)
                if par >= 2 and par > bp:
                    best, bp = (st, "+" + e), par
        _LEM[w] = best
        return best
    return _list_lemmatize(w)


def _list_lemmatize(w):
    for suf, add in (("ies", "y"), ("ied", "y"), ("ing", ""), ("ing", "e"), ("ed", ""), ("ed", "e"), ("es", ""), ("s", ""), ("d", ""),
                     ("est", ""), ("eth", ""), ("eth", "e")):
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            b = w[: -len(suf)] + add
            if b in VOCAB and VOCAB[b] >= 3:
                return b, "+" + suf
    return w, "Ø"


def suffix(head, base):
    if VOCAB is not None:
        return lemmatize(head)[1]
    if head == base:
        return "Ø"
    for cut in (0, 1):  # base "love" -> "loved": drop a final e
        b = base[:-cut] if cut else base
        if cut and not base.endswith("e"):
            continue
        if head.startswith(b) and len(head) - len(b) <= 4:
            return "+" + head[len(b):]
    if base.endswith("y") and head.startswith(base[:-1]) and head[len(base) - 1:] in ("ies", "ied"):
        return "+" + head[len(base) - 1:]
    return "irr"


def apply_suffix(base, suf):
    if suf == "Ø":
        return base
    s = suf[1:]
    if ENDS is not None and os.environ.get("ENDINGS") != "hybrid":   # learned endings: a stem and its ending, nothing else
        return base + s
    if s in ("ies", "ied") and base.endswith("y"):
        return base[:-1] + s
    if base.endswith("e") and s[:1] in ("e", "i"):
        return base[:-1] + s
    return base + s


class Cells:
    def __init__(self, C, refs):
        global VOCAB
        VOCAB = collections.Counter(w.lower() for v in C.verses.values() for w in v["words"])
        self.C = C
        self.ctx = {}
        heads = collections.defaultdict(collections.Counter)
        rows = []
        for ref in refs:
            cx = contexts(C, ref); self.ctx.update(cx)
            for t in C.tok[ref]:
                r = C.rendering(ref, t)
                if r is None or t["class"] not in ("verb", "noun"):
                    continue
                pre, core, post = split_rendering(r)
                if not core:
                    continue
                rows.append((t, pre, core, post, cx[t["key"]]))
                heads[t["lemma"]][head(t, core)] += 1
        # base form: the commonest head among the plainest cells (verb: present, not 3S; noun: nominative singular), else commonest
        plain = collections.defaultdict(collections.Counter)
        for t, pre, core, post, cx in rows:
            if (t["class"] == "verb" and t["tense"] == "present" and not (t["person"] == "third" and t["number"] == "singular")) or \
               (t["class"] == "noun" and t["number"] == "singular"):
                plain[t["lemma"]][head(t, core)] += 1
        self.base = {l: (plain[l] or c).most_common(1)[0][0] for l, c in heads.items()}
        if os.environ.get("ENDINGS") in ("learn", "hybrid"):
            learn_families(heads, self.base)
        self.core = {}
        cc = collections.defaultdict(collections.Counter)
        for t, pre, core, post, cx in rows:
            cc[t["lemma"]][rest(t, core)] += 1
        self.core = {l: c.most_common(1)[0][0] for l, c in cc.items()}  # the core's other words ("went" + "out", "unclean" + "spirit")
        self.grid = collections.defaultdict(collections.Counter)
        for t, pre, core, post, cx in rows:
            self.grid[self.key(t, cx)][(pre, suffix(head(t, core), self.base[t["lemma"]]), post)] += 1
        self.rows = rows

    def key(self, t, cx):
        if t["class"] == "verb":
            return ("verb",) + tuple(t[f] for f in VFEAT) + (cx["subj"], cx["neg"], cx["q"]) + extra("verb", cx)
        return ("noun",) + tuple(t[f] for f in NFEAT) + (cx["art"],) + extra("noun", cx)

    def backoff(self, k):
        """the same cell with context features generalised one by one, then dropped"""
        yield k
        n = (3 if k[0] == "verb" else 1) + len(extra(k[0], {}))
        for i in range(1, n + 1):
            yield k[:-i] + (None,) * i

    def pattern(self, k):
        for b in self.backoff(k):
            if None in b:
                c = collections.Counter()
                for kk, v in self.grid.items():
                    if all(x is None or x == y for x, y in zip(b, kk)):
                        c.update(v)
            else:
                c = self.grid.get(b)
            if c and sum(c.values()) >= 3:
                return c.most_common(1)[0][0]
        return None

    def render(self, t):
        if t["class"] not in ("verb", "noun") or t["lemma"] not in self.base:
            return None
        cx = self.ctx.get(t["key"])
        if cx is None:
            ref = f"{t['book']} {t['ch']}:{t['v']}"
            self.ctx.update(contexts(self.C, ref)); cx = self.ctx[t["key"]]
        p = self.pattern(self.key(t, cx))
        if p is None:
            return None
        pre, suf, post = p
        base = self.base[t["lemma"]]
        head = base if suf == "irr" else apply_suffix(base, suf)
        if suf == "irr":  # an irregular cell: the lemma's own commonest head in that cell, if seen
            seen = collections.Counter(head(tt, core) for tt, pr, core, po, c in self.rows if tt["lemma"] == t["lemma"] and
                                       self.key(tt, c)[:6] == self.key(t, cx)[:6])
            if seen:
                head = seen.most_common(1)[0][0]
        other = list(self.core.get(t["lemma"], ()))
        core = [head] + other if t["class"] == "verb" else other + [head]
        return list(pre) + core + list(post)


def contrast_tables(cells, out):
    G = cells.grid
    lines = ["# Contrast tables (E1b), Greek NT -> BSB, training split", "",
             "Per feature: two cells equal in every other feature and context, compared on the function words before the word",
             "(pre) and on the head word's suffix against the lemma's base form. Counts are tokens; 'top' is the commonest pattern.", ""]
    feats = {"verb": list(VFEAT) + ["subj", "neg", "q"], "noun": list(NFEAT) + ["art"]}
    summary = {}
    for cls, fs in feats.items():
        for i, f in enumerate(fs, start=1):
            pairs = collections.defaultdict(lambda: [collections.Counter(), collections.Counter(), 0])
            ks = [k for k in G if k[0] == cls]
            index = collections.defaultdict(list)
            for k in ks:
                index[k[:i] + k[i + 1:]].append(k)
            for rest, group in index.items():
                for a in group:
                    for b in group:
                        if str(a[i]) < str(b[i]):
                            na, nb = sum(G[a].values()), sum(G[b].values())
                            if na < 3 or nb < 3:
                                continue
                            pa = G[a].most_common(1)[0][0]; pb = G[b].most_common(1)[0][0]
                            d = pairs[(a[i], b[i])]
                            d[0][(pa[0], pa[1])] += na; d[1][(pb[0], pb[1])] += nb; d[2] += 1
            lines += [f"## {cls}: {f}", "", "| A | B | cell pairs | A's top patterns (pre, suffix) | B's top patterns |", "|---|---|---|---|---|"]
            rows = sorted(pairs.items(), key=lambda kv: -kv[1][2])[:8]
            for (va, vb), (ca, cb, n) in rows:
                fmt = lambda c: "; ".join(f"{' '.join(p) or '–'} / {s} ({k})" for (p, s), k in c.most_common(3))
                lines.append(f"| {va} | {vb} | {n} | {fmt(ca)} | {fmt(cb)} |")
                summary[f"{cls}:{f}:{va}|{vb}"] = dict(pairs=n, a=ca.most_common(3), b=cb.most_common(3))
            lines.append("")
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return summary


def main():
    C = E.Corpus(); train = C.split("train")
    cl = Cells(C, train)
    res = os.path.join(E.PRIV, "results"); os.makedirs(res, exist_ok=True)
    s = contrast_tables(cl, os.path.join(res, "contrasts.md"))
    grid = {" ".join(map(str, k)): [[" ".join(p[0]), p[1], " ".join(p[2]), n] for p, n in v.most_common(5)] for k, v in cl.grid.items()}
    json.dump(grid, open(os.path.join(res, "grid.json"), "w"), indent=1, ensure_ascii=False)
    print(len(cl.grid), "cells;", len(cl.base), "lemmas with a base form;", len(s), "contrast pairs")


if __name__ == "__main__":
    main()
