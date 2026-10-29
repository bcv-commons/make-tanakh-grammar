"""samples of E5 right / E6 wrong where the content word differs (nouns, verbs), with E6's step"""
import collections, json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../engine"))
import engine as E, cells as CL, heb_run as HR, final_eval as FE  # noqa: E402
CL.contexts = HR.heb_contexts
H = HR.HebCorpus(); train = H.split("train")
B = random.Random(8).sample(train, 1500); train = [r for r in train if r not in set(B)]
e5 = FE.build(H, train, "e5"); e6 = FE.build(H, train, "e6")
kinds = collections.Counter(); ex = collections.defaultdict(list)
for ref in B:
    for t in H.tok[ref]:
        g = H.rendering(ref, t)
        if g is None or t.get("class") not in ("noun", "verb"):
            continue
        g = [x.lower() for x in g]; w5, _ = e5.render(t); w6, h6 = e6.render(t)
        c5 = [x for x in w5 if x not in E.FUNC]; c6 = [x for x in w6 if x not in E.FUNC]
        if w5 == g and c5 != c6:
            k = "plural/singular" if c5 and c6 and (c5[-1].rstrip("s") == c6[-1].rstrip("s") or c5[-1][:4] == c6[-1][:4]) else "other word" if c5 and c6 else "E6 none" if not c6 else "E5 none"
            kinds[(t["class"], h6, k)] += 1
            if len(ex[k]) < 10: ex[k].append(f'{ref} {t["lemma"]} {t["morph"]} E5 «{" ".join(w5)}» E6 «{" ".join(w6)}» {h6}')
print(kinds.most_common(20))
for k, v in ex.items(): print(k, *v, sep="\n  ")
