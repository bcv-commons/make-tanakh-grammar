#!/usr/bin/env python3
"""The corpus of a language: the team's text as parts, each part with its word and its slot, and the links from the source
words to the parts. Everything the drafter knows about a language's wording comes from this file.

Built from two inputs, named in the language's configuration under the corpus ("split", "layer"):

  split   the split file of the team's text (bcv-split: words.parquet + _split.json): every word of every verse divided into
          parts by the language's segmenter (lexeme-aligner's segmenter, a bundle of the language-analysis dataset), each
          part with its slot (prefix, stem, suffix; whole = an undivided word) and its position class
  layer   the alignment layer of the same text by parts (compact-alignments: <book>_<fingerprint>.json + .meta.json). Either
          a published layer on the written words with a parts channel (lexeme-aligner's, at its pin), or the layer of a
          local run on the parts view (onboard/align.py); then "units" names the view's unit map (units.json), which says which
          token and part each of the layer's positions is, and "view" the view itself: the corpus's parts are then the view's
          units as the aligner saw them (a divided word's parts without their marks, a part without letters left out)

A book whose text fingerprint in the layer is not the split file's is skipped and reported: the two inputs must be of the
same text. The source words are named by the toolkit's public index (compact-alignments).

    . ./env.sh
    python3 onboard/corpus.py build --lang zin [--source grc]        -> the corpus named in the configuration (replaced)
    python3 onboard/corpus.py check --lang zin [--against OTHER.db]  -> figures; with --against, the difference to another corpus

The corpus (SQLite): verse(ref, book, ch, v, split, words, wordidx, slots): words = the parts in reading order, wordidx = each
part's word, slots = each part's slot (`stem`, `p<position>.<k>` before the stem, `s<position>.<k>` after it; k counts parts
of one position outward from the stem); link(key, ref, positions, ...): a source word's key and the parts it is linked to.

--source hbo builds the corpus of a team's Tanakh text the same way. Its split file and layer are in the Hebrew Bible's
numbering (onboard/align.py writes the text so); a verse is kept under its reference in the team's numbering (`ref`) with the
Hebrew one beside it (`heb`), and a link is named by the Hebrew word (`word`). A psalm's title, and the second of two Hebrew
verses that share one verse of the team's numbering, are left out."""
import argparse, collections, glob, json, os, sqlite3, sys, time, unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths  # noqa: E402
from source import tokens  # noqa: E402
import full_align as FA, vrs  # noqa: E402  (the toolkit: the public index of the source words; the numberings)


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
    """'c4:14.0,14.1 f10:32 ...' -> {(kind, ordinal): [(token, part or None), ...]}"""
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


def slots_of(rows):
    """the slots of one word's parts [(part, text, slot, position)] in order: stem, p<position>.<k>, s<position>.<k>"""
    if len(rows) == 1:
        return ["stem"]
    stem = next((i for i, r in enumerate(rows) if r[2] == "stem"), None)
    if stem is None and all(r[2] == "prefix" for r in rows):      # a piece of a hyphen word whose stem is in the next piece
        stem = len(rows) - 1
    elif stem is None and all(r[2] == "suffix" for r in rows):
        stem = 0
    if stem is None:                                   # no stem named: the longest part is the stem
        h = max(range(len(rows)), key=lambda i: (len(rows[i][1]), -i))
        return [f"p9.{h - 1 - i}" if i < h else ("stem" if i == h else f"s9.{i - h - 1}") for i in range(len(rows))]
    lab = [None] * len(rows); lab[stem] = "stem"; cnt = collections.Counter()
    for i in range(stem - 1, -1, -1):
        k = ("p", rows[i][3] or 0); lab[i] = f"p{k[1]}.{cnt[k]}"; cnt[k] += 1
    for i in range(stem + 1, len(rows)):
        k = ("s" if rows[i][2] != "prefix" else "p", rows[i][3] or 0); lab[i] = f"{k[0]}{k[1]}.{cnt[k]}"; cnt[k] += 1
    return lab


def read_split(d):
    """(book, ch, v) -> [(token index, part, text, slot, position)] in reading order; and the books' text fingerprints"""
    import pyarrow.parquet as pq
    rows = pq.read_table(os.path.join(d, "words.parquet"), columns=["book", "chapter", "verse", "i", "part", "text", "slot", "position"]).to_pylist()
    verses = collections.defaultdict(list)
    for r in rows:
        verses[(r["book"], int(r["chapter"]), int(r["verse"]))].append((int(r["i"]), int(r["part"]), r["text"], r["slot"], r["position"]))
    for k in verses:
        verses[k].sort(key=lambda x: (x[0], x[1]))
    return verses, json.load(open(os.path.join(d, "_split.json"), encoding="utf-8"))


