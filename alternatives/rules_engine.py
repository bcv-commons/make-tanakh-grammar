#!/usr/bin/env python3
"""The data layer and the rule container of the rule draft (alternatives/rules.py): TBTA's propositions with their pairing to
the source clause spans, the constituents of a proposition matched to source tokens, the team's linked parts, the source-derived
clause fields, and the decision-list tables the rules sit in. Ported from the research drafter (lab/tbta_drafter: common.py,
rulebase.py, source_feats.py at state t2_final); imported, not run.

The TBTA data is private and stays under $MAKE_TANAKH_PRIVATE/tbta (copied from research, MANIFEST.json there):
  props/<bk><ccc>_props.jsonl        TBTA's propositions per chapter (with _macula_clauses.jsonl beside them when paired)
  pairing/resolved.tsv               a proposition's MACULA span and anchor
  clauses/clause_{feats,layers}_{nt,ot}.json   clause fields per clause-layout row (force, negation, voice, person; discourse line)
The concept-to-Strong's table is TBTA's own (its download, in $MAKE_TANAKH_PRIVATE/tbta/download). No chapter that shared/holdout.py shuts is read:
Book refuses it, and the team's text of such a chapter is never loaded."""
import collections, csv, glob, json, os, re, sqlite3, unicodedata

from shared import holdout, paths

NT_BOOKS = ("MAT", "MRK", "LUK", "JHN", "ACT", "EPH", "PHP", "COL", "1TH", "2TH", "TIT", "PHM", "2JN", "REV")
TIME = {"Immediate Past": "past.today", "Earlier Today": "past.today", "Yesterday": "past.yesterday", "Discourse": "discourse",
        "Present": "present", "Immediate Future": "future.near", "Later Today": "future.near", "Tomorrow": "future.days",
        "2 Days from Now": "future.days", "3 Days from Now": "future.days", "A Month from Now": "future.remote",
        "A Year from Now": "future.remote", "Unknown Future": "future.remote"}
REMOTE = {"3 Days Ago", "A Week Ago", "A Month Ago", "A Year Ago", "Historic Past", "Unknown Past", "During Speaker's Lifetime"}
HEB_CLS = {"cj": "conj", "art": "det", "om": "ptcl", "rel": "conj", "ij": "ptcl", "x": "ptcl"}


def tbta(*p):
    return paths.private("tbta", *p)


# ------------------------------------------------------------------ chapters and the guard

class Guard:
    """the language's shut chapters (shared/holdout.py): every read of TBTA's propositions or the team's text asks it"""
    def __init__(self, cfg):
        self.shut = holdout.shut(cfg)

    def __call__(self, book, ch):
        if self.shut(book, ch):
            raise SystemExit(f"{book} {ch} is closed or held out: never read without the user's go")


def chapters(books, shut=None):
    """[(BOOK, ch)] that have TBTA propositions paired to the source, in file order; shut chapters left out"""
    out = []
    for f in sorted(glob.glob(tbta("props", "*_props.jsonl"))):
        b = os.path.basename(f); code = b[:3].upper(); ch = int(b[3:6])
        if code in books and not (shut and shut(code, ch)) and os.path.exists(f.replace("_props.jsonl", "_macula_clauses.jsonl")):
            out.append((code, ch))
    return out


def top(c):
    """a Counter's most common (key, count); a tie goes to the smallest key (by repr), not to the first counted, so a result
    no longer depends on the order sets of strings iterate in (PYTHONHASHSEED)"""
    return min(c.items(), key=lambda kv: (-kv[1], repr(kv[0])))


def marked(parts, wordidx, mark="@@ "):
    """parts with their word numbers -> the parts string (words by spaces, parts inside a word by `mark`)"""
    out, cur, prev = [], [], None
    for p, w in zip(parts, wordidx):
        if prev is not None and w != prev:
            out.append(mark.join(cur)); cur = []
        cur.append(p); prev = w
    if cur:
        out.append(mark.join(cur))
    return " ".join(out)


def words_of(wordidx):
    """[[part positions] per word] in reading order"""
    out, prev = [], object()
    for i, w in enumerate(wordidx):
        if w != prev:
            out.append([]); prev = w
        out[-1].append(i)
    return out


def slot_order(slot):
    side, rest = slot[0], slot[1:]; pos, k = rest.split("."); pos, k = int(pos), int(k)
    return (0, pos, -k) if side == "p" else (2, pos, k)


def strip_marks(w):
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")


