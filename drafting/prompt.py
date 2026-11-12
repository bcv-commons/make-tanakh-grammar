#!/usr/bin/env python3
"""The drafter's prompt for one verse: the source verse, its clauses word by word, and for every clause the evidence from the
team's own translation. This is the prompt measured in research as arm L13, with the grammar pages of arm L135g where a language
has them:

  per clause      the 20 most similar clauses of the team's translation, as parts with their links to the source words;
                  per function word, the team's commonest renderings with an example
  per verse       the team's 3 most similar whole verses; the team's decided terms and names
  completeness    how much fuller the team's text is than the source, and that the team's unlinked words belong to the translation
  grammar notes   the language's grammar pages (optional), without the lines that cite closed chapters or the chapters drafted
  content words   (optional, --lexicon) per content word, the team's commonest forms of its lexeme over the whole team text
                  (drafting/lexicon.py, the chapters drafted and the books left out not counted); a Hebrew word's own forms
                  first, then those of its usual Greek equivalents in the team's NT

Every text shown comes from the pool (drafting/evidence.py) or the lexicon counted without the job's chapters, so nothing of a
closed or held-out chapter can reach a prompt."""
import collections, json, os, re

from shared import holdout, paths
from source import tokens

CONTENT = tokens.CONTENT
N_EVIDENCE, N_SIMILAR = 20, 3
SYSTEM = """You translate the Bible into {lang}, a language with a translation team. You draft one verse at a time. The verse is shown \
whole and then clause by clause (the clause division of the source text); each clause lists its source words with an English gloss, \
the word class and, for verbs, the grammatical cell. Translate the verse into natural {lang}, keeping to the clause division: write the \
translation of each clause in its own entry, in order, so that the entries read together give the whole verse (a clause may need words \
from a neighbour moved into it, or very rarely nothing of its own: then give an empty text). Where the prompt shows the team's own \
translation of similar clauses or other evidence, follow the team's words, forms and spelling: they are the standard to match. Write \
only {lang} in the texts, with the team's punctuation. Answer with the JSON object only."""
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["clauses"],
          "properties": {"clauses": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["c", "text"],
                                                                 "properties": {"c": {"type": "integer"}, "text": {"type": "string"}}}}}}
BOOK_NAMES = {"GEN": "Genesis", "EXO": "Exodus", "LEV": "Leviticus", "NUM": "Numbers", "DEU": "Deuteronomy", "JOS": "Joshua", "JDG": "Judges",
              "RUT": "Ruth", "1SA": "1 Samuel", "2SA": "2 Samuel", "1KI": "1 Kings", "2KI": "2 Kings", "1CH": "1 Chronicles", "2CH": "2 Chronicles",
              "EZR": "Ezra", "NEH": "Nehemiah", "EST": "Esther", "JOB": "Job", "PSA": "Psalms", "PRO": "Proverbs", "ECC": "Ecclesiastes",
              "SNG": "Song of Songs", "ISA": "Isaiah", "JER": "Jeremiah", "LAM": "Lamentations", "EZK": "Ezekiel", "DAN": "Daniel", "HOS": "Hosea",
              "JOL": "Joel", "AMO": "Amos", "OBA": "Obadiah", "JON": "Jonah", "MIC": "Micah", "NAM": "Nahum", "HAB": "Habakkuk", "ZEP": "Zephaniah",
              "HAG": "Haggai", "ZEC": "Zechariah", "MAL": "Malachi", "MAT": "Matthew", "MRK": "Mark", "LUK": "Luke", "JHN": "John", "ACT": "Acts",
              "ROM": "Romans", "1CO": "1 Corinthians", "2CO": "2 Corinthians", "GAL": "Galatians", "EPH": "Ephesians", "PHP": "Philippians",
              "COL": "Colossians", "1TH": "1 Thessalonians", "2TH": "2 Thessalonians", "1TI": "1 Timothy", "2TI": "2 Timothy", "TIT": "Titus",
              "PHM": "Philemon", "HEB": "Hebrews", "JAS": "James", "1PE": "1 Peter", "2PE": "2 Peter", "1JN": "1 John", "2JN": "2 John",
              "3JN": "3 John", "JUD": "Jude", "REV": "Revelation"}
