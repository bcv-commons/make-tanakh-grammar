#!/usr/bin/env python3
"""Evidence for drafting: for every source clause of the chapters to draft, the team's own translation of the most similar clauses.

The pool is the team's text as clauses: every clause of the source texts whose verse the team has translated, with its source
words, the team's words of that stretch as parts, and the links between them. Never in the pool: the closed and held-out chapters
(shared/holdout.py), a corpus's excluded books, the books a job leaves out, and at ranking the chapter being drafted itself.

The ranking: shared content lexemes, idf-weighted, plus the clause columns (kind, rule, the finite verb's tense and mood, its
person and number, negation) at fixed weights. A Greek clause asks the Greek pool by lemma. A Hebrew clause asks the Hebrew pool
by Strong's number and the Greek pool through the bridges (source/bridges.py): a Hebrew lexeme counts for its three best Greek
lexemes at their share, a Hebrew conjugation and stem matches the Greek tenses and moods it corresponds to.

Two modes. The default merges the segments of an interrupted clause into one query clause and shows every ranked pool clause
as it is. `legacy=True` reproduces the research harness, in which a clause of several segments was represented by its last
segment (as a query and as a pool record) and ties were broken in set order (PYTHONHASHSEED=0): it exists so that the prompts
measured in research can be rebuilt byte for byte (tests/parity.py), and goes when the default has been measured against it."""
import collections, json, math, sqlite3

from shared import holdout, paths
from source import bridges, layout, tokens

CONTENT = tokens.CONTENT
NEG = {"οὐ", "μή", "οὐδέ", "μηδέ", "οὔτε", "μήτε", "οὐδείς", "μηδείς", "οὐκέτι", "μηκέτι"}        # Greek negation lemmas
HEB_NEG = {"3808", "408", "1077", "369", "1115", "1097"}                                    # lo', 'al, bal, 'ayin, bilti, beli (Strong's)
COL_WEIGHT = {"kind": 1.0, "rule": 1.5, "verb": 2.0, "pn": 1.5, "neg": 1.5}                 # in idf units (a lemma's idf is about 3-9)
HEB_HEAD = ("verb", "noun", "adj")
K = 100


# ------------------------------------------------------------------ the team's text

def head_word(pos, wi, sl):
    """the linked word holding a linked stem part, else the one with the most linked parts; ties: the later word"""
    n = collections.Counter(wi[p] for p in pos); stem = {wi[p] for p in pos if sl[p] == "stem"}
    return max(n, key=lambda w: (w in stem, n[w], w))


def read_corpus(cfg, source, leave_out_books=()):
    """(verses {ref: (parts, word index per part, slot per part)}, gold {source key: (parts of the head word, stem, affix pattern,
    ref, word index, linked part positions, linked word indexes)}, heb {Hebrew-numbering ref: ref}) of the language's corpus of one
    source language, outside everything a pool may not hold"""
    x = paths.corpus(cfg, source)
    if x is None:
        return {}, {}, {}
    shut = holdout.shut(cfg); out = set(x.get("exclude_books", ())) | set(leave_out_books)
    z = sqlite3.connect(x["_db"]); verses = {}; heb = {}
    cols = [r[1] for r in z.execute("pragma table_info(verse)")]
    for ref, book, ch, words, wi, sl, hb in z.execute(f"select ref, book, ch, words, wordidx, slots, {'heb' if 'heb' in cols else 'ref'} from verse"):
        if book in out or shut(book, ch) or not wi:
            continue
        verses[ref] = (json.loads(words), json.loads(wi), json.loads(sl)); heb[hb or ref] = ref
    gold = {}
    for k, ref, pos in z.execute(f"select {x['key']}, ref, positions from link"):
        v = verses.get(ref)
        if not v:
            continue
        ws, wi, sl = v; pos = sorted({p for p in json.loads(pos or "[]") if p < len(wi)})
        if not pos:
            continue
        w = head_word(pos, wi, sl); idx = [i for i, y in enumerate(wi) if y == w]
        parts = tuple(ws[i].lower() for i in idx)
        st = [ws[i].lower() for i in idx if sl[i] == "stem" and i in pos] or [ws[i].lower() for i in idx if sl[i] == "stem"]
        stem = st[0] if st else max(parts, key=len)
        gold[k] = (parts, stem, tuple("_" if y == stem else y for y in parts), ref, w, tuple(pos), tuple(sorted({wi[p] for p in pos})))
    return verses, gold, heb


