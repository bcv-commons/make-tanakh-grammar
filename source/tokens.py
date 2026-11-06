#!/usr/bin/env python3
"""The source texts' words: the Greek NT and the Hebrew Bible as the work copy of make-tanakh holds them (orig/grc.sqlite,
orig/heb.sqlite, built from MACULA Greek and MACULA Hebrew). Keys are the texts' own token keys; a Hebrew token is a morpheme and
its word is the key without the last digit. Verse references of the Hebrew are in the Hebrew numbering."""
import collections, sqlite3

from shared import paths

HEB_CLASS = {"verb": "verb", "noun": "noun", "adj": "adj"}
CONTENT = ("noun", "verb", "adj")


def norm_strong(s):
    s = "".join(c for c in (s or "") if c.isdigit())
    return s.lstrip("0")


def _db(source):
    return sqlite3.connect(paths.work("orig", "grc.sqlite" if source == "grc" else "heb.sqlite"))


def greek():
    """key -> token (lemma, cls, tense, mood, person, number, ref, strong, text)"""
    return {k: dict(lemma=lem, cls=c, tense=t, mood=m, person=p, number=n, ref=f"{b} {ch}:{v}", strong=norm_strong(s), text=tx)
            for k, lem, c, t, m, p, n, b, ch, v, s, tx in
            _db("grc").execute("select key, lemma, class, tense, mood, person, number, book, ch, v, strong, text from tokens")}


def hebrew(books):
    """morpheme key -> token of the given books; 'tense' is the conjugation and 'mood' the stem, so that both sources share one
    record shape; 'word' = the word's key"""
    q = ",".join("?" * len(books))
    return {k: dict(lemma=lem, cls=HEB_CLASS.get(c, c), tense=ty, mood=st, person=p, number=n, strong=norm_strong(lx), word=k[:-1], text=tx,
                    ref=f"{b} {ch}:{v}")
            for k, lem, c, ty, st, p, n, lx, tx, b, ch, v in
            _db("hbo").execute(f"select key, lemma, class, type, stem, person, number, lexeme, text, book, ch, v from tokens where book in ({q})",
                               tuple(books))}


def glosses(source, books=None):
    """key -> English gloss (Greek: every token; Hebrew: the morphemes of the given books)"""
    if source == "grc":
        return {k: (g or "").strip() for k, g in _db("grc").execute("select key, gloss from tokens")}
    q = ",".join("?" * len(books))
    return {k: (g or e or "").strip() for k, g, e in
            _db("hbo").execute(f"select key, gloss, english from tokens where book in ({q})", tuple(books))}


def verse_texts(source, refs):
    """ref -> the verse's source text"""
    out = collections.defaultdict(str); books = sorted({r.split()[0] for r in refs})
    if not books:
        return {}
    q = ",".join("?" * len(books))
    for b, ch, v, t, a in _db(source).execute(f"select book, ch, v, text, coalesce(after, ' ') from tokens where book in ({q}) order by key", tuple(books)):
        r = f"{b} {ch}:{v}"
        if r in refs:
            out[r] += t + a
    return {r: " ".join(t.split()) for r, t in out.items()}


def chapter_refs(source, book, chapters):
    """the verse references of a book's chapters, in order"""
    q = ",".join("?" * len(chapters))
    return [f"{book} {ch}:{v}" for ch, v in
            _db(source).execute(f"select distinct ch, v from tokens where book = ? and ch in ({q}) order by ch, v", (book, *chapters))]


def books(source):
    return [b for b, in _db(source).execute("select book from tokens group by book order by min(key)")]