ALIAS = {"GENESIS": "GEN", "JOHN": "JHN", "LUKE": "LUK", "MARK": "MRK", "MATT": "MAT", "MATTHEW": "MAT", "ACTS": "ACT", "RUTH": "RUT",
         "JONAH": "JON", "JAMES": "JAS", "PHIL": "PHP", "PHILIPPIANS": "PHP", "JUDGES": "JDG", "JUDE": "JUD", "PHILEMON": "PHM", "EZEKIEL": "EZK",
         "JOEL": "JOL", "NAHUM": "NAM", "SONG": "SNG", "PSALM": "PSA", "PSALMS": "PSA", "PROVERBS": "PRO", "MK": "MRK", "MT": "MAT", "LK": "LUK", "JN": "JHN"}


def ref_key(r):
    b, cv = r.split(); c, v = cv.split(":"); return (b, int(c), int(v))


# ------------------------------------------------------------------ what the pool shows of a clause

def word_str(ws):
    out = []
    for p, s in ws:
        out.append(p if s == "stem" else (p + "-" if s.startswith("p") else "-" + p if s.startswith("s") else p))
    return "[" + " ".join(out) + "]"


def ev_words(c):
    """the numbered target words of a pool clause: [(ref, absolute word index, [[part, slot]], [linked token numbers 1-based])]"""
    link = collections.defaultdict(list)
    for i, t in enumerate(c["tokens"], 1):
        if t["w"] is not None:
            for w in (t.get("ws") or [t["w"]]):
                link[(t["ref"], w)].append(i)
    out = []
    for ref in sorted(c["words"]):
        x = c["words"][ref]
        for j, ws in enumerate(x["words"]):
            w = x["w0"] + j
            out.append((ref, w, ws, link.get((ref, w), [])))
    return out


def ev_part_links(c):
    """per numbered target word of a pool clause (ev_words' order): per part, the linked token numbers (1-based)"""
    out = []
    for ref in sorted(c["words"]):
        x = c["words"][ref]
        for wp in x["pos"]:
            out.append([[i for i, t in enumerate(c["tokens"], 1) if t["ref"] == ref and p in (t.get("pos") or ())] for p in wp])
    return out


def link_marker(ws, lk, pl):
    """'<- g3,g5' for a word whose linked parts all link alike; per part ('<- a-:g2 b:g5', unlinked parts left out) when its parts
    link to different source words; '<- -' for a word linked to no source word"""
    if pl and len({tuple(x) for x, (p, s) in zip(pl, ws) if x}) > 1:
        return "<- " + " ".join((p if s == "stem" else p + "-" if s.startswith("p") else "-" + p if s.startswith("s") else p) + ":"
                                + ",".join(f"g{i}" for i in x) for x, (p, s) in zip(pl, ws) if x)
    return "<- " + (",".join(f"g{i}" for i in lk) if lk else "-")


def tok_line(i, t, G, lemma=True):
    s = f"{i} {t['text']}"
    if lemma and t["cls"] in CONTENT:
        s += f" ({t['lemma']})"
    s += f" '{G.get(t['key'], '')}' {t['cls']}"
    if t["cls"] == "verb" and t["cell"]:
        s += " [" + " ".join(x for x in t["cell"] if x) + "]"
    return s


def tok_line_word(i, t):
    """a word-level Hebrew source token (evidence.word_level)"""
    s = f"{i} {t['text']}"
    if t["cls"] in CONTENT:
        s += f" ({t['lemma']})"
    s += f" '{t.get('gloss', '')}' {t['cls']}"
    if t["cls"] == "verb" and t["cell"]:
        s += " [" + " ".join(x for x in t["cell"] if x) + "]"
    return s


def ev_lines(c, G):
    head = ("Hebrew: " if c["lang"] == "hbo" else "Greek: ") + " | ".join(tok_line(i, t, G) for i, t in enumerate(c["tokens"], 1))
    pls = ev_part_links(c)
    tgt = "Team: " + " ; ".join(f"{w_no} {word_str(ws)} " + link_marker(ws, lk, pls[w_no - 1] if pls else None)
                                 for w_no, (ref, w, ws, lk) in enumerate(ev_words(c), 1))
    return [head, tgt]


def word_of(c, ref, w):
    x = c["words"].get(ref)
    if not x or not (0 <= w - x["w0"] < len(x["words"])):
        return None
    return tuple(p for p, _ in x["words"][w - x["w0"]])


