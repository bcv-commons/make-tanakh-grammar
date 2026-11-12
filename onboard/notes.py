#!/usr/bin/env python3
"""Grammar notes for a language, written from its own aligned text: a step of the first stage.

For each topic the source side picks the examples: clauses of the Greek NT that show the topic (a connector, a question word, a
verb cell, a clause order ...), each with the team's translation of that stretch as words and as parts with their links. A model
reads a topic's examples and writes one page: how the language expresses these things, as rules a drafter can apply, each backed
by examples it was shown. The drafter's prompt carries the pages (drafting/prompt.py).

What the pages are worth is a question for the language's dev check (drafting/devcheck.py: a run with the notes against a run
without). Pages a team has answered questions on helped in research; pages written from the text alone are measured per language.

The examples come from the pool only (drafting/evidence.py): no closed or held-out chapter, none of the books left out. Leave
the dev book out while the dev check is still to be run, so that the pages have not seen it.

    . ./env.sh
    python3 onboard/notes.py build --lang zin --leave-out JHN      # the prompts (free)
    python3 onboard/notes.py send  --lang zin                      # one request per page; rerun to go on
    python3 onboard/notes.py use   --lang zin                      # name the pages in the language's configuration

With --register, every page's examples are followed by the team's decided entries of the register (terms, names, formulas,
rules, morphs, spelling, questionnaire answers), as binding: where the examples and a decision disagree, the page follows the
decision and says so (plan internal-docs/review-feedback-data-plan-2026-11-10.md, section 3.9). --out <name> keeps such pages
apart (notes/prompts-<name>, notes/<name>, build-<name>.json); the drafter reads them with draft.py build --pages <name>.

Prompts and pages: $MAKE_TANAKH_PRIVATE/lang/<iso>/notes/{prompts, grammar}/<page>.md."""
import argparse, collections, glob, hashlib, json, os, sqlite3, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import llm, paths, rights  # noqa: E402
from source import tokens  # noqa: E402
from drafting import evidence, prompt  # noqa: E402

