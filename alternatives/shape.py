#!/usr/bin/env python3
"""The shape draft: an alternative in which the model writes no word itself. For every clause it writes a template, slot by
slot in target order; each slot points into the team's own translation: an evidence clause's word, or a candidate stem with
the affixes of an evidence word. Code turns the template into words. So every word of the shape draft has a trace back to a
clause of the team's text, which is what a reviewer gets from it; as a draft it is weaker than the main draft.

It reads what the main draft reads (the 20 most similar clauses per clause, drafting/evidence.py) plus, per content word,
the candidate stems: the stems the team's text gives the same lexeme, counted by where they come from
  text      the team's text of the same source language (the lemma; for Hebrew the lexeme's number)
  bridged   (a Hebrew word) the team's NT for the Greek lexemes the Hebrew lexeme corresponds to, weighted by their share
  evidence  the evidence clauses shown for the clause

    . ./env.sh
    python3 alternatives/shape.py build --lang kvg --book EXO --chapters 1      # the prompts (free)
    python3 alternatives/shape.py send  --lang kvg --book EXO                   # the templates; rerun to go on
    python3 alternatives/shape.py words --lang kvg --book EXO                   # templates -> answers/ and trace.json

The run lives beside the main draft: runs/<lang>/draft/<book>/<label>/ (label: shape); templates/ holds the model's answers,
answers/ the realised clauses in the main draft's form, trace.json per clause the source of every word (clause ids and word
numbers, never text). Closed and held-out chapters are refused.

This is the research shape writer without its rule-engine fall-back and its catalogue codes (neither is in this repository):
a slot that cannot be resolved yields nothing."""
import argparse, collections, glob, hashlib, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import llm, paths, rights  # noqa: E402
from source import tokens  # noqa: E402
from drafting import draft, evidence, prompt  # noqa: E402

N_EV, N_CAND = prompt.N_EVIDENCE, 8
SYSTEM = ("You plan translations into {lang} for a Bible translation team. You never write a {lang} word yourself: you point to words "
          "of the team's own translation that are shown to you. Answer with JSON only.")
SLOT = {"type": "object", "additionalProperties": False,
        "properties": {"for": {"type": ["integer", "null"]}, "ref": {"type": "array", "items": {"type": "integer"}},
                       "lex": {"type": "integer"}, "affix": {"type": "array", "items": {"type": "integer"}}, "none": {"type": "string"}}}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["clauses"],
          "properties": {"clauses": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["c", "slots"],
                                                               "properties": {"c": {"type": "integer"}, "slots": {"type": "array", "items": SLOT}}}}}}
TASK = """## Task

For each clause above write the template of its translation into {lang}, in target word order. Answer with ONE JSON object:

    {{"clauses": [{{"c": 1, "slots": [ ... ]}}, {{"c": 2, "slots": [ ... ]}}, ...]}}

Each slot stands for one target word and is one of:
- {{"for": i, "ref": [e, w]}}: copy target word w of evidence clause e of this clause. For a content word i of the source clause the
  word's affixes are kept around its stem; add "lex": n to put candidate stem n of word i in place of the evidence word's stem. For
  a function word, or a target word no source word stands for ("for": null), the evidence word is copied whole.
- {{"for": i, "lex": n, "affix": [e, w]}}: candidate stem n of source word i with the affixes of evidence word [e, w]; without
  "affix" the stem stands alone.
- {{"none": "reason", "for": i}}: nothing is written for source word i (a word this translation leaves unexpressed).

i = the source word's number in its clause, e = the evidence clause's number under that clause, w = the target word's number
inside that evidence clause, n = the candidate's number under its source word. Follow the word order and the clause shapes the
evidence shows. Never write a target word yourself: every target word must come from a reference."""


def stem_of(ws):
    """the stem part of a word [[part, slot], ...]: the part in the stem slot, else the longest"""
    st = [p for p, s in ws if s == "stem"]
    return (st[0] if st else max((p for p, _ in ws), key=len)).lower()


def linked_word(c, t):
    x = c["words"].get(t["ref"]) if t.get("w") is not None else None
    if not x or not (0 <= t["w"] - x["w0"] < len(x["words"])):
        return None
    return x["words"][t["w"] - x["w0"]]


