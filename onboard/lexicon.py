#!/usr/bin/env python3
"""The lexicons of a language (the preparation plan's P8): the team's word forms indexed to the source lexemes, built by
code from the alignment layers. No verse text inside: word forms, counts and references only. Private, like the corpus.

    . ./env.sh
    python3 onboard/lexicon.py words --lang xxx [--out F] -> $MAKE_TANAKH_PRIVATE/lang/<iso>/lexicon/words.db (replaced)
    python3 onboard/lexicon.py check --lang xxx          -> coverage figures

words.db is in make-tanakh's format (scripts/words.py, docs/word-db.md: our schema extended; written by its write_db
since v0.5.0), from the layer on the written words (whole words) of every corpus of the configuration. Its tables:

  lexeme(id, lang, strong, lemma, cls, n, type)    a source lexeme: `grc:26`, `hbo:3117` (Strong's number as the public
                                                   index writes it, a Hebrew homonym letter kept: `hbo:2050b`)
  form(id, form, plain, bare, tokens, n, project)  a target form as written (NFC), lower case (`plain`), and without its
                                                   marks (`bare`; the configuration's "keep_marks" are kept); a link to
                                                   several tokens is one form, its tokens joined by a space, or by " … "
                                                   where words of the verse stand between them
  link(lexeme, form, n, n_strong, books, share, back)
                                                   one row per pair; n_strong = links the aligner itself rated high (method
                                                   letter in upper case); share = of the lexeme's links, back = of the form's
  occ(lexeme, form, ref, src, key, positions, method, edition, layer, level)
                                                   every link: the verse (the team's numbering), the source word (`c3` = the
                                                   fourth content word of the verse in the public index, `f0` a function
                                                   word), its token key, the target token positions, the method letter,
                                                   the edition, the layer, `words`
  vocab(plain, bare, book, ch, n, edition)         the written words per chapter (make-tanakh's spelling check reads it)
  meta(name, value)                                what it was built from; `format` is make-tanakh's

The layer is the corpus's "words_layer" when it names one (a published layer of the same wording, checked verse by verse
when the entry says "verses": true; onboard/corpus.py), else the corpus's own layer when it is on the written words (a
published layer, Zinza); a layer on the parts view (onboard/align.py with a segmenter) has its words layer beside it,
align/out_words. Closed and held-out chapters and the
corpus's excluded books are left out (shared/holdout.py)."""
import argparse, collections, glob, json, os, re, sqlite3, sys, time, unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import holdout, paths  # noqa: E402
from source import tokens  # noqa: E402
from onboard.corpus import parse, published_verses, verse_hash  # noqa: E402
import full_align as FA, vrs  # noqa: E402  (the toolkit: the public index of the source words; the numberings)
import words as WT  # noqa: E402  (the toolkit's word DB: its format and writer)


def words_layer(lang, cfg, x):
    """the folder of the layer on the written words for one corpus"""
    if x.get("words_layer"):
        return paths.resolve(lang, x["words_layer"])
    if x.get("layer") and not x.get("units"):
        return paths.resolve(lang, x["layer"])
    code = cfg.get("code", cfg["iso"])
    d = glob.glob(paths.lang_dir(lang, "align", "out_words", "compact", "*", code, cfg["text"]["edition"]))
    if not d:
        sys.exit(f"{lang}: no layer on the written words for {x['source']} (run onboard/align.py, or name \"words_layer\")")
    return d[0]


def split_tokens(d):
    """(book, ch, v) -> [word as written, ...] by the aligner's token index: the split's `word`, verse-text's
    tokenize_written (the aligner's own token, tokenize, drops every mark NFC cannot compose)"""
    import pyarrow.parquet as pq
    if "word" not in pq.read_schema(os.path.join(d, "words.parquet")).names:
        sys.exit(f"{d}: the split file has no `word` column (the word as written, verse-text's tokenize_written): write it with onboard/split_export.py")
    out = collections.defaultdict(dict); al = collections.defaultdict(dict)
    for r in pq.read_table(os.path.join(d, "words.parquet"), columns=["book", "chapter", "verse", "i", "token", "word"]).to_pylist():
        k = (r["book"], int(r["chapter"]), int(r["verse"])); al[k][int(r["i"])] = r["token"] or ""
        out[k][int(r["i"])] = r["word"] if r["word"] is not None else r["token"]
    return ({k: [v.get(i, "") for i in range(max(v) + 1)] for k, v in out.items()}, json.load(open(os.path.join(d, "_split.json"), encoding="utf-8")),
            {k: verse_hash([v[i] for i in sorted(v)]) for k, v in al.items()})


def lex_id(source, s):
    """the public index's Strong's number -> `grc:26`, `hbo:2050b`"""
    m = re.match(r"0*(\d+)([a-z]?)$", s or "")
    return f"{source}:{m.group(1)}{m.group(2)}" if m else None


def bare(s, keep):
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c) or c in keep))


