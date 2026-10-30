#!/usr/bin/env python3
"""Thresholded / weighted variants of the lexeme bridge as NT->OT priors, against lexeme-aligner's own lxx_greek priors
(lexeme-aligner 2026-10-30: our whole table gave no chain gain; causes: low-count macula pairs, frequent Greek words in the glaux
tier, e.g. YHWH -> autos, hoti, poieo, sy). Measured by prior_quality.py's test (does the recipe's top candidate match the
reference word of a Hebrew content token?) on each book given, with the SAME NT eflomal renderings as their recipe.

Variants (filters on bridge/strong_bridge_bq.json: bcv-query's tiers + our jev, spine merges applied):
  all           every pair, weights as before (macula min(1, 0.5 + share), glaux 0.8 x Dice, jev 0.7 x p)
  mac_top4      macula only, top 4 per Hebrew lexeme (lxx_greek's rule), weight = share
  mac_c5        macula count >= 5, weight = share
  mac_c10s05    macula count >= 10 and share >= 0.05, weight = share
  w_share       all tiers, weight = the pair's own score (no 0.5 floor), pairs below 0.05 dropped
  top4+glx      mac_top4 + glaux pairs with Dice >= 0.5 whose Greek lexeme is a content word and not among the 50 most frequent
  top4+glx+jev  as top4+glx + the jev tier
A Greek lexeme is a content word when most of its NT tokens are content tokens in the spine.
Result 2026-10-30 (NOTES.md): the gain is in the weighting (their recipe counts every Greek equivalent in full); top4+glx best.

    . ./env.sh; ~/sil-study/.venv/bin/python lab/bridge/prior_variants.py --out private/align/kvg_all/out_words --edition kvg_kunt
        --book RUT=private/align/kvg_m/k/kvg/kvg-m_wbt+llm+jev-v4/RUT_e9d22404.json
        --book JON=private/align/kvg_all/jev_folded/k/kvg/kvg_kunt/JON_<fp>.json --text private/align/kvg_all/text"""
import argparse, collections, json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import prior_quality as PQ  # noqa: E402
from link_agree import links  # noqa: E402
PRIV = PQ.PRIV


def greek_content():
    sp = sqlite3.connect(os.path.join(os.environ["ALIGNER_DATA"], "lexeme-spine-macula.db"))
    c, n = collections.Counter(), collections.Counter()
    for s, ic in sp.execute("select strong, is_content from spine_words where lexeme like 'grc:%' and strong is not null"):
        g = int(str(s).lstrip("G")); n[g] += 1; c[g] += bool(ic)
    top50 = {g for g, _ in n.most_common(50)}
    return {g for g in n if c[g] / n[g] > 0.5 and g not in top50}


def variants(B):
    h2g = B["h2g"]; content = greek_content()
    def pick(keep, weight):
        out = {}
        for h, gs in h2g.items():
            rows = [[g, t, c, weight(t, c, s)] for g, t, c, s in keep(h, gs)]
            rows = [r for r in rows if r[3] > 0]
            if rows:
                out[h] = rows
        return out
    def mac(gs):
        return sorted([x for x in gs if x[1] == "macula"], key=lambda x: -x[2])
    def glx(gs):
        return [x for x in gs if x[1] == "lxx" and x[3] >= 0.5 and int(str(x[0]).lstrip("G")) in content]
    old = lambda t, c, s: PQ.TIER_W[t] * (s if t != "macula" else min(1.0, 0.5 + s))
    share = lambda t, c, s: s
    return {
        "all": pick(lambda h, gs: gs, old),
        "mac_top4": pick(lambda h, gs: mac(gs)[:4], share),
        "mac_c5": pick(lambda h, gs: [x for x in mac(gs) if x[2] >= 5], share),
        "mac_c10s05": pick(lambda h, gs: [x for x in mac(gs) if x[2] >= 10 and x[3] >= 0.05], share),
        "w_share": pick(lambda h, gs: [x for x in gs if x[3] >= 0.05], share),
        "top4+glx": pick(lambda h, gs: mac(gs)[:4] + glx(gs), share),
        "top4+glx+jev": pick(lambda h, gs: mac(gs)[:4] + glx(gs) + [x for x in gs if x[1] == "jev"], share),
    }