def noun_class(word):
    """a noun stem's class, a surface proxy: the first syllable after an optional initial vowel (abantu -> ba)"""
    w = strip_marks(word.lower()); m = re.match(r"^[aeiou]?([^aeiou]*[aeiou])", w)
    return m.group(1) if m else w[:2]


# ------------------------------------------------------------------ the corpus: source tokens, the team's parts, links

def function_parts(db, source, refs, min_n=5):
    """the function parts of the corpus's verses `refs`: seen >= min_n times and linked to function tokens at least as often as to content tokens
    (research kept a list per corpus; on Zinza this rule gives all 363 of its parts and 42 more)"""
    z = sqlite3.connect(db); kcol = "key" if source == "grc" else "word"
    src = sqlite3.connect(paths.work("orig", "grc.sqlite" if source == "grc" else "heb.sqlite"))
    cls = {k[:11]: HEB_CLS.get(c, c) for k, c in src.execute("select key, class from tokens order by key desc")}   # a Hebrew word: its first morpheme's
    lk = collections.defaultdict(lambda: collections.defaultdict(set))
    for k, r, p in z.execute(f"select {kcol}, ref, positions from link"):
        for i in json.loads(p):
            lk[r][i].add(cls.get(k))
    n, fn, cont = collections.Counter(), collections.Counter(), collections.Counter()
    for r, w in z.execute("select ref, words from verse"):
        for i, p in enumerate(json.loads(w or "[]") if r in refs else ()):
            p = p.lower(); n[p] += 1; x = lk[r].get(i)
            if x:
                if x & {"noun", "verb", "adj"}:
                    cont[p] += 1
                else:
                    fn[p] += 1
    return {p for p in n if n[p] >= min_n and fn[p] + cont[p] and fn[p] >= cont[p]}


def hebrew_word(wid, ms):
    """a Hebrew word as one token: the content morpheme's lemma, class and Strong's (prefixed conjunctions, articles and
    prepositions and the suffixes do not make a token of their own, as in research's Hebrew corpus)"""
    body = [m for m in ms if m["pos"] != "suffix"] or ms
    c = next((m for m in reversed(body) if m["class"] not in ("cj", "art") and not (m["class"] == "prep" and m is not body[-1])), body[-1])
    return dict(key=wid, lemma=c["lemma"], strong=re.sub(r"\D", "", c["lexeme"] or "").lstrip("0"), gloss=c["english"] or c["gloss"],
                gstrong=c["greekstrong"], number=c["number"], text="".join(m["text"] for m in ms), **{"class": HEB_CLS.get(c["class"], c["class"])})


class Corpus:
    """the research engine's Corpus on production's data, for one source: tok {ref: [token]} of the given books (Greek: grc.sqlite
    tokens; Hebrew: words from heb.sqlite), and where the team has text, verses {ref: {words, wordidx, slots, book, ch}} and
    link {source key: (part positions,)} from the language's corpus. The team's text of shut chapters, of the corpus's excluded
    books and of `leave_out` books is not loaded; `text=False` loads none (drafting reads no team text)."""
    def __init__(self, cfg, source, books, leave_out=(), text=True):
        self.source = source; self.verses, self.link = {}, {}; self.tok = collections.defaultdict(list); shut = holdout.shut(cfg)
        x = paths.corpus(cfg, source); self.db = x["_db"] if x else None; self.heb2ref = {}
        if self.db and not text:                    # only the verse numbering (the Hebrew's -> the corpus's)
            z = sqlite3.connect(self.db)
            if "heb" in [r[1] for r in z.execute("pragma table_info(verse)")]:
                self.heb2ref = {h: r for h, r in z.execute("select heb, ref from verse") if h}
        if self.db and text:
            excl = set(x.get("exclude_books", ())) | set(leave_out); z = sqlite3.connect(self.db)
            heb = "heb" in [r[1] for r in z.execute("pragma table_info(verse)")]
            for r in z.execute(f"select ref, book, ch, words, wordidx, slots{', heb' if heb else ''} from verse"):
                ref, b, ch, ws, wi, sl = r[:6]
                if wi is None or shut(b, ch) or b in excl or b not in books:
                    continue
                self.verses[ref] = dict(book=b, ch=ch, words=json.loads(ws), wordidx=json.loads(wi), slots=json.loads(sl))
                if heb and r[6]:
                    self.heb2ref[r[6]] = ref
            kcol = "key" if source == "grc" else "word"
            for k, ref, pos in z.execute(f"select {kcol}, ref, positions from link"):
                if ref in self.verses:
                    self.link[k] = (json.loads(pos),)
        q = ",".join("?" * len(books))
        db = sqlite3.connect(paths.work("orig", "grc.sqlite" if source == "grc" else "heb.sqlite")); db.row_factory = sqlite3.Row
        if source == "grc":
            for t in db.execute(f"select key, book, ch, v, lemma, class, strong, gloss, number, ln, text from tokens where book in ({q}) order by key", tuple(books)):
                d = dict(t); d["strong"] = re.sub(r"\D", "", d["strong"] or "").lstrip("0"); self.tok[f"{d['book']} {d['ch']}:{d['v']}"].append(d)
        else:
            ms = collections.OrderedDict()
            for t in db.execute(f"select key, book, ch, v, lemma, lexeme, class, pos, number, gloss, english, greekstrong, text from tokens "
                                f"where book in ({q}) order by key", tuple(books)):
                ms.setdefault(t["key"][:-1], []).append(dict(t))
            for wid, m in ms.items():
                h = f"{m[0]['book']} {m[0]['ch']}:{m[0]['v']}"; ref = self.heb2ref.get(h, h); b, cv = ref.split()
                self.tok[ref].append(dict(hebrew_word(wid, m), book=b, ch=int(cv.split(":")[0]), v=int(cv.split(":")[1]), href=h))


