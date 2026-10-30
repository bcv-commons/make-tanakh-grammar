#!/usr/bin/env python3
"""A language's TARGET module for an LLM aligner (Jev), generated from its language store (user 2026-10-26: conventions in
modules: source rules once per source language, a target module per language, generated, every rule with its origin).

    /usr/bin/python3 lab/split/conventions.py <project> <DIR>   -> DIR/conventions.md, jev.md, rules.json, terms.tsv

conventions.md   the whole module, one line per rule with its figures: the affixes (how each part is linked), the words never split,
                 the team's decisions, the grammar features and claims, the letters; each line names its store id, status and method
jev.md           the short form for an aligner (user 2026-10-27: we choose what Jev gets): the rules that bear on linking, within
                 JEV_BUDGET bytes, same ids
rules.json       every rule with its id, section, text, status, method and figures (for tools)
terms.tsv        names and terms (and names derived from the NT alignment where the store has none): source (Hebrew / Greek lemma or the source note), target form, kind, status, store id

Nothing here is written by hand: a change to the store changes the module. Every entry keeps its standing: `team-decision`
comes from speakers; `corpus-*` was learned from the text and its alignment (a hypothesis with figures); `project-decision` is
the project's choice where the corpus is silent."""
import collections, datetime, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.environ["MAKE_TANAKH_WORK"]

# a morph's Greek feature -> how its part is linked (the source side's rules are the source module's)
LINK = [
    ("negated", "to the source's negative particle (οὐ, μή, …; לֹא, אַל, …) when the clause has one, else with the verb"),
    ("object", "to the source's object pronoun of that person and number (αὐτόν, σε, ἡμᾶς; a suffix on the Hebrew verb or אֵת + "
               "suffix) when the clause has one; else with the verb (the object is only in the verb, or named)"),
    ("person+number", "with the source verb (its ending carries the person); to a separate subject pronoun (ἐγώ, σύ, αὐτός) only "
                      "when the target has no free pronoun word in the clause for it"),
    ("possessor", "to the source's possessive pronoun (μου, σου, αὐτοῦ; a Hebrew suffix pronoun)"),
    ("tense", "with the source verb, never with another word"), ("mood", "with the source verb, never with another word"),
    ("voice", "with the source verb, never with another word"), ("aspect", "with the source verb, never with another word"),
    ("number", "with the noun it is on"), ("case", "with the noun it is on, or the preposition that governs it"),
]


def load(pname):
    ents = []
    for f in ("observations.json", "decisions.json"):
        p = os.path.join(R, "export", pname, "profile", f)
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            ents += [dict(e, _file=f) for e in d.get("entries", []) if e.get("status") != "superseded"]
    return ents


def standing(e):
    return f"`{e['id']}` {e.get('status')}, {e.get('method')}"


# the same, as a label for the Jev file (its legend is printed once there)
LINK_SHORT = {"negated": "NEG", "object": "OBJ", "person+number": "VERB-SUBJ", "possessor": "POSS", "tense": "VERB",
              "mood": "VERB", "voice": "VERB", "aspect": "VERB", "number": "HOST", "case": "HOST"}
LEGEND = {"NEG": "the source's negative (οὐ, μή; לֹא, אַל), else the verb",
          "OBJ": "the source's object pronoun of that person and number, else the verb",
          "VERB-SUBJ": "the source verb; a separate subject pronoun only if the target has no free pronoun for it in the clause",
          "POSS": "the source's possessive pronoun (μου, αὐτοῦ; a Hebrew suffix)", "VERB": "the source verb only",
          "HOST": "the word it is on (or the preposition governing it)", "FEAT": "the source word with the feature named"}


def link_short(e):
    g = e.get("greek") or {}
    parts = {x for k in g for x in k.split("+")} | set(g)
    for k, _ in LINK:
        if k in parts:
            return LINK_SHORT[k]
    return "FEAT"


def link_of(e):
    g = e.get("greek") or {}
    parts = {x for k in g for x in k.split("+")} | set(g)
    for k, how in LINK:
        if k in parts:
            return how
    return "with the source word that carries " + (", ".join(f"{k}={v}" for k, v in g.items()) if g else "its meaning (no claim yet)")


def figs(e):
    s = e.get("stats") or {}
    out = [f"{k} {s[k]}" for k in ("count", "hosts", "odds", "test_odds") if k in s]
    return ", ".join(out)


