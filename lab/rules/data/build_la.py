#!/usr/bin/env python3
"""The lab's corpus from lexeme-aligner's BSB layer (decided 2026-10-26: their pinned layers are the source, our table rebuild
only a fallback): bcv-commons/full-alignments-manual v1.0 (a12264ed) `e/eng/eng_BSB+manual+bsb-tables`, local copy
data/bsbfix/v1 (e0/layercheck_v1.py downloads it).

    /usr/bin/python3 lab/rules/data/build_la.py   -> data/nt_la.db, data/ot_la.db (the schema of nt.db / ot.db)

The verse words, splits and verse set are those of nt.db / ot.db (the BSB as setup.py builds it; Psalm headings stay in verse 1,
unlinked: their positions are the layer's plus the heading's length). Per source word (NT: Nestle id; OT: MACULA word = morpheme
keys without the last digit): the spans of its tokens in `main` and `fn` with the `+` words that name them; `supplied` = those
`+` words and the `s<pos>` words of a row. A row over tokens of several words goes to its keyed token's word (k<i>).

**Joined tokens** (one spine token for 2+ source words: names, "ὁ τοῦ", "πάντα πᾶσιν"): the token's link and its other rows in
`rows` each carry a table row id (R<id> = BSB Sort); the rows, in the table's source order (Greek / Heb Sort), are given to the
token's words in order. When the number of rows is not the number of words, the whole span goes to the first word (counted)."""
import collections, csv, glob, json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE); R = os.environ["MAKE_TANAKH_WORK"]
sys.path.insert(0, os.path.join(R, "scripts")); sys.path.insert(0, os.path.join(LAB, "e0"))
import full_align as FA, vrs  # noqa: E402
import layercheck_v1 as LC  # noqa: E402

DL = os.path.join(PRIV, "data/bsbfix/v1")
TABLES = os.path.join(os.environ["BCV_COMMONS"], "bcv-query/example/bsb_tables.tsv")
csv.field_size_limit(10 ** 9)


def table_sort():
    """BSB Sort -> the source word's order key (Greek Sort or Heb Sort)"""
    out = {}
    for row in csv.reader(open(TABLES, encoding="utf-8"), delimiter="\t"):
        if row[0] == "Heb Sort" or not row[2].isdigit():
            continue
        out[int(row[2])] = float(row[1] if row[4] == "Greek" else row[0])
    return out


def rids(x):
    """the R ids in one wx entry"""
    out = []
    for part in (x or "").split(";"):
        if part.startswith("R"):
            out += [int(y) for y in part[1:].split(",") if y.isdigit()]
    return out


def ext(fields, c):
    return [f[1:] for f in fields if f[:1] == c]


