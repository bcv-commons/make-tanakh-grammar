"""eng_v8 on Hebrew -> Vamvas, held-out B: tokens E5 renders exactly and E6 doesn't, by class, E6's step and kind of miss
(same stem other ending = form; other word; E6 none), with examples; and the same count the other way (E6 right, E5 wrong)"""
import collections, json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../eng_v8"))
import engine as E, cells as CL, heb_run as HR, final_eval as FE  # noqa: E402
CL.contexts = HR.heb_contexts
H = HR.HebCorpus(); train = H.split("train")
B = random.Random(8).sample(train, 1500); train = [r for r in train if r not in set(B)]
e5 = FE.build(H, train, "e5"); e6 = FE.build(H, train, "e6")
ART = {'ο', 'η', 'το', 'του', 'της', 'τον', 'την', 'τω', 'τη', 'οι', 'αι', 'τα', 'των', 'τους', 'τας', 'τοις', 'ταις'}
ART_ONLY = 1; arts = collections.Counter(); art_ex = collections.defaultdict(list)
hows = collections.defaultdict(collections.Counter); kinds = collections.Counter(); back = collections.Counter(); ex = collections.defaultdict(list); n = collections.Counter()
for ref in B:
    for t in H.tok[ref]:
        g = H.rendering(ref, t)
        if g is None:
            continue
        g = [x.lower() for x in g]; w5, _ = e5.render(t); w6, h6 = e6.render(t)
        n[t["class"]] += 1
        if w5 == g and w6 != g:
            c5 = [x for x in w5 if x not in E.FUNC]; c6 = [x for x in w6 if x not in E.FUNC]
            f5 = [x for x in w5 if x in E.FUNC]; f6 = [x for x in w6 if x in E.FUNC]
            a5 = [x for x in w5 if x in ART]; a6 = [x for x in w6 if x in ART]
            r5 = [x for x in w5 if x not in ART]; r6 = [x for x in w6 if x not in ART]
            if ART_ONLY and w6 and (r5 == r6 or a5 != a6):
                art_k = ("article missing in E6" if a5 and not a6 else "article extra in E6" if a6 and not a5 else
                         "other article" if a5 != a6 else "same article")
                rest_k = "rest same" if r5 == r6 else "rest differs"
                arts[(t["class"], art_k, rest_k)] += 1
                if r5 == r6 and len(art_ex[(t["class"], art_k)]) < 8:
                    art_ex[(t["class"], art_k)].append(f'{ref} {t["lemma"]} {t.get("type")} {t.get("gcase") or ""} E5 «{" ".join(w5)}» E6 «{" ".join(w6)}» {h6}')
            if not w6: k = "E6 none"
            elif c5 == c6 and f5 != f6: k = "same word, function words differ" + (": E6 lacks the article" if set(f5) - set(f6) & ART else "")
            elif c5 and c6 and len(c5) == len(c6) and all(x.rstrip("ν") == y.rstrip("ν") for x, y in zip(c5, c6)): k = "movable nu only"
            elif c5 and c6 and c5[-1][:4] == c6[-1][:4]: k = "same stem, other ending" + (" (+ function words differ)" if f5 != f6 else "")
            elif len(c5) > len(c6) and c6 and all(x in c5 for x in c6): k = "E6 lacks a content word (periphrasis, suffix)"
            else: k = "other word"
            kinds[(t["class"], k)] += 1; hows[(t["class"], k)][h6] += 1
            key = (t["class"], k)
            if len(ex[key]) < 12: ex[key].append(f'{ref} {t["lemma"]} {t.get("gcase")} {t.get("role")} E5 «{" ".join(w5)}» E6 «{" ".join(w6)}» {h6}')
        elif w6 == g and w5 != g:
            back[t["class"]] += 1
print("tokens by class", dict(n))
print("E5 right, E6 wrong:", sum(kinds.values()), "| E6 right, E5 wrong:", sum(back.values()), dict(back))
for k, v in kinds.most_common(20):
    print(f"{v:6} {k}  E6 step: {dict(hows[k].most_common(4))}")
for k, _ in kinds.most_common(10):
    print(k, *ex[k], sep="\n  ")

print("\n== the article, among E5 right / E6 wrong (class, article, rest)")
for k, v in arts.most_common(14):
    print(f"{v:6} {k}")
for k, v in art_ex.items():
    print(k, *v, sep="\n  ")
