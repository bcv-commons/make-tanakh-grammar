#!/usr/bin/env python3
"""Rung 1b data: Hebrew OT -> BSB, from the BSB Translation Tables (bcv-query's copy), as build.py does for the NT.
The tables align whole Hebrew words (prefixes and suffixes included); MACULA Hebrew (orig/heb.sqlite) splits words into
morphemes (key = word id + part). The unit here is the Hebrew word: its MACULA morphemes, with their lemmas and features, and
the table's English chunk. Hebrew verse numbers are kept (the drafting convention); the BSB verse is found by orig/vrs.
    /usr/bin/python3 lab/rules/data/build_ot.py   -> $MAKE_TANAKH_PRIVATE/rules/data/ot.db"""
import collections, csv, difflib, json, os, re, sqlite3, sys, unicodedata
R = os.environ["MAKE_TANAKH_WORK"]; sys.path.insert(0, os.path.join(R, "scripts"))
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
from full_align import tokenize  # noqa: E402
import vrs  # noqa: E402
from build import chunk_words, bsb_verses, TABLES  # noqa: E402
csv.field_size_limit(10**9)
DEV = {("GEN", 3), ("GEN", 24)}
TEST = {("GEN", 22), ("GEN", 37), ("GEN", 44)}


def cons(w):
    """consonants only: niqqud, cantillation, maqaf and punctuation dropped"""
    return "".join(c for c in unicodedata.normalize("NFD", w) if "א" <= c <= "ת")


def main():
    names = {l.split("\t")[1]: l.split("\t")[0].upper() for l in open(os.path.join(R, "books.tsv"), encoding="utf-8").read().splitlines()[1:]}
    names.update({"Psalm": "PSA"})
    rows = collections.defaultdict(list); vid = None
    for row in csv.reader(open(TABLES, encoding="utf-8"), delimiter="\t"):
        if row[0] == "Heb Sort":
            continue
        if row[12].strip():
            vid = row[12].strip()
        if row[4] == "Hebrew" and row[5].strip():
            rows[vid].append((float(row[0]), int(row[2]), row[5].strip(), row[10].strip(), row[18].strip()))
    h = sqlite3.connect(os.path.join(R, "orig/heb.sqlite"))
    words = collections.defaultdict(list)       # BSB ref -> [(word id, text, heb ref)]
    for key, book, ch, v, text in h.execute("select key, book, ch, v, text from tokens order by key"):
        bch = vrs.to_bsb(book.lower(), ch, v)
        if not bch or bch[1] == "title":
            continue
        ref = f"{book} {bch[0]}:{bch[1]}"
        wid = key[:-1]
        w = words[ref]
        if w and w[-1][0] == wid:
            w[-1] = (wid, w[-1][1] + text, w[-1][2])
        else:
            w.append((wid, text, f"{book} {ch}:{v}"))
    db = os.path.join(PRIV, "data", "ot.db")
    if os.path.exists(db):
        os.remove(db)
    o = sqlite3.connect(db)
    o.executescript("""create table verse(ref text primary key, heb text, book text, ch int, v int, split text, words text);
        create table link(word text primary key, ref text, positions text, supplied text, chunk text, row int);
        create table meta(name text, value text);""")
    st = collections.Counter()
    for vid_, rr in rows.items():
        m = re.match(r"(.+) (\d+):(\d+)$", vid_)
        code = names.get(m[1])
        if not code:
            st["book?"] += 1; continue
        ch, v = int(m[2]), int(m[3])
        ref = f"{code} {ch}:{v}"
        try:
            text = bsb_verses(code.lower(), ch)[v]
        except (KeyError, FileNotFoundError):
            st["verse unread"] += 1; continue
        vw = tokenize(text)
        pos, sup, k = {}, {}, 0
        order = sorted(rr, key=lambda r: r[1])
        for hs, bs, w, s, en in order:
            cw = chunk_words(en)
            pos[hs] = list(range(k, k + len(cw))); sup[hs] = [i for i, (_, f) in zip(pos[hs], cw) if f]; k += len(cw)
        if [x.lower() for x in vw] != [x.lower() for r in order for x, _ in chunk_words(r[4])]:
            st["verse words differ: dropped"] += 1; continue
        mw = words.get(ref)
        if not mw:
            st["verse not in MACULA"] += 1; continue
        heb = sorted({x[2] for x in mw})
        split = "test" if (code, ch) in TEST else "dev" if (code, ch) in DEV else "train"
        o.execute("insert into verse values (?,?,?,?,?,?,?)", (ref, " ".join(heb), code, ch, v, split, json.dumps(vw, ensure_ascii=False)))
        raw = sorted(rr)
        sm = difflib.SequenceMatcher(None, [cons(r[2]) for r in raw], [cons(x[1]) for x in mw], autojunk=False)
        n = 0
        for a, b, size in sm.get_matching_blocks():
            for i in range(size):
                r, x = raw[a + i], mw[b + i]
                o.execute("insert or replace into link values (?,?,?,?,?,?)", (x[0], ref, json.dumps(pos[r[0]]), json.dumps(sup[r[0]]), r[4], r[0]))
                n += 1
        st["verses"] += 1; st["words"] += len(mw); st["words linked"] += n; st["rows unmatched"] += len(raw) - n; st[f"verses {split}"] += 1
    o.executemany("insert into meta values (?,?)", [(k, str(v)) for k, v in st.items()] + [("dev", json.dumps(sorted(DEV))), ("test", json.dumps(sorted(TEST)))])
    o.commit()
    print(dict(st))


if __name__ == "__main__":
    main()
