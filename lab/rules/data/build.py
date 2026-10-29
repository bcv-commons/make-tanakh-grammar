#!/usr/bin/env python3
"""E0: the lab's NT data (rung 1, Greek NT -> BSB), built from the BSB Translation Tables themselves (bcv-query's copy of
bsb_tables.tsv), not from lexeme-aligner's layer (9.0% of its NT links differ from the tables: scratch/rules/e0/swapcheck.py).

Per verse: the BSB verse words (tokenizer v2, as compact-alignments), and per MACULA Nestle 1904 token its BSB word positions,
which of them are supplied (bracketed in the tables), and the table's chunk. Only verses whose table chunks rebuild the BSB verse
word for word are kept (7,904 of 7,939). MACULA's tree (orig/grc.sqlite nodes, tokens) is read from orig/grc.sqlite at run time.
    /usr/bin/python3 lab/rules/data/build.py   -> scratch/rules/data/nt.db"""
import collections, csv, difflib, json, os, re, sqlite3, sys, unicodedata
R = os.environ["MAKE_TANAKH_WORK"]; sys.path.insert(0, os.path.join(R, "scripts"))
from full_align import tokenize  # noqa: E402
HERE = os.path.dirname(os.path.abspath(__file__))
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
TABLES = "/home/lgunnars/dev/bcv-commons/bcv-query/example/bsb_tables.tsv"
csv.field_size_limit(10**9)

# Mark, fixed 2026-10-26 before anything was measured: the agent and the rule scripts never read TEST
DEV = {("MRK", 3), ("MRK", 9), ("MRK", 12)}
TEST = {("MRK", 5), ("MRK", 10), ("MRK", 15)}


def norm(w):
    return "".join(c for c in unicodedata.normalize("NFD", w.lower()) if not unicodedata.combining(c) and c.isalpha())


def chunk_words(chunk):
    """the chunk's words with a supplied flag (inside [ ]), tokenizer v2 per piece"""
    out, sup = [], False
    for piece in re.split(r"(\[|\])", chunk.replace("vvv", "")):
        if piece == "[":
            sup = True
        elif piece == "]":
            sup = False
        else:
            out += [(w, sup) for w in tokenize(piece)]
    return out


def bsb_verses(code, ch, _c={}):
    if (code, ch) not in _c:
        t = open(os.path.join(R, "reference/BSB", f"{code.lower()}{ch:03d}.txt"), encoding="utf-8").read()
        t = re.sub(r"(?m)^==.*$", "", t); t = re.sub(r"\{[^}]*\}", "", t)
        _c[(code, ch)] = {int(m[1]): m[2] for m in re.finditer(r"\bv(\d+)\s+(.*?)(?=\bv\d+\s|\Z)", t, re.S)}
    return _c[(code, ch)]


def main():
    names = {l.split("\t")[1]: l.split("\t")[0].upper() for l in open(os.path.join(R, "books.tsv"), encoding="utf-8").read().splitlines()[1:]}
    verses = collections.defaultdict(list); vid = None
    for row in csv.reader(open(TABLES, encoding="utf-8"), delimiter="\t"):
        if row[0] == "Heb Sort":
            continue
        if row[12].strip():
            vid = row[12].strip()
        if row[4] == "Greek" and row[5].strip():
            verses[vid].append((int(row[1]), int(row[2]), row[5].strip(), row[11].strip(), row[18].strip()))
    g = sqlite3.connect(os.path.join(R, "orig/grc.sqlite"))
    db = os.path.join(PRIV, "data", "nt.db")
    if os.path.exists(db):
        os.remove(db)
    o = sqlite3.connect(db)
    o.executescript("""create table verse(ref text primary key, book text, ch int, v int, split text, words text);
        create table link(key text primary key, ref text, positions text, supplied text, chunk text, row int);
        create table meta(name text, value text);""")
    st = collections.Counter()
    for vid, rows in verses.items():
        m = re.match(r"(.+) (\d+):(\d+)$", vid)
        code = names.get(m[1]); ch, v = int(m[2]), int(m[3])
        toks = g.execute("select key, text from tokens where book=? and ch=? and v=? order by key", (code, ch, v)).fetchall()
        try:
            text = bsb_verses(code.lower(), ch)[v]
        except (KeyError, FileNotFoundError, AttributeError):
            st["verse unread"] += 1; continue
        words = tokenize(text)
        pos, sup, k = {}, {}, 0
        for gs, bs, w, s, en in sorted(rows, key=lambda r: r[1]):
            cw = chunk_words(en)
            pos[gs] = list(range(k, k + len(cw))); sup[gs] = [i for i, (_, f) in zip(pos[gs], cw) if f]; k += len(cw)
        if [w.lower() for w in words] != [w.lower() for w, _ in (x for r in sorted(rows, key=lambda r: r[1]) for x in chunk_words(r[4]))]:
            st["verse words differ: dropped"] += 1; continue
        if not toks:
            st["verse not in MACULA"] += 1; continue
        split = "test" if (code, ch) in TEST else "dev" if (code, ch) in DEV else "train"
        ref = f"{code} {ch}:{v}"
        o.execute("insert into verse values (?,?,?,?,?,?)", (ref, code, ch, v, split, json.dumps(words, ensure_ascii=False)))
        raw = sorted(rows)
        sm = difflib.SequenceMatcher(None, [norm(r[2]) for r in raw], [norm(t[1]) for t in toks], autojunk=False)
        matched = 0
        for a, b, n in sm.get_matching_blocks():
            for i in range(n):
                r, t = raw[a + i], toks[b + i]
                o.execute("insert into link values (?,?,?,?,?,?)", (t[0], ref, json.dumps(pos[r[0]]), json.dumps(sup[r[0]]), r[4], r[0]))
                matched += 1
        st["verses"] += 1; st["tokens"] += len(toks); st["tokens linked"] += matched; st["table rows unmatched"] += len(raw) - matched
        st[f"verses {split}"] += 1
    o.executemany("insert into meta values (?,?)", [(k, str(v)) for k, v in st.items()] +
                  [("dev", json.dumps(sorted(DEV))), ("test", json.dumps(sorted(TEST))), ("source", TABLES)])
    o.commit()
    print(dict(st))


if __name__ == "__main__":
    main()
