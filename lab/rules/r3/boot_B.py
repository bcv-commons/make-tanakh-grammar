#!/usr/bin/env python3
"""paired bootstrap on held-out B of one switch: hypotheses with the env as given (ON) against the same run with the switch
variables cleared (OFF). argv: nt|ot stage var=value ...   prints mean [95%] of chrF(ON) - chrF(OFF)"""
import json, os, random, subprocess, sys
lang, stage, sets = sys.argv[1], sys.argv[2], dict(a.split("=", 1) for a in sys.argv[3:])
if os.environ.get("_CHILD"):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../engine"))
    import engine as E, final_eval as FE  # noqa
    if lang == "ot":
        import cells as CL, heb_run as HR
        CL.contexts = HR.heb_contexts; C = HR.HebCorpus(); tr = C.split("train")
        B = random.Random(8).sample(tr, 1500); tr = [r for r in tr if r not in set(B)]
    else:
        import metamorphic2 as M2
        C = E.Corpus(); tr, B = M2.hold(C)
    _, h = E.measure(C, FE.build(C, tr, stage), B)
    json.dump({"refs": B, "hyps": h, "words": [" ".join(C.verses[r]["words"]) for r in B]}, sys.stdout)
    sys.exit()
def run(on):
    env = dict(os.environ, _CHILD="1", HOLD="1", PYTHONPATH=os.path.join(os.environ["MAKE_TANAKH_WORK"], "scripts"))
    for k, v in sets.items():   # var=ON or var=ON|OFF (OFF empty by default)
        on_v, _, off_v = v.partition("|")
        env[k] = on_v if on else off_v
    return json.loads(subprocess.run([sys.executable, __file__] + sys.argv[1:], env=env, capture_output=True, text=True).stdout)
a, b = run(False), run(True)
import sacrebleu
R = a["words"]; rnd = random.Random(11); d = []
for _ in range(1000):
    idx = [rnd.randrange(len(R)) for _ in R]
    x = sacrebleu.corpus_chrf([a["hyps"][i] for i in idx], [[R[i] for i in idx]]).score
    y = sacrebleu.corpus_chrf([b["hyps"][i] for i in idx], [[R[i] for i in idx]]).score
    d.append(y - x)
d.sort(); print(lang, stage, sets, "chrF ON-OFF", round(sum(d) / 1000, 2), [round(d[25], 2), round(d[975], 2)], flush=True)
