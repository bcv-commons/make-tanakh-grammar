"""rung 4: Danish nouns on held-out B: E5/E6's head word against the human-side (our draft's) head, by kind of miss:
definiteness (the same stem with/without -en/-et/-n/-t/-ne/-erne...), number, genitive -s, other ending, other word, none.
ENGINE (default eng_v10), STAGE (e6)"""
import collections, os, random, sqlite3, sys
LAB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
os.environ.update(OT_DB="data/dan_ot.db", FUNC_FILE="data/dan_func.txt")
sys.path.insert(0, os.path.join(LAB, os.environ.get("ENGINE", "eng_v10")))
import engine as E, cells as CL, heb_run as HR, final_eval as FE  # noqa: E402
CL.contexts = HR.heb_contexts
common = None
for d in ("data/dan_ot.db", "data/ot.db", "data/vamvas_ot.db"):
    s_ = {r for (r,) in sqlite3.connect(os.path.join(PRIV, d)).execute("select ref from verse")}
    common = s_ if common is None else common & s_
H = HR.HebCorpus(); tr = sorted(r for r in H.split("train") if r in common)
B = random.Random(8).sample(tr, 800); train = [r for r in tr if r not in set(B)]
eng = FE.build(H, train, os.environ.get("STAGE", "e6"))
DEF = ("erne", "ene", "ne", "en", "et", "n", "t")
def base(w):
    w = w[:-1] if w.endswith("s") and len(w) > 4 else w
    for e in DEF:
        if w.endswith(e) and len(w) - len(e) >= 3:
            return w[:-len(e)], True
    return w, False
c = collections.Counter(); ex = collections.defaultdict(list)
for ref in B:
    for t in H.tok[ref]:
        if t["class"] != "noun":
            continue
        g = H.rendering(ref, t)
        if not g:
            continue
        gc = [x.lower() for x in g if x.lower() not in E.FUNC]
        w, _ = eng.render(t); wc = [x.lower() for x in w if x.lower() not in E.FUNC]
        if not gc:
            continue
        if not wc:
            k = "none"
        elif wc[-1] == gc[-1]:
            k = "head right"
        else:
            a, b = wc[-1], gc[-1]
            (ba, da), (bb, db) = base(a), base(b)
            if a.rstrip("s") == b.rstrip("s") or (a.endswith("s") != b.endswith("s") and a[:-1] == b or b[:-1] == a):
                k = "genitive -s"
            elif ba[:4] == bb[:4] and da != db:
                k = "definiteness" + (" (gold definite)" if db else " (gold indefinite)")
            elif a[:4] == b[:4]:
                k = "same stem, other ending"
            else:
                k = "other word"
        c[k] += 1
        if len(ex[k]) < 8:
            ex[k].append(f"{ref} {t['lemma']} art={t['art']} {t['gcase']} {t['number']}: engine «{' '.join(w)}» draft «{' '.join(g)}»")
n = sum(c.values())
for k, v in c.most_common():
    print(f"{v:6} {v / n:6.1%} {k}")
for k in os.environ.get("SHOW", "definiteness (gold definite)|definiteness (gold indefinite)|same stem, other ending").split("|"):
    print(k, *ex[k], sep="\n  ")