def corpus_books(cfg, source):
    """the books of the language's corpus of one source language (excluded books left out)"""
    x = paths.corpus(cfg, source)
    if x is None:
        return []
    out = set(x.get("exclude_books", ()))
    return [b for b, in sqlite3.connect(x["_db"]).execute("select distinct book from verse") if b not in out]


# ------------------------------------------------------------------ clause records

def cell(t):
    return (t["tense"], t["mood"], t["person"], t["number"])


def finite(toks, lang):
    if lang == "grc":
        return next((t for t in toks if t["cls"] == "verb" and t["mood"] not in (None, "participle", "infinitive")), None)
    return next((t for t in toks if t["cls"] == "verb" and t["tense"] and not t["tense"].startswith(("participle", "infinitive"))), None)


def clause_record(cid, lang, book, ch, kind, rule, keys, T, gold, verses, query=False):
    """one clause: columns, lexemes, tokens (with cell and linked word index) and, for a pool clause, the team's parts of the
    words its tokens link to (the verse's word span between the first and the last linked word)"""
    toks = [dict(T[k], key=k) for k in keys if k in T]
    fin = finite(toks, lang)
    neg = any(t["lemma"] in NEG for t in toks) if lang == "grc" else any(t["strong"] in HEB_NEG for t in toks)
    rec = dict(id=cid, lang=lang, book=book, ch=ch, kind=kind or "", rule=rule or "", refs=sorted({t["ref"] for t in toks}),
               verb=f"{fin['tense']}|{fin['mood']}" if fin else "", pn=f"{fin['person']}|{fin['number']}" if fin else "", neg=neg,
               lem={t["lemma"] for t in toks if t["cls"] in CONTENT and t["lemma"]},
               skeys={("G" if lang == "grc" else "H") + t["strong"] for t in toks if t["cls"] in CONTENT and t["strong"]})
    tl = []
    for t in toks:
        g = None if query else gold.get(t["key"] if lang == "grc" else t["word"])
        tl.append(dict(key=t["key"], lemma=t["lemma"], strong=t["strong"], cls=t["cls"], text=t["text"],
                       cell=list(cell(t)) if t["cls"] == "verb" else None, ref=g[3] if g else None, w=g[4] if g else None,
                       pos=list(g[5]) if g else [], ws=list(g[6]) if g else [], sref=t["ref"]))
    rec["tokens"] = tl
    if not query:
        span = collections.defaultdict(list)
        for d in tl:
            if d["w"] is not None:
                span[d["ref"]].extend(d["ws"])                 # every linked word, not only the head
        words = {}
        for ref, ws in span.items():
            ps, wi, sl = verses[ref]; lo, hi = min(ws), max(ws)
            words[ref] = {"w0": lo, "words": [[[ps[i], sl[i]] for i in range(len(ps)) if wi[i] == w] for w in range(lo, hi + 1)],
                          "pos": [[i for i in range(len(ps)) if wi[i] == w] for w in range(lo, hi + 1)]}
        rec["words"] = words
    return rec


def _in_job(refs, book, chapters, legacy):
    """does a clause with these verse references (in order) belong to the job? Legacy: when all its verses do; default: by its first"""
    ok = [r.split()[0] == book and int(r.split()[1].split(":")[0]) in chapters for r in refs]
    return bool(ok) and (all(ok) if legacy else ok[0])


def greek_clauses(T, gold, verses, query_verses):
    """(pool, query rows) of the Greek clause layout: a row is a pool clause when its first word's verse has team text in `verses`,
    a query row when that verse is in query_verses"""
    pool, queries = [], []
    for r in layout.greek_rows():
        if not r["words"] or r["words"][0] not in T:
            continue
        ref = T[r["words"][0]]["ref"]; a = (f"G:{r['clause']}", "grc", r["book"], r["chapter"], r["kind"], r["rule"], r["words"], T, gold, verses)
        if ref in query_verses:
            queries.append(clause_record(*a, True))
        elif ref in verses:
            pool.append(clause_record(*a))
    return pool, queries


def hebrew_clauses(H, gold, verses, query_verses, book, shut, query_chapters=None):
    """(pool, query rows) of one book's Hebrew clause layout. A row's verse is given in the English numbering (the corpus's);
    query_chapters selects query rows by the Hebrew chapter instead of by verse"""
    pool, queries = [], []
    for r in layout.hebrew_rows(book):
        ref = r["verse_ref_en"]; b, cv = ref.split(); ch = int(cv.split(":")[0])
        if shut(r["book"], r["chapter"]) or shut(b, ch) or not r["words"]:
            continue
        a = (f"H:{r['clause_key']}", "hbo", r["book"], r["chapter"], r["kind"], r["rule"], r["words"], H, gold, verses)
        if (r["chapter"] in query_chapters) if query_chapters is not None else (ref in query_verses):
            queries.append(clause_record(*a, True))
        if ref in verses:
            pool.append(clause_record(*a))
    return pool, queries


