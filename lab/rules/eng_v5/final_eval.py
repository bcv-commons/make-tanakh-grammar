#!/usr/bin/env python3
"""The one evaluation on the held-out test chapters (Mark 5, 10, 15; Genesis 22, 37, 44), run once at the end of the day
(2026-10-26). Every stage on the same verses; chrF differences with a paired bootstrap over verses (1,000 resamples).
    ~/sil-study/.venv/bin/python final_eval.py   -> results/final_test.json"""
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import engine as E, cells as CL, gen6, rules as RU  # noqa: E402
import sacrebleu  # noqa: E402

KEYS = ["coverage (lemma known)", "word choice (content, stem)", "form (content, exact)", "rendering exact (all tokens)",
        "function words P", "function words R", "order tau (mean per verse)", "chrF (summary)"]


def build(C, train, stage, rulefile=None):
    lex, lem = E.learn_lexicon(C, train)
    eng = E.Engine(lex, lem, E.learn_order(C, train) if stage != "e1" else None)
    if stage in ("e3", "e5", "e6", "e7", "e8pre", "e8lex"):
        eng.ctxlex = E.CtxLex(C, train)
    if stage in ("e5", "e6", "e7", "e8pre", "e8lex"):
        eng.factored = E.Factored(C, train, eng.ctxlex); eng.ctx_first = True
    if stage in ("e6", "e7", "e8pre", "e8lex"):
        eng.gen6 = gen6.Gen6(C, train, eng.ctxlex, eng.factored); eng.memory_first = stage == "e7"
        eng.memory_mode = stage[2:] if stage.startswith("e8") else None
    if rulefile:
        RU.Ruled(eng, RU.load_rules(rulefile))
    return eng


def boot(C, refs, ha, hb, n=1000):
    R = [" ".join(C.verses[r]["words"]) for r in refs]
    rnd = random.Random(11); d = []
    for _ in range(n):
        idx = [rnd.randrange(len(refs)) for _ in refs]
        a = sacrebleu.corpus_chrf([ha[i] for i in idx], [[R[i] for i in idx]]).score
        b = sacrebleu.corpus_chrf([hb[i] for i in idx], [[R[i] for i in idx]]).score
        d.append(b - a)
    d.sort()
    return round(sum(d) / n, 2), round(d[int(0.025 * n)], 2), round(d[int(0.975 * n)], 2)


def run(C, train, label, stages, out):
    test = C.split("test")
    hyps = {}
    for name, stage, rf in stages:
        eng = build(C, train, stage, rf)
        res, h = E.measure(C, eng, test)
        hyps[name] = h
        out[f"{label} {name}"] = {k: res[k] for k in KEYS}
        print(label, name, {k: res[k] for k in KEYS}, flush=True)
    return test, hyps


def main():
    out = {}
    r2 = os.path.join(E.PRIV, "rules/en_bsb_r2.jsonl")
    C = E.Corpus()
    for pool in ("nogospels", "nt"):
        train = C.split("train")
        if pool == "nogospels":
            train = [r for r in train if C.verses[r]["book"] not in {"MAT", "LUK", "JHN"}]
        stages = [("E1", "e1", None), ("E2", "e2", None), ("E5", "e5", None), ("E6", "e6", None), ("E7", "e7", None), ("E6+rules r2", "e6", r2)]
        test, h = run(C, train, f"NT {pool}", stages, out)
        for a, b in (("E1", "E2"), ("E2", "E5"), ("E2", "E6"), ("E6", "E6+rules r2"), ("E6", "E7")):
            out[f"NT {pool} chrF {b} - {a}"] = boot(C, test, h[a], h[b])
            print(pool, b, "-", a, out[f"NT {pool} chrF {b} - {a}"], flush=True)
    import heb_run as HR
    CL.contexts = HR.heb_contexts
    H = HR.HebCorpus()
    test, h = run(H, H.split("train"), "OT", [("E1", "e1", None), ("E2", "e2", None), ("E5", "e5", None), ("E6", "e6", None), ("E7", "e7", None)], out)
    for a, b in (("E1", "E2"), ("E2", "E5"), ("E2", "E6"), ("E6", "E7")):
        out[f"OT chrF {b} - {a}"] = boot(H, test, h[a], h[b])
        print("OT", b, "-", a, out[f"OT chrF {b} - {a}"], flush=True)
    json.dump(out, open(os.path.join(E.PRIV, "results/final_test.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
