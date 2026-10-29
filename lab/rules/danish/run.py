#!/usr/bin/env python3
"""Rung 4: eng_v9 on Hebrew -> Danish (data/dan_ot.db), and on the SAME verses with the BSB (data/ot.db) and Vamvas
(data/vamvas_ot.db) as targets, so the three are compared on equal data. Training = the Danish corpus's train verses that
all three corpora have, less a held-out sample B (seed 8, N_B verses); dev = Genesis 24 (the lab's dev chapter) where present.
One JSON line per target and stage.
    T=dan|bsb|vamvas PYTHONPATH=<repo>/scripts ~/sil-study/.venv/bin/python danish/run.py"""
import json, os, random, sqlite3, sys
LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
T = os.environ.get("T", "dan")
DB = {"dan": "data/dan_ot.db", "bsb": "data/ot.db", "vamvas": "data/vamvas_ot.db"}[T]
os.environ["OT_DB"] = DB
if T in ("dan", "vamvas"):
    os.environ["FUNC_FILE"] = {"dan": "data/dan_func.txt", "vamvas": "data/vamvas_func.txt"}[T]
sys.path.insert(0, os.path.join(LAB, os.environ.get("ENGINE", "eng_v9")))
import engine as E, cells as CL, heb_run as HR, final_eval as FE  # noqa: E402
CL.contexts = HR.heb_contexts
common = None
for d in DB.values() if False else ("data/dan_ot.db", "data/ot.db", "data/vamvas_ot.db"):
    s = {r for (r,) in sqlite3.connect(os.path.join(PRIV, d)).execute("select ref from verse")}
    common = s if common is None else common & s
H = HR.HebCorpus()
tr = sorted(r for r in H.split("train") if r in common)
if os.environ.get("FULL"):            # the whole training pool of the target (B stays the same verses)
    B0 = random.Random(8).sample(tr, int(os.environ.get("N_B", "800")))
    tr = sorted(set(H.split("train")) | set(B0))
dev = sorted(r for r in H.split("dev") if r in common)
B = B0 if os.environ.get("FULL") else random.Random(8).sample(tr, int(os.environ.get("N_B", "800")))
stages = os.environ.get("STAGES", "e1,e2,e5,e6,e7").split(",")
for on, train, refs in (("B", [r for r in tr if r not in set(B)], B), ("dev", tr, dev)):
    if not refs:
        continue
    for st in stages:
        res, hyp = E.measure(H, FE.build(H, train, st), refs)
        if os.environ.get("DUMP") and on == "B":          # hypotheses for a paired bootstrap (danish/boot.py)
            json.dump({"refs": refs, "hyps": hyp, "words": [" ".join(H.verses[r]["words"]) for r in refs]},
                      open(os.path.join(PRIV, os.environ["DUMP"]) + f".{st}.json", "w"), ensure_ascii=False)
        print(json.dumps({"target": T, "on": on, "n_train": len(train), "n": len(refs), "stage": st,
                          **{k: res[k] for k in FE.KEYS}}, ensure_ascii=False), flush=True)
