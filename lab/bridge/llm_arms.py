#!/usr/bin/env python3
"""The LLM pilot's prompts, one file per (arm, chapter), and the scoring of the answers. Arms (the engine = the rules engine):

  alone     the Hebrew verses only                                   (the LLM by itself)
  postedit  + the engine's draft of each verse, to be corrected      (H1: engine first, LLM edits)
  glosses   + the engine's rendering of each Hebrew word, in order   (H2: the engine as the tool that resolves forms)
  icl       + retrieved training verses (Hebrew -> the edition), by lemma overlap   (H5: examples)
  icl_gl    + both the examples and the glosses

The answer is a JSON object {ref: Danish verse}. Scoring: score.py on the corpus (OT_DB, FUNC_FILE), per arm and run.

    . ./env.sh; OT_DB=data/dfb_base.db FUNC_FILE=data/dan_func.txt ~/sil-study/.venv/bin/python lab/bridge/llm_arms.py prompts
        --split dev --engine bridge/dev_e5_dan_ot.json --out bridge/llm/dev [--k 8] [--arms alone postedit ...]
    ... llm_arms.py score --out bridge/llm/dev [--split dev]      (answers in <out>/<arm>/<run>/<BOOK_ch>.json)"""
import argparse, collections, glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score as S  # noqa: E402
E, HR = S.E, S.HR
ARMS = ("alone", "postedit", "glosses", "icl", "icl_gl", "lexicon", "icl_lex")
HEAD = ("You translate the Hebrew Bible into Danish, verse by verse, in the register of a modern Danish Bible translation "
        "(plain, exact, no archaisms). Translate every verse below. Answer with ONE JSON object only, {\"<ref>\": \"<Danish>\", ...}, "
        "the refs exactly as given, no verse numbers inside the text, no notes.\n")
note = {"postedit": ("Each verse comes with a DRAFT from a rule-based engine that learned Danish word choices and word forms from "
                     "aligned text. Its words and forms are often right; its word order can be off and function words (articles, "
                     "prepositions, conjunctions) can be missing or wrong. Correct the draft against the Hebrew: keep every draft word "
                     "that renders the Hebrew correctly, change only what is wrong or missing.\n"),
        "glosses": ("Each verse comes with GLOSSES: for each Hebrew word in order, the Danish rendering a rule-based engine chose for it "
                    "in this context (word and form; '-' = no rendering). Use them as the lexical and morphological evidence; you decide "
                    "the sentence.\n"),
        "icl": "EXAMPLES: similar verses of the same translation (Hebrew, then its Danish). Follow their wording and style.\n"}
note["lexicon"] = ("Each verse comes with a LEXICON: for each Hebrew word (lemma) in order, how this translation has rendered that lemma "
                   "elsewhere (its commonest words, with counts; '-' = not seen). Prefer these renderings where they fit.\n")
note["icl_gl"] = note["icl"] + note["glosses"]; note["icl_lex"] = note["icl"] + note["lexicon"]


def lexicon(C, train, FUNC, top=3):
    """{lemma: [(rendering, count), ...]} from the training verses' alignment (content words, lower case)"""
    cnt = collections.defaultdict(collections.Counter)
    for r in train:
        for t in C.tok[r]:
            w = [x.lower() for x in (C.rendering(r, t) or []) if x.lower() not in FUNC]
            if w:
                cnt[t["lemma"]][" ".join(w)] += 1
    return {l: c.most_common(top) for l, c in cnt.items()}


def hebrew(C, ref):
    return " ".join(t["text"] + ("" if (t["after"] or "").strip() == "" else "") for t in C.tok[ref]).replace("־", "־ ")


def retrieve(C, ref, train, k):
    """training verses by lemma-set overlap (Jaccard) with ref, the longest overlap first"""
    q = {t["lemma"] for t in C.tok[ref]}
    sc = []
    for r in train:
        s = {t["lemma"] for t in C.tok[r]}
        if s:
            sc.append((len(q & s) / len(q | s), r))
    return [r for _, r in sorted(sc, reverse=True)[:k]]


