#!/usr/bin/env python3
"""Rung 1c, OT: Hebrew -> KJV (OT_DB=data/kjv_ot.db) with eng_v3's switches (HEB_SFX, LEX_ART, noun.after_cstr), the KJV's
function words added. Dev (Genesis 3, 24) and held-out B (seed 8); one JSON line per stage.
    OT_DB=data/kjv_ot.db FUNC_KJV=1 PYTHONPATH=<repo>/scripts ~/sil-study/.venv/bin/python kjv/run_ot.py"""
import json, os, random, sys
for k, v in (("HEB_SFX", "1"), ("LEX_ART", "1"), ("CTX_EXTRA", "noun.after_cstr")):
    os.environ.setdefault(k, v)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../engine"))
import engine as E, cells as CL, heb_run as HR, final_eval as FE  # noqa: E402
CL.contexts = HR.heb_contexts
H = HR.HebCorpus(); tr = H.split("train"); B = random.Random(8).sample(tr, 1500)
for on, train, refs in (("dev", tr, H.split("dev")), ("B", [r for r in tr if r not in set(B)], B)):
    for st in ("e1", "e2", "e5", "e6", "e7"):
        res, _ = E.measure(H, FE.build(H, train, st), refs)
        print(json.dumps({"target": {"data/kjv_ot.db": "KJV", "data/vamvas_ot.db": "VAMVAS"}.get(os.environ.get("OT_DB", ""), "BSB"), "on": on, "stage": st, **{k: res[k] for k in FE.KEYS}}), flush=True)
