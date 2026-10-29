#!/usr/bin/env python3
"""Rung 1c, OT: the KJV Old Testament as the Hebrew engine's corpus (data/kjv_ot.db, the schema of data/ot.db), from
bcv-commons/full-alignments-llm layer eng_kjv+llm+jev-v4 (CC0, keyed to MACULA Hebrew by compact-alignments' _index) on the KJV
text (helloAO eng_kjv, kjv/text.py; each book's fingerprint checked).

A Hebrew word (MACULA word id = its morpheme keys without the last digit) gets the KJV positions of its content morpheme (main
channel), of its function morphemes (fn channel: prefixes, article, suffixes) and the words added for either (`+pos>ord`). Spans
are keyed by the Hebrew verse; the KJV words are read from its English verse (vrs.to_bsb: the KJV and the BSB number alike). A
Hebrew verse that is a psalm title, or shares its English verse with another Hebrew verse, is left out. Splits follow data/ot.db.
    /usr/bin/python3 lab/rules/kjv/build_ot.py      (downloads the 39 book files into data/kjv/dl/ot/)"""
import collections, json, os, sqlite3, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE)
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
sys.path.insert(0, HERE)
import text as KT  # noqa: E402
sys.path.insert(0, os.path.join(KT.R, "scripts"))
import full_align as FA, vrs  # noqa: E402

LAYER = "eng_kjv+llm+jev-v4"
BASE = f"https://huggingface.co/datasets/bcv-commons/full-alignments-llm/resolve/v1.0/e/eng/{LAYER}"
DIR = os.path.join(PRIV, "data/kjv/dl/ot_v1"); OUT = os.path.join(PRIV, "data/kjv_ot.db")


def files():
    os.makedirs(DIR, exist_ok=True)
    tree = json.load(urllib.request.urlopen(f"https://huggingface.co/api/datasets/bcv-commons/full-alignments-llm/tree/v1.0/e/eng/{LAYER}"))
    out = {}
    for f in tree:
        name = os.path.basename(f["path"])
        if name.startswith("_") or not name.endswith(".json"):
            continue
        dst = os.path.join(DIR, name)
        if not os.path.exists(dst):
            urllib.request.urlretrieve(f"{BASE}/{name}", dst)
        if not name.endswith(".meta.json"):
            out[name.split("_")[0]] = dst
    return out


def added(s):
    """the fn string's `+` entry -> {("c"|"f", ord): [positions]}"""
    out = collections.defaultdict(list)
    for e in (s or "").split():
        if e.startswith("+"):
            for part in e[1:].split(","):
                pos, _, own = part.partition(">")
                if not own:
                    continue
                kind = "f" if own.startswith("f") else "c"
                a, _, b = pos.partition("-")
                if a.isdigit() and (not b or b.isdigit()):
                    out[(kind, int(own.lstrip("f")))].extend(range(int(a), int(b or a) + 1))
    return out


def main():
    ot = sqlite3.connect(os.path.join(PRIV, "data/ot.db"))
    split = dict(ot.execute("select ref, split from verse"))
    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.execute("create table verse(ref text primary key, heb text, book text, ch int, v int, split text, words text)")
    db.execute("create table link(word text primary key, ref text, positions text, supplied text, chunk text, row int)")
    db.execute("create table meta(name text, value text)")
    st = collections.Counter()
    for book, path in sorted(files().items()):
        rows = KT.rows(book)
        if FA.text_fingerprint(rows)[0][:8] != os.path.basename(path)[:-5].split("_")[1]:
            st["books with another fingerprint"] += 1; print("fingerprint differs:", book); continue
        text = {(c, v): t for c, v, t in rows}
        main_s = json.load(open(path, encoding="utf-8")); meta = json.load(open(path[:-5] + ".meta.json", encoding="utf-8"))
        fn_s = meta.get("fn") or [""] * len(main_s)
        refs = list(FA.index(book, "lexemes")); keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys")
        eng = collections.defaultdict(list)
        for r in refs:
            c, v = (int(x) for x in r.split(" ")[1].split(":"))
            e = vrs.to_bsb(book.lower(), c, v)
            if e and e[1] != "title":
                eng[(int(e[0]), int(e[1]))].append(r)
        for i, r in enumerate(refs):
            c, v = (int(x) for x in r.split(" ")[1].split(":"))
            e = vrs.to_bsb(book.lower(), c, v)
            if not e or e[1] == "title":
                st["title or unmapped verses"] += 1; continue
            ek = (int(e[0]), int(e[1]))
            if len(eng[ek]) > 1:
                st["Hebrew verses sharing an English verse"] += 1; continue
            ref = f"{book} {ek[0]}:{ek[1]}"
            toks = FA.tokenize(text.get(ek, ""))
            if not toks or ref not in split:
                st["verses without text or not in ot.db"] += 1; continue
            pos = collections.defaultdict(set)
            add = added(fn_s[i] if i < len(fn_s) else "")
            ck, fk = keys.get(r, []), fkeys.get(r, [])
            for o, ids in FA.parse(main_s[i]).items():
                for k in (ck[o].split("+") if o < len(ck) and ck[o] else []):
                    pos[k[:-1]].update(ids + add.get(("c", o), []))
            for o, ids in FA.parse(fn_s[i] if i < len(fn_s) else "").items():
                for k in (fk[o].split("+") if o < len(fk) and fk[o] else []):
                    pos[k[:-1]].update(ids + add.get(("f", o), []))
            db.execute("insert into verse values (?,?,?,?,?,?,?)", (ref, r, book, ek[0], ek[1], split[ref], json.dumps(toks, ensure_ascii=False)))
            # v1.0: `+` words with no owner are the checker's "renders no source word" (decided none)
            none = set()
            for e in (fn_s[i] if i < len(fn_s) else "").split():
                if e.startswith("+"):
                    for part in e[1:].split(","):
                        if ">" not in part:
                            a, _, b = part.partition("-")
                            if a.isdigit() and (not b or b.isdigit()):
                                none.update(range(int(a), int(b or a) + 1))
            linked = {p for ps in pos.values() for p in ps}
            st["target tokens"] += len(toks); st["target tokens linked"] += len(linked & set(range(len(toks))))
            st["target tokens decided none"] += len(none - linked); st["target tokens undecided"] += len(set(range(len(toks))) - linked - none)
            st["verses"] += 1
            for n, (w, ps) in enumerate(sorted(pos.items())):
                ps = sorted(p for p in ps if 0 <= p < len(toks))
                if ps:
                    st["words linked"] += 1
                    db.execute("insert or ignore into link values (?,?,?,?,?,?)", (w, ref, json.dumps(ps), "[]", " ".join(toks[p] for p in ps), n))
    for k, v in st.items():
        db.execute("insert into meta values (?,?)", (k, str(v)))
    db.commit()
    print(dict(st))


if __name__ == "__main__":
    main()
