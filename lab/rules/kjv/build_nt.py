#!/usr/bin/env python3
"""Rung 1c data: the KJV New Testament as the engine's corpus (data/kjv_nt.db, the schema of data/nt.db), from
bcv-commons/alignments-by-id `tr/e/eng/eng_kjv` (CC0; links to the TR spine, each with the MACULA Nestle 1904 ids of the same
words where TR and Nestle agree) on the KJV text (helloAO eng_kjv, kjv/text.py; fingerprints checked per book).

A verse is keyed by the MACULA verse of its linked ids; its words are that KJV verse's tokens (compact-alignments' tokenizer).
A KJV verse whose ids fall in another MACULA verse (2CO 13:14 = Nestle 13:13) is left out. Splits follow data/nt.db (dev MRK 3,
9, 12; test MRK 5, 10, 15). Unlinked MACULA words (Nestle-only readings, TR-only words, `none`) have no rendering.
    /usr/bin/python3 lab/rules/kjv/build_nt.py      (downloads the 27 book files into data/kjv/dl/nt/)"""
import collections, json, os, sqlite3, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE)
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
sys.path.insert(0, HERE)
import text as KT  # noqa: E402
sys.path.insert(0, os.path.join(KT.R, "scripts"))
import full_align as FA  # noqa: E402

BASE = "https://huggingface.co/datasets/bcv-commons/alignments-by-id"
DIR = os.path.join(PRIV, "data/kjv/dl/nt"); OUT = os.path.join(PRIV, "data/kjv_nt.db")


def files():
    os.makedirs(DIR, exist_ok=True)
    tree = json.load(urllib.request.urlopen("https://huggingface.co/api/datasets/bcv-commons/alignments-by-id/tree/main/tr/e/eng/eng_kjv"))
    out = {}
    for f in tree:
        p = f["path"]; name = os.path.basename(p)
        if not name.endswith(".json") or name.startswith("_"):
            continue
        dst = os.path.join(DIR, name)
        if not os.path.exists(dst):
            urllib.request.urlretrieve(f"{BASE}/resolve/main/{p}", dst)
        out[name.split("_")[0]] = dst
    return out


def main():
    nt = sqlite3.connect(os.path.join(PRIV, "data/nt.db"))
    split = dict(nt.execute("select ref, split from verse"))
    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.execute("create table verse(ref text primary key, book text, ch int, v int, split text, words text)")
    db.execute("create table link(key text primary key, ref text, positions text, supplied text, chunk text, row int)")
    db.execute("create table meta(name text, value text)")
    st = collections.Counter()
    for book, path in sorted(files().items()):
        rows = KT.rows(book)
        fp = FA.text_fingerprint(rows)[0][:8]
        if fp != os.path.basename(path)[:-5].split("_")[1]:
            st["books with another fingerprint"] += 1; print("fingerprint differs:", book); continue
        text = {f"{c}:{v}": t for c, v, t in rows}
        for cv, d in json.load(open(path, encoding="utf-8")).items():
            toks = FA.tokenize(text.get(cv, ""))
            mverses = collections.Counter(i[1:9] for l in d["links"] for i in l[3])
            if not toks or not mverses:
                continue
            mv = mverses.most_common(1)[0][0]
            ref = f"{book} {int(mv[2:5])}:{int(mv[5:8])}"
            if ref != f"{book} {cv}" or len(mverses) > 1:
                st["verses numbered otherwise / spread"] += 1; continue
            if ref not in split:
                st["verses not in nt.db"] += 1; continue
            db.execute("insert into verse values (?,?,?,?,?,?)", (ref, book, int(cv.split(":")[0]), int(cv.split(":")[1]), split[ref], json.dumps(toks, ensure_ascii=False)))
            st["verses"] += 1
            sup = {int(str(p).split(".")[0]) for p in d.get("supplied", [])}
            for n, (pos, _, cls, ids) in enumerate(d["links"]):
                ps = sorted({int(str(p).split(".")[0]) for p in pos})
                for k in ids:
                    st["links"] += 1
                    db.execute("insert or ignore into link values (?,?,?,?,?,?)", (k[1:], ref, json.dumps(ps), json.dumps(sorted(sup & set(ps))),
                                                                                   " ".join(toks[i] for i in ps), n))
                if not ids:
                    st["TR words without a Nestle id"] += 1
    for k, v in st.items():
        db.execute("insert into meta values (?,?)", (k, str(v)))
    db.commit()
    print(dict(st))


if __name__ == "__main__":
    main()
