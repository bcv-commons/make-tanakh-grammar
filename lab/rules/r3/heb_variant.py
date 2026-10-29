#!/usr/bin/env python3
"""rung 1b variants (env HEB_SFX): E5 and E6 on the OT dev chapters, or with HOLD=1 on 1,500 training verses held out
(seed 8). Prints one JSON line.   PYTHONPATH=<repo>/scripts ~/sil-study/.venv/bin/python heb_variant.py"""
import json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../engine"))
import engine as E, cells as CL, heb_run as HR, final_eval as FE  # noqa: E402
CL.contexts = HR.heb_contexts
H = HR.HebCorpus(); train = H.split("train"); dev = H.split("dev")
if os.environ.get("HOLD"):
    dev = random.Random(8).sample(train, 1500); train = [r for r in train if r not in set(dev)]
out = {"HEB_SFX": os.environ.get("HEB_SFX", ""), "LEX_ART": os.environ.get("LEX_ART", ""), "extra": os.environ.get("CTX_EXTRA", ""), "on": "B" if os.environ.get("HOLD") else "dev"}
for st in ("e5", "e6"):
    res, _ = E.measure(H, FE.build(H, train, st), dev)
    out[st] = {k: res[k] for k in FE.KEYS}
print(json.dumps(out, ensure_ascii=False), flush=True)
