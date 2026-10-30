#!/usr/bin/env python3
"""Greek NT -> Kuni engine corpora (the schema of data/nt_la.db) from lexeme-aligner's published morphed layer
`kvg-m_wbt+llm+jev-v4` (bcv-commons/full-alignments-llm; local copy $PRIV/../align/kvg_m) and the local split file of the Kuni
text by parts (lexeme-aligner's pipeline/work/kvg-parts/split, CC BY-NC-ND text, never published). Two corpora:

  words  the target unit is the written word (the layer's own token positions)                 -> data/kvg_nt_words.db
  parts  the target unit is the PART (prefixes, stem, tone, suffixes, in reading order): a source word linked to parts (the meta
         file's `parts` channel, `c<n>:tok.part,...`) links those parts; one linked whole links all the token's parts -> data/kvg_nt_parts.db

Ruth and Jonah (Hebrew source) are left out here (they are the Kuni OT test in data/kvg_ot.db). Splits: test = MRK JAS,
dev = PHM 2JN 3JN JUD TIT, else train. Function words (data/kvg_nt_{words,parts}_func.txt) derived from the fn channel as in
hebm95/build.py. A book is skipped when the layer file's text fingerprint is not the split file's.

    . ./env.sh; ~/sil-study/.venv/bin/python lab/bridge/build_kvg_nt.py [--split-dir DIR] [--layer DIR]"""
import argparse, collections, glob, json, os, sqlite3, sys
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")
sys.path.insert(0, os.path.join(os.environ["MAKE_TANAKH_WORK"], "scripts"))
import full_align as FA  # noqa: E402
TEST = {"MRK", "JAS"}; DEV = {"PHM", "2JN", "3JN", "JUD", "TIT"}; SKIP = {"RUT", "JON"}


def parse(s):
    """'o:a-b o:c,d ...' -> {ordinal: [token positions]}"""
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


def parse_parts(s):
    """'c4:14.0,14.1 f10:32 ...' -> {(kind, ordinal): [(tok, part or None), ...]}"""
    out = {}
    for e in (s or "").split():
        head, _, sp = e.partition(":")
        if len(head) < 2 or head[0] not in "cfp" or not head[1:].isdigit() or not sp:
            continue
        items = []
        for x in sp.split(","):
            t, _, p = x.partition(".")
            if t.isdigit():
                items.append((int(t), int(p) if p.isdigit() else None))
        out[(head[0], int(head[1:]))] = items
    return out


