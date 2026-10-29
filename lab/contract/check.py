#!/usr/bin/env python3
"""The contract test (RELATIONS.md, section 7): one chapter of each format the lab reads from the work repo, recorded as
schemas, counts and hashes (no text), and compared at each run. A format change (a table's columns, a toolkit function
gone, the .align layout, a store's fields, the tokenizer or the verse mapping) fails; a data change in a format that
holds (MACULA's chapter, the index, our draft's .align) is reported, since lab figures move with it.

    . ./env.sh; /usr/bin/python3 lab/contract/check.py            compare with expected.json (exit 1 on a format change)
    /usr/bin/python3 lab/contract/check.py record                 write expected.json (after a deliberate change)

Chapters: Greek MRK 1 and Hebrew RUT 1 (orig/*.sqlite), the published index of RUT, our Danish draft JOL 1 (CC0; .align),
the Danish and Kuni stores (fields only), the Kuni language DB (schema only)."""
import hashlib, json, os, sqlite3, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.environ["MAKE_TANAKH_WORK"]
sys.path.insert(0, os.path.join(R, "scripts"))
import full_align as FA, grammar, langtools, morphs, vrs  # noqa: E402
EXPECTED = os.path.join(HERE, "expected.json")
sha = lambda x: hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]

# what the lab calls in the toolkit (grep of lab/: FA.*, morphs.*, vrs.*, grammar.load, langtools.Project)
API = {"full_align": (FA, ["index", "tokenize", "parse", "text_fingerprint", "text_hash", "read_chapter", "draft_texts",
                           "chapters"]),
       "morphs": (morphs, ["load", "clusters", "affix_entries", "is_confirmed", "word_classes", "meaning", "Segmenter"]),
       "grammar": (grammar, ["load"]), "langtools": (langtools, ["Project"]), "vrs": (vrs, ["to_bsb"])}
# verses whose numbering differs between the Hebrew and the BSB (the lab maps every OT verse through vrs.to_bsb)
VRS = [("jol", 3, v) for v in range(1, 6)] + [("mal", 3, v) for v in range(18, 25)] + [("gen", 32, v) for v in (1, 2, 33)] \
    + [("psa", 3, v) for v in (1, 2, 9)] + [("num", 17, v) for v in (1, 15, 16, 28)] + [("1ki", 5, v) for v in (1, 14, 15, 32)]
# tokenizer v2 on our own words: Danish letters, a hyphen word, digits and punctuation, Greek with accents
TOKENS = ["Æblet faldt ned - og så? Ja: 12 æbler, ø-boer", "Anne-Marie tolv", "λόγος, ἐν ἀρχῇ; καὶ", "can't stop—now"]


def schema(db, tables=None):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    names = [n for (n,) in c.execute("select name from sqlite_master where type='table' order by name")]
    return {n: [r[1] for r in c.execute(f"pragma table_info({n})")] for n in names if tables is None or n in tables}


def orig(db, book, ch, meta):
    c = sqlite3.connect(f"file:{os.path.join(R, db)}?mode=ro", uri=True)
    toks = c.execute("select * from tokens where book=? and ch=? order by key", (book, ch)).fetchall()
    nodes = c.execute("select * from nodes where book=? and ch=? order by id", (book, ch)).fetchall()
    return ({"schema": schema(os.path.join(R, db), ("tokens", "nodes", "bsb", "map", "meta"))},
            {"version": dict(c.execute("select name, value from meta")).get(meta), f"{book} {ch} tokens": [len(toks), sha(toks)],
             f"{book} {ch} nodes": [len(nodes), sha(nodes)]})


def shape(x):
    """a JSON value's structure: dict -> its value shape (keys taken as data), list -> its first item's"""
    if isinstance(x, dict):
        return {"dict": shape(next(iter(x.values()))) if x else None}
    if isinstance(x, list):
        return {"list": shape(x[0]) if x else None}
    return type(x).__name__


def store(pname):
    o = json.load(open(os.path.join(R, "export", pname, "profile", "observations.json"), encoding="utf-8"))
    es = o.get("entries", [])
    return {"top": sorted(o), "entry fields": sorted({k for e in es for k in e}), "kinds": sorted({e.get("kind") for e in es}),
            "grammar.load -> morphs": hasattr(grammar.load(pname), "morphs")}


