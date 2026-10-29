import json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../eng_v8"))
import engine as E, cells as CL, final_eval as FE, metamorphic2 as M2, rules as RU  # noqa
lang, on = sys.argv[1], sys.argv[2]
if lang == "ot":
    import heb_run as HR
    CL.contexts = HR.heb_contexts; C = HR.HebCorpus(); tr = C.split("train"); refs = C.split("dev")
    if on == "B":
        refs = random.Random(8).sample(tr, 1500); tr = [r for r in tr if r not in set(refs)]
else:
    C = E.Corpus()
    if on == "B":
        os.environ["HOLD"] = "1"
    tr, refs = M2.hold(C)
for st in ("e1", "e2", "e5", "e6", "e7"):
    res, _ = E.measure(C, FE.build(C, tr, st), refs)
    print(json.dumps({"engine": "v8", "corpus": os.environ.get("CORPUS_DB"), "lang": lang, "on": on, "stage": st, **{k: res[k] for k in FE.KEYS}}, ensure_ascii=False), flush=True)
