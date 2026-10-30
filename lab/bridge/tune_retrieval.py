#!/usr/bin/env python3
"""Tune the clause retriever's four weights (verb, shape, tense, lex; clause_index.retrieve_one) on DEV, without the LLM: the
retrieved NT clause is useful to a drafter when the target verse it stands in shares wording with the reference verse of the OT
clause. Objective per clause: the share of the retrieved NT verse's content stems that occur in the reference OT verse
(precision of its wording), averaged over clauses with a candidate; also the share of clauses whose top candidate contributes
at least one reference stem (hit). Grid over the weight simplex on a k-best retrieval file (clause_index.py retrieve --k 20).
Then `apply` reranks a k-best file with chosen weights into the prompt builder's format.

    . ./env.sh; OT_DB=data/dfb_jev+dan.db FUNC_FILE=data/dan_func.txt ~/sil-study/.venv/bin/python lab/bridge/tune_retrieval.py tune
        --kbest bridge/retrieval_dev_k20.json --nt-text private/align/dfb_nt/text [--stem dan] [--step 0.05] [--top 2]
    ... tune_retrieval.py apply --kbest bridge/retrieval_test_k20.json --weights 0.4 0.25 0.2 0.15 --out bridge/retrieval_test_tuned.json"""
import argparse, itertools, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score as S  # noqa: E402
from build_nllb_retrieval import nt_text  # noqa: E402
E = S.E
PARTS = ("verb", "shape", "tense", "lex")
DEFAULT = (0.4, 0.25, 0.2, 0.15)


def rescore(cands, w):
    return sorted(cands, key=lambda c: -sum(wi * c[p] for wi, p in zip(w, PARTS)))


def tune(a):
    C, FUNC = S.corpus(); stem = S.STEMS[a.stem]; NTD = nt_text(a.nt_text)
    R = json.load(open(os.path.join(E.PRIV, a.kbest), encoding="utf-8"))
    stems_of = {}

    def stems(text):
        if text not in stems_of:
            stems_of[text] = {stem(w.lower()) for w in S.tokenize(text)} - set(FUNC)
        return stems_of[text]
    items = []                                           # (ref stems, [cand parts + its verse stems])
    for ref, clauses in R.items():
        if ref not in C.verses:
            continue
        rs = stems(" ".join(C.verses[ref]["words"]))
        for cl in clauses:
            cands = [dict(c, vs=stems(NTD.get(c["ref"], ""))) for c in cl.get("top") or [] if NTD.get(c["ref"])]
            if cands:
                items.append((rs, cands))
    print(f"{len(items)} dev clauses with candidates")

    def evaluate(w, top):
        p = h = 0.0
        for rs, cands in items:
            best = rescore(cands, w)[:top]; vs = set().union(*(c["vs"] for c in best))
            if vs:
                p += len(vs & rs) / len(vs); h += bool(vs & rs)
        return p / len(items), h / len(items)
    steps = [round(i * a.step, 4) for i in range(int(round(1 / a.step)) + 1)]
    grid = [w for w in itertools.product(steps, repeat=4) if abs(sum(w) - 1) < 1e-6]
    res = [(evaluate(w, 1), w) for w in grid]
    res.sort(reverse=True)
    d1 = evaluate(DEFAULT, 1); print(f"default {DEFAULT}: precision {d1[0]:.4f} hit {d1[1]:.4f}")
    print("| weights (verb, shape, tense, lex) | precision | hit |\n|---|---|---|")
    for (p, h), w in res[:8]:
        print(f"| {w} | {p:.4f} | {h:.4f} |")
    for name in ("verb", "shape", "tense", "lex"):
        w = tuple(1.0 if p == name else 0.0 for p in PARTS); p, h = evaluate(w, 1); print(f"{name} alone: precision {p:.4f} hit {h:.4f}")
    best = res[0][1]
    for top in (1, 2, 3):
        p, h = evaluate(best, top); pd, hd = evaluate(DEFAULT, top)
        print(f"top-{top}: best {p:.4f}/{h:.4f}  default {pd:.4f}/{hd:.4f}")
    print("best", best)


def apply(a):
    R = json.load(open(os.path.join(E.PRIV, a.kbest), encoding="utf-8")); w = tuple(a.weights); n = 0
    for ref, clauses in R.items():
        for cl in clauses:
            if cl.get("top"):
                cl["top"] = rescore(cl["top"], w)
                for c in cl["top"]:
                    c["score"] = round(sum(wi * c[p] for wi, p in zip(w, PARTS)), 3)
                n += 1
    json.dump(R, open(os.path.join(E.PRIV, a.out), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{n} clauses reranked with {w} -> {a.out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["tune", "apply"]); ap.add_argument("--kbest", required=True)
    ap.add_argument("--nt-text", default=""); ap.add_argument("--stem", default="dan"); ap.add_argument("--step", type=float, default=0.05)
    ap.add_argument("--weights", nargs=4, type=float); ap.add_argument("--out", default="")
    a = ap.parse_args(); tune(a) if a.cmd == "tune" else apply(a)