class Lexicon:
    """stems of the team's text per source lexeme, from the pool: {('grc', lemma) | ('hbo', number) | ('G', Greek number): Counter}"""
    def __init__(self, pool):
        self.by = collections.defaultdict(collections.Counter)
        for c in pool:
            for t in c["tokens"]:
                if t["cls"] not in prompt.CONTENT:
                    continue
                ws = linked_word(c, t)
                if ws:
                    s = stem_of(ws); self.by[(c["lang"], t["lemma"] if c["lang"] == "grc" else t["strong"])][s] += 1
                    if c["lang"] == "grc":
                        self.by[("G", t["strong"])][s] += 1


def candidates(L, lex, source, q, ev):
    """{source word number: [(stem, {origin: count})]} for the content words of a query clause, commonest first"""
    out = {}
    for i, t in enumerate(q["tokens"], 1):
        if t["cls"] not in prompt.CONTENT:
            continue
        c = collections.defaultdict(lambda: collections.defaultdict(float))
        for s, n in L.by.get((source, t["lemma"] if source == "grc" else t["strong"]), {}).items():
            c[s]["text"] += n
        if source == "hbo":
            for g, share in lex.get(t["strong"], [])[:3]:
                for s, n in L.by.get(("G", g), {}).items():
                    c[s]["bridged"] += round(n * share, 1)
        gs = set(t.get("gstrongs") or ())
        for e in ev:
            for u in e["tokens"]:
                same = (u["lemma"] == t["lemma"]) if e["lang"] == source == "grc" else (u["strong"] == t["strong"]) if e["lang"] == source else u["strong"] in gs
                ws = linked_word(e, u) if same and u["cls"] in prompt.CONTENT else None
                if ws:
                    c[stem_of(ws)]["evidence"] += 1
        rank = sorted(c.items(), key=lambda kv: (-(kv[1].get("evidence", 0) * 3 + kv[1].get("text", 0) + kv[1].get("bridged", 0)), kv[0]))[:N_CAND]
        if rank:
            out[i] = [(s, {k: round(v, 1) for k, v in src.items()}) for s, src in rank]
    return out


class Shape:
    def __init__(self, cfg, E):
        self.cfg, self.E = cfg, E; self.G = tokens.glosses("grc"); self.L = Lexicon(E.pool)
        from source import bridges
        self.lex = bridges.lexemes() if E.source == "hbo" else {}

    def groups(self):
        g = collections.OrderedDict()
        for qid in self.E.order:
            q = self.E.queries[qid]; g.setdefault(sorted(q["refs"], key=prompt.ref_key)[0], []).append(q)
        return g

    def parts(self, q):
        ev = self.E.top(q["id"], N_EV); return ev, candidates(self.L, self.lex, self.E.source, q, ev)

    def verse(self, clauses):
        E, src, name = self.E, self.E.source, self.cfg["name"]
        refs = sorted({r for q in clauses for r in q["refs"]}, key=prompt.ref_key)
        L = [f"# {' / '.join(refs)} ({name}): templates", "",
             "Target words of the evidence are numbered; each is [parts]: prefixes end in '-', suffixes begin with '-', the stem is bare. "
             "'<- g3' = linked to source word 3 of that evidence clause; '<- -' = linked to none; 'a-:g2 b:g5' = the word's parts link "
             "to different source words.", ""]
        for k, q in enumerate(clauses, 1):
            ev, cands = self.parts(q)
            L.append(f"## Clause C{k} ({paths.SOURCE_NAME[src]})")
            L += [prompt.tok_line_word(i, t) if src == "hbo" else prompt.tok_line(i, t, self.G) for i, t in enumerate(q["tokens"], 1)]
            L += ["", f"### Evidence for C{k}: the team's translation of the {len(ev)} most similar clauses"]
            for e_no, c in enumerate(ev, 1):
                L += [f"E{e_no}"] + prompt.ev_lines(c, self.G)
            if cands:
                L += ["", f"### Candidate stems for C{k} (counts: text = the team's text for this lexeme" +
                      ("; bridged = the team's New Testament for the Greek lexemes it corresponds to" if src == "hbo" else "") + "; evidence = the clauses above)"]
                for i, cl in cands.items():
                    t = q["tokens"][i - 1]
                    L.append(f"- word {i} {t['text']} ({t['lemma']}): " + "; ".join(
                        f"{n} {s} (" + ", ".join(f"{k_} {v:g}" for k_, v in o.items()) + ")" for n, (s, o) in enumerate(cl, 1)))
            L.append("")
        L.append(TASK.format(lang=name))
        return "\n".join(L), refs