def derived_names(pname, have):
    """names from the language DB (lang.py build: d_names, the NT's Greek names and their linked target words), where the store
    has none; the DB's text is lower case, so the form is given capitalised"""
    db = os.path.join(R, "export", pname, "_learn", "lang.sqlite")
    if not os.path.exists(db):
        return []
    import sqlite3
    c = sqlite3.connect(db)
    raw = collections.defaultdict(collections.Counter); tok = collections.Counter()
    for form, rw in c.execute("select form, raw from nt_tokens"):
        raw[form][rw] += 1; tok[form] += 1
    by = collections.defaultdict(list); linked = collections.Counter()
    for lem, form, n in c.execute("select lemma, form, n from d_names"):
        by[lem].append((form, n)); linked[form] += n
    out = []
    for lem, fs in sorted(by.items()):
        if lem in have:
            continue
        tot = sum(n for _, n in fs)
        for form, n in sorted(fs, key=lambda x: -x[1]):
            # a name: >= 3 links, >= 0.2 of the name's links, and a fifth of the form's tokens are linked to a name (not "aati")
            if n < 3 or n < 0.2 * tot or not tok[form] or linked[form] < 0.2 * tok[form]:
                continue
            w = raw[form].most_common(1)[0][0]
            out.append((lem, w[:1].upper() + w[1:], n, tot))
    return out


EXAMPLES = os.environ.get("JEV_EXAMPLES") == "1"   # trial (2026-10-27): one attested example per jev.md line, from the
EXAMPLE_WORDS = 6                                  # entry's own evidence (already counted as quoted), with its reference


def example(e):
    """the entry's first evidence form of at most EXAMPLE_WORDS words that differs from its value, with its reference"""
    for r in (e or {}).get("evidence") or []:
        f = (r.get("form") or "").strip()
        if f and r.get("ref") and len(f.split()) <= EXAMPLE_WORDS and f != str((e or {}).get("form") or "") \
                and f != str((e or {}).get("value") or ""):
            return f"{f} ({r['ref']})"
    return None


TOK = re.compile(r"(?:[^\W\d_][̀-ͯ᪰-᫿᷀-᷿⃐-⃿︠-︯]*)+")


MARKS = "̀-ͯ᪰-᫿᷀-᷿"
GENERAL = re.compile(rf"(?:^|[\s(/'\"‘“])[^\W\d_][\w{MARKS}꞉]*-(?![\w{MARKS}])|(?<![\w{MARKS}])-[^\W\d_][\w{MARKS}꞉]*"
                     r"|<[^>]+>|\btones?\b|\bprefix|\bsuffix|\bending|\bstem\b|\bparadigm", re.I)


# rules whose text quotes words only as examples of something general (style, any name): checked by hand, kept general
GENERAL_IDS = {"sentence_length", "sentence_length.2", "explanation_in_text", "vocative", "vocative.2"}


def target_vocab(pname):
    """(the target's written words, lowercased, marks kept: the NT's tokens in the language DB; the English words of the BSB);
    (None, None) without a language DB"""
    import sqlite3, unicodedata
    db = os.path.join(R, "export", pname, "_learn", "lang.sqlite")
    if not os.path.exists(db):
        return None, None
    tgt = {unicodedata.normalize("NFC", r) for (r,) in sqlite3.connect(db).execute("select distinct raw from nt_tokens where raw is not null")}
    eng = set()
    for f in os.listdir(os.path.join(R, "reference", "BSB")):
        eng.update(w.lower() for w in TOK.findall(open(os.path.join(R, "reference", "BSB", f), encoding="utf-8").read()))
    return tgt, eng


def rule_words(e, tgt, eng):
    """the target words a rule concerns (user 2026-10-27, note 22 to lexeme-aligner: an aligner keeps the rule only where one
    of them is in the request): the words its own text names that are words of the target's NT and not English words (its
    evidence is not used: a general rule's examples are not its words); as the tokenizer cuts them (a hyphen divides),
    lowercased, marks kept. An affix (a morph entry) is never filtered by words. [] = a
    general rule (word order, how a construction is built): no filter. A rule about an affix, a tone or a pattern (its text
    writes an affix with a hyphen, a slot <X>, or speaks of tone, a prefix or suffix) holds on words it does not name, so it
    stays general: its examples are not its words."""
    import unicodedata
    v = unicodedata.normalize("NFC", str(e.get("value") or ""))
    if not tgt or not e or e.get("kind") == "morph" or e.get("id") in GENERAL_IDS or GENERAL.search(v):
        return []
    out = []
    for w in TOK.findall(v.lower()):
        if w in tgt and w not in out and len(w) > 1 and w not in eng:
            out.append(w)
    return out


