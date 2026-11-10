#!/usr/bin/env python3
"""The reviewer's bundle of drafted Tanakh chapters: the main draft in the published chapter format, the alternative drafts
beside it. It is what the publish step puts into a language's text repository.

  <book>/<book>_<ccc>.md / .units / .notes / .align   the main draft; units are authored (every draft is written clause by
                                                      clause); .align = lexeme-aligner's alignment with the team's text (publish/align.py)
  (no support marks: the review editor computes the alternatives' agreement from these files, decided 2026-11-09)
  .tanakh/alternatives/<kind>/<book>/<book>_<ccc>.md / .units / .notes / .align   the alternatives; never edited, replaced as a whole
  .tanakh/alternatives/README.md                  one line per kind: what made it, when

A draft is a run of drafting/draft.py or of an alternative (alternatives/nllb.py, shape.py, rules.py) under
runs/<lang>/draft/<book>/<label>/; --main names the main draft's label, each --alt an alternative's (its label is its kind).

The verbatim gate (publish/verbatim.py) checks every clause of every draft against the team's text of the same verse, where
the team has one. A flagged clause of the MAIN draft is, in this order and re-checked after each: (1) rephrased by the drafter,
which gets its own clause, the source and the team's renderings of similar clauses of other verses, never the team's verse
(two tries); (2) replaced by a clean alternative's clause; (3) withheld: left empty with a note to the reviewers. A flagged
clause of an ALTERNATIVE is left out. The published files say only "rephrased", "taken from <kind>", "withheld" or "left out";
the flag report (clause ids and run lengths, no text) goes to $MAKE_TANAKH_PRIVATE/publish/<lang>/flags/, outside the bundle.

    . ./env.sh
    python3 publish/bundle.py --lang kvg --book EXO --chapters 1-3 --alt nllb [--alt shape] [--main main] [--no-rephrase]

Writes $MAKE_TANAKH_PRIVATE/publish/<lang>/bundle/ (or --out). Nothing leaves the box here: publishing is its own step."""
import argparse, collections, copy, datetime, json, os, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import llm, paths, rights  # noqa: E402
from source import tokens  # noqa: E402
from drafting import draft, evidence, prompt  # noqa: E402
from publish import align as AL, chapter_format as CF, verbatim as V  # noqa: E402
FA = CF.FA

STATUS = [("Maturity", "Machine draft"), ("Translation", ""), ("Exegesis", "Not yet"), ("Literary check", "Not yet"), ("Date", "")]
MADE_BY = {"main": "LLM draft ({model}): for every clause the team's translation of the most similar clauses as parts, the team's "
                     "function-word renderings, similar whole verses{notes}",
             "nllb": "NLLB parts model fine-tuned on the team's text ({model}): consensus of the beam output and {samples} samples, the verse "
                     "cut to clauses by their share of the source words",
             "shape": "shape draft ({model}): every word a reference into a clause of the team's translation or a lexicon candidate",
             "rules": "rule draft ({model}, no model call): TBTA's propositions rendered clause by clause with a lexicon by concept, "
                      "affix pieces, function parts, order and pronouns counted from the team's linked parts; uncovered words from the "
                      "team's forms per lexeme"}
REPHRASE_SYS = ("You revise one clause of a machine draft in {lang}. Keep its meaning exactly and keep it good {lang}, but change the "
                "wording: other word order, other words or forms of the same meaning that the draft or your knowledge of {lang} supports. "
                "Do not add or drop content. Answer with JSON only.")
REPHRASE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["text"], "properties": {"text": {"type": "string"}}}


def toks(text):
    return [unicodedata.normalize("NFC", t.lower()) for t in FA.tokenize(text)]


