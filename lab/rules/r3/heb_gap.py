#!/usr/bin/env python3
"""Hebrew E6 vs E5 on B (eng_v3 switches): per token class, which stage renders the BSB's words exactly, and the function
words each one adds or misses (before / after the content word). Writes results/heb_gap_B.json."""
import collections, json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../engine"))
import engine as E, cells as CL, heb_run as HR, final_eval as FE  # noqa: E402
CL.contexts = HR.heb_contexts
H = HR.HebCorpus(); train = H.split("train")
B = random.Random(8).sample(train, 1500); train = [r for r in train if r not in set(B)]
e5 = FE.build(H, train, "e5"); e6 = FE.build(H, train, "e6")
cls = collections.defaultdict(collections.Counter); fw = collections.Counter(); how6 = collections.defaultdict(collections.Counter)
for ref in B:
    for t in H.tok[ref]:
        g = H.rendering(ref, t)
        if g is None:
            continue
        g = [x.lower() for x in g]; w5, _ = e5.render(t); w6, h6 = e6.render(t)
        k = t.get("class") or "?"
        cls[k]["n"] += 1; cls[k]["e5"] += w5 == g; cls[k]["e6"] += w6 == g
        how6[h6]["n"] += 1; how6[h6]["right"] += w6 == g; how6[h6]["e5 right"] += w5 == g
        if w5 == g and w6 != g:
            f5 = [x for x in w5 if x in E.FUNC]; f6 = [x for x in w6 if x in E.FUNC]
            for x in set(f5) - set(f6): fw[("E6 drops", x)] += 1
            for x in set(f6) - set(f5): fw[("E6 adds", x)] += 1
            if [x for x in w5 if x not in E.FUNC] != [x for x in w6 if x not in E.FUNC]: fw[("content word differs", k)] += 1
out = {"by class": {k: {"n": c["n"], "e5": round(c["e5"] / c["n"], 3), "e6": round(c["e6"] / c["n"], 3), "e5 - e6 tokens": c["e5"] - c["e6"]}
                    for k, c in sorted(cls.items(), key=lambda kv: kv[1]["e6"] - kv[1]["e5"])},
       "e6 by step": {h: dict(c) for h, c in how6.items()},
       "where E5 right, E6 wrong": [[" ".join(map(str, k)), v] for k, v in fw.most_common(40)]}
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.environ.get("GAP_OUT", "../results/heb_gap_B.json")), "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False, indent=0)[:5000])