def checks():
    """{name: (format record, data record)}"""
    out = {"toolkit API": ({m: [f for f in fs if not hasattr(mod, f)] for m, (mod, fs) in API.items()}, {})}
    out["tokenizer v2, text hash, parse"] = ({"tokens": [FA.tokenize(t) for t in TOKENS],
                                              "text_hash": FA.text_hash(1, [(1, "a b"), (2, "c")]),
                                              "parse": FA.parse("1:2-4,7 3:5 !x f2:1 u")}, {})
    out["vrs.to_bsb"] = ({"map": [[f"{b} {c}:{v}", vrs.to_bsb(b, c, v)] for b, c, v in VRS]}, {})
    out["orig/grc.sqlite"] = orig("orig/grc.sqlite", "MRK", 1, "macula_greek")
    out["orig/heb.sqlite"] = orig("orig/heb.sqlite", "RUT", 1, "macula_hebrew")
    idx = {k: FA.index("RUT", k) for k in ("keys", "lexemes", "fn", "fn_keys")}
    out["index RUT"] = ({k: shape(v) for k, v in idx.items()}, {k: [len(v), sha(v)] for k, v in idx.items()})
    al = os.path.join(R, "export/dan/dan_BSB/jol/jol001.align"); txt = al[:-6] + ".txt"
    head = open(al, encoding="utf-8").readline().rstrip("\n")
    h, rows = FA.read_chapter(al)
    lines = [l for l in open(al, encoding="utf-8").read().splitlines() if l and not l.startswith("#")]
    parsed = all(FA.parse(m) or not m for m, _, _ in rows.values())
    out[".align (dan JOL 1)"] = ({"head": head, "fields per row": sorted({len(l.split("\t")) for l in lines}),
                                  "profiles": sorted({p for _, _, p in rows.values()}), "rows parse": parsed,
                                  "text hash = draft": h == FA.text_hash(1, FA.draft_texts(txt))},
                                 {"rows": [len(rows), sha(rows)], "text hash": h[:16]})
    out["store dan/dan_BSB"] = (store("dan/dan_BSB"), {})
    out["store kvg/kvg_BSB"] = (store("kvg/kvg_BSB"), {})
    out["lang.sqlite (kvg)"] = (schema(os.path.join(R, "export/kvg/kvg_BSB/_learn/lang.sqlite"),
                                       ("nt_tokens", "nt_links", "d_names", "meta")), {})
    return out


def work_commit():
    return subprocess.run(["git", "-C", R, "log", "-1", "--format=%h %cs"], capture_output=True, text=True).stdout.strip()


def main():
    got = {k: {"format": f, "data": d} for k, (f, d) in checks().items()}
    got = json.loads(json.dumps(got, ensure_ascii=False, default=str))   # as read back: tuples -> lists, int keys -> str
    if sys.argv[1:] == ["record"]:
        json.dump({"work repo": work_commit(), "checks": got}, open(EXPECTED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"recorded {len(got)} checks at the work repo's {work_commit()} -> {os.path.relpath(EXPECTED)}"); return 0
    exp = json.load(open(EXPECTED, encoding="utf-8"))
    print(f"expected: work repo {exp['work repo']}; now: {work_commit()}")
    bad = 0
    for k in sorted(set(exp["checks"]) | set(got)):
        e, g = exp["checks"].get(k), got.get(k)
        if e is None or g is None:
            print(f"FORMAT  {k}: {'new check' if e is None else 'check gone'}"); bad += 1; continue
        fd = [f for f in sorted(set(e["format"]) | set(g["format"])) if e["format"].get(f) != g["format"].get(f)]
        dd = [f for f in sorted(set(e["data"]) | set(g["data"])) if e["data"].get(f) != g["data"].get(f)]
        if k == "toolkit API":
            fd = [f"{m}: missing {', '.join(g['format'][m])}" for m in g["format"] if g["format"][m]]
        print(("FORMAT  " if fd else "data    " if dd else "ok      ") + k + (f": {', '.join(fd)}" if fd else "")
              + (f" (data changed: {', '.join(dd)})" if dd else ""))
        bad += bool(fd)
    print(f"contract: {len(got)} checks, {bad} format changes")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