PER_KEY, PER_TOPIC, MAX_KEYS = 10, 260, 45
MIN_TOK, MAX_TOK, MIN_LINKED = 3, 14, 0.6
PERSONAL = ("ἐγώ", "σύ", "αὐτός", "ἡμεῖς", "ὑμεῖς")
TOPICS = [
    ("connectors", "Connectors, relative clauses, time",
     "how clauses are joined: 'and', 'but', 'for', 'so', 'that', 'in order that', 'if', 'when', 'as', 'until', and how relative clauses are made",
     1200, {"lemma": ("καί", "δέ", "γάρ", "ἀλλά", "οὖν", "ὅτι", "ἵνα", "εἰ", "ἐάν", "ὅτε", "ὅταν", "ὡς", "καθώς", "ἕως", "ὅς", "ὅστις", "διό",
                      "ὥστε", "ἐπεί", "πρίν", "μέν", "τέ", "ἤ", "ὅπου", "διότι", "ὅπως", "τότε")}),
    ("existence-naming-counting", "Existence, naming, counting",
     "'to be' (identity, description, place, existence), 'to become', naming ('called', 'whose name is'), numbers and quantities ('one', 'two', 'all', 'many')",
     1200, {"lemma": ("εἰμί", "γίνομαι", "ὑπάρχω", "καλέω", "ὄνομα", "πᾶς", "πολύς", "ὅλος", "ἄλλος", "ἕκαστος", "οὐδείς", "μηδείς", "τις"), "cls": ("num",)}),
    ("possession", "Possession",
     "possession: 'my', 'your', 'his', 'their', a noun possessed by a noun ('the house of the man'), 'to have', 'one's own'",
     1000, {"lemma": ("ἔχω", "ἴδιος", "ἐμός", "σός", "ἑαυτοῦ"), "genitive": PERSONAL}),
    ("adpositions", "Prepositions, place and noun marking",
     "how the meanings of prepositions are expressed ('in', 'to', 'from', 'with', 'on', 'through', 'for', 'about', 'before', 'under'): separate words, "
     "prefixes or suffixes on the noun, or forms of the verb", 1200, {"cls": ("prep",)}),
    ("pronouns", "Pronouns and demonstratives",
     "independent pronouns for each person and number, when they are written and when the verb alone carries the person, 'this' and 'that', reflexives, 'each other'",
     1000, {"lemma": PERSONAL + ("οὗτος", "ἐκεῖνος", "ἑαυτοῦ", "ἀλλήλων", "ὅδε", "τοιοῦτος", "ἐμαυτοῦ", "σεαυτοῦ")}),
    ("questions", "Questions",
     "questions: 'who', 'what', 'why', 'how', 'where', 'when', 'how many', yes-no questions, and how a question is marked",
     800, {"lemma": ("τίς", "πῶς", "ποῦ", "πότε", "πόθεν", "ποῖος", "πόσος", "μήτι"), "question": True}),
    ("verbs", "Verbs",
     "the verb: how person and number of the subject, tense and aspect, mood (statement, command, wish, purpose), negation and the object are marked; "
     "infinitives and participles; the order of the parts inside the verb word", 3000, {"cells": True}),
    ("word-order", "Word order and sentence rhythm",
     "the order of subject, object and verb, the place of adverbs and place and time phrases, where a clause is split into shorter sentences, "
     "and which words the team adds that the source does not have", 1000, {"rules": True}),
]
SYSTEM = """You are a field linguist. You write short, exact grammar notes on {name} for Bible translators and for a drafting model that \
must write {name} the way its translation team does. You are given clauses of the Greek New Testament with the team's {name} \
translation; you know only what these examples show."""
TASK = """# Task

The {n} clauses above were chosen to show: {about}.

Write a grammar page in Markdown, beginning with the line `# {title}`. Then, in sections with `##` headings:

- State how {name} expresses each of these things as rules a drafter can apply: which word or which part of a word does the work, \
its form and its variants, where it stands, what it agrees with.
- Under each rule quote one to three of the examples above: the {name} words exactly as the team writes them (whole words, not the \
bracketed parts), an English gloss, and the reference in round brackets, for example (ROM 3:4).
- Say where a Greek word has no {name} word of its own, and which {name} words the team writes that no Greek word stands for.
- Where two forms compete, say what seems to decide between them; if the examples do not show it, say so.
- Say only what the examples show. Where they are too few or disagree, write a line beginning `Open:` with the question a \
speaker of {name} could answer.
- Do not explain Greek. Do not copy long stretches: a quoted example is at most eight {name} words.

Keep the page under about {words} words. Answer with the page only."""


def linked_share(c):
    return sum(1 for t in c["tokens"] if t["w"] is not None) / max(1, len(c["tokens"]))


def usable(c):
    """a clause that shows something: of middling length, mostly linked, and with a compact stretch of the team's text"""
    if c["lang"] != "grc" or not MIN_TOK <= len(c["tokens"]) <= MAX_TOK or not c.get("words") or linked_share(c) < MIN_LINKED:
        return False
    return sum(len(x["words"]) for x in c["words"].values()) <= 2 * len(c["tokens"]) + 4


def stable(c):
    """an order that does not depend on the run: by a hash of the clause id"""
    return hashlib.sha256(c["id"].encode()).hexdigest()


def pick(groups, per_key=PER_KEY, total=PER_TOPIC):
    """round-robin over the MAX_KEYS commonest keys, each key's clauses in their stable order, a clause once"""
    keys = sorted(groups, key=lambda k: (-len(groups[k]), str(k)))[:MAX_KEYS]; seen = set(); out = []
    lists = {k: sorted(groups[k], key=stable)[:per_key * 3] for k in keys}; n = collections.Counter()
    for i in range(per_key * 3):
        for k in keys:
            if len(out) >= total:
                return out
            if i < len(lists[k]) and n[k] < per_key and lists[k][i]["id"] not in seen:
                seen.add(lists[k][i]["id"]); out.append((k, lists[k][i])); n[k] += 1
    return out


