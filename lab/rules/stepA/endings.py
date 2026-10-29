#!/usr/bin/env python3
"""Candidate verb endings the Kuni store doesn't split, for an audit-store pass (Step A, part 3).

Verb words = Kuni NT tokens linked mostly to Greek verbs (morphs.word_classes; >= 3 links, verb share >= 0.6). Each is cut by
the store's segmenter; its stem (tone marks off) is tried as base + ending (ending 1-3 letters, base >= 3 letters). An ending
is a candidate where at least MIN_BASES bases take it and at least one other ending: a paradigm alternation, not a word's
last letters. Endings the store already has as suffixes are left out. Per candidate: tokens, bases, examples, and the Greek
features its linked tokens carry most against all verb tokens (person, number, tense, mood: odds of the share).
Ruth's evidence (verbs.py's 'stem near' pairs, human vs draft) is listed beside it.
    ~/sil-study/.venv/bin/python lab/rules/stepA/endings.py [--out FILE]   (local: Kuni words as examples)"""
import collections, os, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
R = os.environ["MAKE_TANAKH_WORK"]
sys.path.insert(0, os.path.join(R, "scripts"))
MIN_BASES, MIN_TOK = 5, 20
FEATS = ("person", "number", "tense", "mood")


def main(a):
    out = a[a.index("--out") + 1] if "--out" in a else None
    import morphs, grammar, lang, langtools as LT
    pname = "kvg/kvg_BSB"
    P = LT.Project(pname)
    S = morphs.load(pname, P)
    have = {fm.strip("-") for (fm, _), e in morphs.affix_entries(grammar.load(pname)).items() if e["slot"] == "suffix"}
    plain = lambda s: "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))
    wc = morphs.word_classes(pname, P)
    verbs = {w for w, c in wc.items() if c[""] >= 3 and c["verb"] / c[""] >= 0.6}

    def cut(w):
        ms = S.split(w)
        return plain("".join(m.form for m in ms if m.slot == "stem")) or plain(w)

    stem_of = {w: cut(w) for w in verbs}
    tokens = collections.Counter({w: wc[w][""] for w in verbs})
    endings = collections.defaultdict(lambda: collections.defaultdict(set))   # base -> ending -> words
    for w, st in stem_of.items():
        for k in (1, 2, 3):
            if len(st) - k >= 3:
                endings[st[:-k]][st[-k:]].add(w)
    cand = collections.defaultdict(lambda: {"bases": set(), "words": set()})
    for base, es in endings.items():
        if len(es) < 2:
            continue
        for e, ws in es.items():
            cand[e]["bases"].add(base)
            cand[e]["words"] |= ws
    rows = []
    for e, d in cand.items():
        n = sum(tokens[w] for w in d["words"])
        if e in have or len(d["bases"]) < MIN_BASES or n < MIN_TOK:
            continue
        rows.append((e, len(d["bases"]), n, d["words"]))

    # Greek features of the tokens linked to each candidate's words, against all verb tokens
    _, con = lang.connect(pname)
    feat = collections.defaultdict(collections.Counter)
    allf = collections.Counter()
    words_of = collections.defaultdict(set)
    for e, _, _, ws in rows:
        for w in ws:
            words_of[w].add(e)
    for raw, *fv in con.execute(f"""select t.raw, {', '.join('g.' + f for f in FEATS)} from nt_links l join nt_tokens t
            on t.book=l.book and t.ch=l.ch and t.v=l.v and t.pos=l.pos join g.tokens g on g.key=l.key
            where g.class='verb'"""):
        if raw not in verbs:
            continue
        fs = {f"{f}={v}" for f, v in zip(FEATS, fv) if v}
        allf.update(fs | {"*"})
        for e in words_of.get(raw, ()):
            feat[e].update(fs | {"*"})

    def top(e):
        c = feat[e]
        if not c["*"]:
            return ""
        sc = []
        for f, k in c.items():
            if f == "*" or k < 5:
                continue
            p, q = k / c["*"], allf[f] / allf["*"]
            if p > q:
                sc.append((p / q, f, p))
        return ", ".join(f"{f} {p:.0%} (x{o:.1f})" for o, f, p in sorted(sc, reverse=True)[:3])

    rows.sort(key=lambda r: -r[2])
    L = [f"# Candidate verb endings the Kuni store doesn't split (kvg/kvg_BSB; {len(verbs)} verb word types in the NT)",
         f"# store suffixes now: {' '.join('-' + h for h in sorted(have))}; candidate = >= {MIN_BASES} bases with another ending too, >= {MIN_TOK} tokens",
         "", "| ending | bases | tokens | Greek features most raised (share, x vs all verbs) | examples (stem as cut now) |",
         "|---|---|---|---|---|"]
    for e, nb, n, ws in rows:
        ex = sorted(ws, key=lambda w: -tokens[w])[:4]
        L.append(f"| -{e} | {nb} | {n} | {top(e)} | {', '.join(ex)} |")
    txt = "\n".join(L)
    print(txt)
    if out:
        open(out, "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