def realise(slots, q, ev, cands):
    """slots -> [(word, trace)]: trace = 'ref:<evidence clause id>#<word>', the same + '+lex', or 'lex'; an unresolvable slot is dropped"""
    out = []; ew = [prompt.ev_words(c) for c in ev]

    def word(r):
        if not (isinstance(r, list) and len(r) == 2 and all(isinstance(x, int) for x in r)) or not (1 <= r[0] <= len(ev)) or not (1 <= r[1] <= len(ew[r[0] - 1])):
            return None
        ref, w, ws, lk = ew[r[0] - 1][r[1] - 1]; x = ev[r[0] - 1]["words"][ref]
        first = (x["w0"] + r[1] - 1) == 0                       # the first word of its verse: its capital is the sentence's
        return [list(p) for p in ws], first

    def cand(i, n):
        cl = cands.get(i) if isinstance(i, int) else None
        return cl[n - 1][0] if cl and isinstance(n, int) and 1 <= n <= len(cl) else None
    for s in slots if isinstance(slots, list) else []:
        if not isinstance(s, dict) or "none" in s:
            continue
        r = s.get("ref") or s.get("affix"); st = cand(s.get("for"), s.get("lex")) if "lex" in s else None
        got = word(r) if r else None
        if got:
            ws, first = got
            if st:
                k = next((j for j, (p, sl) in enumerate(ws) if sl == "stem"), max(range(len(ws)), key=lambda j: len(ws[j][0])))
                ws[k][0] = st
            w = "".join(p for p, _ in ws)
            if first and w[:1].isupper() and not w[1:2].isupper():
                w = w[:1].lower() + w[1:]
            out.append((w, f"ref:{ev[r[0] - 1]['id']}#{r[1]}" + ("+lex" if st else "")))
        elif st:
            out.append((st, "lex"))
    return out


def cmd_build(a):
    cfg = paths.config(a.lang); src = a.source or draft.source_of(a.book); chs = draft.chapters_arg(a.chapters)
    E = evidence.build(cfg, src, a.book, chs, tuple(x for x in (a.leave_out or "").split(",") if x)); S = Shape(cfg, E)
    d = draft.job_dir(a, "prompts"); n = chars = 0; groups = {}; h = hashlib.sha256()
    for v, cl in S.groups().items():
        txt, refs = S.verse(cl); open(os.path.join(d, draft.vid(v) + ".md"), "w", encoding="utf-8").write(txt)
        groups[draft.vid(v)] = {"refs": refs, "clauses": [q["id"] for q in cl]}; n += 1; chars += len(txt); h.update(txt.encode("utf-8"))
    draft.save_groups(a, groups); m = draft.load_manifest(a)
    m["builds"].append({"when": time.strftime("%Y-%m-%d %H:%M"), "code": draft.commit(), "kind": "shape", "source": src, "chapters": chs, "verses": n,
                        "clauses": len(E.order), "characters": chars, "prompts sha256": h.hexdigest(), "evidence": E.meta,
                        "leave out": [x for x in (a.leave_out or "").split(",") if x]})
    draft.save_manifest(a, m)
    print(f"{a.lang} {a.book} {chs}: {n} verses, {len(E.order)} clauses, {chars} characters (about {chars // 3} input tokens) -> {d}")


