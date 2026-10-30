#!/usr/bin/env python3
"""Review flags from ALIGNING a draft (the user's direction, 2026-10-30): a draft chapter aligned by align-text (NT bridge, Jev)
gives, per Hebrew content word, whether the draft has a word linked to it. An UNLINKED source content word is a flag ("the draft
may lack this"); an unlinked draft word is a note ("this may be an addition"). Scored like the checker, against the human text's
alignment (OT_DB test split, the reference renderings): a flag is right (strict) when the draft lacks every reference stem of
that word. Also the engine checker's flags on the same drafts for comparison, and the union.

    . ./env.sh; OT_DB=data/kvg_ot_jev.db FUNC_FILE=data/kvg_ot_jev_func.txt ~/sil-study/.venv/bin/python lab/bridge/draft_review.py
        --layer private/align/kvg_drafts/out/full-alignments-llm/k/kvg/kvg_draft+llm+jev-v4 --text private/align/kvg_drafts/text
        --segmenter private/hf/language-analysis/kvg/2cd8a4bc/bundle [--books RUT JON]"""
import argparse, collections, glob, json, os, sys
sys.path.insert(0, os.path.join(os.environ["MAKE_TANAKH_WORK"], "scripts"))
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)   # the lab's score.py first
import score as S  # noqa: E402
from link_agree import links  # noqa: E402
import checker as CK  # noqa: E402


def main(a):
    C, FUNC = S.corpus()
    sys.path.insert(0, a.segmenter); import bcv_segment
    seg = bcv_segment.load(a.segmenter); cache = {}

    def stem(w):
        if w not in cache:
            cache[w] = next((p["text"] for p in seg.split(w) if p["slot"] == "stem"), w)
        return cache[w]
    draft = {}
    for f in glob.glob(os.path.join(a.text, "*.txt")):
        book = os.path.basename(f)[:3]
        for line in open(f, encoding="utf-8"):
            cv, _, t = line.strip().partition(" ")
            if t:
                draft[f"{book} {cv}"] = t
    linked = collections.defaultdict(set); tlinked = collections.defaultdict(set); linked2 = collections.defaultdict(set)
    for lf in sorted(glob.glob(os.path.join(a.layer2, "*_*.json"))) if a.layer2 else []:
        if os.path.basename(lf).count(".") == 1 and (not a.books or os.path.basename(lf)[:3] in a.books):
            for kind, r, key, p in links(lf, os.path.basename(lf)[:3]):
                linked2[r].add(key[:11])
    for lf in sorted(glob.glob(os.path.join(a.layer, "*_*.json"))):
        if os.path.basename(lf).count(".") != 1:
            continue
        book = os.path.basename(lf).split("_")[0]
        if a.books and book not in a.books:
            continue
        for kind, r, key, p in links(lf, book):
            linked[r].add(key[:11]); tlinked[r].add(p)      # spine key = corpus key + part digit
    N, T = CK.tables(C, FUNC, stem)
    refs = [r for r, v in C.verses.items() if v["split"] == "test" and r in draft and (not a.books or v["book"] in a.books)]
    k = collections.Counter(); per_class = collections.defaultdict(collections.Counter)
    for r in refs:
        hs = {stem(w.lower()) for w in S.tokenize(draft[r])}
        dtoks = S.tokenize(draft[r]); k["draft words"] += len(dtoks); k["draft words unlinked"] += sum(1 for i in range(len(dtoks)) if i not in tlinked[r])
        for t in C.tok[r]:
            if t["class"] not in S.CONTENT:
                continue
            rw = [w for w in (stem(x.lower()) for x in (C.rendering(r, t) or [])) if w not in FUNC]
            if not rw:
                continue
            real = not any(w in hs for w in rw)
            k["content tokens"] += 1; k["real misses"] += real
            unl = t["key"] not in linked[r]
            unl2 = unl and t["key"] not in linked2[r]
            unl_any = unl or t["key"] not in linked2[r]
            n = N.get(t["lemma"], 0); chk = False
            if n >= a.n and T[t["lemma"]]:
                top, c = T[t["lemma"]].most_common(1)[0]
                chk = c / n >= a.t and not any(w in hs for w, x in T[t["lemma"]].most_common() if x / n >= a.t)
            for name, flag in (("unlinked", unl), ("unlinked in both runs", unl2), ("unlinked in either run", unl_any), ("checker", chk), ("either", unl or chk), ("both", unl and chk)):
                if flag:
                    k[f"{name} flags"] += 1; k[f"{name} right"] += real; per_class[name][t["class"]] += 1
    print(f"{len(refs)} draft verses; {k['content tokens']} Hebrew content tokens with a reference, {k['real misses']} real misses "
          f"(reference stem absent from the draft); draft words {k['draft words']}, unlinked {k['draft words unlinked']}")
    print("| flags from | flags | precision (real miss) | recall of real misses |\n|---|---|---|---|")
    for name in ("unlinked", "unlinked in both runs", "unlinked in either run", "checker", "either", "both"):
        f = k[f"{name} flags"]
        print(f"| {name} | {f} | {k[f'{name} right'] / max(1, f):.2f} | {k[f'{name} right'] / max(1, k['real misses']):.2f} |")
    print("unlinked flags by class:", dict(per_class["unlinked"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True); ap.add_argument("--text", required=True); ap.add_argument("--segmenter", required=True)
    ap.add_argument("--books", nargs="*"); ap.add_argument("--layer2", default="", help="a second alignment run of the same drafts"); ap.add_argument("--n", type=int, default=5); ap.add_argument("--t", type=float, default=0.8)
    main(ap.parse_args())