def read_view(d):
    """the parts view's verse texts: {book: {(chapter, verse): [unit, ...]}} (the files lexeme-aligner's write_view writes)"""
    out = {}
    for f in sorted(glob.glob(os.path.join(d, "[0-9]*-*.json"))):
        book = os.path.basename(f).split("-", 1)[1][:3]; vs = out.setdefault(book, {}); ch = None
        for el in json.load(open(f, encoding="utf-8"))["content"]:
            if el.get("type") == "chapter":
                ch = int(el["number"])
            elif el.get("type") == "para":
                cur = None
                for x in el["content"]:
                    if isinstance(x, dict) and x.get("type") == "verse":
                        cur = int(str(x["number"]).split("-")[0])
                    elif isinstance(x, str) and cur is not None:
                        vs[(ch, cur)] = vs.get((ch, cur), []) + x.split()
    return out


def cmd_build(a):
    cfg = paths.config(a.lang, built=False); x = paths.corpus(cfg, a.source)
    if not x or not x.get("split") or not x.get("layer"):
        sys.exit(f"{a.lang}: the configuration's {a.source} corpus names no \"split\" and \"layer\" to build from")
    hebrew = a.source == "hbo"; mine = set(tokens.books(a.source)); seen = set(); kcol = x.get("key", "word" if hebrew else "key")
    sd, ld = paths.resolve(a.lang, x["split"]), paths.resolve(a.lang, x["layer"]); verses, hdr = read_split(sd); fp = hdr["text_fp"]
    umap = json.load(open(paths.resolve(a.lang, x["units"]), encoding="utf-8")) if x.get("units") else None
    vtext = read_view(paths.resolve(a.lang, x["view"])) if x.get("view") else None
    os.makedirs(os.path.dirname(x["_db"]), exist_ok=True); tmp = x["_db"] + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    db = sqlite3.connect(tmp)
    db.execute(f"create table verse(ref text primary key, {'heb text, ' if hebrew else ''}book text, ch int, v int, split text, words text, wordidx text, slots text)")
    db.execute(f"create table link({kcol} text primary key, ref text, positions text, supplied text, chunk text, row int)")
    db.execute("create table meta(name text, value text)")
    st = collections.Counter(); skipped = []; exclude = set()
    for lf in sorted(glob.glob(os.path.join(ld, "*_*.json"))):
        if os.path.basename(lf).count(".") != 1 or os.path.basename(lf).startswith("_"):      # <book>_<fingerprint>.json only
            continue
        book, f = os.path.basename(lf)[:-5].split("_")
        if book not in mine or book in exclude:
            continue
        if umap is None and fp.get(book) != f:
            skipped.append(book); continue
        main_s = json.load(open(lf, encoding="utf-8")); meta = json.load(open(lf[:-5] + ".meta.json", encoding="utf-8"))
        fn_s = meta.get("fn") or [""] * len(main_s); parts_s = meta.get("parts") or [""] * len(main_s)
        refs = list(FA.index(book, "lexemes")); keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys"); st["books"] += 1
        for i, r in enumerate(refs):
            c, v = (int(n) for n in r.split(" ")[1].split(":")); rows = verses.get((book, c, v))
            if not rows:
                st["source verses without text"] += 1; continue
            ref = r
            if hebrew:                                     # r is in the Hebrew numbering; the corpus is keyed by the team's
                e = vrs.to_bsb(book.lower(), c, v)
                if not e or e[1] == "title":
                    st["verses left out (title)"] += 1; continue
                ref = f"{book} {int(e[0])}:{int(e[1])}"
                if ref in seen:
                    st["verses sharing a verse of the team's numbering (second left out)"] += 1; continue
                seen.add(ref)
            if umap is not None:                           # a layer on the parts view: the verse is the view's units, in its order
                un = (umap.get(book) or {}).get(f"{c}:{v}"); vt = (vtext.get(book) or {}).get((c, v)) if vtext is not None else None
                if un is None or (vt is not None and len(vt) != len(un)):
                    st["verses without units"] += 1; continue
                srow = collections.defaultdict(dict)
                for t, p, text, slot, posn in rows:
                    srow[t][p] = (text, slot, posn)
                urows = []
                for n, (t, part) in enumerate(un):
                    if part is None:                       # an undivided word
                        urows.append((t, 0, vt[n] if vt else "".join(x_[0] for _, x_ in sorted(srow[t].items())), "whole", None))
                    else:
                        text, slot, posn = srow[t].get(part, ("", "stem", None)); urows.append((t, part, vt[n] if vt else text, slot, posn))
                rows = urows
            toks = sorted({t for t, *_ in rows}); rank = {t: n for n, t in enumerate(toks)}
            flat = {(t, p): n for n, (t, p, *_) in enumerate(rows)}; byt = collections.defaultdict(list)
            for n, (t, p, text, slot, posn) in enumerate(rows):
                byt[t].append((p, text, slot, posn))
            units = [text for _, _, text, _, _ in rows]; widx = [rank[t] for t, *_ in rows]
            slots = [s for t in toks for s in slots_of(byt[t])]; pmap = parse_parts(parts_s[i] if i < len(parts_s) else "")
            pos = collections.defaultdict(set)
            for kind, s, ks in (("c", main_s[i] if i < len(main_s) else "", keys.get(r, [])), ("f", fn_s[i] if i < len(fn_s) else "", fkeys.get(r, []))):
                for o, ps in parse(s).items():
                    k = ks[o] if o < len(ks) else None
                    if not k:
                        continue
                    spec = pmap.get((kind, o)); tp = []
                    if umap is not None:                     # the layer's positions are the view's units
                        tp = [p_ for p_ in ps if p_ < len(rows)]
                    elif spec:
                        for t, part in spec:
                            tp += [flat[(t, part)]] if part is not None and (t, part) in flat else [n for (t2, _), n in flat.items() if t2 == t]
                    else:
                        tp = [n for (t2, _), n in flat.items() if t2 in ps]
                    for k2 in (k.split("+") if hebrew else [k.split("+")[0].lstrip("n")]):
                        pos[k2[:-1] if hebrew else k2].update(tp)      # Hebrew: the word of the morpheme
            rc, rv = (int(n) for n in ref.split(" ")[1].split(":"))
            db.execute(f"insert into verse values ({'?,' if hebrew else ''}?,?,?,?,?,?,?,?)", ((ref, r) if hebrew else (ref,)) + (
                book, rc, rv, "", json.dumps(units, ensure_ascii=False), json.dumps(widx), json.dumps(slots, ensure_ascii=False)))
            st["verses"] += 1; st["parts"] += len(units); st["words"] += len(toks)
            for n, (w, ps) in enumerate(sorted(pos.items())):
                ps = sorted(p for p in ps if 0 <= p < len(units))
                if ps:
                    st["source words linked"] += 1
                    db.execute("insert or ignore into link values (?,?,?,?,?,?)", (w, ref, json.dumps(ps), "[]", " ".join(units[p] for p in ps), n))
    if not st["verses"]:
        db.close(); os.remove(tmp); sys.exit(f"no verse of a {a.source} book in the layer and the split file: nothing built, the corpus is left as it was")
    rec = {"built": time.strftime("%Y-%m-%d %H:%M"), "split": {k: hdr.get(k) for k in ("spec", "edition", "source", "sha256", "date")},
           "layer": os.path.basename(os.path.normpath(ld)), "books skipped (fingerprint)": skipped, **st}
    for k, v in rec.items():
        db.execute("insert into meta values (?,?)", (k, json.dumps(v) if not isinstance(v, str) else v))
    db.commit(); db.close(); os.replace(tmp, x["_db"])
    print(json.dumps({k: v for k, v in rec.items() if k != "split"}), "->", x["_db"])
    if skipped:
        print("skipped books: the layer and the split file are not of the same text there", file=sys.stderr)