def main(a):
    import pyarrow.parquet as pq
    split = pq.read_table(os.path.join(a.split_dir, "words.parquet")).to_pylist()
    hdr = json.load(open(os.path.join(a.split_dir, "_split.json"), encoding="utf-8")); text_fp = hdr["text_fp"]
    verses = collections.defaultdict(list)                # (book, ch, v) -> [(i, part, text, slot)] in order
    for r in split:
        verses[(r["book"], int(r["chapter"]), int(r["verse"]))].append((int(r["i"]), int(r["part"]), r["text"], r["slot"]))
    for k in verses:
        verses[k].sort()
    dbs = {}
    for mode in ("words", "parts"):
        p = os.path.join(PRIV, "data", f"{a.prefix}_{mode}.db")
        if os.path.exists(p):
            os.remove(p)
        db = sqlite3.connect(p)
        db.execute("create table verse(ref text primary key, book text, ch int, v int, split text, words text)")
        db.execute("create table link(key text primary key, ref text, positions text, supplied text, chunk text, row int)")
        db.execute("create table meta(name text, value text)")
        dbs[mode] = db
    st = {m: collections.Counter() for m in dbs}; fnw = {m: collections.defaultdict(collections.Counter) for m in dbs}
    for lf in sorted(glob.glob(os.path.join(a.layer, "*_*.json"))):
        if lf.endswith(".meta.json"):
            continue
        book, fp = os.path.basename(lf)[:-5].split("_")
        if book in SKIP:
            continue
        if text_fp.get(book) != fp:
            print("skip", book, "fingerprint", fp, "split has", text_fp.get(book), file=sys.stderr); continue
        main_s = json.load(open(lf, encoding="utf-8")); meta = json.load(open(lf[:-5] + ".meta.json", encoding="utf-8"))
        fn_s = meta.get("fn") or [""] * len(main_s); parts_s = meta.get("parts") or [""] * len(main_s)
        refs = list(FA.index(book, "lexemes")); keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys")
        sp = "test" if book in TEST else "dev" if book in DEV else "train"
        for i, r in enumerate(refs):
            c, v = (int(x) for x in r.split(" ")[1].split(":"))
            rows = verses.get((book, c, v))
            if not rows:
                for m in dbs:
                    st[m]["verses without text"] += 1
                continue
            toks = []                                      # word mode: token texts by i
            for i_, part, text, slot in rows:
                if part == 0:
                    toks.append(text if slot == "whole" else "")
            for i_, part, text, slot in rows:              # rebuild the written word for word mode from its parts
                if slot != "whole":
                    toks[i_] = toks[i_] + text
            parts_list = [(i_, part, text) for i_, part, text in ((x[0], x[1], x[2]) for x in rows)]
            flat = {(i_, part): n for n, (i_, part, _) in enumerate(parts_list)}
            pmap = parse_parts(parts_s[i] if i < len(parts_s) else "")
            for mode, db in dbs.items():
                pos = collections.defaultdict(set); kind_of = collections.defaultdict(set)
                for kind, s, ks in (("c", main_s[i] if i < len(main_s) else "", keys.get(r, [])),
                                    ("f", fn_s[i] if i < len(fn_s) else "", fkeys.get(r, []))):
                    for o, ps in parse(s).items():
                        k = ks[o] if o < len(ks) else None
                        if not k:
                            continue
                        w = k.split("+")[0].lstrip("n")
                        if mode == "words":
                            tp = [p for p in ps if p < len(toks)]
                        else:
                            spec = pmap.get((kind, o))
                            tp = []
                            if spec:
                                for t, part in spec:
                                    tp += [flat[(t, part)]] if part is not None and (t, part) in flat else [n for (i2, p2), n in flat.items() if i2 == t]
                            else:
                                tp = [n for (i2, p2), n in flat.items() if i2 in ps]
                        pos[w].update(tp)
                        for p in tp:
                            kind_of[p].add(kind)
                units = toks if mode == "words" else [t for _, _, t in parts_list]
                for p, kinds in kind_of.items():
                    fnw[mode][units[p].lower()][kinds == {"f"}] += 1
                db.execute("insert into verse values (?,?,?,?,?,?)", (r, book, c, v, sp, json.dumps(units, ensure_ascii=False)))
                st[mode]["verses"] += 1; st[mode][f"verses {sp}"] += 1
                for n, (w, ps) in enumerate(sorted(pos.items())):
                    ps = sorted(p for p in ps if 0 <= p < len(units))
                    if ps:
                        st[mode]["words linked"] += 1
                        db.execute("insert or ignore into link values (?,?,?,?,?,?)", (w, r, json.dumps(ps), "[]", " ".join(units[p] for p in ps), n))
    for mode, db in dbs.items():
        func = sorted(w for w, c in fnw[mode].items() if sum(c.values()) >= 5 and c[True] * 2 >= sum(c.values()))
        open(os.path.join(PRIV, "data", f"{a.prefix}_{mode}_func.txt"), "w", encoding="utf-8").write("\n".join(func) + "\n")
        st[mode]["function words derived"] = len(func)
        for k, v in st[mode].items():
            db.execute("insert into meta values (?,?)", (k, str(v)))
        db.commit(); print(mode, dict(st[mode]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split-dir", default=os.path.join(os.environ["BCV_COMMONS"], "lexeme-aligner/pipeline/work/kvg-parts/split"))
    ap.add_argument("--layer", default=os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "align/kvg_m/k/kvg/kvg-m_wbt+llm+jev-v4"))
    ap.add_argument("--prefix", default="kvg_nt", help="output data/<prefix>_{words,parts}.db (zin_nt_jev for the Zinza layer)")
    main(ap.parse_args())
