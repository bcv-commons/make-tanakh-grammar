#!/usr/bin/env python3
"""Step A's measures for ANY hypothesis (the engine's, an LLM's, NLLB's) against a reference corpus (data/*.db built by
build_corpus.py or danish/build_ot.py), so every method is scored alike. The reference side is aligned; the hypothesis is
not: a measure asks whether the hypothesis verse HAS the reference's words.

  word choice   per Hebrew content word (noun, verb, adj, adv): a hypothesis word with the stem of one of the reference's
                linked words (content words of the link; marks kept, case folded)
  form          the reference's linked content words all present, exactly; "any": at least one
  function words P / R   per verse, bag of the corpus's function words (FUNC file), against the reference verse
  order tau     Kendall tau of the matched reference words' first position in the hypothesis against the Hebrew order
  chrF          corpus chrF over the verses (sacrebleu), the summary

    . ./env.sh; OT_DB=... FUNC_FILE=... ~/sil-study/.venv/bin/python lab/bridge/score.py HYPS.json [--refs R1 R2 ...]
    HYPS.json = {"<BSB ref>": "text", ...}; module use: score(C, hyps, func, stem) -> dict"""
import collections, itertools, json, os, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.join(os.path.dirname(HERE), "rules")
sys.path.insert(0, os.path.join(LAB, os.environ.get("ENGINE", "eng_v10")))
import engine as E, heb_run as HR  # noqa: E402
sys.path.insert(0, os.path.join(E.R, "scripts"))
from full_align import tokenize  # noqa: E402
CONTENT = {"noun", "verb", "adj", "adv"}
DAN_SUF = ("ernes", "erne", "enes", "ende", "ede", "ene", "ets", "ens", "ers", "er", "en", "et", "es", "e", "s", "t")


def stem_dan(w):
    w = w.lower()
    for s in DAN_SUF:
        if w.endswith(s) and len(w) - len(s) >= 3:
            return w[:-len(s)]
    return w


def stem_none(w):
    return w.lower()


STEMS = {"dan": stem_dan, "eng": E.stem, "none": stem_none}


def kendall(xs, ys):
    c = d = 0
    for i, j in itertools.combinations(range(len(xs)), 2):
        s = (xs[i] - xs[j]) * (ys[i] - ys[j]); c += s > 0; d += s < 0
    return (c - d) / (c + d) if c + d else None


def corpus(db=None, func=None):
    """(HebCorpus on db, FUNC set): db and func override OT_DB / FUNC_FILE (paths under $MAKE_TANAKH_PRIVATE/rules)"""
    if db:
        HR.OT = os.path.join(E.PRIV, db)
    C = HR.HebCorpus()
    F = set(open(os.path.join(E.PRIV, func), encoding="utf-8").read().split()) if func else E.FUNC
    return C, F


def score(C, hyps, FUNC, stem=stem_dan, refs=None, by_class=False):
    """hyps = {BSB ref: text}; refs = the verses to score (default: all of hyps that the corpus has)"""
    refs = [r for r in (refs or hyps) if r in C.verses and r in hyps]
    M = collections.Counter(); byc = collections.defaultdict(collections.Counter); taus = []
    H, T = [], []
    for ref in refs:
        words = C.verses[ref]["words"]
        ht = [w.lower() for w in tokenize(hyps[ref])]
        hset = set(ht); hstem = {stem(w) for w in ht}
        first = {}
        for i, w in enumerate(ht):
            first.setdefault(w, i)
        xs, ys = [], []
        for i, t in enumerate(C.tok[ref]):
            r = C.rendering(ref, t)
            if not r:
                continue
            gw = [w.lower() for w in r]
            gc = [w for w in gw if w not in FUNC] or gw
            if t["class"] in CONTENT:
                c = t["class"] if by_class else "content"
                for m in (M, byc[c]):
                    m["content"] += 1
                    m["choice"] += bool({stem(w) for w in gc} & hstem)
                    m["form"] += all(w in hset for w in gc)
                    m["any"] += any(w in hset for w in gc)
            hit = [first[w] for w in gw if w in first]
            if hit:
                xs.append(min(hit)); ys.append(i)
        k = kendall(xs, ys) if len(xs) >= 3 else None
        if k is not None:
            taus.append(k)
        fe = collections.Counter(w for w in ht if w in FUNC); fr = collections.Counter(w.lower() for w in words if w.lower() in FUNC)
        M["func tp"] += sum((fe & fr).values()); M["func e"] += sum(fe.values()); M["func r"] += sum(fr.values())
        H.append(" ".join(ht)); T.append(" ".join(w.lower() for w in words))
    res = {"verses": len(refs), "content words": M["content"],
           "word choice (content, stem)": round(M["choice"] / max(1, M["content"]), 4),
           "form (content, exact)": round(M["form"] / max(1, M["content"]), 4),
           "form (any word)": round(M["any"] / max(1, M["content"]), 4),
           "function words P": round(M["func tp"] / max(1, M["func e"]), 4),
           "function words R": round(M["func tp"] / max(1, M["func r"]), 4),
           "order tau (mean per verse)": round(sum(taus) / max(1, len(taus)), 4), "tau verses": len(taus)}
    if by_class:
        res["by class"] = {c: {"n": m["content"], "choice": round(m["choice"] / m["content"], 3), "form": round(m["form"] / m["content"], 3)}
                           for c, m in byc.items()}
    try:
        import sacrebleu
        res["chrF (summary)"] = round(sacrebleu.corpus_chrf(H, [T]).score, 2)
    except ImportError:
        pass
    return res


def boot(C, hyps_a, hyps_b, FUNC, stem=stem_dan, refs=None, n=1000, key="chrF (summary)"):
    """paired bootstrap over verses of score(b) - score(a) on `key`: (mean difference, 95% interval, share > 0)"""
    import random
    refs = [r for r in (refs or hyps_a) if r in C.verses and r in hyps_a and r in hyps_b]
    rng = random.Random(7); diffs = []
    for _ in range(n):
        s = [rng.choice(refs) for _ in refs]
        diffs.append(score(C, hyps_b, FUNC, stem, s)[key] - score(C, hyps_a, FUNC, stem, s)[key])
    diffs.sort()
    return round(sum(diffs) / n, 3), (round(diffs[int(n * .025)], 3), round(diffs[int(n * .975)], 3)), round(sum(d > 0 for d in diffs) / n, 3)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("hyps"); ap.add_argument("--refs", nargs="*"); ap.add_argument("--stem", default="dan")
    ap.add_argument("--by-class", action="store_true"); a = ap.parse_args()
    C, F = corpus()
    print(json.dumps(score(C, json.load(open(a.hyps, encoding="utf-8")), F, STEMS[a.stem], a.refs, a.by_class), ensure_ascii=False, indent=1))
