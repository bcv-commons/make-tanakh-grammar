#!/usr/bin/env python3
"""Phase 5 of the bridge plan: the LLM with evidence rationed PER CLAUSE (the clause layout's clauses of each verse), one kind
of evidence per arm, never a chapter dump. Arms (the first is llm_arms.py's):

  alone    the Hebrew verses only, shown clause by clause
  conf     + per clause, the engine corpus's CONFIDENT renderings only (lemma seen >= 5 times, top rendering >= 80%): word = rendering
  ret      + per clause, the most similar NT clause through the bridges (clause_index.py; score >= 0.6): its Greek and the Danish
             verse it stands in (this translation's own NT)
  repair   + the DRAFT of an earlier run (alone) and the checker's flags per clause (checker.py flags): correct flagged clauses only

Prompts per (arm, chapter) in <out>/prompts/<arm>__<BOOK_ch>.md; answers in <out>/<arm>/<run>/<BOOK_ch>.json; scoring as llm_arms.py.

    . ./env.sh; OT_DB=data/dfb_jev+dan.db FUNC_FILE=data/dan_func.txt ~/sil-study/.venv/bin/python lab/bridge/llm_arms2.py prompts
        --split test --out bridge/llm2/test --retrieval bridge/retrieval_test.json --nt-text private/align/dfb_nt/text
        --draft-dir bridge/llm/test/alone/run1 --flags bridge/flags_test_alone1.json [--arms alone conf ret repair]
    ... llm_arms2.py score --out bridge/llm2/test --split test"""
import argparse, collections, glob, json, os, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score as S  # noqa: E402
import llm_arms as L1  # noqa: E402
import checker as CK  # noqa: E402
from build_nllb_retrieval import nt_text  # noqa: E402
E = S.E
ARMS = ("alone", "conf", "ret", "repair")
note = {
    "alone": "Each verse is shown whole and then CLAUSE BY CLAUSE (the clause division of the Hebrew). Translate the verse as one sentence or more, as Danish needs.\n",
    "conf": ("Each verse is shown whole and then CLAUSE BY CLAUSE. Under a clause, CONFIDENT lines give the rendering this translation "
             "uses for a Hebrew word nearly always (the share and the number of cases are given). Use that word unless the context "
             "forbids it; where no line is given, you decide freely.\n"),
    "ret": ("Each verse is shown whole and then CLAUSE BY CLAUSE. Under a clause, a SIMILAR line gives a New Testament clause of the "
            "same shape with the same verb (through a Hebrew-Greek bridge) and the Danish verse of this very translation in which it "
            "stands. Take the wording and construction of that Danish where it fits the Hebrew; ignore it where it does not.\n"),
    "repair": ("Each verse comes with a DRAFT (an earlier translation by a model like you) and, under some clauses, CHECK lines from a "
               "corpus check: a Hebrew word that this translation renders with a given Danish word nearly always, which the draft "
               "lacks. Return the DRAFT unchanged except in clauses with a CHECK line, where you correct the draft if the check is "
               "right in context (use the given word in the right form); if the draft is right as it stands, keep it.\n")}


def cons(s):
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch) and ch not in "־׀׃׆").replace("ֽ", "")


def clause_tokens(C, ref, clauses):
    """Assign the verse's corpus tokens to the layout's clauses in order, by their consonantal text."""
    toks = C.tok[ref]; out = [[] for _ in clauses]; ci = 0; rest = cons(clauses[0]["text"]).replace(" ", "") if clauses else ""
    for t in toks:
        w = cons(t["text"]).replace(" ", "")
        while ci < len(clauses) and w and w not in rest and rest.replace(w, "", 1) == rest:
            ci += 1; rest = cons(clauses[ci]["text"]).replace(" ", "") if ci < len(clauses) else ""
        if ci >= len(clauses):
            out[-1].append(t) if out else None; continue
        out[ci].append(t); rest = rest.replace(w, "", 1)
    return out


def context(dirs, book, ch):
    """The project's chapter materials (Step A's verse pack and clause packs: <code><ch:03d>*.md in one of the dirs), as one block."""
    for d in dirs:
        fs = sorted(glob.glob(os.path.join(d, f"{book.lower()}{ch:03d}*.md")))
        if fs:
            parts = []
            for f in fs:
                t = open(f, encoding="utf-8").read()
                if not f.endswith(".pkg.md"):          # the verse pack: keep decisions, grammar, parts, names, glossary; drop the store index and the per-verse section (the clause pack carries the lexical evidence)
                    keep, on = [], True
                    for line in t.split("\n"):
                        if line.startswith("## "):
                            on = not (line.startswith("## Store index") or line.startswith("## Verses"))
                        if on:
                            keep.append(line)
                    t = "\n".join(keep)
                parts.append(t)
            return "CONTEXT: the project's materials for this chapter (team decisions bind; 'had' lines are what the project and its NT use for a Hebrew word).\n\n" + "\n\n".join(parts) + "\n\n"
    return ""