def team_text(v):
    ps, wi, sl = v; ws = collections.defaultdict(str)
    for p, i in zip(ps, wi):
        ws[i] += p
    return " ".join(ws[i] for i in sorted(ws))


# ------------------------------------------------------------------ indexes over the pool

class FuncIndex:
    """per function lemma of a source language, the team's words that render it (with counts) and for each the shortest example
    clause; Hebrew entries keep their chapter so that the chapter being drafted can be left out"""
    def __init__(self, pool):
        self.n = collections.defaultdict(collections.OrderedDict)        # (lang, lemma) -> {chapter: Counter(word)}
        self.ex = collections.defaultdict(collections.OrderedDict)       # (lang, lemma) -> {(chapter, word): example}
        for c in pool:
            ch = c["ch"] if c["lang"] == "hbo" else None
            for t in c["tokens"]:
                if t["w"] is None or t["cls"] in CONTENT:
                    continue
                wd = word_of(c, t["ref"], t["w"])
                if not wd:
                    continue
                k = (c["lang"], t["lemma"])
                self.n[k].setdefault(ch, collections.Counter())[wd] += 1
                e = self.ex[k].get((ch, wd))
                if e is None or len(c["tokens"]) < len(e["tokens"]):
                    self.ex[k][(ch, wd)] = {"tokens": [[y["text"], y["cls"]] for y in c["tokens"]], "ref": c["refs"][0] if c["refs"] else "",
                                             "words": [list(word_of(c, r, w) or ()) for r in sorted(c["words"])
                                                       for w in range(c["words"][r]["w0"], c["words"][r]["w0"] + len(c["words"][r]["words"]))]}

    def of(self, lang, lemma, skip_ch):
        """(renderings [(word, share, n)] best two, total, example of the best) or None"""
        cn = collections.Counter()
        for ch, x in self.n.get((lang, lemma), {}).items():
            if ch is None or ch != skip_ch:
                cn.update(x)
        if not cn:
            return None
        tot = sum(cn.values()); top = cn.most_common(2)
        e = next((v for (ch, wd), v in self.ex[(lang, lemma)].items() if wd == top[0][0] and (ch is None or ch != skip_ch)), None)
        return [(w, round(n / tot, 2), n) for w, n in top], tot, e


def fullness(cfg, source, book, chapters, leave_out_books=()):
    """the team's words per source word over the team's text of one source language, outside the chapters drafted and the books
    left out; None when the language has no text from that source language"""
    from drafting import evidence
    verses, _, heb = evidence.read_corpus(cfg, source, leave_out_books)
    if not verses:
        return None
    sw = collections.defaultdict(set)
    if source == "grc":
        for k, t in tokens.greek().items():
            sw[t["ref"]].add(k)
        ref_of = lambda r: r
    else:
        inv = {v: k for k, v in heb.items()}
        for k, t in tokens.hebrew(sorted({r.split()[0] for r in verses})).items():
            sw[t["ref"]].add(t["word"])
        ref_of = lambda r: inv.get(r, r)
    tw = n = 0
    for r, (ps, wi, sl) in verses.items():
        b, cv = r.split(); s = ref_of(r)
        if (b == book and int(cv.split(":")[0]) in chapters) or s not in sw:
            continue
        tw += max(wi) + 1; n += len(sw[s])
    return tw / max(1, n)


def similar_verses(E, clauses, k=N_SIMILAR):
    """the k pool verses with the highest summed scores over the verse's clauses' retrieved clauses: [(language, the verse as the
    source numbers it, the team's verse)]. Verses of the job's source language; where the language has no text from it (a Hebrew
    job for a language with an NT only), the team's NT verses"""
    lang, verses, heb = (E.source, E.verses, E.heb) if E.verses else ("grc", E.greek_verses, {})
    sc = collections.Counter(); own = {r for q in clauses for r in q["refs"]}
    for q in clauses:
        for c in E.top(q["id"], N_EVIDENCE):
            if c["lang"] == lang and c["refs"] and c["refs"][0] not in own and heb.get(c["refs"][0], c["refs"][0]) in verses:
                sc[c["refs"][0]] += c["score"]
    return [(lang, r, verses[heb.get(r, r)]) for r, _ in sc.most_common(k)]


# ------------------------------------------------------------------ the team's decisions and the grammar notes

