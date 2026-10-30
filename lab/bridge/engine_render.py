#!/usr/bin/env python3
"""The rules engine's renderings of verses OUTSIDE its training corpus: built on one corpus (OT_DB, its train split, a stage),
rendering the verses of another (--on DB), whose Hebrew side alone is read; the renderings go to a {ref: text} JSON for
score.py, and the engine's own measure is printed beside the common scorer's (a cross-check on the same verses).

    . ./env.sh; OT_DB=data/dan_ot.db FUNC_FILE=data/dan_func.txt ~/sil-study/.venv/bin/python lab/bridge/engine_render.py
        --on data/dfb4_test.db --stage e5 --out bridge/eng_drafts_e5.json [--split test] [--train-split train]
    ENGINE=eng_v10 (default); engine options as environment (eng_v10/engine.py)"""
import argparse, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.join(os.path.dirname(HERE), "rules")
sys.path.insert(0, os.path.join(LAB, os.environ.get("ENGINE", "eng_v10"))); sys.path.insert(0, HERE)
import engine as E, cells as CL, heb_run as HR, final_eval as FE  # noqa: E402
import score as S  # noqa: E402
CL.contexts = HR.heb_contexts


def retarget(eng, C):
    """point the engine's context-bearing parts at corpus C (source side only is read when rendering)"""
    for name in ("ctxlex", "factored", "gen6"):
        o = getattr(eng, name, None)
        if o is not None and hasattr(o, "C"):
            o.C = C
            if hasattr(o, "cx"):
                o.cx = {}


def main(a):
    t0 = time.time()
    H = HR.HebCorpus(); train = sorted(H.split(a.train_split))
    if a.train_frac < 1:                                   # a learning curve: a fixed random share of the training verses
        import random; train = sorted(random.Random(8).sample(train, int(len(train) * a.train_frac)))
    eng = FE.build(H, train, a.stage)
    print(f"engine {os.environ.get('ENGINE', 'eng_v10')} {a.stage} on {len(train)} verses: {time.time() - t0:.0f}s", file=sys.stderr)
    T, FUNC = S.corpus(a.on, os.environ.get("FUNC_FILE"))
    refs = sorted(r for r, v in T.verses.items() if not a.split or v["split"] == a.split)
    retarget(eng, T)
    own = {} if a.no_measure else E.measure(T, eng, refs)[0]
    retarget(eng, T)
    hyps, gl = {}, {}
    for r in refs:
        o, at = eng.verse(T, r)
        hyps[r] = " ".join(o)
        toks = {t["key"]: t for t in T.tok[r]}
        gl[r] = [[toks[k]["text"], " ".join(o[p:p + n]), how] for k, (p, n, how) in sorted(at.items()) if k in toks]
    out = os.path.join(E.PRIV, a.out); os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(hyps, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(gl, open(out[:-5] + ".glosses.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)   # per Hebrew word: its rendering
    if a.no_measure:                                       # a corpus without a target side: renderings only
        print(len(hyps), "verses rendered ->", out); return
    print(json.dumps({"engine measure": {k: v for k, v in own.items() if k != "how"}}, ensure_ascii=False))
    print(json.dumps({"common scorer": S.score(T, hyps, FUNC, S.STEMS[a.stem], refs)}, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--on", required=True); ap.add_argument("--stage", default="e5"); ap.add_argument("--out", required=True)
    ap.add_argument("--split", default="test"); ap.add_argument("--train-split", default="train"); ap.add_argument("--stem", default="dan")
    ap.add_argument("--train-frac", type=float, default=1.0)
    ap.add_argument("--no-measure", action="store_true")
    main(ap.parse_args())