def prompts(a):
    C, FUNC = S.corpus()
    eng = json.load(open(os.path.join(E.PRIV, a.engine), encoding="utf-8"))
    gl = json.load(open(os.path.join(E.PRIV, a.engine[:-5] + ".glosses.json"), encoding="utf-8"))
    refs = sorted((r for r, v in C.verses.items() if v["split"] == a.split), key=lambda r: (C.verses[r]["book"], C.verses[r]["ch"], C.verses[r]["v"]))
    train = sorted(r for r, v in C.verses.items() if v["split"] == "train")
    by_ch = collections.defaultdict(list)
    for r in refs:
        by_ch[f"{C.verses[r]['book']}_{C.verses[r]['ch']}"].append(r)
    out = os.path.join(E.PRIV, a.out, "prompts"); os.makedirs(out, exist_ok=True)
    lex = lexicon(C, train, FUNC) if any(x in ("lexicon", "icl_lex") for x in a.arms) else {}
    for arm in a.arms:
        for ch, rs in by_ch.items():
            lines = [HEAD, note.get(arm, ""), ""]
            if arm.startswith("icl"):
                seen = []
                for r in rs:
                    for x in retrieve(C, r, train, a.k):
                        if x not in seen:
                            seen.append(x)
                lines.append("EXAMPLES:")
                for x in seen[:a.k * len(rs) // 2]:
                    lines.append(f"  {hebrew(C, x)}\n  -> {' '.join(C.verses[x]['words'])}")
                lines.append("")
            lines.append("VERSES:")
            for r in rs:
                lines.append(f"{r}\n  Hebrew: {hebrew(C, r)}")
                if arm == "postedit":
                    lines.append(f"  DRAFT: {eng[r]}")
                if arm in ("glosses", "icl_gl"):
                    lines.append("  GLOSSES: " + " | ".join(f"{h} = {d or '-'}" for h, d, _ in gl[r]))
                if arm in ("lexicon", "icl_lex"):
                    lines.append("  LEXICON: " + " | ".join(f"{t['text']} = " + (", ".join(f"{w} ({n})" for w, n in lex[t['lemma']]) if t["lemma"] in lex else "-")
                                                             for t in C.tok[r] if t["class"] in S.CONTENT))
            open(os.path.join(out, f"{arm}__{ch}.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{len(a.arms)} arms x {len(by_ch)} chapters -> {out}")


def score_runs(a):
    C, FUNC = S.corpus()
    refs = sorted(r for r, v in C.verses.items() if v["split"] == a.split)
    res = {}
    for d in sorted(glob.glob(os.path.join(E.PRIV, a.out, "*", "*"))):
        arm, run = d.split(os.sep)[-2:]
        if arm == "prompts":
            continue
        hyps = {}
        for f in glob.glob(os.path.join(d, "*.json")):
            hyps.update(json.load(open(f, encoding="utf-8")))
        hyps = {r: t for r, t in hyps.items() if r in C.verses}
        if hyps:
            res[f"{arm}/{run}"] = S.score(C, hyps, FUNC, S.STEMS[a.stem], [r for r in refs if r in hyps])
            res[f"{arm}/{run}"]["missing"] = len([r for r in refs if r not in hyps])
    json.dump(res, open(os.path.join(E.PRIV, a.out, "scores.json"), "w"), indent=1)
    keys = ["verses", "word choice (content, stem)", "form (content, exact)", "function words P", "function words R", "order tau (mean per verse)", "chrF (summary)", "missing"]
    print("| arm/run | " + " | ".join(k.split(" (")[0] for k in keys) + " |\n|" + "---|" * (len(keys) + 1))
    for k, v in res.items():
        print(f"| {k} | " + " | ".join(str(v[x]) for x in keys) + " |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["prompts", "score"])
    ap.add_argument("--split", default="dev"); ap.add_argument("--engine"); ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=8); ap.add_argument("--arms", nargs="*", default=list(ARMS)); ap.add_argument("--stem", default="dan")
    a = ap.parse_args()
    prompts(a) if a.cmd == "prompts" else score_runs(a)