def cmd_words(a):
    cfg = paths.config(a.lang); shut = holdout.shut(cfg); keep = set(cfg.get("keep_marks", []))
    out = a.out or paths.lang_dir(a.lang, "lexicon", "words.db")
    edition = cfg["text"]["edition"]; SRC = WT.Source()                       # the type (proper or not) as make-tanakh reads it
    lex, occ, vocab = {}, [], collections.Counter(); st = collections.Counter(); rec = {"built": time.strftime("%Y-%m-%d %H:%M"), "corpora": {}}
    for x in cfg["corpora"]:
        source = x["source"]; hebrew = source == "hbo"; mine = set(tokens.books(source)); excl = set(x.get("exclude_books") or [])
        ld = words_layer(a.lang, cfg, x); layer = os.path.relpath(ld, paths.private()); toks, hdr, vhash = split_tokens(paths.resolve(a.lang, x["split"])); fp = hdr.get("text_fp", {})
        vcheck = published_verses(ld) if x.get("verses") else None
        src_tok = tokens.hebrew(sorted(mine)) if hebrew else tokens.greek(); seen = set(); used = []
        for lf in sorted(glob.glob(os.path.join(ld, "*_*.json"))):
            name = os.path.basename(lf)
            if name.count(".") != 1:
                continue
            book, f = name[:-5].split("_")
            if book not in mine or book in excl:
                continue
            if vcheck is None and fp.get(book) != f:
                st["books skipped (layer and split are not of the same text)"] += 1; continue
            used.append(book); main_s = json.load(open(lf, encoding="utf-8")); meta = json.load(open(lf[:-5] + ".meta.json", encoding="utf-8"))
            fn_s = meta.get("fn") or []; meth = meta.get("method") or []       # one method letter per entry of the main string
            refs = list(FA.index(book, "lexemes")); L = FA.index(book, "lexemes"); K = FA.index(book, "keys")
            FL = FA.index(book, "fn"); FK = FA.index(book, "fn_keys")
            for i, r in enumerate(refs):
                c, v = (int(n) for n in r.split(" ")[1].split(":")); tk = toks.get((book, c, v))
                if not tk:
                    continue
                if vcheck is not None and vcheck.get(r) != vhash.get((book, c, v)):
                    st["verses whose tokens are not the published text's (left out)"] += 1; continue
                ref = r
                if hebrew:                                     # the layer is in the Hebrew numbering; the lexicon in the team's
                    e = vrs.to_bsb(book.lower(), c, v)
                    if not e or e[1] == "title":
                        continue
                    ref = f"{book} {int(e[0])}:{int(e[1])}"
                    if ref in seen:
                        continue
                    seen.add(ref)
                if shut(book, int(ref.split(" ")[1].split(":")[0])):
                    st["verses left out (closed or held out)"] += 1; continue
                st["verses"] += 1; bk, ch = ref.split(" ")[0], int(ref.split(" ")[1].split(":")[0])
                for w in tk:
                    if re.search(r"\w", w):
                        vocab[(unicodedata.normalize("NFC", w).lower(), bk, ch, edition)] += 1
                for kind, s, lexs, keys, ms in (("c", main_s[i] if i < len(main_s) else "", L.get(r, []), K.get(r, []), meth[i] if i < len(meth) else ""),
                                                ("f", fn_s[i] if i < len(fn_s) else "", FL.get(r, []), FK.get(r, []), "")):
                    for j, (o, ps) in enumerate(parse(s).items()):
                        lx = lex_id(source, lexs[o]) if o < len(lexs) else None; key = keys[o] if o < len(keys) else ""
                        ps = sorted(p for p in set(ps) if 0 <= p < len(tk) and re.search(r"\w", tk[p]))
                        if not lx or not ps:
                            continue
                        form = unicodedata.normalize("NFC", "".join((" … " if n and p > ps[n - 1] + 1 else " " if n else "") + tk[p]
                                                                    for n, p in enumerate(ps))); m = ms[j] if j < len(ms) else ""
                        if lx not in lex:
                            k0 = key.split("+")[0].lstrip("n"); t = src_tok.get(k0) or {}
                            lex[lx] = (source, lx.split(":")[1], t.get("lemma"), t.get("cls"), (SRC.book(source, book).get(k0) or (None, None, None))[2])
                        occ.append((lx, form, ref, f"{kind}{o}", key, json.dumps(ps), m, edition, layer, "words")); st["links"] += 1
        rec["corpora"][source] = {"layer": layer, "books": used}
    rec.update({k: v for k, v in st.items()}, language=a.lang, keep_marks=[f"U+{ord(c):04X}" for c in sorted(keep)])
    WT.write_db(out, occ, lex, vocab, rec, keep=tuple(keep))
    db = sqlite3.connect(out); m = dict(db.execute("select name, value from meta")); db.close()
    print(json.dumps({k: m[k] for k in ("built", "format", "lexemes", "forms", "links", "pairs", "verses") if k in m}), "->", out)


def cmd_check(a):
    p = paths.lang_dir(a.lang, "lexicon", "words.db")
    if not os.path.exists(p):
        sys.exit(f"{a.lang}: no words.db yet (onboard/lexicon.py words)")
    db = sqlite3.connect(p); q = lambda s: db.execute(s).fetchone()[0]
    res = {"lexemes": q("select count(*) from lexeme"), "forms": q("select count(*) from form"), "links": q("select count(*) from occ")}
    for lang in ("grc", "hbo"):
        n = q(f"select count(*) from lexeme where lang='{lang}'")
        if n:
            res[f"{lang}: lexemes seen 3+ times, top form's share (median)"] = q(
                f"select share from (select max(l.share) share from link l join lexeme x on x.id=l.lexeme where x.lang='{lang}' and x.n>=3 "
                f"group by l.lexeme) order by share limit 1 offset (select count(*)/2 from lexeme where lang='{lang}' and n>=3)")
    res["links rated high by the aligner"] = round(q("select sum(n_strong)*1.0/sum(n) from link"), 3)
    print(json.dumps(res, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("words", "check")); ap.add_argument("--lang", required=True)
    ap.add_argument("--out", help="words: another file than lexicon/words.db (to compare)")
    a = ap.parse_args(); {"words": cmd_words, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
