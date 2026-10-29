"""(danish/gap.py, adapted from r3/heb_gap3.py, 2026-10-28) eng_v9 on Hebrew -> Danish, rung 4's held-out B: tokens E5 renders exactly and E6 doesn't, by class, E6's step and kind of miss
(same stem other ending = form; other word; E6 none), with examples; and the same count the other way (E6 right, E5 wrong)"""
import collections, json, os, random, sqlite3, sys
LAB0 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
os.environ["OT_DB"] = "data/dan_ot.db"; os.environ["FUNC_FILE"] = "data/dan_func.txt"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../eng_v9"))
import engine as E, cells as CL, heb_run as HR, final_eval as FE  # noqa: E402
CL.contexts = HR.heb_contexts
common = None
for d in ("data/dan_ot.db", "data/ot.db", "data/vamvas_ot.db"):
    s_ = {r for (r,) in sqlite3.connect(os.path.join(PRIV, d)).execute("select ref from verse")}
    common = s_ if common is None else common & s_
H = HR.HebCorpus(); train = sorted(r for r in H.split("train") if r in common)
B = random.Random(8).sample(train, 800); train = [r for r in train if r not in set(B)]
e5 = FE.build(H, train, "e5"); e6 = FE.build(H, train, "e6")
ART = {'den', 'det', 'de'}
kinds = collections.Counter(); back = collections.Counter(); ex = collections.defaultdict(list); n = collections.Counter()
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
            if not w6: k = "E6 none"
            elif c5 == c6 and f5 != f6: k = "same word, function words differ" + (": E6 lacks the article" if set(f5) - set(f6) & ART else "")
            elif c5 and c6 and len(c5) == len(c6) and False: k = "movable nu only"
            elif c5 and c6 and c5[-1][:4] == c6[-1][:4]: k = "same stem, other ending" + (" (+ function words differ)" if f5 != f6 else "")
            elif len(c5) > len(c6) and c6 and all(x in c5 for x in c6): k = "E6 lacks a content word (periphrasis, suffix)"
            else: k = "other word"
            kinds[(t["class"], k)] += 1
            key = (t["class"], k)
            if len(ex[key]) < 6: ex[key].append(f'{ref} {t["lemma"]} {t.get("gcase")} {t.get("role")} E5 «{" ".join(w5)}» E6 «{" ".join(w6)}» {h6}')
        elif w6 == g and w5 != g:
            back[t["class"]] += 1
print("tokens by class", dict(n))
print("E5 right, E6 wrong:", sum(kinds.values()), "| E6 right, E5 wrong:", sum(back.values()), dict(back))
for k, v in kinds.most_common(20):
    print(f"{v:6} {k}")
for k, _ in kinds.most_common(10):
    print(k, *ex[k], sep="\n  ")
