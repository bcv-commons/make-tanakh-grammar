#!/usr/bin/env python3
"""Rung 2h: Greek NT -> Hebrew (Salkinson-Ginsburg 1885/86, public domain) as the engine's corpus (data/hebnt.db, the schema
of data/nt.db), from bcv-commons/alignments-by-id v1.1 `n1904/h/heb/heb_scg` (CC0; links keyed by MACULA Nestle 1904 ids;
a position is a token, "6.0" a part of token 6) and bcv-commons/hebrew-nt-analysis v0.1 (CC BY 4.0; the parts of every word,
with MACULA classes).

The target unit is the PART, unpointed (a prefix ו ב ל ה, a stem, a suffix pronoun), so Hebrew's function morphemes are the
engine's function words. A link to a whole token takes all its parts; to "i.p" that part. The article inside a preposition
(a part without letters) is left out. The function-word list (data/hebnt_func.txt) is derived: part strings whose occurrences
are at least half of the classes prep, cj, art, pron, om, rel, ptcl, among strings seen at least 5 times. Verses keyed by the MACULA verse of their ids; splits as
data/nt.db.
    ~/sil-study/.venv/bin/python lab/rules/hebnt/build.py"""
import collections, json, os, sqlite3, unicodedata, urllib.request
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE)
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
DL = os.path.join(PRIV, "data/hebnt/dl"); OUT = os.path.join(PRIV, "data/hebnt.db")
BASE = "https://huggingface.co/datasets/bcv-commons/alignments-by-id/resolve/v1.1"
FUNC_CLS = {"prep", "cj", "art", "pron", "om", "rel", "ptcl"}


def unpoint(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(c))


def files():
    tree = json.load(urllib.request.urlopen("https://huggingface.co/api/datasets/bcv-commons/alignments-by-id/tree/v1.1/n1904/h/heb/heb_scg"))
    out = {}
    for f in tree:
        name = os.path.basename(f["path"])
        if name.startswith("_") or not name.endswith(".json"):
            continue
        dst = os.path.join(DL, name)
        if not os.path.exists(dst):
            urllib.request.urlretrieve(f"{BASE}/{f['path']}", dst)
        out[name.split("_")[0]] = dst
    return out


def main():
    W = pd.read_parquet(os.path.join(DL, "words.parquet"))
    W = W[W["class"] != "verse-number"]
    parts = collections.defaultdict(list)          # (book, c, v) -> [(i, part, text, class)]
    cls_of = collections.defaultdict(collections.Counter)
    for r in W.itertuples(index=False):
        t = unpoint(r.text)
        if not t:
            continue
        parts[(r.book, int(r.chapter), int(r.verse))].append((int(r.i), int(r.part), t, r._8))
        cls_of[t][r._8 in FUNC_CLS] += 1
    func = sorted(t for t, c in cls_of.items() if c[True] * 2 >= sum(c.values()) and sum(c.values()) >= 5)
    open(os.path.join(PRIV, "data/hebnt_func.txt"), "w", encoding="utf-8").write("\n".join(func) + "\n")
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
        for cv, d in json.load(open(path, encoding="utf-8")).items():
            c, v = (int(x) for x in cv.split(":"))
            ps = sorted(parts.get((book, c, v), []))
            if not ps:
                st["verses without parts"] += 1; continue
            idx = {(i, p): n for n, (i, p, _, _) in enumerate(ps)}
            by_tok = collections.defaultdict(list)
            for (i, p), n in idx.items():
                by_tok[i].append(n)
            mv = collections.Counter(x[1:9] for l in d["links"] for x in l[1])
            if not mv:
                continue
            m = mv.most_common(1)[0][0]
            ref = f"{book} {int(m[2:5])}:{int(m[5:8])}"
            if len(mv) > 1 or ref != f"{book} {cv}":
                st["verses numbered otherwise / spread"] += 1; continue
            if ref not in split:
                st["verses not in nt.db"] += 1; continue
            words = [t for _, _, t, _ in ps]
            db.execute("insert into verse values (?,?,?,?,?,?)", (ref, book, c, v, split[ref], json.dumps(words, ensure_ascii=False)))
            st["verses"] += 1; st["parts"] += len(words)
            for n, (pos, ids, cls) in enumerate(d["links"]):
                sel = set()
                for x in pos:
                    if isinstance(x, int) or (isinstance(x, str) and "." not in x):
                        sel.update(by_tok.get(int(x), []))
                    else:
                        i, p = (int(y) for y in str(x).split("."))
                        if (i, p) in idx:
                            sel.add(idx[(i, p)])
                sel = sorted(sel)
                for k in ids:
                    st["links"] += 1
                    db.execute("insert or ignore into link values (?,?,?,?,?,?)", (k[1:], ref, json.dumps(sel), "[]", " ".join(words[j] for j in sel), n))
    for k, v in st.items():
        db.execute("insert into meta values (?,?)", (k, str(v)))
    db.commit()
    print(dict(st), "function parts:", len(func), func[:40])


if __name__ == "__main__":
    main()
