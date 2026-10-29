#!/usr/bin/env python3
"""Rung 4 (2026-10-28): Hebrew OT -> Danish, on our own Danish drafts (export/dan/dan_BSB, CC0) and their .align files (the
drafter's links, bcv-commons format; only verse lines with profile b, i.e. made or checked by an agent, and only chapters whose
text hash matches the draft). The schema of data/ot.db -> data/dan_ot.db; adapted from vamvas/build_ot.py. These are machine
drafts: the engine is measured on reproducing our agents' Danish, not a human translation (Den Frie Bibel comes next).

A Hebrew word gets the Greek positions of its content morpheme (main channel) and of its function morphemes (fn: prefixes,
article, suffixes), with the `+` words that name either. Verses are keyed by their BSB reference (vrs.to_bsb), as data/ot.db;
a verse that shares its BSB verse with another, or is a psalm title, is left out.

Function words (data/dan_func.txt) are DERIVED from the alignment, with no knowledge of Danish: a Danish word is one when in
at least half of its occurrences (and at least 5) it is linked only to Hebrew function morphemes (the fn channel).
    /usr/bin/python3 lab/rules/danish/build_ot.py"""
import collections, json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE); R = os.environ["MAKE_TANAKH_WORK"]
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
sys.path.insert(0, os.path.join(R, "scripts"))
import full_align as FA, ot_routes as OR, vrs  # noqa: E402

OUT = os.path.join(PRIV, "data/dan_ot.db")
PROJ = "dan/dan_BSB"


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
    by_book = collections.defaultdict(list); seen = set()
    for code, ch, txt, al in FA.chapters(PROJ):
        if os.path.exists(al):
            by_book[code.upper()].append((ch, txt, al))
    for book, chs in sorted(by_book.items()):
        keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys"); refs = set(FA.index(book, "lexemes"))
        for ch, txt, al in sorted(chs):
            verses = FA.draft_texts(txt)
            h, rows = FA.read_chapter(al)
            if h != FA.text_hash(ch, verses):
                st["chapters whose .align doesn't match the draft"] += 1; print("skip", book, ch); continue
            text = dict(verses)
            for v, (main_v, fs, prof) in sorted(rows.items()):
                if prof != "b":
                    st["verse lines not profile b"] += 1; continue
                r = f"{book} {ch}:{v}"
                if r not in refs:
                    st["verses not in the Hebrew index"] += 1; continue
                e = vrs.to_bsb(book.lower(), ch, v)
                if not e or e[1] == "title":
                    st["verses left out (title)"] += 1; continue
                ref = f"{book} {int(e[0])}:{int(e[1])}"
                toks = FA.tokenize(text.get(v, ""))
                if not toks or ref not in split:
                    st["verses without text or not in ot.db"] += 1; continue
                if ref in seen:
                    st["verses sharing a BSB verse (second left out)"] += 1; continue
                seen.add(ref)
                if split[ref] == "test":
                    st["verses in the lab's test chapters (left out)"] += 1; continue
                pos = collections.defaultdict(set); kind_of = collections.defaultdict(set)
                add = added(fs)
                for kind, s, ks in (("c", main_v, keys.get(r, [])), ("f", fs, fkeys.get(r, []))):
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
    open(os.path.join(PRIV, "data/dan_func.txt"), "w", encoding="utf-8").write("\n".join(func) + "\n")
    for k, v in st.items():
        db.execute("insert into meta values (?,?)", (k, str(v)))
    db.commit()
    print(dict(st), "function words:", len(func), func[:60])


if __name__ == "__main__":
    main()