def main():
    order = table_sort()
    for test, src in (("NT", "nt.db"), ("OT", "ot.db")):
        old = sqlite3.connect(os.path.join(PRIV, "data", src))
        verses = list(old.execute("select * from verse"))
        vcols = [d[0] for d in old.execute("select * from verse").description]
        words = {r: json.loads(w) for r, w in old.execute("select ref, words from verse")}
        out = os.path.join(PRIV, "data", src.replace(".db", "_la.db"))
        if os.path.exists(out):
            os.remove(out)
        db = sqlite3.connect(out)
        db.execute(old.execute("select sql from sqlite_master where name='verse'").fetchone()[0])
        db.execute(old.execute("select sql from sqlite_master where name='link'").fetchone()[0])
        lcols = [d[0] for d in old.execute("select * from link limit 1").description]
        db.execute("create table meta(name text, value text)")
        db.executemany(f"insert into verse values ({','.join('?' * len(vcols))})", verses)
        head_off = {}
        if test == "OT":
            import re
            for f in glob.glob(os.path.join(R, "reference/BSB/psa*.txt")):
                ch = int(os.path.basename(f)[3:6]); lines = open(f, encoding="utf-8").read().splitlines()
                for k, l in enumerate(lines):
                    if l.startswith("v1 "):
                        nxt = next((x for x in lines[k + 1:] if x.strip()), "")
                        if nxt.startswith("//"):
                            head_off[f"PSA {ch}:1"] = len(FA.tokenize(re.sub(r"\{[^}]*\}", "", l[3:])))
                        break
        st = collections.Counter()
        wordkey = (lambda k: k.lstrip("n")) if test == "NT" else (lambda k: k[:-1])
        for book in sorted({r.split()[0] for r in words}):
            f = [x for x in glob.glob(os.path.join(DL, f"{book}_*.json")) if not x.endswith(".meta.json") and len(os.path.basename(x)) == len(book) + 14]
            if len(f) != 1:
                st["books without a layer file"] += 1; continue
            main_s = json.load(open(f[0], encoding="utf-8")); meta = json.load(open(f[0][:-5] + ".meta.json", encoding="utf-8"))
            fn_s, rows_s, wx_s = meta.get("fn") or [], meta.get("rows") or [], meta.get("wx") or []
            refs = list(FA.index(book, "lexemes")); keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys")
            for i, r in enumerate(refs):
                if test == "OT":
                    c, v = (int(x) for x in r.split(" ")[1].split(":"))
                    e = vrs.to_bsb(book.lower(), c, v)
                    if not e or e[1] == "title":
                        continue
                    ref = f"{book} {int(e[0])}:{int(e[1])}"
                else:
                    ref = r
                if ref not in words:
                    continue
                off = head_off.get(ref, 0); n = len(words[ref])
                ms, fs = main_s[i] or "", (fn_s[i] if i < len(fn_s) else "") or ""
                wx = (wx_s[i] if i < len(wx_s) else "").split()
                ents = [("c", x) for x in ms.split()] + [("f", x) for x in fs.split()]
                tok = {("c", o): kk for o, kk in enumerate(keys.get(r, []))}
                tok.update({("f", o): kk for o, kk in enumerate(fkeys.get(r, []))})
                pos = collections.defaultdict(set); sup = collections.defaultdict(set)
                # per token: [(R id or None, positions, supplied)] -- its link, its `+` words, its other rows
                per = collections.defaultdict(list)
                adds = collections.defaultdict(list)
                for j, (kind, x) in enumerate(ents):
                    if x.startswith("+"):
                        for part in x[1:].split(","):
                            p_, _, own = part.partition(">")
                            if own:
                                a, _, b = p_.partition("-")
                                if a.isdigit() and (not b or b.isdigit()):
                                    adds[("f" if own.startswith("f") else "c", int(own.lstrip("f")))] += list(range(int(a), int(b or a) + 1))
                empty = set()   # `!`, `u`, `e` lists: tokens with no target word of their own (a link with no positions)
                for kind, x in ents:
                    if x[:1] in "!ue" and x[1:2].isdigit():
                        for part in x[1:].split(","):
                            a, _, b = part.split("@")[0].partition("-")
                            if a.isdigit() and (not b or b.isdigit()):
                                empty.update((kind, o) for o in range(int(a), int(b or a) + 1))
                for j, (kind, x) in enumerate(ents):
                    if x[:1] in "+u!e" or ":" not in x:
                        continue
                    o, _, sp = x.partition(":")
                    if not o.isdigit():
                        continue
                    per[(kind, int(o))].append([(rids(wx[j]) if j < len(wx) else []) or [None], set(LC.span_pos(sp)), set()])
                for t, ps in adds.items():
                    if per.get(t):
                        per[t][0][1] |= set(ps); per[t][0][2] |= set(ps)
                    else:
                        per[t].append([[None], set(ps), set(ps)])
                word_of = {f"{k}{o}": wordkey(kk.split("+")[0]) for (k, o), kk in tok.items() if kk}
                cross = LC.row_fix(rows_s[i] if i < len(rows_s) else "", word_of)
                for e_ in (rows_s[i] if i < len(rows_s) else "").split():
                    fl = e_.split(":")
                    if len(fl) < 2:
                        continue
                    srcs = fl[0].split(",")
                    if len(srcs) != 1 or not srcs[0][1:].isdigit():
                        continue                     # a row over several tokens: its views are already in main / fn
                    t = (srcs[0][0], int(srcs[0][1:]))
                    if "+" not in (tok.get(t) or ""):
                        continue                     # a plain token's other rows are views of its link
                    s_ = {int(y) for y in sum((z.split(",") for z in ext(fl[2:], "s")), []) if y.isdigit()}
                    per[t].append([[int(z) for z in sum((y.split(",") for y in ext(fl[2:], "R")), []) if z.isdigit()] or [None],
                                   set(LC.span_pos(fl[1])) | s_, s_])
                for t, items in per.items():
                    kk = tok.get(t)
                    if not kk:
                        continue
                    ws = [wordkey(k) for k in kk.split("+")]
                    if len(ws) == 1:
                        for _, ps, ss in items:
                            pos[ws[0]] |= ps; sup[ws[0]] |= ss
                        continue
                    st["joined tokens"] += 1
                    srt = sorted(items, key=lambda it: min(order.get(x, 10 ** 9) for x in it[0]) if it[0][0] is not None else 10 ** 9)
                    if len(srt) == len(ws) and all(it[0][0] is not None for it in srt):
                        st["joined tokens split by their rows"] += 1
                        for w, (_, ps, ss) in zip(ws, srt):
                            pos[w] |= ps; sup[w] |= ss
                    else:
                        st["joined tokens to their first word"] += 1
                        for _, ps, ss in items:
                            pos[ws[0]] |= ps; sup[ws[0]] |= ss
                for w, take in cross.items():
                    pos[w] -= take
                for t in empty:
                    for k in (tok.get(t) or "").split("+"):
                        if k and wordkey(k) not in pos:
                            pos[wordkey(k)] = set(); st["words with no target word (! u e)"] += 1
                for k, (w, ps) in enumerate(sorted(pos.items())):
                    ps0 = ps
                    ps = sorted(p + off for p in ps if 0 <= p + off < n)
                    if not ps and ps0:
                        continue
                    ss = sorted(p + off for p in sup[w] if 0 <= p + off < n)
                    vals = {"key": w, "word": w, "ref": ref, "positions": json.dumps(ps), "supplied": json.dumps(ss),
                            "chunk": " ".join(words[ref][p] for p in ps), "row": k}
                    db.execute(f"insert or ignore into link values ({','.join('?' * len(lcols))})", [vals[c] for c in lcols])
                    st["words linked"] += 1
        for k, v in st.items():
            db.execute("insert into meta values (?,?)", (k, str(v)))
        db.commit()
        print(test, dict(st))


if __name__ == "__main__":
    main()