def rule(rules, rid, section, text, e=None, figures=None, method=None, status=None, words=None):
    rules.append({"id": rid, "section": section, "kind": (e or {}).get("kind"), "text": text,
                  "status": status or (e or {}).get("status"), "method": method or (e or {}).get("method"), "figures": figures,
                  "example": example(e)})
    if (e or {}).get("form") and section in ("affix", "word"):
        rules[-1]["form"] = e["form"]
    if words:
        rules[-1]["words"] = words
    r = rules[-1]
    f = figures if isinstance(figures, str) else ", ".join(f"{k} {v}" for k, v in figures.items()) if figures else ""
    return f"- {text}" + (f" (figures: {f})" if f else "") + f" [`{rid}` {r['status']}, {r['method']}]"


def short(text, n=140):
    """a Jev line's text: its first clause, at most n characters (the whole text is in rules.json and conventions.md)"""
    if len(text) <= n:
        return text
    cut = text[:n]; k = max(cut.rfind("; "), cut.rfind(". "), cut.rfind(": "))
    return (cut[:k] if k > 60 else cut.rsplit(" ", 1)[0]) + " …"


JEV_BUDGET = int(os.environ.get("JEV_BUDGET") or 8000)   # bytes; to be agreed with lexeme-aligner from their request costs
# per language, where the default leaves out the rules that matter (user 2026-10-27: Kuni's affixes and protected words
# filled 8 KB, leaving 1 of 31 team decisions); a language here gets a new version anyway when its store changes
JEV_BUDGET_FOR = {"kvg": 16300}   # 16000 + the format-3 header sentence on {words: …} (lexeme-aligner, 2026-10-30: keep every rule d8fdb53e had)
JEV_SECTIONS = [("affix", "Affixes: part → what it links to", None), ("word", "Never divided (or only as shown)", None),
                ("team", "The translation team's decisions", 140), ("letter", "Letters in names", None),
                ("grammar", "Linking facts", 140), ("alternation", "Two words with the same letters", None)]   # in this order; affixes and words always, the rest line by line to the budget


def credit(pname):
    """the style edition's credit line (edition.yaml `credit`), or None"""
    import glob, yaml
    proj = yaml.safe_load(open(os.path.join(R, "export", pname, "project.yaml"), encoding="utf-8")) \
        if os.path.exists(os.path.join(R, "export", pname, "project.yaml")) else {}
    for f in glob.glob(os.path.join(R, "import", "*", "*", "*", "edition.yaml")):
        y = yaml.safe_load(open(f, encoding="utf-8")) or {}
        sf = proj.get("style_from") or []
        if os.path.basename(os.path.dirname(f)) in (sf if isinstance(sf, list) else [sf]):
            return y.get("credit")
    return None