def team_terms(cfg):
    """the team's decided terms and names: [(id, value)], from the language's register (shared/register.py) where it has
    one, else from the store"""
    if cfg.get("_register") and os.path.exists(os.path.join(cfg["_register"], "VERSION.json")):
        from shared import register
        return register.team_terms(register.load(cfg["_register"]))
    return team_terms_store(cfg)


def team_terms_store(cfg):
    """the store's team decisions on terms and names: [(id, value)]"""
    out = []
    if not cfg["_store"]:
        return out
    from shared import register                      # make-tanakh's loader: an old JSON store or a converted one alike
    files = register.T.store_files(cfg["_store"])
    for f in ("observations.json", "decisions.json"):
        if f in files:
            for e in files[f].get("entries", []):
                if e.get("method") == "team-decision" and e.get("status") != "superseded" and str(e.get("id", "")).startswith(("term:", "name:")):
                    out.append((e["id"], e.get("value") or ""))
    return out


def team_decisions(cfg):
    """the drafter's lines for the team's other decided entries (formulas, rules, morphs, spelling) from the register:
    {section: [line]}; {} without a register"""
    if cfg.get("_register") and os.path.exists(os.path.join(cfg["_register"], "VERSION.json")):
        from shared import register
        return register.decision_lines(register.load(cfg["_register"]))
    return {}


DECISIONS = {"set phrases": ("The team's set phrases", "Phrases the team has decided how to write: use them where the source has them."),
             "rules": ("The team's rules", "Rules of {name} the team has stated. They are binding: where the examples or the grammar notes "
                       "disagree with them, follow these."),
             "spelling": ("The team's spelling rules", "")}


def grammar_notes(cfg, book, chapters, leave_out_books=()):
    """(lines, dropped): the language's grammar pages for the prompt, headings one level down. A line that cites a chapter no pool
    may hold (closed, held out, an excluded or left-out book) or a chapter being drafted is dropped: the pages quote the team's text"""
    if not cfg.get("notes"):
        return [], 0
    shut = holdout.shut(cfg); excl = {b for x in cfg["corpora"] for b in x.get("exclude_books", ())}
    shut_ch = set(shut.chapters) | {(book, c) for c in chapters}; shut_b = set(shut.books) | excl | set(leave_out_books)
    names = re.compile(r"\b(" + "|".join(re.escape(BOOK_NAMES[b]) for b in sorted(shut_b) if b in BOOK_NAMES) + r")\b") if shut_b else None

    def cites_shut(line):
        for m in re.finditer(r"\b([1-3]?[A-Za-z]{2,9})\.?\s?(\d{1,3})[:.](\d{1,3})", line):
            b = ALIAS.get(m.group(1).upper(), m.group(1).upper()[:3])
            if b in shut_b or (b, int(m.group(2))) in shut_ch:
                return True
        return bool(names and names.search(line))
    name = cfg["name"]
    L = ["## Grammar notes", "", cfg["notes"].get("intro") or f"Notes on {name} grammar collected from the team's translation:"]; dropped = 0
    for pg in cfg["notes"]["pages"]:
        for ln in open(os.path.join(cfg["_notes_dir"], pg + ".md"), encoding="utf-8").read().splitlines():
            if cites_shut(ln):
                dropped += 1
            elif ln.strip() or (L and L[-1].strip()):
                L.append(("#" + ln) if ln.startswith("#") else ln)
    return L, dropped


# ------------------------------------------------------------------ the prompt