def cmd_send(a):
    cfg = paths.config(a.lang); d = draft.job_dir(a, "prompts"); td = draft.job_dir(a, "templates"); rights.check(cfg, "llm")
    files = [f for f in sorted(glob.glob(os.path.join(d, "*.md"))) if not os.path.exists(os.path.join(td, os.path.basename(f)[:-3] + ".json"))]
    if not files:
        print("nothing to send: every prompt has its template"); return
    if llm.BACKEND != "cli":
        sys.exit("the shape draft runs on the cli backend (set CLAUDE_BACKEND=cli)")
    m = draft.load_manifest(a); rec = {"when": time.strftime("%Y-%m-%d %H:%M"), "backend": llm.BACKEND, "model": llm.MODEL, "effort": "medium",
                                       "code": draft.commit(), "prompts": len(files), "answered": 0, "unparsable": [], "errors": [], "list USD": 0.0}
    m["sends"].append(rec); items = [(os.path.basename(f)[:-3], open(f, encoding="utf-8").read()) for f in files]
    print(f"{llm.BACKEND}: {len(items)} prompts, model {llm.MODEL}", flush=True)
    for i, r in llm.run(items, SYSTEM.format(lang=cfg["name"]), SCHEMA):
        if not r["ok"]:
            rec["errors"].append([i, r.get("error")])
        else:
            rec["list USD"] = round(rec["list USD"] + (r.get("list_usd") or 0.0), 4)
            try:
                o = json.loads(r["text"]); assert isinstance(o.get("clauses"), list)
                json.dump(o, open(os.path.join(td, i + ".json"), "w", encoding="utf-8"), ensure_ascii=False); rec["answered"] += 1
            except (ValueError, AssertionError, AttributeError):
                rec["unparsable"].append(i)
        done = rec["answered"] + len(rec["errors"]) + len(rec["unparsable"])
        if done % 10 == 0 or done == len(items):
            draft.save_manifest(a, m); print(f"{done}/{len(items)}", flush=True)
    rec["finished"] = time.strftime("%Y-%m-%d %H:%M"); draft.save_manifest(a, m); print(json.dumps(rec))


def cmd_words(a):
    cfg = paths.config(a.lang); m = draft.load_manifest(a); b = next((x for x in reversed(m["builds"]) if x.get("kind") == "shape"), None)
    if not b:
        sys.exit("no shape build in this run: build first")
    chs = sorted({c for x in m["builds"] if x.get("kind") == "shape" for c in x["chapters"]})
    E = evidence.build(cfg, b["source"], a.book, chs, tuple(b.get("leave out", ()))); S = Shape(cfg, E)
    td = draft.job_dir(a, "templates"); od = draft.job_dir(a, "answers"); trace = {}; st = collections.Counter()
    for i, refs, ids in draft.load_groups(a):
        p = os.path.join(td, i + ".json")
        if not os.path.exists(p):
            st["verses without a template"] += 1; continue
        by = {x.get("c"): x.get("slots") for x in json.load(open(p, encoding="utf-8")).get("clauses", []) if isinstance(x, dict)}; cl = []
        for k, qid in enumerate(ids, 1):
            q = E.queries[qid]; ev, cands = S.parts(q); ws = realise(by.get(k), q, ev, cands)
            n_slots = sum(1 for s in (by.get(k) or []) if isinstance(s, dict) and "none" not in s)
            st["slots"] += n_slots; st["slots resolved"] += len(ws); st["clauses"] += 1; st["clauses without words"] += not ws
            cl.append({"c": k, "text": " ".join(w for w, _ in ws)}); trace[qid] = [t for _, t in ws]
        json.dump({"clauses": cl}, open(os.path.join(od, i + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(trace, open(os.path.join(draft.job_dir(a), "trace.json"), "w"), indent=0)
    print(json.dumps(dict(st)), "->", od)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "send", "words")); ap.add_argument("--lang", required=True); ap.add_argument("--book", required=True)
    ap.add_argument("--chapters"); ap.add_argument("--label", default="shape"); ap.add_argument("--source", choices=paths.SOURCES); ap.add_argument("--leave-out")
    a = ap.parse_args(); a.book = a.book.upper()
    if a.cmd == "build" and not a.chapters:
        sys.exit("build needs --chapters")
    {"build": cmd_build, "send": cmd_send, "words": cmd_words}[a.cmd](a)


if __name__ == "__main__":
    main()