# ------------------------------------------------------------------ TBTA's side

def tgroup(t):
    if t in REMOTE:
        return "past.remote"
    return TIME.get(t, "na" if t in (None, "", "Not Applicable") else "other")


def load_resolved(books):
    """{BOOK.ref#n: dict(relation, anchor, span=(k1, k2) | None)}; source keys without their n/o prefix"""
    csv.field_size_limit(10**9); out = {}
    for r in csv.DictReader(open(tbta("pairing", "resolved.tsv"), encoding="utf-8"), delimiter="\t"):
        b = r["tbta_prop"].split(".")[0]
        if b not in books:
            continue
        span = None
        if r["macula_span"]:
            a, z = r["macula_span"].split(".."); span = (a[1:], z[1:])
        out[r["tbta_prop"]] = dict(relation=r["relation"], anchor=r["macula_anchor"][1:] if r["macula_anchor"] else None, span=span, status=r["status"])
    return out


def load_props(book, ch):
    props = [json.loads(l) for l in open(tbta("props", f"{book.lower()}{ch:03d}_props.jsonl"), encoding="utf-8")]
    return [p for p in props if p["kind"] == "prop"]


def split_concept(s):
    """TBTA's adjective / adverb strings: 'happy/Ajoyful' -> ('happy', 'A'); 'much-many' -> ('much-many', '')"""
    if "/" in s:
        a, b = s.split("/", 1)
        return a, (b[:1] if b[:1].isupper() else "")
    return s, ""


SKIP_PART = re.compile(r"^-(Quote|Comment)")


