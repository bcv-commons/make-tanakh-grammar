#!/usr/bin/env python3
"""Rung 1c: the engine on Greek NT -> KJV (data/kjv_nt.db), the same code and switches as rung 1 (eng_v3's: MID_KEYS=1,
CTX_EXTRA=pron.gov, LEX_ART=1), the KJV's function words added (FUNC_KJV=1). Dev (Mark 3, 9, 12) and held-out B, pools
nogospels and nt; one JSON line per stage. CORPUS_DB unset = the BSB, for the same table.
    CORPUS_DB=data/kjv_nt.db FUNC_KJV=1 ~/sil-study/.venv/bin/python kjv/run.py"""
import json, os, random, sys
for k, v in (("MID_KEYS", "1"), ("CTX_EXTRA", "pron.gov"), ("LEX_ART", "1")):
    os.environ.setdefault(k, v)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../engine"))
import engine as E, final_eval as FE  # noqa: E402
C = E.Corpus(); tgt = {"data/kjv_nt.db": "KJV", "data/hebnt.db": "HEB-SCG"}.get(os.environ.get("CORPUS_DB", ""), "BSB")
for pool in ("nogospels", "nt"):
    tr = C.split("train")
    if pool == "nogospels":
        tr = [r for r in tr if C.verses[r]["book"] not in {"MAT", "LUK", "JHN"}]
    sA = set(random.Random(7).sample(tr, 1500)); B = random.Random(8).sample([r for r in tr if r not in sA], 1500)
    for on, train, refs in (("dev", tr, C.split("dev")), ("B", [r for r in tr if r not in set(B)], B)):
        for st in ("e1", "e2", "e5", "e6", "e7"):
            res, _ = E.measure(C, FE.build(C, train, st), refs)
            print(json.dumps({"target": tgt, "pool": pool, "on": on, "stage": st, "train": len(train), **{k: res[k] for k in FE.KEYS}}, ensure_ascii=False), flush=True)
