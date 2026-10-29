#!/usr/bin/env python3
"""Rung 2: Greek NT -> Modern Hebrew (HEBM95, © 1995 Bible Society in Israel; LOCAL ONLY, never published or quoted beyond the
licensing rules) as the engine's corpus (data/hebm95_nt.db, the schema of data/nt_la.db), from lexeme-aligner's layer
`HEBM95+llm+jev-v4` (local copy data/hebm95/layer/, its source index data/hebm95/_index/, the USJ text data/hebm95/usj/).

The target unit is the written WORD as the bibles tokenizer v2 counts it (the layer's positions): a prefixed word (והבית) stays
whole, and a Greek function word the layer points at the word that carries it (ὁ, καί -> והבית) shares that word's position.
Verse texts are read with lexeme-aligner's own USJ reader (their code, imported read-only), and every book's text fingerprint
must equal its layer file's name, else the book is left out. Verses and splits as data/nt_la.db.

Function words (data/hebm95_func.txt) are DERIVED, as for Vamvas, with no knowledge of Hebrew: a word is one when in at least
half of its occurrences (and at least 5) only Greek function words (the fn channel) link to it.
    ~/sil-study/.venv/bin/python lab/rules/hebm95/build.py"""
import collections, glob, json, os, sqlite3, sys
from pathlib import Path
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE); R = os.environ["MAKE_TANAKH_WORK"]
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
LA = os.path.expanduser("~/dev/bcv-commons/lexeme-aligner/pipeline")
sys.path.insert(0, LA); sys.path.insert(0, os.path.join(LA, "vendor/bibles"))
import bcv_tokenize as T  # noqa: E402
from lexeme_aligner import usj_source as U  # noqa: E402

D = os.path.join(PRIV, "data/hebm95"); OUT = os.path.join(PRIV, "data/hebm95_nt.db")


def parse(s):
    """'o:a-b o:c ...' -> {ordinal: [positions]}"""
    out = collections.defaultdict(list)
    for e in (s or "").split():
        o, _, sp = e.partition(":")
        if not o.isdigit() or not sp:
            continue
        for part in sp.split(","):
            a, _, b = part.partition("-")
            if a.isdigit() and (not b or b.isdigit()):
                out[int(o)] += list(range(int(a), int(b or a) + 1))
    return out


def main():
    old = sqlite3.connect(os.path.join(PRIV, "data/nt_la.db"))
    split = dict(old.execute("select ref, split from verse"))
    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    for (sql,) in old.execute("select sql from sqlite_master where type='table'"):
        db.execute(sql)
    st = collections.Counter(); fnw = collections.defaultdict(collections.Counter)
    usj = {os.path.basename(p).split("-", 1)[1][:3]: p for p in glob.glob(os.path.join(D, "usj/*.json"))}
    for lf in sorted(glob.glob(os.path.join(D, "layer/*_*.json"))):
        if lf.endswith(".meta.json"):
            continue
        book, fp = os.path.basename(lf)[:-5].split("_")
        if book not in usj:
            st["books without text"] += 1; continue
        verses = U.read_verses(Path(usj[book]), warn=open(os.devnull, "w"))
        if T.file_hash(T.fingerprints(verses)[0]) != fp:
            st["books whose fingerprint differs"] += 1; print("skip", book, file=sys.stderr); continue
        main_s = json.load(open(lf, encoding="utf-8")); meta = json.load(open(lf[:-5] + ".meta.json", encoding="utf-8"))
        fn_s = meta.get("fn") or [""] * len(main_s)
        idx = lambda k: json.load(open(os.path.join(D, "_index", f"{book}_{k}.json"), encoding="utf-8"))
        refs = list(idx("lexemes")); keys = idx("keys"); fkeys = idx("fn_keys")
        for i, r in enumerate(refs):
            if r not in split:
                st["verses not in nt_la.db"] += 1; continue
            c, v = (int(x) for x in r.split(" ")[1].split(":"))
            toks = T.tokenize(verses.get((c, v), ""))
            if not toks:
                st["verses without text"] += 1; continue
            pos = collections.defaultdict(set); kind_of = collections.defaultdict(set)
            for kind, s, ks in (("c", main_s[i] if i < len(main_s) else "", keys.get(r, [])),
                                ("f", fn_s[i] if i < len(fn_s) else "", fkeys.get(r, []))):
                for o, ps in parse(s).items():
                    k = ks[o] if o < len(ks) else None
                    if not k:
                        continue
                    ws = k.split("+")
                    if len(ws) > 1:
                        st["joined source tokens (to their first word)"] += 1
                    pos[ws[0].lstrip("n")].update(ps)
                    for p in ps:
                        kind_of[p].add(kind)
            for p, kinds in kind_of.items():
                if p < len(toks):
                    fnw[toks[p]][kinds == {"f"}] += 1
            b_, c_, v_ = r.split()[0], c, v
            db.execute("insert into verse values (?,?,?,?,?,?)", (r, b_, c_, v_, split[r], json.dumps(toks, ensure_ascii=False)))
            st["verses"] += 1
            for n, (w, ps) in enumerate(sorted(pos.items())):
                ps = sorted(p for p in ps if 0 <= p < len(toks))
                if ps:
                    st["words linked"] += 1
                    db.execute("insert or ignore into link values (?,?,?,?,?,?)", (w, r, json.dumps(ps), "[]", " ".join(toks[p] for p in ps), n))
    func = sorted(w for w, c in fnw.items() if sum(c.values()) >= 5 and c[True] * 2 >= sum(c.values()))
    open(os.path.join(PRIV, "data/hebm95_func.txt"), "w", encoding="utf-8").write("\n".join(func) + "\n")
    st["function words derived"] = len(func)
    for k, v in st.items():
        db.execute("insert into meta values (?,?)", (k, str(v)))
    db.commit()
    print(dict(st))


if __name__ == "__main__":
    main()
