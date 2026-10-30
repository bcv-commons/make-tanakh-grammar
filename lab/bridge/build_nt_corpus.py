#!/usr/bin/env python3
"""A Greek NT -> target engine corpus (the schema of data/nt_la.db) from an align-text layer directory (compact or
full-alignments-llm: BOOK_<fp>.json main string per spine verse, BOOK_<fp>.meta.json with the fn channel) and align-text's
plain-text export of the target (BOOK.txt, 'c:v text'), tokenized as the aligner tokenized it (full_align.tokenize, as
build_corpus.py). Splits: --splits nt = test MRK JAS, dev PHM 2JN 3JN JUD TIT, else train (a direct Greek -> target engine
figure); --splits none = all train (the corpus feeds a bridged OT engine). Function words derived from the fn channel.

    . ./env.sh; /usr/bin/python3 lab/bridge/build_nt_corpus.py --layer private/align/dfb_nt/out/full-alignments-llm/d/dan/dan_dfb+llm+jev-v4
        --text private/align/dfb_nt/text --out private/rules/data/dfb_nt_jev.db [--splits nt|none] [--books MAT ...]"""
import argparse, collections, glob, json, os, sqlite3, sys
R = os.environ["MAKE_TANAKH_WORK"]; sys.path.insert(0, os.path.join(R, "scripts"))
import full_align as FA  # noqa: E402
TEST = {"MRK", "JAS"}; DEV = {"PHM", "2JN", "3JN", "JUD", "TIT"}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_kvg_nt import parse  # noqa: E402


def main(a):
    if os.path.exists(a.out):
        os.remove(a.out)
    db = sqlite3.connect(a.out)
    db.execute("create table verse(ref text primary key, book text, ch int, v int, split text, words text)")
    db.execute("create table link(key text primary key, ref text, positions text, supplied text, chunk text, row int)")
    db.execute("create table meta(name text, value text)")
    st = collections.Counter(); fnw = collections.defaultdict(collections.Counter)
    for lf in sorted(glob.glob(os.path.join(a.layer, "*_*.json"))):
        if os.path.basename(lf).count(".") != 1:               # BOOK_fp.json only (not .meta / .extra files)
            continue
        book = os.path.basename(lf).split("_")[0]
        if a.books and book not in a.books:
            continue
        tf = os.path.join(a.text, f"{book}.txt")
        if not os.path.exists(tf):
            print("no text for", book, file=sys.stderr); continue
        toks_of = {}
        for line in open(tf, encoding="utf-8"):
            cv, _, t = line.rstrip("\n").partition(" ")
            if ":" in cv and t:
                toks_of[cv] = FA.tokenize(t)
        main_s = json.load(open(lf, encoding="utf-8")); meta = json.load(open(lf[:-5] + ".meta.json", encoding="utf-8"))
        fn_s = meta.get("fn") or [""] * len(main_s)
        refs = list(FA.index(book, "lexemes")); keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys")
        sp = ("test" if book in TEST else "dev" if book in DEV else "train") if a.splits == "nt" else "train"
        for i, r in enumerate(refs):
            cv = r.split(" ")[1]; c, v = (int(x) for x in cv.split(":"))
            toks = toks_of.get(cv)
            if not toks:
                st["verses without text"] += 1; continue
            pos = collections.defaultdict(set); kind_of = collections.defaultdict(set)
            for kind, s, ks in (("c", main_s[i] if i < len(main_s) else "", keys.get(r, [])),
                                ("f", fn_s[i] if i < len(fn_s) else "", fkeys.get(r, []))):
                for o, ps in parse(s).items():
                    k = ks[o] if o < len(ks) else None
                    if not k:
                        continue
                    ps = [p for p in ps if p < len(toks)]
                    pos[k.split("+")[0].lstrip("n")].update(ps)
                    for p in ps:
                        kind_of[p].add(kind)
            for p, kinds in kind_of.items():
                fnw[toks[p].lower()][kinds == {"f"}] += 1
            db.execute("insert into verse values (?,?,?,?,?,?)", (r, book, c, v, sp, json.dumps(toks, ensure_ascii=False)))
            st["verses"] += 1; st[f"verses {sp}"] += 1
            for n, (w, ps) in enumerate(sorted(pos.items())):
                ps = sorted(ps)
                if ps:
                    st["words linked"] += 1
                    db.execute("insert or ignore into link values (?,?,?,?,?,?)", (w, r, json.dumps(ps), "[]", " ".join(toks[p] for p in ps), n))
    func = sorted(w for w, c in fnw.items() if sum(c.values()) >= 5 and c[True] * 2 >= sum(c.values()))
    open(a.out[:-3] + "_func.txt", "w", encoding="utf-8").write("\n".join(func) + "\n")
    st["function words derived"] = len(func)
    for k, v in st.items():
        db.execute("insert into meta values (?,?)", (k, str(v)))
    db.commit(); print(os.path.basename(a.out), dict(st))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True); ap.add_argument("--text", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--splits", choices=["nt", "none"], default="nt"); ap.add_argument("--books", nargs="*")
    main(ap.parse_args())