def select(pool, spec, case, quest):
    """the clauses of a topic: {key: [clauses]} by what the topic asks for"""
    g = collections.defaultdict(list)
    for c in pool:
        if not usable(c):
            continue
        for t in c["tokens"]:
            if t["lemma"] in spec.get("lemma", ()):
                g[t["lemma"]].append(c)
            if t["cls"] in spec.get("cls", ()):
                g[t["lemma"]].append(c)
            if t["lemma"] in spec.get("genitive", ()) and case.get(t["key"]) == "genitive":
                g[t["lemma"] + " (genitive)"].append(c)
        if spec.get("question") and any(t["key"] in quest for t in c["tokens"]):
            g["question mark"].append(c)
        if spec.get("cells"):
            for t in c["tokens"]:
                if t["cls"] == "verb" and t["cell"]:
                    g[" ".join(str(x) for x in t["cell"][:2] if x) + (", negated" if c["neg"] else "")].append(c)
                    if t["cell"][2]:
                        g["person " + " ".join(str(x) for x in t["cell"][2:] if x)].append(c)
        if spec.get("rules") and c["rule"]:
            g[c["rule"]].append(c)
    return g


def example(n, key, c, G):
    """one example clause: the Greek words, the team's words plain, and the team's words as parts with links"""
    ws = prompt.ev_words(c); pls = prompt.ev_part_links(c)
    return [f"E{n} ({c['refs'][0]}; chosen for: {key})",
            "Greek: " + " | ".join(prompt.tok_line(i, t, G) for i, t in enumerate(c["tokens"], 1)),
            "Team: " + " ".join("".join(p for p, _ in w) for _, _, w, _ in ws),
            "Parts: " + " ; ".join(f"{j} {prompt.word_str(w)} " + prompt.link_marker(w, lk, pls[j - 1] if pls else None) for j, (_, _, w, lk) in enumerate(ws, 1))]


def notes_dir(lang, *sub):
    d = paths.lang_dir(lang, "notes", *sub); os.makedirs(d, exist_ok=True); return d


def dirs(a):
    """(prompts, pages, build record) of --out"""
    o = a.out or "grammar"
    return ("prompts" if o == "grammar" else f"prompts-{o}"), o, ("build.json" if o == "grammar" else f"build-{o}.json")


def decisions_block(cfg):
    """the page prompt's section of the team's decided entries ([] when the register has none)"""
    from shared import register as RG
    if not cfg.get("_register"):
        return []
    E = RG.load(cfg["_register"]); B = RG.binding(E); P = RG.parameters(); name = cfg["name"]; L = []
    for e in B:
        k = e["kind"]
        if k in ("term", "name"):
            also = RG.forms(e, "admitted"); no = RG.forms(e, "deprecated")
            L.append(f"- {k} {e.get('source') or e['id'].split(':', 1)[1]}" + (f" ('{', '.join(e['words'][:3])}')" if e.get("words") else "") +
                     f": {e['value']}" + (f"; also {', '.join(also)}" if also else "") + (f"; not {', '.join(no)}" if no else ""))
        elif k == "formula":
            L.append(f"- set phrase {e.get('source') or e['id'].split(':', 1)[1]}: {e['value']}")
        elif k == "rule":
            L.append(f"- rule: {e.get('said') or e['value']}")
        elif k == "morph":
            L.append(f"- morpheme {e['id'].split(':')[1]} ({e.get('slot')}, on a {e.get('host')}): {e['value']}")
        elif k in ("letter", "orthography"):
            L.append(f"- spelling: {e['value']}")
        elif k == "feature" and e.get("parameter") in P and not e["parameter"].startswith("MT-A3"):
            L.append(f"- {P[e['parameter']].get('question') or e['parameter']}: {e['value']}" + (f" ({e['note']})" if e.get("note") else ""))
    if not L:
        return []
    return ["# The team's decisions", "", f"The {name} translation team has decided these points. They are binding: where an example above "
            "disagrees with one, the decision holds; write the rule as the team decided it and say on the page that the team decided it. "
            "Do not repeat the decisions that have nothing to do with this page's topic.", ""] + L + [""]