class Builder:
    """everything the verses of one job share: the evidence, the function-word index, the glosses, the fullness figure, the team's
    terms and the grammar notes. bridged = the language has no text from the job's source language (a Hebrew job for a language
    with an NT only): function words, similar verses and the fullness figure then come from the team's NT, through the bridges"""
    def __init__(self, cfg, E, book, chapters, notes=True, lexicon=False, pieces=False, decisions=False):
        self.pieces = pieces; self.order = None             # pieces: False | "mark" (say where clauses are cut) | "select" (only find them)
        self.cfg, self.E, self.book, self.chapters = cfg, E, book, set(chapters)
        self.lexi = None
        if lexicon:
            from drafting import lexicon as lx
            self.lexi = lx.Lexicon(cfg, {(book, c) for c in chapters}, E.left_out)
            if not self.lexi.ok:
                raise SystemExit(f"{cfg['iso']}: no lexicon/words.db (onboard/lexicon.py words)")
        self.G = tokens.glosses("grc")
        self.func = FuncIndex(E.pool)
        self.bridged = E.source == "hbo" and not E.verses
        self.ratio = fullness(cfg, "grc" if self.bridged else E.source, book, self.chapters, E.left_out)
        self.terms = team_terms(cfg); self.decisions = team_decisions(cfg) if decisions else {}
        self.notes, self.notes_dropped = grammar_notes(cfg, book, self.chapters, E.left_out) if notes else ([], 0)
        self.vtext = tokens.verse_texts(E.source, {r for qid in E.order for r in E.queries[qid]["refs"]})
        if self.bridged:
            from source import bridges
            self.lex = bridges.lexemes(); self.glemma = {}
            for c in E.pool:
                for t in c["tokens"]:
                    self.glemma.setdefault(t["strong"], t["lemma"])

    def func_of(self, q, t):
        """the team's renderings of a function word of a query clause: (shown lemma, renderings, n, example) or None"""
        if not self.bridged:
            f = self.func.of(self.E.source, t["lemma"], q["ch"] if self.E.source == "hbo" else None)
            return (t["lemma"],) + f if f else None
        for g, _ in self.lex.get(t["strong"], [])[:3]:                 # the Hebrew word's usual Greek equivalents, best first
            lem = self.glemma.get(g)
            f = self.func.of("grc", lem, None) if lem else None
            if f:
                return (f"{t['lemma']} (as Greek {lem})",) + f
        return None

    def content_lines(self, q):
        """the content words' forms in the team's text (--lexicon), or nothing"""
        if not self.lexi:
            return []
        out = []
        for i, t in enumerate(q["tokens"], 1):
            if t["cls"] not in CONTENT:
                continue
            parts = []
            for label, rows, tot, _ in self.lexi.renderings(self.E.source, t):
                fs = "; ".join(f"{f} {s:.0%}" for f, s, _ in rows) + f" (n {tot})"
                parts.append(fs if label is None else f"as Greek {label}: {fs}")
            if parts:
                out.append(f"- word {i} {t['lemma']}: " + " | ".join(parts))
        if out:
            head = "Content words: the team's commonest forms of each word's lexeme anywhere in its translation (share of n)"
            out.insert(0, head + ("; for a Hebrew word its own forms first, then those of its usual Greek equivalents in the "
                                  "team's New Testament:" if self.E.source == "hbo" else ":"))
        return out

    def groups(self):
        """{first verse: [query clauses]} in text order: a clause belongs to the prompt of its first verse"""
        g = collections.OrderedDict()
        for qid in self.E.order:
            q = self.E.queries[qid]
            g.setdefault(sorted(q["refs"], key=ref_key)[0], []).append(q)
        return g

    def cuts(self, clauses):
        """clauses cut in pieces by other clauses of the verse group (the layout's tree): {k: the prompt's line}; self.order = the
        pieces in text order [(clause number, piece number)] when there are any, else None"""
        units = []
        for k, q in enumerate(clauses, 1):
            for j, keys in enumerate(q.get("pieces") or [sorted({t["key"][:11] for t in q["tokens"]})]):
                units.append((keys[0], k, j))
        units.sort(); out = {}
        for k, q in enumerate(clauses, 1):
            ps = q.get("pieces") or []
            if len(ps) < 2:
                continue
            pos = [[i for i, t in enumerate(q["tokens"], 1) if t["key"][:11] in set(p)] for p in ps]
            at = [n for n, u in enumerate(units) if u[1] == k]
            between = [sorted({units[n][1] for n in range(at[j] + 1, at[j + 1])}) for j in range(len(at) - 1)]
            if not any(between):
                continue
            seq = []
            for j, p in enumerate(pos):
                seq.append(f"words {p[0]}-{p[-1]}" if len(p) > 1 else f"word {p[0]}")
                if j < len(between):
                    seq.append(" and ".join(f"C{x}" for x in between[j]) or "(nothing)")
            out[k] = (f"In the Hebrew this clause is cut in {len(ps)} pieces by another clause: {', then '.join(seq)}. Write its text with "
                      f"{len(ps) - 1} '|' where the clause between goes in {self.cfg['name']}: inside the clause if that is natural, or a "
                      "'|' at the start or the end to put it before or after the whole clause.")
        self.order = [(k, j) for _, k, j in units] if out else None
        return out

    def verse(self, clauses):
        """(prompt text, refs) of one verse group"""
        E, src, name = self.E, self.E.source, self.cfg["name"]; srcname = paths.SOURCE_NAME[src]
        refs = sorted({r for q in clauses for r in q["refs"]}, key=ref_key)
        vtext = self.vtext
        L = [f"# {' / '.join(refs)} ({name})", "", f"## Source verse ({srcname})", ""]
        L += [f"{r}: {vtext.get(r, '')}" for r in refs]
        sim = similar_verses(E, clauses)
        if sim:
            st = tokens.verse_texts(sim[0][0], {r for _, r, _ in sim})
            L += ["", "## Similar verses in the team's translation", "", "The team's translation of the most similar verses, whole, to show "
                  "how its sentences run (the words between and around the clauses included):"]
            for lg, r, tv in sim:
                L += [f"- {r}", f"  {paths.SOURCE_NAME[lg]}: " + st.get(r, ""), "  Team: " + team_text(tv)]
        if self.notes:
            L[2:2] = self.notes + [""]
        L += ["", "## Clauses", ""]
        cuts = self.cuts(clauses) if self.pieces else {}
        for k, q in enumerate(clauses, 1):
            L.append(f"### Clause C{k}")
            if k in cuts and self.pieces == "mark":
                L.append(cuts[k])
            for i, t in enumerate(q["tokens"], 1):
                L.append(tok_line_word(i, t) if src == "hbo" else tok_line(i, t, self.G))
            ev = E.top(q["id"], N_EVIDENCE)
            if ev:
                L.append(f"The team's translation of the {len(ev)} most similar clauses (target words numbered; [parts]: prefixes end in "
                         "'-', suffixes begin with '-'; '<- g3' = linked to source word 3 of that clause; 'a-:g2 b:g5' = the word's "
                         "parts link to different source words):")
                for c_no, c in enumerate(ev, 1):
                    L.append(f"E{c_no} ({c['refs'][0] if c['refs'] else ''})")
                    L += ev_lines(c, self.G)
            func = []
            for i, t in enumerate(q["tokens"], 1):
                if t["cls"] not in CONTENT:
                    f = self.func_of(q, t)
                    if f:
                        func.append((i,) + f)
            if func:
                L.append("Function words: the team's commonest rendering of each (share of n), with an example:" if not self.bridged else
                         "Function words: the team's commonest rendering of each word's usual Greek equivalent in its New Testament "
                         "(share of n), with an example:")
                for i, lemma, rend, tot, e in func:
                    L.append(f"- word {i} {lemma}: " + "; ".join(f"{''.join(w) or '(nothing)'} {s:.0%}" for w, s, _ in rend) + f" (n {tot})")
                    if e:
                        L.append(f"  e.g. {e['ref']}: " + " ".join(y for y, _ in e["tokens"]) + " = " + " ".join("".join(w) for w in e["words"]))
            L += self.content_lines(q)
            L.append("")
        if self.terms:
            L += ["## The team's decided terms and names", ""] + [f"- {i}: {v}" for i, v in self.terms] + [""]
        for k, lines in self.decisions.items():
            head, intro = DECISIONS[k]
            L += [f"## {head}", ""] + ([intro.format(name=name), ""] if intro else []) + lines + [""]
        if self.ratio is not None:
            fuller = f"its {name} has about {self.ratio:.1f} words for every source word" if not self.bridged else \
                f"in its New Testament its {name} has about {self.ratio:.1f} words for every Greek word"
            L += ["## Completeness", "", f"The team's translation is fuller than the source text: {fuller}. Natural {name} needs connectives, "
                  "pronouns, auxiliaries and "
                  "particles for which the source has no word of its own. In the examples above these are the team's words marked '<- -' "
                  "(linked to no source word). They are part of the translation: write such words wherever the team would, and do not leave "
                  "a word out because no source word stands for it. Before you answer, read your entries together: they must give the "
                  "complete verse as the team would write it.", ""]
        L += ["## Task", "", f"Write the {name} translation as JSON: " + '{"clauses": [{"c": 1, "text": "..."}, ...]}' +
              f", one entry per clause C1-C{len(clauses)} in order."]
        return "\n".join(L), refs