def jev(lang, pname, rules, version_note):
    """the Jev file: the rules that bear on linking, short, within JEV_BUDGET; the same ids as conventions.md / rules.json.
    Grammar here is the store's `feature` entries only (the claims, paradigms and tone patterns are drafting grammar)."""
    out = [f"# {lang}: target rules for an aligner", "",
           "Short form of `conventions.md` (same store, build and ids; whole text and figures there and in `rules.json`). "
           "A line here overrides the source module. [id status method]: `team-decision` from the translators, `corpus-*` "
           "learned from the text (a hypothesis), `project-decision` the project's. The unit is the clause (or 2-3 clauses of "
           "one sentence): \"in the clause\" means the request's clauses (`CLAUSES.md`). `{words: a b}` on a team or linking "
           "line: the target words it concerns (as the tokenizer cuts them, lowercase, marks kept); it applies only where one of "
           "them is in the request. A line without it is general.", ""]
    left = []
    budget = int(os.environ.get("JEV_BUDGET") or JEV_BUDGET_FOR.get(lang, JEV_BUDGET))
    marks = 0                                                         # bytes of {words: …} marks written so far
    if EXAMPLES:
        cr = credit(pname)
        out += [f"Examples in *italics* are short quotations from the edition, with their verse: {cr}. They are not under "
                "this file's CC0." if cr else "Examples in *italics* are attested forms of the edition, with their verse.", ""]
    for sec, title, n in JEV_SECTIONS:
        rs = [r for r in rules if r["section"] == sec and (sec != "grammar" or r.get("kind") == "feature")
              and (sec != "alternation" or r.get("jev"))]
        if not rs:
            continue
        if sec == "affix":
            used = sorted({r["jev"].rsplit("→ ", 1)[1] for r in rs})
            out += [f"## {title}", "", "Links: " + "; ".join(f"{k} = {LEGEND[k]}" for k in used) + ".", ""]
        else:
            out += [f"## {title}", ""]
        k = 0
        for r in rs:
            ex = f" e.g. *{r['example']}*" if EXAMPLES and r.get("example") else ""
            ws = f" {{words: {' '.join(r['words'])}}}" if r.get("words") and sec in ("team", "grammar") else ""
            line = f"- {r.get('jev') or (short(r['text'], n) if n else r['text'])}{ex}{ws} [`{r['id']}` {r['status']} {r['method']}]"
            size = len("\n".join(out + [line]).encode()) - marks - len(ws.encode())   # the marks do not count: an aligner
            if sec not in ("affix", "word", "alternation") and size > budget - 200:     # shows a marked line only where its words occur
                break
            out.append(line); marks += len(ws.encode()); k += 1
        if k < len(rs):
            left.append(f"{title}: {len(rs) - k} of {len(rs)}")
        out.append("")
    # what was left out is told in conventions.md and rules.json, not here: a line that changes with every store update would
    # change every request built from this file and defeat an aligner's answer cache (lexeme-aligner, 2026-10-30)
    return "\n".join(out), left