def prompts(a):
    C, FUNC = S.corpus(); stem = S.STEMS[a.stem]
    refs = sorted((r for r, v in C.verses.items() if v["split"] == a.split), key=lambda r: (C.verses[r]["book"], C.verses[r]["ch"], C.verses[r]["v"]))
    by_ch = collections.defaultdict(list)
    for r in refs:
        by_ch[f"{C.verses[r]['book']}_{C.verses[r]['ch']}"].append(r)
    if a.chapters:
        by_ch = {k: v for k, v in by_ch.items() if k in a.chapters}
    R = json.load(open(os.path.join(E.PRIV, a.retrieval), encoding="utf-8")) if "ret" in a.arms else {}
    NTD = nt_text(a.nt_text) if "ret" in a.arms else {}
    N, T = CK.tables(C, FUNC, stem) if "conf" in a.arms else ({}, {})
    draft = {}
    if "repair" in a.arms:
        for f in glob.glob(os.path.join(E.PRIV, a.draft_dir, "*.json")):
            draft.update(json.load(open(f, encoding="utf-8")))
        flags = json.load(open(os.path.join(E.PRIV, a.flags), encoding="utf-8"))
    out = os.path.join(E.PRIV, a.out, "prompts"); os.makedirs(out, exist_ok=True); n_ev = collections.Counter()
    for arm in a.arms:
        for ch, rs in by_ch.items():
            lines = [L1.HEAD.replace("Danish", a.lang), note[arm].replace("Danish", a.lang), ""]
            if a.context:
                lines.append(context(a.context, ch.split("_")[0], int(ch.split("_")[1])))
            lines.append("VERSES:")
            for r in rs:
                lines.append(f"{r}\n  Hebrew: {L1.hebrew(C, r)}")
                clauses = R.get(r) or [{"text": c["text"], "top": []} for c in []]
                if not clauses:
                    clauses = [{"text": L1.hebrew(C, r), "top": []}]
                ct = clause_tokens(C, r, clauses)
                if arm == "repair":
                    lines.append(f"  DRAFT: {draft.get(r, '')}")
                for k, (cl, toks) in enumerate(zip(clauses, ct)):
                    lines.append(f"  clause {k + 1}: {cl['text']}")
                    if arm == "conf":
                        ev = []
                        for t in toks:
                            n = N.get(t["lemma"], 0)
                            if n >= a.n and T[t["lemma"]]:
                                top, c = T[t["lemma"]].most_common(1)[0]
                                if c / n >= a.t and t["class"] in S.CONTENT:
                                    ev.append(f"{t['text']} = {top} ({c} of {n})")
                        if ev:
                            lines.append("    CONFIDENT: " + " | ".join(ev[:3])); n_ev[arm] += 1
                    elif arm == "ret":
                        for t0 in [t for t in (cl.get("top") or []) if t["score"] >= a.min_score][:a.n_ret]:
                            dan = NTD.get(t0["ref"], "")
                            if dan:
                                lines.append(f"    SIMILAR (NT, {t0['ref']}): {t0['text']}  ->  {dan}"); n_ev[arm] += 1
                    elif arm == "repair":
                        fl = [f for f in flags.get(r, []) if any(f["word"] == t["text"] for t in toks)]
                        for f in fl[:2]:
                            lines.append(f"    CHECK: {f['word']} is rendered '{f['expected'][0]}' in {int(f['share'] * 100)}% of {f['n']} cases; the draft lacks it"); n_ev[arm] += 1
            open(os.path.join(out, f"{arm}__{ch}.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{len(a.arms)} arms x {len(by_ch)} chapters -> {out}; evidence lines {dict(n_ev)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["prompts", "score"])
    ap.add_argument("--split", default="test"); ap.add_argument("--out", required=True); ap.add_argument("--arms", nargs="*", default=list(ARMS))
    ap.add_argument("--retrieval", default="bridge/retrieval_test.json"); ap.add_argument("--nt-text", default="")
    ap.add_argument("--draft-dir", default=""); ap.add_argument("--flags", default=""); ap.add_argument("--stem", default="dan")
    ap.add_argument("--n", type=int, default=5); ap.add_argument("--t", type=float, default=0.8); ap.add_argument("--min-score", type=float, default=0.6)
    ap.add_argument("--lang", default="Danish"); ap.add_argument("--context", nargs="*", default=[], help="dirs of chapter materials (<code><ch:03d>*.md)")
    ap.add_argument("--chapters", nargs="*", default=[], help="only these BOOK_ch"); ap.add_argument("--n-ret", type=int, default=1, help="SIMILAR lines per clause")
    ap.add_argument("--segmenter", default="", help="bcv_segment bundle for the stems in scoring")
    a = ap.parse_args()
    if a.segmenter:
        sys.path.insert(0, a.segmenter); import bcv_segment
        seg = bcv_segment.load(a.segmenter); cache = {}

        def sstem(w):
            if w not in cache:
                cache[w] = next((p["text"] for p in seg.split(w) if p["slot"] == "stem"), w)
            return cache[w]
        S.STEMS["seg"] = sstem; a.stem = "seg"
    prompts(a) if a.cmd == "prompts" else L1.score_runs(a)
