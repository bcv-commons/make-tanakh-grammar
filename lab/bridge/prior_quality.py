#!/usr/bin/env python3
"""Prior quality for the NT -> OT bridge, on one OT book with a reference layer (e.g. Ruth, published Jev-by-parts layer): for each
Hebrew content token with a reference link, does a recipe's candidate list (target words with weights) hold the reference word?
Recipes:

  theirs      lexeme-aligner's nt_bridge priors as written by align-text (OUT/nt_bridge_priors_<edition>.tsv: Strong's, word, weight)
  ours+efl    our three-tier lexeme bridge (strong_bridge.json) x the SAME NT eflomal renderings (OUT/align_eflomal_<edition>_<NT>.jsonl)
  ours+jev    our bridge x the published NT Jev layer's renderings (data/kvg_nt_words.db train split, via the spine's Strong's)

Metrics: coverage (a candidate list exists), hit@1, hit@5 (reference word among the top candidates), over the tokens; words compared
lower-cased, whole tokens (the reference's tokens on the same text).

    . ./env.sh; ~/sil-study/.venv/bin/python lab/bridge/prior_quality.py --book RUT --out private/align/kvg_all/out_words --edition kvg_kunt
        --ref private/align/kvg_m/k/kvg/kvg-m_wbt+llm+jev-v4/RUT_e9d22404.json --text private/align/kvg_all/text/RUT.txt --nt-db data/kvg_nt_words.db"""
import argparse, collections, glob, json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.environ["MAKE_TANAKH_WORK"], "scripts"))
import full_align as FA  # noqa: E402
from link_agree import links  # noqa: E402
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")
TIER_W = {"macula": 1.0, "lxx": 0.8, "jev": 0.7}
NT = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB",
      "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}


def theirs(tsv):
    out = collections.defaultdict(collections.Counter)
    for line in open(tsv, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if len(f) < 3:
            continue
        s = next((x for x in f if x[:1] == "H" and x[1:].isdigit()), None)
        try:
            w = float(f[-1])
        except ValueError:
            continue
        if s:
            word = [x for x in f if x != s and x != f[-1]][-1]
            out[s][word.lower()] += w
    return out


def efl_renderings(out_dir, edition):
    """Greek Strong's -> Counter(target word): single-token content links of the NT eflomal files (nt_bridge.nt_renderings)."""
    rend = collections.defaultdict(collections.Counter)
    for f in glob.glob(os.path.join(out_dir, f"align_eflomal_{edition}_*.jsonl")):
        if os.path.basename(f)[:-6].split("_")[-1] not in NT:
            continue
        for line in open(f, encoding="utf-8"):
            for p in json.loads(line).get("pairs", []):
                if p.get("content") and p.get("strong") and len(p.get("t_idx") or []) == 1:
                    rend[p["strong"]][p["target"].lower()] += 1
    return rend


def jev_renderings(nt_db):
    sp = sqlite3.connect(os.path.join(os.environ["ALIGNER_DATA"], "lexeme-spine-macula.db"))
    strong_of = dict(sp.execute("select key, strong from spine_words where lexeme like 'grc:%' and strong is not null"))
    db = sqlite3.connect(os.path.join(PRIV, nt_db))
    words = {r: json.loads(w) for r, w, s in db.execute("select ref, words, split from verse") if s == "train"}
    rend = collections.defaultdict(collections.Counter)
    for key, ref, pos in db.execute("select key, ref, positions from link"):
        ps = json.loads(pos)
        if ref in words and key in strong_of and len(ps) == 1 and ps[0] < len(words[ref]):
            rend[strong_of[key]][words[ref][ps[0]].lower()] += 1
    return rend


def ours(h2g, rend, top_k=5, min_share=0.1):
    """Hebrew Strong's -> Counter(word): tier-weighted sum of the NT renderings' shares, their top_k / min_share rule per Greek lexeme."""
    out = collections.defaultdict(collections.Counter)
    for h, gs in h2g.items():
        for g, tier, c, s in gs:
            w = TIER_W[tier] * (s if tier != "macula" else min(1.0, 0.5 + s))
            if w < 0.3:
                continue
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
    strong_of = {k: s for k, s, ic in sp.execute("select key, strong, is_content from spine_words where lexeme like 'hbo:%' and strong is not null and is_content = 1")}
    toks = {}
    for line in open(a.text, encoding="utf-8"):
        cv, _, t = line.rstrip("\n").partition(" ")
        if ":" in cv and t:
            toks[cv] = [w.lower() for w in FA.tokenize(t)]
    ref = collections.defaultdict(set)
    for kind, r, key, p in links(a.ref, a.book):
        if kind == "c" and key in strong_of:
            cv = r.split(" ")[1]
            if cv in toks and p < len(toks[cv]):
                ref[(r, key)].add(toks[cv][p])
    B = json.load(open(os.path.join(PRIV, "bridge", "strong_bridge.json"), encoding="utf-8"))
    recipes = {"theirs": theirs(os.path.join(a.out, f"nt_bridge_priors_{a.edition}.tsv")),
               "ours+efl": ours(B["h2g"], efl_renderings(a.out, a.edition)),
               "ours+jev": ours(B["h2g"], jev_renderings(a.nt_db))}
    print(f"{a.book}: {len(ref)} Hebrew content tokens with a reference link")
    print("| recipe | Hebrew lexemes with priors | coverage | hit@1 | hit@5 | hit@1 (covered) |\n|---|---|---|---|---|---|")
    for name, pri in recipes.items():
        n = collections.Counter()
        for (r, key), words in ref.items():
            hn = int(str(strong_of[key]).lstrip("H"))
            c = pri.get(f"H{hn:04d}") or pri.get(f"H{hn}")
            n["tokens"] += 1
            if c:
                n["cov"] += 1; top = [w for w, _ in c.most_common(5)]
                n["h1"] += top[0] in words; n["h5"] += any(w in words for w in top)
        t = max(1, n["tokens"])
        print(f"| {name} | {len(pri)} | {n['cov'] / t:.3f} | {n['h1'] / t:.3f} | {n['h5'] / t:.3f} | {n['h1'] / max(1, n['cov']):.3f} |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True); ap.add_argument("--out", required=True); ap.add_argument("--edition", required=True)
    ap.add_argument("--ref", required=True); ap.add_argument("--text", required=True); ap.add_argument("--nt-db", required=True)
    main(ap.parse_args())