def merge_segments(rows):
    """the rows of one clause id joined into one query clause: the words in text order, the columns of the first row"""
    by = collections.OrderedDict()
    for q in rows:
        by.setdefault(q["id"], []).append(q)
    out = []
    for cid, qs in by.items():
        if len(qs) == 1:
            out.append(qs[0]); continue
        toks = sorted({t["key"]: t for q in qs for t in q["tokens"]}.values(), key=lambda t: t["key"])
        m = dict(qs[0], tokens=toks, refs=sorted({r for q in qs for r in q["refs"]}), lem=set().union(*(q["lem"] for q in qs)),
                 skeys=set().union(*(q["skeys"] for q in qs)), neg=any(q["neg"] for q in qs))
        m["pieces"] = [sorted({t["key"][:11] for t in q["tokens"]}) for q in sorted(qs, key=lambda q: min(t["key"] for t in q["tokens"]))]
        fq = next((q for q in qs if q["verb"]), None)
        if fq:
            m["verb"], m["pn"] = fq["verb"], fq["pn"]
        out.append(m)
    return out


def word_level(q, gl, lex):
    """a Hebrew query clause with its morphemes merged into words (key = the word's key, the corpus's link key): text = the
    morphemes joined by '+', the content morpheme's lemma, Strong's number, class and cell (verb > noun > adj > the first), gloss =
    the morphemes' glosses joined by ' + '"""
    words = collections.OrderedDict()
    for t in q["tokens"]:
        words.setdefault(t["key"][:11], []).append(t)
    toks = []
    for w, ms in words.items():
        head = next((m for c in HEB_HEAD for m in ms if m["cls"] == c), ms[0])
        toks.append(dict(head, key=w, mkey=head["key"], text="+".join(m["text"] for m in ms), morphemes=[m["key"] for m in ms],
                         gstrongs=[g for g, _ in lex.get(head["strong"], [])[:bridges.TOP]],
                         gloss=" + ".join(y for y in (gl.get(m["key"], "") for m in ms) if y)))
    return dict(q, tokens=toks)


# ------------------------------------------------------------------ ranking

class Ranker:
    """idf over the pool's lexemes plus the clause columns. space = 'lem' (Greek lemmas: a Greek query) or 'skeys' (Strong's
    numbers with the bridges: a Hebrew query)"""
    def __init__(self, pool, space, lex=None, cells=None, legacy=False):
        self.pool, self.space, self.legacy = pool, space, legacy; self.lb = lex or {}; self.cb = cells or {}
        df = collections.Counter(l for c in pool for l in c[space]); N = len(pool)
        self.idf = {l: math.log(N / d) for l, d in df.items()}
        self.inv = collections.defaultdict(list)
        for i, c in enumerate(pool):
            for l in c[space]:
                self.inv[l].append(i)

    def qkeys(self, q):
        keys = q[self.space] if self.legacy else sorted(q[self.space])
        if self.space == "lem":
            return [(l, 1.0) for l in keys]
        out = []
        for h in keys:
            out.append((h, 1.0))
            for g, p in self.lb.get(h[1:], [])[:bridges.TOP]:
                out.append(("G" + g, p))
        return out

    def verb_match(self, q, c):
        if q["verb"] == "":
            return False
        if c["lang"] == q["lang"]:
            return c["verb"] == q["verb"]
        return c["verb"] in self.cb.get(q["verb"], ())

    def rank(self, q, k, exclude=None):
        sc = collections.Counter()
        for l, w in self.qkeys(q):
            for i in self.inv.get(l, ()):
                sc[i] += self.idf[l] * w
        if exclude:
            for i in [i for i in sc if exclude(self.pool[i])]:
                del sc[i]
        cw = COL_WEIGHT
        for i in list(sc):
            c = self.pool[i]
            sc[i] += cw["kind"] * (c["kind"] == q["kind"]) + cw["rule"] * (c["rule"] == q["rule"]) + cw["verb"] * self.verb_match(q, c) \
                + cw["pn"] * (q["pn"] != "" and c["pn"] == q["pn"]) + cw["neg"] * (c["neg"] == q["neg"])
        return sc.most_common(k) if self.legacy else sorted(sc.items(), key=lambda x: (-x[1], x[0]))[:k]