def constituents(p, pid=None):
    """the proposition's constituents in TBTA order, each {cid, cat, concept, sense, f: features}; cat V, N (an NP head; nested
    heads carry rel), A (adjective in an NP: head cid in 'of'), PA (predicate adjective), ADV, CONJ, SUB, PART"""
    out = []
    clause = {k: p.get(k) for k in ("type", "illoc", "topic", "speaker", "listener", "genre", "sequence", "location", "implicit_info",
                                    "attitude", "salience", "rhet_q", "notional")}
    v0 = (p["verbs"] or [{}])[0]
    clause.update({"time": v0.get("time"), "tgroup": tgroup(v0.get("time")), "aspect": v0.get("aspect"), "mood": v0.get("mood"),
                   "polarity": v0.get("polarity")})

    def add(cat, concept, sense, f, **kw):
        c = dict(cid=f"{pid or p['id']}/{len(out)}", cat=cat, concept=concept, sense=sense or "", f=dict(f), **kw)
        out.append(c); return c

    for x in p["conj"]:
        add("CONJ", x, "", clause)
    for x in p["subordinator"]:
        add("SUB", x, "", clause)
    for x in p["particles"]:
        if not SKIP_PART.match(x):
            add("PART", x, "", clause)

    def np_heads(np, role, depth, parent):
        for h in np["heads"]:
            c = (h.get("complex") or h.get("simple") or h.get("concept") or "")
            if not c:
                continue
            f = dict(clause); f.update({k: h.get(k) for k in ("number", "person", "tracking", "proximity", "surface", "status", "polarity")})
            f.update(role=role, rel=np.get("rel") or ("" if depth == 0 else "nested"), relativized=np.get("relativized"),
                     np_implicit=np.get("implicit"), depth=depth)
            hc = add("N", c, h.get("sense"), f, of=parent, nphead=True, index=h.get("index"))
            for a in np.get("adj", []):
                ac, s = split_concept(a); add("A", ac, s, dict(f), of=hc["cid"])
            for nn in np.get("nested", []):
                np_heads(nn, role, depth + 1, hc["cid"])

    verbs = []; nps = list(p["nps"])
    first = [np for np in nps if np["role"] == "Most Agent-like"][:1]
    for np in first:
        np_heads(np, np["role"], 0, None)
    for v in p["verbs"]:
        c = v.get("complex") or v.get("simple") or v.get("concept")
        f = dict(clause); f.update({k: v.get(k) for k in ("time", "aspect", "mood", "polarity", "reflexivity", "degree", "target_tense",
                                                         "target_aspect", "target_mood", "vp_implicit")})
        f["tgroup"] = tgroup(v.get("time")); verbs.append(add("V", c, v.get("sense"), f))
    for np in nps:
        if np not in first:
            np_heads(np, np["role"], 0, None)
    for x in p["pred_adj"]:
        ac, s = split_concept(x); add("PA", ac, s, clause)
    for x in p["advs"]:
        ac, s = split_concept(x); add("ADV", ac, s, clause)
    ag = next((c for c in out if c["cat"] == "N" and c["f"]["role"] == "Most Agent-like" and c["f"]["depth"] == 0), None)
    pa = next((c for c in out if c["cat"] == "N" and c["f"]["role"] == "Most Patient-like" and c["f"]["depth"] == 0), None)
    for v in verbs:                                 # the participants onto the verbs (the source side of feature copying, R4)
        for pre, h in (("subj", ag), ("obj", pa)):
            if h:
                v["f"].update({f"{pre}_person": h["f"].get("person"), f"{pre}_number": h["f"].get("number"), f"{pre}_concept": h["concept"],
                               f"{pre}_cid": h["cid"]})
            else:
                v["f"][f"{pre}_person"] = "none"
    return out


def lexkey(c):
    return f"{c['cat']}:{c['concept']}" + (f"-{c['sense']}" if c["sense"] else "")


def lexkey0(c):
    return f"{c['cat']}:{c['concept']}"


# ------------------------------------------------------------------ matching constituents to source tokens

COMPAT = {"V": {"verb"}, "N": {"noun", "pron", "adj", "num"}, "A": {"adj", "num", "verb", "adv"}, "PA": {"adj", "verb", "adv", "noun"},
          "ADV": {"adv", "adj", "ptcl", "prep"}, "CONJ": {"conj", "adv", "ptcl"}, "SUB": {"conj", "adv", "prep", "ptcl"},
          "PART": {"ptcl", "intj", "adv", "conj"}}
FUNCCAT = {"CONJ", "SUB", "PART", "ADV", "A", "PA"}
STOP = set("the a an he she it they his her their to of in and et had has have who whom which that dm my your our me you us him them i we "
           "o will may let be is was were are being shall not there here then so as for with by from on at into before after all this these "
           "those also but if".split())


def norm_strong(s):
    return re.sub(r"[^0-9]", "", (s or "").upper().lstrip("GH")).lstrip("0")


def gloss_words(g):
    g = re.sub(r"[\[\]()]", " ", g or "")
    return [w for w in (x.strip().lower() for x in re.split(r"[.\s/,-]+", g)) if w and w not in STOP]


def en_stem(w):
    w = w.lower()
    for suf, rep in (("ies", "y"), ("ied", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)] + rep
    return w


def same_word(a, b):
    a, b = en_stem(a), en_stem(b)
    return a == b or (len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)))


_SMAP = {}


def load_smap():
    """TBTA's concept -> {G<n>, H<n>} (concept_strongs_mappings.tsv in TBTA's download, private/tbta/download)"""
    if not _SMAP:
        m = collections.defaultdict(set)
        f = paths.private("tbta", "download", "ai-framework", "scripts", "add_strongs_to_concepts", "data", "concept_strongs_mappings.tsv")
        for r in csv.DictReader(open(f, encoding="utf-8"), delimiter="\t"):
            for s in r["strongs_list"].split(","):
                s = s.strip()
                if s:
                    m[r["stem"].lower()].add(s[0] + norm_strong(s))
        _SMAP["m"] = m
    return _SMAP["m"]


