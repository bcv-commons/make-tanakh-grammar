#!/usr/bin/env python3
"""The confidence-aware checker (plan phase 3): the engine corpus's own tables, not its drafts. From the training split of OT_DB,
each Hebrew lemma's rendering distribution (stemmed content words of the reference linked to it): n occurrences, the top
rendering and its share. A draft's content word is FLAGGED when its lemma is confident (n >= N, top share >= T) and no rendering
with share >= T stands in the draft. Against the reference: a flag is RIGHT (strict) when the reference has the expected stem;
a REAL MISS when the reference's own rendering of that word is absent from the draft (loose precision); recall = flagged real
misses / real misses among confident words. The grid over (N, T) is the precision-recall curve.

  curve   . ./env.sh; OT_DB=data/dfb_jev+dan.db FUNC_FILE=data/dan_func.txt ~/sil-study/.venv/bin/python lab/bridge/checker.py curve
              --draft bridge/nllb_dfb.json --split dev [--draft-dir bridge/llm/dev/alone/run1]
  rerank  ... checker.py rerank --nbest bridge/nbest_dfb+300.json --split test --n 10 --t 0.7 --out bridge/rerank_test.json
              (picks per verse the candidate with the fewest flags, ties by rank; scores plain vs reranked, paired bootstrap)
  flags   ... checker.py flags --draft X --split S --n 10 --t 0.7 --out bridge/flags_X.json   (the flags themselves, for an LLM repair arm)"""
import argparse, collections, glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score as S  # noqa: E402
from score import tokenize  # noqa: E402
E = S.E


def tables(C, FUNC, stem):
    """lemma -> (n, Counter of rendering stems) from the training split."""
    T = collections.defaultdict(collections.Counter); N = collections.Counter()
    for r in C.split("train"):
        for t in C.tok[r]:
            ws = [stem(w.lower()) for w in (C.rendering(r, t) or [])]
            ws = [w for w in ws if w and w not in FUNC]
            if ws:
                N[t["lemma"]] += 1
                for w in set(ws):
                    T[t["lemma"]][w] += 1
    return N, T


def load_draft(a):
    hyps = {}
    if a.draft:
        hyps.update(json.load(open(os.path.join(E.PRIV, a.draft), encoding="utf-8")))
    if a.draft_dir:
        for f in glob.glob(os.path.join(E.PRIV, a.draft_dir, "*.json")):
            hyps.update(json.load(open(f, encoding="utf-8")))
    return hyps


def flags_for(C, FUNC, stem, N, T, hyps, refs, n_min, t_min):
    """Per verse: list of (token text, lemma, expected stems, right, real_miss); plus the count of real misses among confident words."""
    out = {}; tot = collections.Counter()
    for r in refs:
        hs = {stem(w.lower()) for w in tokenize(hyps[r])}; rs = {stem(w.lower()) for w in C.verses[r]["words"]}
        fl = []
        for t in C.tok[r]:
            n = N.get(t["lemma"], 0)
            if n < n_min:
                continue
            top, c = T[t["lemma"]].most_common(1)[0]
            if c / n < t_min:
                continue
            expected = [w for w, k in T[t["lemma"]].most_common() if k / n >= t_min]
            ref_words = [stem(w.lower()) for w in (C.rendering(r, t) or [])]; ref_words = [w for w in ref_words if w not in FUNC]
            real_miss = bool(ref_words) and not any(w in hs for w in ref_words)
            tot["confident words"] += 1; tot["real misses"] += real_miss
            if not any(w in hs for w in expected):
                right = any(w in rs for w in expected)
                fl.append({"word": t["text"], "lemma": t["lemma"], "expected": expected, "n": n, "share": round(c / n, 2), "right": right, "real_miss": real_miss})
                tot["flags"] += 1; tot["right"] += right; tot["flagged real misses"] += real_miss
        out[r] = fl
    return out, tot


def curve(a):
    C, FUNC = S.corpus(); stem = S.STEMS[a.stem]; N, T = tables(C, FUNC, stem); hyps = load_draft(a)
    refs = sorted(r for r, v in C.verses.items() if v["split"] == a.split and r in hyps)
    print(f"draft verses {len(refs)}; lemmas with tables {len(N)}")
    print("| n >= | top share >= | confident words | flags | precision strict | precision loose | recall |")
    print("|---|---|---|---|---|---|---|")
    for n_min in (3, 5, 10, 20):
        for t_min in (0.5, 0.6, 0.7, 0.8, 0.9):
            _, tot = flags_for(C, FUNC, stem, N, T, hyps, refs, n_min, t_min)
            f = max(1, tot["flags"])
            print(f"| {n_min} | {t_min} | {tot['confident words']} | {tot['flags']} | {tot['right'] / f:.2f} | {tot['flagged real misses'] / f:.2f} | "
                  f"{tot['flagged real misses'] / max(1, tot['real misses']):.2f} |")


def flags(a):
    C, FUNC = S.corpus(); stem = S.STEMS[a.stem]; N, T = tables(C, FUNC, stem); hyps = load_draft(a)
    refs = sorted(r for r, v in C.verses.items() if v["split"] == a.split and r in hyps)
    out, tot = flags_for(C, FUNC, stem, N, T, hyps, refs, a.n, a.t)
    print(dict(tot)); p = os.path.join(E.PRIV, a.out); json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0); print("written", p)


def rerank(a):
    C, FUNC = S.corpus(); stem = S.STEMS[a.stem]; N, T = tables(C, FUNC, stem)
    nb = json.load(open(os.path.join(E.PRIV, a.nbest), encoding="utf-8"))
    refs = sorted(r for r, v in C.verses.items() if v["split"] == a.split and r in nb)
    plain = {r: nb[r][0] for r in refs}; picked = {}; changed = 0
    for r in refs:
        best = None
        for rank, cand in enumerate(nb[r]):
            fl, _ = flags_for(C, FUNC, stem, N, T, {r: cand}, [r], a.n, a.t)
            k = (len(fl[r]), rank)
            if best is None or k < best[0]:
                best = (k, cand)
        picked[r] = best[1]; changed += picked[r] != plain[r]
    print(f"verses {len(refs)}, changed by reranking {changed}")
    for name, h in (("plain", plain), ("reranked", picked)):
        print(name, json.dumps(S.score(C, h, FUNC, stem, refs), ensure_ascii=False))
    for key in ("chrF (summary)", "word choice (content, stem)", "form (content, exact)", "function words R", "order tau (mean per verse)"):
        print("reranked - plain", key, S.boot(C, plain, picked, FUNC, stem, refs, n=200, key=key))
    p = os.path.join(E.PRIV, a.out); json.dump(picked, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0); print("written", p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("curve", "flags", "rerank"):
        s = sub.add_parser(name); s.add_argument("--split", default="dev"); s.add_argument("--stem", default="dan")
        s.add_argument("--draft", default=""); s.add_argument("--draft-dir", default=""); s.add_argument("--nbest", default="")
        s.add_argument("--n", type=int, default=10); s.add_argument("--t", type=float, default=0.7); s.add_argument("--out", default="bridge/checker_out.json")
    a = ap.parse_args(); {"curve": curve, "flags": flags, "rerank": rerank}[a.cmd](a)