def read(db):
    z = sqlite3.connect(db)
    V = {r: (json.loads(w), json.loads(wi) if wi else None, json.loads(sl) if sl else None) for r, w, wi, sl in z.execute("select ref, words, wordidx, slots from verse")}
    kcol = [c[1] for c in z.execute("pragma table_info(link)")][0]
    L = {(k, r): json.loads(p) for k, r, p in z.execute(f"select {kcol}, ref, positions from link")}
    return V, L


def cmd_check(a):
    cfg = paths.config(a.lang); x = paths.corpus(cfg, a.source); V, L = read(x["_db"]); nfc = lambda s: unicodedata.normalize("NFC", s)
    res = {"corpus": x["db"], "verses": len(V), "parts": sum(len(v[0]) for v in V.values()), "words": sum(max(v[1]) + 1 for v in V.values() if v[1]),
           "links": len(L), "parts with a link": len({(r, p) for (k, r), ps in L.items() for p in ps}),
           "divided words": sum(1 for v in V.values() if v[1] for n in collections.Counter(v[1]).values() if n > 1)}
    if a.against:
        V2, L2 = read(a.against); both = [r for r in V if r in V2 and V2[r][1] is not None]
        res["against"] = {"verses there": len(V2), "there with word boundaries": sum(v[1] is not None for v in V2.values()), "in both": len(both),
                          "same parts": sum([nfc(p) for p in V[r][0]] == [nfc(p) for p in V2[r][0]] for r in both),
                          "same word boundaries": sum(V[r][1] == V2[r][1] for r in both), "same slots": sum(V[r][2] == V2[r][2] for r in both),
                          "links there": len(L2), "links only here": len(set(L) - set(L2)), "links only there": len(set(L2) - set(L)),
                          "links with the same parts": sum(L[k] == L2[k] for k in L if k in L2)}
    print(json.dumps(res, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "check")); ap.add_argument("--lang", required=True); ap.add_argument("--source", default="grc", choices=paths.SOURCES)
    ap.add_argument("--against"); a = ap.parse_args(); {"build": cmd_build, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
