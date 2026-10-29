#!/usr/bin/env python3
"""Rung 3: Hebrew OT -> Modern Greek (Neophytos Vamvas 1850, public domain) as the Hebrew engine's corpus
(data/vamvas_ot.db, the schema of data/ot.db), from bcv-commons/full-alignments-llm layer ell_GreVamvas+llm+jev-v4 (CC0; local
copy from setup.py --only vamvas-align, the books whose fingerprint matches our text: scripts/ot_routes.vamvas_check) on our
Vamvas text (import/CC0/ell/vamvas/text/, Hebrew numbering, so a span's positions are tokens of the Hebrew-numbered verse).

A Hebrew word gets the Greek positions of its content morpheme (main channel) and of its function morphemes (fn: prefixes,
article, suffixes), with the `+` words that name either. Verses are keyed by their BSB reference (vrs.to_bsb), as data/ot.db;
a verse that shares its BSB verse with another, or is a psalm title, is left out.

Function words (data/vamvas_func.txt) are DERIVED from the alignment, with no knowledge of Greek: a Greek word is one when in
at least half of its occurrences (and at least 5) it is linked only to Hebrew function morphemes (the fn channel).
    /usr/bin/python3 lab/rules/vamvas/build_ot.py"""
import collections, json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE); R = os.environ["MAKE_TANAKH_WORK"]
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
sys.path.insert(0, os.path.join(R, "scripts"))
import full_align as FA, ot_routes as OR, vrs  # noqa: E402

OUT = os.path.join(PRIV, "data/vamvas_ot.db")


def added(s):
    out = collections.defaultdict(list)
    for e in (s or "").split():
        if e.startswith("+"):
            for part in e[1:].split(","):
                pos, _, own = part.partition(">")
                if not own:
                    continue
                a, _, b = pos.partition("-")
                if a.isdigit() and (not b or b.isdigit()):
                    out[("f" if own.startswith("f") else "c", int(own.lstrip("f")))].extend(range(int(a), int(b or a) + 1))
    return out


def main():
    split = dict(sqlite3.connect(os.path.join(PRIV, "data/ot.db")).execute("select ref, split from verse"))
    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.execute("create table verse(ref text primary key, heb text, book text, ch int, v int, split text, words text)")
    db.execute("create table link(word text primary key, ref text, positions text, supplied text, chunk text, row int)")
    db.execute("create table meta(name text, value text)")
    st = collections.Counter(); fnw = collections.defaultdict(collections.Counter)
    check = OR.vamvas_check()
    for book, (path, mine, theirs, ok) in sorted(check.items()):
        if not ok:
            st["books whose fingerprint differs"] += 1; print("skip", book); continue
        text = {(c, v): t for c, v, t in OR.vamvas_rows(book)}
        main_s = json.load(open(path, encoding="utf-8")); meta = json.load(open(path[:-5] + ".meta.json", encoding="utf-8"))
        fn_s = meta.get("fn") or [""] * len(main_s)
        refs = list(FA.index(book, "lexemes")); keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys")
        bsb = {}
        for r in refs:
            c, v = (int(x) for x in r.split(" ")[1].split(":"))
            e = vrs.to_bsb(book.lower(), c, v)
            if e and e[1] != "title":
                bsb.setdefault((int(e[0]), int(e[1])), []).append(r)
        for i, r in enumerate(refs):
            c, v = (int(x) for x in r.split(" ")[1].split(":"))
            e = vrs.to_bsb(book.lower(), c, v)
            if not e or e[1] == "title" or len(bsb[(int(e[0]), int(e[1]))]) > 1:
                st["verses left out (title, shared)"] += 1; continue
            ref = f"{book} {int(e[0])}:{int(e[1])}"
            toks = FA.tokenize(text.get((c, v), ""))
            if not toks or ref not in split:
                st["verses without text or not in ot.db"] += 1; continue
            pos = collections.defaultdict(set); kind_of = collections.defaultdict(set)
            fs = fn_s[i] if i < len(fn_s) else ""
            add = added(fs)
            for kind, s, ks in (("c", main_s[i], keys.get(r, [])), ("f", fs, fkeys.get(r, []))):
                for o, ids in FA.parse(s).items():
                    ids = ids + add.get((kind, o), [])
                    for k in (ks[o].split("+") if o < len(ks) and ks[o] else []):
                        pos[k[:-1]].update(ids)
                    for p in ids:
                        kind_of[p].add(kind)
            for p, kinds in kind_of.items():
                if p < len(toks):
                    fnw[toks[p].lower()][kinds == {"f"}] += 1
            db.execute("insert into verse values (?,?,?,?,?,?,?)", (ref, r, book, int(e[0]), int(e[1]), split[ref], json.dumps(toks, ensure_ascii=False)))
            st["verses"] += 1
            for n, (w, ps) in enumerate(sorted(pos.items())):
                ps = sorted(p for p in ps if 0 <= p < len(toks))
                if ps:
                    st["words linked"] += 1
                    db.execute("insert or ignore into link values (?,?,?,?,?,?)", (w, ref, json.dumps(ps), "[]", " ".join(toks[p] for p in ps), n))
    func = sorted(w for w, c in fnw.items() if sum(c.values()) >= 5 and c[True] * 2 >= sum(c.values()))
    open(os.path.join(PRIV, "data/vamvas_func.txt"), "w", encoding="utf-8").write("\n".join(func) + "\n")
    for k, v in st.items():
        db.execute("insert into meta values (?,?)", (k, str(v)))
    db.commit()
    print(dict(st), "function words:", len(func), func[:60])


if __name__ == "__main__":
    main()