class Matcher:
    """constituents to source tokens in the proposition's span: Strong's of TBTA's concept mapping (3), the token's gloss (2), the
    learned concept-lemma association (Dice x 4, learned on training spans, n >= 3), greedy one to one; a verb left without a
    match takes the span's only free verb. score >= 1 to match."""
    def __init__(self, lang_prefix="G"):
        self.smap = load_smap(); self.pre = lang_prefix; self.assoc = {}

    def learn_assoc(self, items):
        """items: [(constituents, span tokens)] of training propositions"""
        nc, nl, ncl = collections.Counter(), collections.Counter(), collections.Counter()
        for cons, toks in items:
            nc.update({lexkey0(c) for c in cons}); nl.update({t["lemma"] for t in toks})
            for c in cons:
                for t in toks:
                    if t["class"] in COMPAT.get(c["cat"], ()):
                        ncl[(lexkey0(c), t["lemma"])] += 1
        self.assoc = {k: 2 * n / (nc[k[0]] + nl[k[1]]) for k, n in ncl.items() if n >= 3}

    def score(self, c, t):
        if t["class"] not in COMPAT.get(c["cat"], ()):
            return 0
        s = 0; con = c["concept"].lower()
        if self.pre + norm_strong(t.get("strong")) in self.smap.get(con, ()):
            s += 3
        if c["cat"] in FUNCCAT:                     # function concepts: the gloss's own words, stop words included
            if set(re.findall(r"[a-z]+", (t.get("gloss") or "").lower())) & set(con.split("-")):
                s += 2
        else:
            g = gloss_words(t.get("gloss"))
            if any(same_word(con, w) for w in g) or (con.split("-")[0] and any(same_word(con.split("-")[0], w) for w in g)):
                s += 2
        return s + 4 * self.assoc.get((lexkey0(c), t["lemma"]), 0)

    def match(self, cons, toks):
        """{cid: token}"""
        cand = sorted(((s, c["cid"], t["key"], t) for c in cons for t in toks for s in (self.score(c, t),) if s >= 1), key=lambda x: (-x[0], x[2]))
        out, used = {}, set()
        for s, cid, k, t in cand:
            if cid not in out and k not in used:
                out[cid] = t; used.add(k)
        for c in cons:
            if c["cat"] == "V" and c["cid"] not in out:
                free = [t for t in toks if t["class"] == "verb" and t["key"] not in used]
                if len(free) == 1:
                    out[c["cid"]] = free[0]; used.add(free[0]["key"])
        return out


# ------------------------------------------------------------------ the book view

class Book:
    """per verse ref the propositions (in order) of a set of chapters, with constituents, pairing, span tokens and matched
    tokens; C is a Corpus. Every chapter passes the guard."""
    def __init__(self, C, chs, matcher, resolved, guard):
        self.C = C; self.verses = collections.OrderedDict(); self.props = {}
        for book, ch in chs:
            guard(book, ch)
            for p in load_props(book, ch):
                ref = f"{book} {p['ref']}"; pid = f"{book}.{p['id']}"
                r = resolved.get(pid) or dict(relation="none", anchor=None, span=None); toks = []
                if r["span"]:
                    a, z = r["span"]; vt0 = C.tok.get(ref) or []
                    if vt0 and len(vt0[0]["key"]) < len(a):     # Hebrew: the unit is the word (the morpheme key without its last digit)
                        a, z = a[:len(vt0[0]["key"])], z[:len(vt0[0]["key"])]
                    seen = set()
                    for vr in [ref] + [f"{book} {int(k[2:5])}:{int(k[5:8])}" for k in (a, z) if len(k) == 11]:
                        if vr not in seen:
                            seen.add(vr); toks += [t for t in C.tok.get(vr, []) if a <= t["key"] <= z]
                    vt = C.tok.get(ref, []); i0 = next((i for i, t in enumerate(vt) if t["key"] >= a), len(vt)); lead = []
                    for t in reversed(vt[max(0, i0 - 3):i0]):   # the conjunctions and particles just before the span open the clause
                        if t["class"] not in ("conj", "ptcl"):
                            break
                        lead.insert(0, t)
                    toks = lead + toks
                self.props[pid] = dict(id=pid, ref=ref, p=p, cons=constituents(p, pid), rel=r["relation"], anchor=r["anchor"], toks=toks, m={})
                self.verses.setdefault(ref, []).append(pid)
        if matcher is not None:
            self.rematch(matcher)

    def rematch(self, matcher):
        for P in self.props.values():
            P["m"] = matcher.match(P["cons"], P["toks"]) if P["toks"] else {}

    def target(self, ref, t):
        """the team's parts linked to source token t: [(position, part)]"""
        l = self.C.link.get(t["key"])
        if not l:
            return []
        ref = f"{t['book']} {t['ch']}:{t['v']}"
        w = self.C.verses[ref]["words"] if ref in self.C.verses else []
        return [(i, w[i]) for i in l[0] if i < len(w)]

    def refs(self, text=True):
        return [r for r in self.verses if r in self.C.verses or not text]

    def word_parts(self, ref, positions):
        """the words holding the given part positions: [[(pos, part, slot)]] in reading order"""
        v = self.C.verses.get(ref)
        if not v or not positions:
            return []
        wi, ps, sl = v["wordidx"], v["words"], v["slots"]; want = sorted({wi[p] for p in positions if p < len(wi)})
        return [[(i, ps[i], sl[i]) for i in range(len(ps)) if wi[i] == w] for w in want]

    def linked(self, ref, t):
        """the words holding the parts linked to token t, each [(pos, part, slot, linked)]; [] without a link"""
        ps = {p for p, _ in self.target(ref, t)}
        if not ps:
            return []
        return [[(i, p, s, i in ps) for i, p, s in w] for w in self.word_parts(f"{t['book']} {t['ch']}:{t['v']}", ps)]


