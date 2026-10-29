#!/usr/bin/env python3
"""one context variant (env CTX_EXTRA) on dev: E5 and E6, trained on the nogospels pool. Prints one JSON line.
    CTX_EXTRA=pron.gov ~/sil-study/.venv/bin/python variant.py"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../engine"))
import engine as E, rules as RU, final_eval as FE  # noqa: E402
import metamorphic2 as M2  # noqa: E402
C = E.Corpus(); train, dev = M2.hold(C)   # HOLD=1: sample B held out of the pool
out = {"extra": os.environ.get("CTX_EXTRA", ""), "on": "B" if os.environ.get("HOLD") else "dev"}
for st in os.environ.get("STAGES", "e5,e6").split(","):
    res, _ = E.measure(C, FE.build(C, train, st), dev)
    out[st] = {k: res[k] for k in FE.KEYS}
print(json.dumps(out, ensure_ascii=False), flush=True)