def rephrase(name, q, text, n, E, G, k=5, run=10):
    """the drafter's own clause reworded; shown: the source clause and the team's renderings of the k most similar clauses of
    OTHER verses, never the team's text of the clause's own verse"""
    src = " ".join(f"{t['text']} '{t.get('gloss') or ''}'" for t in q["tokens"]); ev = []
    for c in E.top(q["id"], k + 5):
        if set(c.get("refs", [])) & set(q["refs"]):
            continue
        ev.append(f"- {' '.join(G.get(t['key'], '') or t['text'] for t in c['tokens'])}  =>  "
                  f"{' '.join('-'.join(p for p, _ in ws) for _, _, ws, _ in prompt.ev_words(c))}")
        if len(ev) == k:
            break
    p = (f"Hebrew clause (word 'gloss'): {src}\n\nHow the {name} translation team renders similar clauses (source glosses => their "
         f"words, parts joined by '-'):\n" + "\n".join(ev) + f"\n\nThe {name} draft of this clause:\n{text}\n\nTry {n}: reword the "
         f"draft with the team's words and forms where they fit, so that no stretch of {max(3, run // 2)} or more words in a row stays as it "
         f"is in the draft; put only the reworded clause in `text`.")
    r = llm.cli_one(p, REPHRASE_SYS.format(lang=name), schema=REPHRASE_SCHEMA)
    if not r["ok"]:
        return None
    try:
        o = json.loads(r["text"])
        while isinstance(o, dict):                    # a nested answer ({"text": "{\"clause\": ...}"}) is unwrapped
            v = o.get("text", o.get("clause"))
            o = json.loads(v) if isinstance(v, str) and v.lstrip().startswith("{") else v
        return " ".join(str(o).replace("-", "").split()) if o else None
    except (ValueError, TypeError):
        return None


def run_of(a, label):
    b = copy.copy(a); b.label = label; return b


