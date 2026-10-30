#!/usr/bin/env python3
"""A rules-engine corpus (the schema of data/ot.db: verse, link, meta) from an align-text layer of an edition, Hebrew OT ->
the edition's text. A Hebrew word gets the positions of its content morpheme (main channel) and of its function morphemes
(fn channel, where the layer has one), with the `+` words naming either, as danish/build_ot.py reads our .align files.
Verses are keyed by their BSB reference (vrs.to_bsb), as data/ot.db; a verse that shares its BSB verse with another, or a
psalm title, is left out. Function words of the edition are DERIVED from the alignment, with no knowledge of the language:
a word is one when in at least half of its occurrences (and at least 5) it is linked only through the fn channel.

    . ./env.sh; /usr/bin/python3 lab/bridge/build_corpus.py --layer LAYERS --edition ED --text TEXT_DIR --out DB
        [--books GEN EXO ...] [--test RUT JON] [--dev GEN:28 JDG:4 ...] [--func FILE]
    LAYERS = align-text's OUT/full-alignments-llm (or OUT/compact); TEXT_DIR = the plain text given to align-text
    (export_edition.py: "c:v text" per line, the spine's numbering)"""
import argparse, collections, glob, json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.environ["MAKE_TANAKH_WORK"]
sys.path.insert(0, os.path.join(R, "scripts")); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "align"))
import full_align as FA, vrs  # noqa: E402
from gold_bsb import added  # noqa: E402


def layer(root, edition, book):
    """{spine verse: {Hebrew word id: (positions, {"c", "f"} kinds)}} from a compact file and its .meta.json fn channel"""
    f = [p for p in glob.glob(os.path.join(root, "*", "*", edition, f"{book}_*.json")) if not p.endswith((".meta.json", ".extra.json"))]
    assert len(f) == 1, (book, f)
    main = json.load(open(f[0])); meta = json.load(open(f[0][:-5] + ".meta.json"))
    fns = meta.get("fn") or [None] * len(main)
    refs = list(FA.index(book, "lexemes")); keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys")
    assert len(refs) == len(main), (book, len(refs), len(main))
    out = {}
    for r, m, fs in zip(refs, main, fns):
        pos = collections.defaultdict(lambda: (set(), set()))
        add = added(m); add.update(added(fs))
        for kind, s, ks in (("c", m, keys.get(r, [])), ("f", fs, fkeys.get(r, []))):
            for o, ids in FA.parse(s).items():
                ids = ids + add.get((kind, o), [])
                for k in (ks[o].split("+") if o < len(ks) and ks[o] else []):
                    pos[k[:-1]][0].update(ids); pos[k[:-1]][1].add(kind)
        out[r] = dict(pos)
    return out


def tokens(text_dir, book):
    out = {}
    for l in open(os.path.join(text_dir, f"{book}.txt"), encoding="utf-8"):
        cv, _, t = l.rstrip("\n").partition(" ")
        out[f"{book} {cv}"] = FA.tokenize(t)
    return out


def main(a):
    if os.path.exists(a.out):
        os.remove(a.out)
    db = sqlite3.connect(a.out)
    db.execute("create table verse(ref text primary key, heb text, book text, ch int, v int, split text, words text)")
    db.execute("create table link(word text primary key, ref text, positions text, supplied text, chunk text, row int)")
    db.execute("create table meta(name text, value text)")
    test = {b.upper() for b in a.test}; dev = {d.upper() for d in a.dev}
    st = collections.Counter(); fnw = collections.defaultdict(collections.Counter); seen = set()
    for book in a.books:
        book = book.upper()
        if not os.path.exists(os.path.join(a.text, f"{book}.txt")):
            st["books without text"] += 1; continue
        L = layer(a.layer, a.edition, book); toks = tokens(a.text, book)
        for r, words in L.items():
            ch, v = (int(x) for x in r.split()[1].split(":"))
            e = vrs.to_bsb(book.lower(), ch, v)
            if not e or e[1] == "title":
                st["verses left out (title)"] += 1; continue
            ref = f"{book} {int(e[0])}:{int(e[1])}"; t = toks.get(r)
            if not t:
                st["verses without text"] += 1; continue
            if ref in seen:
                st["verses sharing a BSB verse (second left out)"] += 1; continue
            seen.add(ref)
            split = "test" if book in test or f"{book}:{ch}" in test else "dev" if f"{book}:{ch}" in dev else "train"
            db.execute("insert into verse values (?,?,?,?,?,?,?)", (ref, r, book, int(e[0]), int(e[1]), split, json.dumps(t, ensure_ascii=False)))
            st["verses"] += 1; st[f"verses {split}"] += 1
            kind_of = collections.defaultdict(set)
            for w, (ps, kinds) in words.items():
                for p in ps:
                    kind_of[p] |= kinds
            for p, kinds in kind_of.items():
                if p < len(t):
                    fnw[t[p].lower()][kinds == {"f"}] += 1
            for n, (w, (ps, _)) in enumerate(sorted(words.items())):
                ps = sorted(p for p in ps if 0 <= p < len(t))
                if ps:
                    st["words linked"] += 1
                    db.execute("insert or ignore into link values (?,?,?,?,?,?)", (w, ref, json.dumps(ps), "[]", " ".join(t[p] for p in ps), n))
    func = sorted(w for w, c in fnw.items() if sum(c.values()) >= 5 and c[True] * 2 >= sum(c.values()))
    if a.func:
        open(a.func, "w", encoding="utf-8").write("\n".join(func) + "\n")
    for k, v in st.items():
        db.execute("insert into meta values (?,?)", (k, str(v)))
    db.execute("insert into meta values (?,?)", ("layer", f"{a.layer} {a.edition}"))
    db.commit()
    print(dict(st), "function words:", len(func), func[:40])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True); ap.add_argument("--edition", required=True); ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--books", nargs="+", default=["RUT", "JON"])
    ap.add_argument("--test", nargs="*", default=[]); ap.add_argument("--dev", nargs="*", default=[]); ap.add_argument("--func")
    main(ap.parse_args())