# ------------------------------------------------------------------ source-derived clause fields

H_FORCE = {"cohortative": "hortatory", "jussive": "imperative"}
H_NEG = {"lo": "ou", "en": "ou", "bal": "ou", "la": "ou", "al": "me", "bilti": "me"}
FIELDS = ("sforce", "sneg", "svoice", "sperson", "sspeech", "sline", "sund", "sfocus", "snscope", "ssubj", "srole", "strans", "sakt")


class SourceFields:
    """a unit's clause fields from the source (research source_feats.py): the clause-layout row holding the verb's matched token,
    else the row holding most span tokens; its force, negator, voice, person (Hebrew values mapped onto the Greek vocabulary the
    grammar keys on) and discourse columns"""
    def __init__(self, source):
        import pyarrow.parquet as pq
        self.w2r = {}; self.cache = {}
        if source == "grc":
            self.feats = json.load(open(tbta("clauses", "clause_feats_nt.json"), encoding="utf-8"))
            for r in pq.read_table(paths.aligner_data("greek-nt-clause-layout", "clauses.parquet"), columns=["first", "words"]).to_pylist():
                for w in r["words"]:
                    self.w2r.setdefault(w, r["first"])
            self.layers = json.load(open(tbta("clauses", "clause_layers_nt.json"), encoding="utf-8"))
        else:
            self.feats = {}
            for k, f in json.load(open(tbta("clauses", "clause_feats_ot.json"), encoding="utf-8")).items():
                g = dict(f); g["force"] = H_FORCE.get(f.get("force"), f.get("force")); g["neg"] = H_NEG.get(f.get("neg"), f.get("neg")); self.feats[k] = g
            for fp in sorted(glob.glob(paths.aligner_data("hebrew-clause-layout", "clauses-*.parquet"))):
                for r in pq.read_table(fp, columns=["clause_key", "words"]).to_pylist():
                    for w in r["words"]:
                        self.w2r.setdefault(w[:11], r["clause_key"])
            self.layers = json.load(open(tbta("clauses", "clause_layers_ot.json"), encoding="utf-8"))

    def row(self, P):
        if not P["toks"]:
            return None
        v = next((c for c in P["cons"] if c["cat"] == "V"), None); t = P["m"].get(v["cid"]) if v else None
        if t is not None and self.w2r.get(t["key"]) in self.feats:
            return self.w2r[t["key"]]
        cnt = collections.Counter(self.w2r[t["key"]] for t in P["toks"] if self.w2r.get(t["key"]) in self.feats)
        if not cnt:
            return None
        top = max(cnt.values())
        return next(r for r in (self.w2r.get(t["key"]) for t in P["toks"]) if cnt.get(r) == top)

    def unit(self, P):
        row = self.row(P)
        if row is None:
            return {f: "na" for f in FIELDS}
        f = self.feats[row]; ly = self.layers.get(row)
        pn = f"{f['person']}{f['number']}" if f.get("person") and f.get("number") else "none"
        lf = ({"sspeech": "speech" if ly["speech"] else "narration", "sline": ly["line"], "sund": ly["undergoer"],
               "sfocus": ly.get("focus", "na"), "snscope": ly.get("neg_scope", "na"),
               "ssubj": f"{ly['part_switch']}_{ly['subj_form']}" if ly.get("part_switch") in ("same", "switch") else "none",
               "srole": ly.get("subj_role", "na"), "strans": str(ly.get("m_trans", "na")), "sakt": ly.get("akt") or "na"} if ly else
              {k: "na" for k in FIELDS[4:]})
        return dict({"sforce": f.get("force") or "na", "sneg": f.get("neg") or "none", "svoice": f.get("voice") or "none", "sperson": pn}, **lf)

    def __call__(self, P):
        v = next((c for c in P["cons"] if c["cat"] == "V"), None); t = P["m"].get(v["cid"]) if v else None
        k = (P["id"], t["key"] if t else None, len(P["toks"]))
        if k not in self.cache:
            self.cache[k] = self.unit(P)
        return self.cache[k]