def ours_w(h2g, rend, top_k=5, min_share=0.1):
    """prior_quality.ours with the weight taken as given (the variant set it), no 0.3 floor."""
    out = collections.defaultdict(collections.Counter)
    for h, gs in h2g.items():
        for g, tier, c, w in gs:
            gn = int(str(g).lstrip("G"))
            cnt = rend.get(f"G{gn:04d}") or rend.get(f"G{gn}") or rend.get(gn)
            if not cnt:
                continue
            tot = sum(cnt.values())
            for word, k in cnt.most_common(top_k):
                if k / tot >= min_share:
                    out[f"H{int(h):04d}"][word] += w * k / tot
    return out


def main(a):
    sp = sqlite3.connect(os.path.join(os.environ["ALIGNER_DATA"], "lexeme-spine-macula.db"))
    strong_of = {k: s for k, s in sp.execute("select key, strong from spine_words where lexeme like 'hbo:%' and strong is not null and is_content = 1")}
    B = json.load(open(os.path.join(PRIV, "bridge", a.bridge), encoding="utf-8"))
    rend = PQ.efl_renderings(a.out, a.edition)
    recipes = {"theirs (lxx_greek)": PQ.theirs(os.path.join(a.out, f"nt_bridge_priors_{a.edition}.tsv"))}
    for name, h2g in variants(B).items():
        recipes[name] = ours_w(h2g, rend)
    res = {}
    for spec in a.book:
        book, path = spec.split("=", 1)
        toks = {}
        for line in open(os.path.join(a.text, f"{book}.txt"), encoding="utf-8"):
            cv, _, t = line.rstrip("\n").partition(" ")
            if ":" in cv and t:
                toks[cv] = [w.lower() for w in PQ.FA.tokenize(t)]
        ref = collections.defaultdict(set)
        for kind, r, key, p in links(path, book):
            if kind == "c" and key in strong_of:
                cv = r.split(" ")[1]
                if cv in toks and p < len(toks[cv]):
                    ref[(r, key)].add(toks[cv][p])
        for name, pri in recipes.items():
            n = res.setdefault(name, collections.Counter())
            for (r, key), words in ref.items():
                hn = int(str(strong_of[key]).lstrip("H"))
                c = pri.get(f"H{hn:04d}") or pri.get(f"H{hn}")
                n["tokens"] += 1; n[f"tokens {book}"] += 1
                if c:
                    top = [w for w, _ in c.most_common(5)]
                    n["cov"] += 1; n["h1"] += top[0] in words; n["h5"] += any(w in words for w in top)
                    n[f"h1 {book}"] += top[0] in words
    books = [s.split("=")[0] for s in a.book]
    print(f"books {books}; Hebrew content tokens with a reference link: {res['all']['tokens']}")
    print("| recipe | lexemes | coverage | hit@1 | hit@5 | " + " | ".join(f"hit@1 {b}" for b in books) + " |\n|" + "---|" * (5 + len(books)))
    for name, n in res.items():
        t = max(1, n["tokens"])
        print(f"| {name} | {len(recipes[name])} | {n['cov'] / t:.3f} | {n['h1'] / t:.3f} | {n['h5'] / t:.3f} | "
              + " | ".join(f"{n[f'h1 {b}'] / max(1, n[f'tokens {b}']):.3f}" for b in books) + " |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--edition", required=True); ap.add_argument("--text", required=True)
    ap.add_argument("--book", action="append", required=True, help="BOOK=reference layer file")
    ap.add_argument("--bridge", default="strong_bridge_bq.json")
    main(ap.parse_args())
