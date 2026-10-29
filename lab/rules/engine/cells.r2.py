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
    for i, t in enumerate(toks):
        neg = any(x["lemma"] in NEG for x in by_clause[t["clause"]])
        nxt = toks[i + 1]["class"] if i + 1 < len(toks) else None
        out[t["key"]] = dict(subj=t["clause"] in subj_clause, neg=neg, q=sent.get(t["key"], False), art=t["node"] in art_np,
                             first="verse" if i == 0 else "clause" if first_of[t["clause"]] == t["key"] else "no", next_class=nxt)
    return out


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


def lemmatize(w):
    """English word -> (stem, suffix) by the corpus vocabulary only: a suffix is stripped when the rest is itself a BSB word"""
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
            return ("verb",) + tuple(t[f] for f in VFEAT) + (cx["subj"], cx["neg"], cx["q"])
        return ("noun",) + tuple(t[f] for f in NFEAT) + (cx["art"],)

    def backoff(self, k):
        """the same cell with context features generalised one by one, then dropped"""
        yield k
        if k[0] == "verb":
            yield k[:-1] + (None,)
            yield k[:-2] + (None, None)
            yield k[:-3] + (None, None, None)
        else:
            yield k[:-1] + (None,)

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