def cmd_build(a):
    cfg = paths.config(a.lang); leave = tuple(x for x in (a.leave_out or "").split(",") if x); T = tokens.greek()
    vg, gg, _ = evidence.read_corpus(cfg, "grc", leave)
    if not vg:
        sys.exit("the language has no aligned NT text: the notes are written from the Greek side (a Hebrew-side sampler is not built)")
    pool, _ = evidence.greek_clauses(T, gg, vg, set()); G = tokens.glosses("grc")
    z = sqlite3.connect(paths.work("orig", "grc.sqlite"))
    case = dict(z.execute("select key, gcase from tokens where gcase is not null")); quest = {k for k, in z.execute("select key from tokens where after like '%;%'")}
    pd, _, bj = dirs(a); dec = decisions_block(cfg) if a.register else []
    d = notes_dir(a.lang, pd); meta = {"when": time.strftime("%Y-%m-%d %H:%M"), "left out": list(leave), "pool clauses": len(pool), "pages": {},
                                       "register": len([x for x in dec if x.startswith("- ")]) if a.register else None}
    for page, title, about, words, spec in TOPICS:
        chosen = pick(select(pool, spec, case, quest))
        L = [f"# {cfg['name']}: examples for the page '{title}'", "",
             "Each example: the Greek clause word by word (number, word, lemma of content words, English gloss, class, verb cell); the team's "
             f"{cfg['name']} words of that stretch; and the same words numbered and divided into [parts] (prefixes end in '-', suffixes begin "
             "with '-'), each with the Greek word numbers it is linked to ('<- g3'; 'a-:g2 b:g5' = its parts link to different Greek "
             "words; '<- -' = linked to no Greek word).", ""]
        for n, (key, c) in enumerate(chosen, 1):
            L += example(n, key, c, G) + [""]
        L += dec
        L.append(TASK.format(n=len(chosen), about=about, title=title, name=cfg["name"], words=words))
        txt = "\n".join(L); open(os.path.join(d, page + ".md"), "w", encoding="utf-8").write(txt)
        meta["pages"][page] = {"title": title, "examples": len(chosen), "keys": len({k for k, _ in chosen}), "characters": len(txt),
                               "books": len({c["book"] for _, c in chosen})}
        print(f"{page}: {len(chosen)} examples of {meta['pages'][page]['keys']} kinds, {len(txt)} characters")
    json.dump(meta, open(os.path.join(notes_dir(a.lang), bj), "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def cmd_send(a):
    pd, o, _ = dirs(a); cfg = paths.config(a.lang); d = notes_dir(a.lang, pd); od = notes_dir(a.lang, o); rights.check(cfg, "llm")
    items = [(p, open(os.path.join(d, p + ".md"), encoding="utf-8").read()) for p, *_ in TOPICS
             if os.path.exists(os.path.join(d, p + ".md")) and not os.path.exists(os.path.join(od, p + ".md"))]
    if not items:
        print("nothing to send: every page is written"); return
    if llm.BACKEND != "cli":
        sys.exit("the notes are written on the cli backend (set CLAUDE_BACKEND=cli)")
    log = {"when": time.strftime("%Y-%m-%d %H:%M"), "model": llm.MODEL, "effort": "high", "pages": {}}
    for page, r in llm.run(items, SYSTEM.format(name=cfg["name"]), None, effort="high"):
        if r["ok"] and r["text"].strip():
            open(os.path.join(od, page + ".md"), "w", encoding="utf-8").write(r["text"].strip() + "\n")
        log["pages"][page] = {"ok": r["ok"], "characters": len(r.get("text") or ""), "list USD": r.get("list_usd"), "error": r.get("error")}
        print(page, log["pages"][page], flush=True)
    json.dump(log, open(os.path.join(notes_dir(a.lang), f"send-{dirs(a)[1]}-{time.strftime('%Y%m%d-%H%M')}.json"), "w"), indent=1)


def cmd_use(a):
    p = paths.lang_dir(a.lang, "config.json"); c = json.load(open(p, encoding="utf-8")); od = notes_dir(a.lang, "grammar")
    pages = [pg for pg, *_ in TOPICS if os.path.exists(os.path.join(od, pg + ".md"))]
    if not pages:
        sys.exit("no pages written yet")
    c["notes"] = {"dir": "notes/grammar", "pages": pages, "intro": f"Notes on {c['name']} grammar, written from the team's translation:"}
    json.dump(c, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False); print("configuration names", len(pages), "pages:", ", ".join(pages))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "send", "use")); ap.add_argument("--lang", required=True); ap.add_argument("--leave-out")
    ap.add_argument("--register", action="store_true", help="build: the team's decided register entries, binding, on every page")
    ap.add_argument("--out", help="build, send: pages of their own under notes/<out> (default grammar)")
    a = ap.parse_args(); {"build": cmd_build, "send": cmd_send, "use": cmd_use}[a.cmd](a)


if __name__ == "__main__":
    main()