def src_triggers(P, ctx, S, va):
    """R3's source triggers [(trigger, anchor cid)] for the fields named in S['src_trig']; with S['src_fill'] a unit whose verb
    lacks TBTA's polarity / illocution (or that has no verb) takes the source's as TBTA's own triggers `neg` / `illoc=...`"""
    want = S.get("src_trig") or []
    if not (want or S.get("src_fill")) or not P["cons"]:
        return []
    anc = va or P["cons"][0]["cid"]; x = ctx.get(anc, {}); out = []
    fo, ng, vo, pn = x.get("sforce", "na"), x.get("sneg", "na"), x.get("svoice", "na"), x.get("sperson", "na")
    tests = {"sforce": fo not in ("declarative", "na") and f"sforce={fo}", "sneg": ng in ("ou", "me") and "sneg",
             "svoice": vo in ("passive", "middle", "middlepassive") and f"svoice={vo}", "sperson": pn not in ("none", "na") and f"sperson={pn}",
             "sspeech": x.get("sspeech") == "speech" and "sspeech=speech", "sline": x.get("sline") in ("main", "background", "setting") and f"sline={x.get('sline')}",
             "sund": x.get("sund") in ("overt", "implicit") and f"sund={x.get('sund')}",
             "sfocus": x.get("sfocus") in ("narrow", "topic", "sentence") and f"sfocus={x.get('sfocus')}",
             "snscope": x.get("snscope") == "constituent" and "snscope=constituent",
             "ssubj": x.get("ssubj") not in (None, "none", "na") and f"ssubj={x.get('ssubj')}", "srole": x.get("srole") == "undergoer" and "srole=undergoer",
             "strans": x.get("strans") in ("0", "2") and f"strans={x.get('strans')}", "sakt": x.get("sakt") not in (None, "na", "") and f"sakt={x.get('sakt')}"}
    out = [(tests[f], anc) for f in FIELDS if f in want and tests[f]]
    if S.get("src_fill"):
        if x.get("polarity") in (None, "na", "Not Applicable") and ng in ("ou", "me"):
            out.append(("neg", anc))
        il = {"imperative": "Imperative", "prohibitive": "Imperative", "hortatory": "Suggestive 'let's'"}.get(fo) if va is None else None
        if il:
            out.append((f"illoc={il}", anc))
    return out


# ------------------------------------------------------------------ the rule container

def when_match(rule, ctx):
    for k, v in rule.get("when", {}).items():
        x = ctx.get(k)
        if (x not in v) if isinstance(v, list) else (x != v):
            return False
    for k, v in (rule.get("unless") or {}).items():
        x = ctx.get(k)
        if (x in v) if isinstance(v, list) else (x == v):
            return False
    return True


class Table:
    """a decision list: `levels` (field lists, most specific first) and `rules` ({kind, sub, when, unless?, do, n, share, source}).
    Learned rules sit at the level their `when` names; rules from elsewhere (an LLM linguist's overrides, a human) carry any
    `when` / `unless` and are tried first: the team's rules (source team:<id>) before all others, then the most specific."""
    def __init__(self, name, levels, rules=()):
        self.name, self.levels = name, [list(l) for l in levels]
        self.idx = [dict() for _ in self.levels]; self.over = []; self.rules = []
        for r in rules:
            self.add(r)

    def add(self, r):
        self.rules.append(r)
        if r.get("source", "counts") == "counts" and not r.get("unless"):
            ks = sorted(r["when"])
            for i, l in enumerate(self.levels):
                if sorted(l) == ks:
                    self.idx[i][tuple(r["when"][f] for f in l)] = r
                    return
        self.over.append(r); self.over.sort(key=lambda x: (not str(x.get("source", "")).startswith("team:"), -len(x.get("when", {}))))   # the team's first

    def lookup(self, ctx, skip=frozenset()):
        """the rule that applies: overrides first, then the decision list; levels naming a field in `skip` are passed over"""
        for r in self.over:
            if (not skip or not (set(r.get("when", {})) | set(r.get("unless") or {})) & skip) and when_match(r, ctx):
                return r
        for i, l in enumerate(self.levels):
            if skip and skip.intersection(l):
                continue
            r = self.idx[i].get(tuple(ctx.get(f) for f in l))
            if r:
                return r
        return None

    def dump(self):
        return {"levels": self.levels, "rules": self.rules}