def main():
    pname, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    ents = load(pname); by = collections.defaultdict(list)
    for e in ents:
        by[e.get("kind")].append(e)
    lang = pname.split("/")[0]
    rules = []; tgt, eng = target_vocab(pname)
    L = [f"# Target module: {lang}", "",
         f"From the make-tanakh store `{pname}`, {datetime.date.today()}. One line per rule: [id, status, method]. "
         "`team-decision` is the translators'; `corpus-*` was learned from the text and its alignment (a hypothesis); "
         "`project-decision` the project's. A line here overrides the source module. The unit is the clause, never the verse "
         "(`CLAUSES.md`). An aligner's short form is `jev.md`; the same rules for tools are in `rules.json`.", ""]
    morphs = sorted(by["morph"], key=lambda e: (e.get("host") or "", e.get("slot") or "", e.get("position") or 0, e.get("form")))
    if morphs:
        L += ["## Affixes: each part and its link", ""]
        for e in morphs:
            pos = f" {e['position']}" if e.get("position") else ""
            L.append(rule(rules, e["id"], "affix", f"**{e['form']}** ({e.get('slot')}{pos}, {e.get('host')}): {e.get('value')}. "
                          f"Link: {link_of(e)}", e, figs(e) or None))
            rules[-1]["jev"] = f"**{e['form']}** {e.get('slot')}{pos} {e.get('host')} {e.get('value')} → {link_short(e)}"
        L.append("")
    words = by["word"]
    if words:
        L += ["## Never divided (or only as shown)", ""]
        for e in sorted(words, key=lambda e: e["form"]):
            ps = " + ".join(p["form"] for p in e.get("parts", [])) if e.get("parts") else "whole"
            L.append(rule(rules, e["id"], "word", f"{e['form']}: {ps}", e, (e.get("stats") or None)))
        L.append("")
    team = [e for e in ents if e.get("method") == "team-decision" and e.get("kind") not in ("name", "term")]
    if team:
        L += ["## The translation team's decisions", ""]
        for e in sorted(team, key=lambda e: e["id"]):
            L.append(rule(rules, e["id"], "team", str(e.get("value")), e, words=rule_words(e, tgt, eng)))
        L.append("")
    claimed = {"claim:morph." + e["id"][2:] for e in morphs} | {e["id"].replace("m:", "claim:morph.", 1) for e in morphs}
    feats = [e for e in by["feature"] + by["claim"] if e.get("method") != "team-decision" and e.get("verdict") != "contradicted"
             and not e["id"].startswith("claim:morph.") and e["id"] not in claimed and not e.get("alternation")]
    if feats:
        L += ["## Grammar", ""]
        for e in sorted(feats, key=lambda e: e["id"]):
            L.append(rule(rules, e["id"], "grammar", str(e.get("value")), e, e.get("figures") or None, words=rule_words(e, tgt, eng)))
        L.append("")
    alts = [e for e in by["feature"] if e.get("alternation") and e.get("status") != "superseded"]
    if alts:
        # forms with the same letters and other marks (scripts/alternations.py): the finding (the note's first sentence, by
        # the checking agent) and the cues; for Jev only the pairs that are two words (they link to different source words)
        L += ["## Forms told apart by their marks", "",
              "Same letters, other tone or length marks; the cue says when the NT writes which (context: the word before or "
              "after, or the linked Greek lemma; p = the share of the cue's tokens written that form).", ""]
        for e in sorted(alts, key=lambda e: e["id"]):
            finding = (e.get("note") or "").split(". ")[0].strip()
            finding = "" if finding.startswith(("Forms with the same letters", "Cues dropped")) else finding
            cues = "; ".join(f"{c['form']}: {c['context']} {c['value']} (p {c['p']}, {c['n']})" for c in e["alternation"]["cues"][:6])
            L.append(rule(rules, e["id"], "alternation", f"{e['value']}. {finding + '. ' if finding else ''}Cues: {cues}", e))
            if finding.startswith("Two words"):
                rules[-1]["jev"] = short(finding, 160)
        L.append("")
    letters = [e for e in by["letter"] if e.get("method") != "team-decision"]
    if letters:
        L += ["## Letters in names", ""]
        L += [rule(rules, e["id"], "letter", str(e.get("value")), e) for e in sorted(letters, key=lambda e: e["id"])] + [""]
    n_terms = 0; have = set(); no_src = 0
    with open(os.path.join(out, "terms.tsv"), "w", encoding="utf-8") as t:
        t.write("source\ttarget\tkind\tstatus\tmethod\tid\n")
        for e in sorted(by["name"] + by["term"], key=lambda e: e["id"]):
            lems = [g.get("lemma") or g.get("form") for g in e.get("gloss") or [] if isinstance(g, dict)]
            src = "; ".join(lems) or e.get("source") or ""
            if not src or not e.get("value"):
                continue
            # the source side is the Greek or Hebrew (or a Strong's number), never an English word (user 2026-10-27)
            if not re.search(r"[\u0370-\u03ff\u1f00-\u1fff\u0590-\u05ff]|\b[HG]\d+\b", src):
                no_src += 1
                continue
            have.update(lems)
            t.write("\t".join(str(x).replace("\t", " ").replace("\n", " ") for x in
                              (src, e["value"], e["kind"], e.get("status"), e.get("method"), e["id"])) + "\n")
            n_terms += 1
        dn = derived_names(pname, have)
        for lem, form, n, tot in dn:
            t.write(f"{lem}\t{form}\tname\tobserved\tcorpus-derived\tlang:name:{lem}:{form}\n")
            n_terms += 1
    L += ["## Names and terms", "", f"`terms.tsv`: {n_terms} rows, source lemma → target"
          + (f" ({len(dn)} names derived from the NT's alignment, ids `lang:name:…`)" if dn else "")
          + (f"; {no_src} store entries without a Greek or Hebrew source are left out." if no_src else "."), ""]
    J, left = jev(lang, pname, rules, None)
    budget = int(os.environ.get("JEV_BUDGET") or JEV_BUDGET_FOR.get(lang, JEV_BUDGET))
    L += ["## The aligner's short form", "", "`jev.md` holds the rules that bear on linking, within " + f"{budget} bytes"
          + (" (the `{words: …}` marks not counted). Left out for the size limit: " + "; ".join(left) + "." if left else
             " (the `{words: …}` marks not counted); nothing left out."), ""]
    open(os.path.join(out, "conventions.md"), "w", encoding="utf-8").write("\n".join(L))
    open(os.path.join(out, "jev.md"), "w", encoding="utf-8").write(J)
    json.dump({"format": "bcv-conventions-rules/0.1", "store": pname, "jev_budget": budget, "jev_left_out": left, "rules": rules},
              open(os.path.join(out, "rules.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(out, "rules", len(rules), "affixes", len(morphs), "words", len(words), "team", len(team), "grammar", len(feats),
          "letters", len(letters), "terms", n_terms, "no source", no_src, "derived names", len(dn), "bytes", len("\n".join(L).encode()), "jev", len(J.encode()), "left out", left)


if __name__ == "__main__":
    main()
