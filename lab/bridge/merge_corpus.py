#!/usr/bin/env python3
"""One engine corpus from several (the schema of data/ot.db): the first corpus named wins where two have the same verse, the
others add their verses as training data (their dev/test verses are left out, so the first corpus's splits are the splits).

    . ./env.sh; /usr/bin/python3 lab/bridge/merge_corpus.py --out data/dfb+dan.db data/dfb.db data/dan_ot.db"""
import argparse, os, sqlite3
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)


def main(a):
    out = os.path.join(PRIV, a.out)
    if os.path.exists(out):
        os.remove(out)
    db = sqlite3.connect(out)
    db.execute("create table verse(ref text primary key, heb text, book text, ch int, v int, split text, words text)")
    db.execute("create table link(word text primary key, ref text, positions text, supplied text, chunk text, row int)")
    db.execute("create table meta(name text, value text)")
    seen, n = set(), {}
    for i, src in enumerate(a.corpora):
        c = sqlite3.connect(os.path.join(PRIV, src)); n[src] = 0
        for row in c.execute("select ref, heb, book, ch, v, split, words from verse"):
            ref, split = row[0], row[5]
            if ref in seen or (i and split != "train"):
                continue
            seen.add(ref); n[src] += 1
            db.execute("insert into verse values (?,?,?,?,?,?,?)", row)
            for l in c.execute("select word, ref, positions, supplied, chunk, row from link where ref = ?", (ref,)):
                db.execute("insert or ignore into link values (?,?,?,?,?,?)", l)
    for src, k in n.items():
        db.execute("insert into meta values (?,?)", (f"verses from {src}", str(k)))
    db.commit(); print(n)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("corpora", nargs="+")
    main(ap.parse_args())