def learn_dl(name, kind, sub, rows, levels, min_n, min_share, extra=None):
    """rows: [(ctx, value)]; per level the top value of each key, kept if seen >= min_n with share >= min_share"""
    T = Table(name, levels)
    for l in levels:
        cnt = collections.defaultdict(collections.Counter)
        for ctx, v in rows:
            key = tuple(ctx.get(f) for f in l)
            if not any(x is None for x in key):
                cnt[key][v] += 1
        for key, c in cnt.items():
            v, n = top(c); tot = sum(c.values())
            if n >= min_n and n / tot >= min_share:
                r = dict(kind=kind, sub=sub, when=dict(zip(l, key)), do={"value": v}, n=n, share=round(n / tot, 3), source="counts")
                r.update(extra or {}); T.add(r)
    return T


def entropy(c):
    import math
    t = sum(c.values())
    return -sum(n / t * math.log2(n / t) for n in c.values() if n)


def backoff_levels(rows, fields, keep=1):
    """the full key, then the least informative field dropped one at a time (conditional entropy), down to `keep` fields"""
    order = []
    for f in fields:
        by = collections.defaultdict(collections.Counter)
        for ctx, v in rows:
            by[ctx.get(f)][v] += 1
        N = sum(sum(c.values()) for c in by.values()) or 1
        order.append((sum(sum(c.values()) / N * entropy(c) for c in by.values()), f))
    levels = [list(fields)]; cur = list(fields)
    for _, f in sorted(order, reverse=True):
        if len(cur) <= keep:
            break
        cur = [x for x in cur if x != f]; levels.append(list(cur))
    return levels


def greek_np(P, c):
    """whether the source has an explicit NP for this head: noun / pron / none (paired proposition), unpaired (no span)"""
    if not P["toks"]:
        return "unpaired"
    t = P["m"].get(c["cid"])
    return "none" if t is None else ("pron" if t["class"] == "pron" else "noun")


def contexts(P, lexclass, prev_tam=None, src=None):
    """{cid: ctx}: a constituent's own features, its proposition's, the source clause fields (src: P -> fields) and the copied
    participant features (subject / object person.number, the target class of their lexicon entries)"""
    out = {}; by = {c["cid"]: c for c in P["cons"]}; sf = src(P) if src is not None else None
    cls = lambda h: lexclass.get(lexkey(h)) or lexclass.get(lexkey0(h)) or "na"
    for c in P["cons"]:
        x = {k: (v if v is not None else "na") for k, v in c["f"].items()}
        if sf:
            x.update(sf)
        x.update(cat=c["cat"], lex=lexkey(c), lex0=lexkey0(c), concept=c["concept"], prev_tgroup=prev_tam or "none")
        if c["cat"] == "N":
            x["greek"] = greek_np(P, c); x["class"] = cls(c); x["pn"] = f"{x.get('person')}.{x.get('number')}"
        if c["cat"] == "V":
            for pre in ("subj", "obj"):
                x[f"{pre}_pn"] = f"{c['f'].get(pre + '_person')}.{c['f'].get(pre + '_number', 'na')}"
                h = by.get(c["f"].get(pre + "_cid"))
                x[f"{pre}_class"] = cls(h) if h else "none"; x[f"{pre}_greek"] = greek_np(P, h) if h else "none"
                x[f"{pre}_pnc"] = f"{x[pre + '_pn']}|{x[pre + '_class']}"
        if c["cat"] == "A" and c.get("of") in by:
            x["head_class"] = cls(by[c["of"]]); x["head_number"] = by[c["of"]]["f"].get("number") or "na"
        if c["cat"] == "N" and c.get("of") in by:
            x["head_class"] = cls(by[c["of"]])
        if c["cat"] == "N":
            kid = next((k for k in P["cons"] if k["cat"] == "N" and k.get("of") == c["cid"]), None)
            x["poss_pn"] = f"{kid['f'].get('person')}.{kid['f'].get('number')}" if kid else "none"
            x["poss_rel"] = (kid["f"].get("rel") or "na") if kid else "none"
        out[c["cid"]] = x
    return out