def generator(kind, man):
    """what made a draft, from its run's manifest"""
    b = (man.get("builds") or [{}])[-1]; s = (man.get("sends") or [{}])[-1]
    if kind == "main":
        return MADE_BY["main"].format(model=s.get("model", "unknown model"), notes=", the language's grammar notes" if b.get("notes") else "")
    if kind == "nllb":
        return MADE_BY["nllb"].format(model=b.get("model", "unknown model"), samples=b.get("samples", "?"))
    return MADE_BY.get(kind, kind + " ({model})").format(model=s.get("model") or b.get("model") or "unknown model")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", required=True); ap.add_argument("--book", required=True); ap.add_argument("--chapters", required=True)
    ap.add_argument("--main", default="main"); ap.add_argument("--alt", action="append", default=[]); ap.add_argument("--out")
    ap.add_argument("--flag-run", type=int, default=10); ap.add_argument("--no-rephrase", action="store_true")
    a = ap.parse_args(); a.book = a.book.upper(); cfg = paths.config(a.lang); chs = draft.chapters_arg(a.chapters)
    if draft.source_of(a.book) != "hbo":
        sys.exit("the bundle is for Tanakh chapters (the text repositories hold the Tanakh)")
    E = evidence.build(cfg, "hbo", a.book, chs)                              # refuses closed and held-out chapters
    byq = {qid: E.queries[qid] for qid in E.order}; kinds = ["main"] + a.alt
    T = {k: draft.clause_texts(run_of(a, a.main if k == "main" else k)) for k in kinds}
    man = {k: draft.load_manifest(run_of(a, a.main if k == "main" else k)) for k in kinds}
    missing = [q for q in byq if not T["main"].get(q)]
    if len(missing) == len(byq):
        sys.exit(f"the main draft '{a.main}' has no text for these chapters")
    refs = {r for q in byq.values() for r in q["refs"]}
    gate = V.Gate(V.team_verses(paths.corpus(cfg, "hbo"), refs), a.flag_run)
    out = a.out or paths.private("publish", a.lang, "bundle"); flags_dir = paths.private("publish", a.lang, "flags"); os.makedirs(flags_dir, exist_ok=True)
    today = datetime.date.today().isoformat()
    report = {"language": a.lang, "book": a.book, "chapters": chs, "rule": "same verse; run >= X or >= 80 % above X words; exact", "X": a.flag_run,
              "built": today, "clauses": len(byq), "main clauses without text": len(missing), "team verses checked against": len(gate.team),
              "flags": [], "actions": collections.Counter()}
    # 1. the gate on every clause of every draft; actions
    final = {k: dict(T[k]) for k in kinds}; notes = collections.defaultdict(list); G = None
    for k in a.alt:
        for qid, q in byq.items():
            f = gate.check(T[k].get(qid, ""), q["refs"])
            if f:
                report["flags"].append({"draft": k, "clause": qid, **f, "action": "left out"}); report["actions"][f"{k}: left out"] += 1
                final[k][qid] = ""; notes[(k, qid)].append("left out: verbatim rule")
    for qid, q in byq.items():
        f = gate.check(T["main"].get(qid, ""), q["refs"])
        if not f:
            continue
        rec = {"draft": "main", "clause": qid, **f}; text = None
        for i in (1, 2) if not a.no_rephrase and rights.allowed(cfg, "llm") else ():
            if G is None:
                G = tokens.glosses("grc"); G.update(tokens.glosses("hbo", sorted({c["book"] for c in E.pool if c["lang"] == "hbo"}) or [a.book]))
            t = rephrase(cfg["name"], q, T["main"][qid], i, E, G, run=a.flag_run)
            if t and not gate.check(t, q["refs"]):
                text, rec["action"] = t, f"rephrased (try {i})"; break
        if text is None:
            for k in a.alt:
                if final[k].get(qid):
                    text, rec["action"] = final[k][qid], f"taken from {k}"; break
        if text is None:
            text, rec["action"] = "", "withheld"
        final["main"][qid] = text
        notes[("main", qid)].append(("rephrased" if rec["action"].startswith("rephrased") else rec["action"]) + ": verbatim rule")
        report["flags"].append(rec); report["actions"][f"main: {rec['action'].split(' (')[0]}"] += 1
    # 2. the files, chapter by chapter
    written = []
    for ch in chs:
        keys = CF.layout_keys(a.book, ch)
        for k in kinds:
            base = out if k == "main" else os.path.join(out, ".tanakh", "alternatives", k)
            verses, units, nts, per_clause = {}, {}, [], {}
            for v in sorted(keys):
                ks, rows = keys[v]; pos = 0; parts = []; texts = []; seen = set()
                for key, r in zip(ks, rows):
                    qid = "H:" + r["clause_key"]
                    if qid in seen or qid not in byq:                 # a clause's text stands at its first segment
                        parts.append(f"{key}:="); continue
                    seen.add(qid); t = " ".join((final[k].get(qid) or "").split()); n = len(FA.tokenize(t))
                    parts.append(f"{key}:{CF.ranges(range(pos, pos + n)) if n else '='}"); per_clause[(v, qid)] = (pos, n)
                    nts += [(v, "N", pos, note) for note in notes.get((k, qid), [])]
                    if t:
                        texts.append(t)
                    pos += n
                verses[v] = " ".join(texts); units[v] = " ".join(parts)
            status = [(l, today if l == "Date" else generator(k, man[k]) if l == "Translation" else val) for l, val in STATUS]
            m = {"chapter": ch, "verses": verses, "headings": [], "notes": nts, "title": f"{a.book} {ch}", "status": status}
            stem = CF.write_chapter(m, a.book, base, units, "authored", extra=() if k == "main" else (("alternative", k), ("built", today)))
            written.append(stem)
    if a.alt:
        rp = os.path.join(out, ".tanakh", "alternatives", "README.md"); os.makedirs(os.path.dirname(rp), exist_ok=True)
        old = [l for l in open(rp, encoding="utf-8").read().splitlines() if l.startswith("- `")] if os.path.exists(rp) else []
        new = {k: f"- `{k}` ({a.book} {a.chapters}): {generator(k, man[k])}; built {today}" for k in a.alt}
        keep = [l for l in old if not any(l.startswith(f"- `{k}` ({a.book} {a.chapters})") for k in new)]
        open(rp, "w", encoding="utf-8").write("\n".join(["# Alternatives (never edited; replaced as a whole when rebuilt)", ""] + keep + list(new.values())) + "\n")
    # 3. the word alignment of every draft, by lexeme-aligner with the team's text (publish/align.py)
    linked = AL.align_bundle(a.lang, out)
    bad = {s: p for s, p in ((s, CF.check_files(s)) for s in written) if p}
    report["actions"] = dict(report["actions"]); report["file problems"] = {os.path.relpath(s, out): p for s, p in bad.items()}
    json.dump(report, open(os.path.join(flags_dir, f"{a.book}_{a.chapters}.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps({"out": out, "chapters": len(chs), "drafts": kinds, "files checked": len(written), "with problems": len(bad),
                      "main clauses without text": len(missing), "flags": len(report["flags"]), "actions": report["actions"],
                      "draft words linked to the Hebrew (lexeme-aligner)": {k: round(n / max(1, t), 3) for k, (t, n) in sorted(linked.items())}}, indent=1))


if __name__ == "__main__":
    main()
