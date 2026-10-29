"""eng_v5's renderings of the dev verses (MRK 3, 9, 12: held out for the engine and for the NLLB instrument alike), per stage
-> $MAKE_TANAKH_PRIVATE/rules/nllb/engine_dev.json {stage: {ref: text}} and the BSB reference"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../eng_v5"))
import engine as E, final_eval as FE, metamorphic2 as M2  # noqa
C = E.Corpus(); tr, refs = M2.hold(C)
out = {"ref": {r: " ".join(C.verses[r]["words"]) for r in refs}}
for st in ("e2", "e5", "e6", "e7"):
    eng = FE.build(C, tr, st)
    out[st] = {r: " ".join(eng.verse(C, r)[0]) for r in refs}
    print(st, flush=True)
json.dump(out, open(os.path.join(E.PRIV, "nllb", "engine_dev.json"), "w"), ensure_ascii=False, indent=0)