# ------------------------------------------------------------------ a job's evidence

class Evidence:
    """.source, .pool (clause records), .verses / .heb (the corpus of the job's source language; empty when the language has no
    text from it), .greek_verses (the team's NT), .queries {clause id: query}, .order (the job's clause ids in text order), top(id, k)"""

    def top(self, qid, k=20):
        """the k best pool clauses of a query clause, each with its retrieval score"""
        return [dict(self._rec(i), score=round(s, 4)) for i, s in self.ranking.get(qid, [])[:k]]


def build(cfg, source, book, chapters, leave_out_books=(), legacy=False, query_verses=None):
    """the Evidence of a job: draft `chapters` of `book` from `source` (grc | hbo) for the language of cfg.
    leave_out_books: books kept out of the pool (a dev check leaves the dev book out). query_verses (legacy only): the verse set
    the research harness ranked together, of which the job is a part"""
    shut = holdout.shut(cfg); chapters = set(chapters); E = Evidence(); E.source = source; E.legacy = legacy
    if any(shut(book, ch) for ch in chapters):
        raise SystemExit(f"{book} {sorted(ch for ch in chapters if shut(book, ch))}: closed or held out; not drafted without the user's go")
    T = tokens.greek()
    vg, gg, _ = read_corpus(cfg, "grc", leave_out_books)
    job_verses = set(tokens.chapter_refs(source, book, sorted(chapters)))
    E.greek_verses = vg; E.left_out = tuple(leave_out_books)
    if source == "grc":
        pool, rows = greek_clauses(T, gg, vg, query_verses if legacy and query_verses is not None else job_verses)
        E.verses, E.heb = vg, {}
        R = Ranker(pool, "lem", legacy=legacy)
    else:
        vh, gh, heb = read_corpus(cfg, "hbo", leave_out_books)
        hb = corpus_books(cfg, "hbo"); hb = [b for b in hb if b not in leave_out_books]
        H = tokens.hebrew(sorted(set(hb) | {book}))
        poolg, _ = greek_clauses(T, gg, vg, set()); poolh, rows = [], []
        order = tokens.books("hbo")
        for b in sorted(set(hb) | {book}, key=order.index):
            qv = query_verses if legacy and query_verses is not None else None
            p, r = hebrew_clauses(H, gh, vh, qv or set(), b, shut, query_chapters=(chapters if b == book else set()) if qv is None else None)
            poolh += p; rows += r
        pool = poolg + poolh; E.verses, E.heb = vh, heb
        lex = bridges.lexemes()
        R = Ranker(pool, "skeys", lex, bridges.cells(), legacy=legacy)
    queries = rows if legacy else merge_segments(rows)
    own = lambda c, q: c["book"] == q["book"] and c["ch"] == q["ch"]                     # the chapter being drafted is never its own evidence
    E.pool = pool; E.ranking = {}; E.queries = {}
    for q in queries:                                                                    # legacy: a later row of the same id replaces the earlier
        E.ranking[q["id"]] = R.rank(q, K, exclude=(lambda c, q=q: own(c, q)))
        E.queries[q["id"]] = q
    if legacy:                                                                           # one record per clause id: the last ranked row
        used = sorted({i for top in E.ranking.values() for i, _ in top}); by_id = {pool[i]["id"]: pool[i] for i in used}
        E._rec = lambda i: by_id[pool[i]["id"]]
    else:
        E._rec = lambda i: pool[i]
    if source == "hbo":
        gl = tokens.glosses("hbo", [book])
        E.queries = {qid: word_level(q, gl, lex) for qid, q in E.queries.items()}
    job = [q for q in E.queries.values() if _in_job([t["sref"] for t in q["tokens"]] if not legacy else q["refs"], book, chapters, legacy)]
    job.sort(key=lambda q: min(t["key"] for t in q["tokens"]))
    E.order = [q["id"] for q in job]
    E.meta = {"language": cfg["iso"], "source": source, "book": book, "chapters": sorted(chapters), "pool clauses": len(pool),
              "pool books": sorted({c["book"] for c in pool}), "left out": sorted(leave_out_books), "clauses": len(job),
              "closed list": bool(cfg.get("closed_list")), "held out": sorted(f"{b} {c}" for b, c in holdout.shut(cfg).chapters), "legacy": legacy}
    return E
