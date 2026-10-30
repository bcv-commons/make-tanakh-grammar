#!/usr/bin/env python3
"""What the NT bridge delivers for an OT target lexicon, measured without the engine's syntax: three lexical tables for a Hebrew
lemma, each giving renderings with counts,

  ot        from the OT corpus's own training alignment (OT_DB train split)
  nt        BRIDGED: Hebrew lemma -> Strong's (the spine) -> Greek lexemes (strong_bridge.json, tier-weighted) -> the Greek->target
            NT corpus's renderings of those lexemes (--nt-db train split)
  ot+nt     ot where it has >= --min-ot cases, else nt (back-off)

scored on the OT_DB test split's content tokens: coverage (a table has an answer) and accuracy at 1 (the top rendering's stem is
among the reference's stems for that token). Then, with --drafts, the confidence-aware checker (checker.py's rule: n >= N, top
share >= T) built from each table, on draft chapter files ('vN text' lines) against the same test reference: flags, strict and
loose precision, recall. Stems: --stem dan|eng|none, or --segmenter DIR (a bcv_segment bundle: the stem part).

    . ./env.sh; OT_DB=data/kvg_ot.db FUNC_FILE=data/kvg_func_derived.txt ~/sil-study/.venv/bin/python lab/bridge/bridge_lexicon_eval.py
        --nt-db data/kvg_nt_words.db --segmenter private/hf/language-analysis/kvg/2cd8a4bc/bundle
        --drafts RUT=$MAKE_TANAKH_WORK/export/kvg/kvg_BSB/_eval/ruth-test JON=$MAKE_TANAKH_WORK/local_output/kvg/jon_test/jon"""
import argparse, collections, glob, json, os, re, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score as S  # noqa: E402
from score import tokenize  # noqa: E402
E = S.E
TIER_W = {"macula": 1.0, "lxx": 0.8, "jev": 0.7}


def nt_tables(nt_db, stem, FUNC):
    """Greek strong -> Counter of rendering stems, from the NT corpus's training links."""
    sp = sqlite3.connect(os.path.join(os.environ["ALIGNER_DATA"], "lexeme-spine-macula.db"))
    strong_of = dict(sp.execute("select key, strong from spine_words where lexeme like 'grc:%' and strong is not null"))
    db = sqlite3.connect(os.path.join(E.PRIV, nt_db))
    words = {r: json.loads(w) for r, w, s in db.execute("select ref, words, split from verse") if s == "train"}
    T = collections.defaultdict(collections.Counter); N = collections.Counter()
    for key, ref, pos in db.execute("select key, ref, positions from link"):
        if ref not in words:
            continue
        g = strong_of.get(key)
        if g is None:
            continue
        ws = {stem(words[ref][p].lower()) for p in json.loads(pos) if p < len(words[ref])}
        ws = {w for w in ws if w and w not in FUNC}
        if ws:
            N[g] += 1
            for w in ws:
                T[g][w] += 1
    return N, T


def bridged(lemma, lemma2h, h2g, Ng, Tg):
    """Counter of renderings for a Hebrew lemma through the bridge (weights x NT counts), and the weighted case count."""
    out = collections.Counter(); n = 0.0
    for h in lemma2h.get(lemma, [])[:1]:
        for g, tier, c, s in h2g.get(str(h), []):
            w = TIER_W[tier] * (s if tier != "macula" else min(1.0, 0.5 + s))
            if w < 0.3 or g not in Tg:
                continue
            n += w * Ng[g]
            for r, k in Tg[g].items():
                out[r] += w * k
    return out, n


def ot_tables(C, FUNC, stem):
    T = collections.defaultdict(collections.Counter); N = collections.Counter()
    for r in C.split("train"):
        for t in C.tok[r]:
            ws = {stem(w.lower()) for w in (C.rendering(r, t) or [])}; ws = {w for w in ws if w and w not in FUNC}
            if ws:
                N[t["lemma"]] += 1
                for w in ws:
                    T[t["lemma"]][w] += 1
    return N, T


def read_drafts(spec):
    """'RUT=dir JON=dir' -> {ref: text} from chapter files bookNNN.txt with 'vN text' lines."""
    hyps = {}
    for item in spec:
        book, d = item.split("=", 1)
        for f in sorted(glob.glob(os.path.join(d, f"{book.lower()}[0-9][0-9][0-9].txt"))):
            ch = int(os.path.basename(f)[3:6])
            body = "\n".join(l for l in open(f, encoding="utf-8") if not l.startswith(("!!<", "==", "#")))
            ms = list(re.finditer(r"(?:^|(?<=\s))v(\d+)\s", body))          # several verses may share a line
            for m, nxt in zip(ms, ms[1:] + [None]):
                hyps[f"{book} {ch}:{int(m.group(1))}"] = body[m.end():nxt.start() if nxt else None].strip()
    return hyps


def main(a):
    C, FUNC = S.corpus()
    if a.segmenter:
        sys.path.insert(0, a.segmenter); import bcv_segment
        seg = bcv_segment.load(a.segmenter); cache = {}

        def stem(w):
            if w not in cache:
                parts = seg.split(w); cache[w] = next((p["text"] for p in parts if p["slot"] == "stem"), w)
            return cache[w]
    else:
        stem = S.STEMS[a.stem]
    B = json.load(open(os.path.join(E.PRIV, "bridge", "strong_bridge.json"), encoding="utf-8"))
    lemma2h, h2g = B["lemma2h"], B["h2g"]
    Ng, Tg = nt_tables(a.nt_db, stem, FUNC); No, To = ot_tables(C, FUNC, stem)
    print(f"NT tables: {len(Tg)} Greek lexemes; OT tables: {len(To)} Hebrew lemmas")
    test = sorted(r for r, v in C.verses.items() if v["split"] == a.split)

    def table(lemma, src):
        if src == "ot":
            return (To[lemma], No[lemma]) if No[lemma] else (None, 0)
        if src == "nt":
            c, n = bridged(lemma, lemma2h, h2g, Ng, Tg); return (c, n) if n else (None, 0)
        if No[lemma] >= a.min_ot:
            return To[lemma], No[lemma]
        c, n = bridged(lemma, lemma2h, h2g, Ng, Tg); return (c, n) if n else ((To[lemma], No[lemma]) if No[lemma] else (None, 0))

    print(f"\nLexical choice on {a.split} ({len(test)} verses): content tokens with a reference rendering")
    print("| table | coverage | accuracy@1 (covered) | accuracy@1 (all) |\n|---|---|---|---|")
    for src in ("ot", "nt", "ot+nt"):
        tot = cov = hit = 0
        for r in test:
            for t in C.tok[r]:
                if t["class"] not in S.CONTENT:
                    continue
                ref = {stem(w.lower()) for w in (C.rendering(r, t) or [])}; ref = {w for w in ref if w and w not in FUNC}
                if not ref:
                    continue
                tot += 1; c, n = table(t["lemma"], src)
                if c:
                    cov += 1; hit += c.most_common(1)[0][0] in ref
        print(f"| {src} | {cov / max(1, tot):.3f} | {hit / max(1, cov):.3f} | {hit / max(1, tot):.3f} |")
    if a.drafts:
        hyps = read_drafts(a.drafts); refs = [r for r in test if r in hyps]
        if a.parts_drafts:                      # a parts corpus: the draft's tokens split into parts by the same segmenter
            sys.path.insert(0, a.parts_drafts); import bcv_segment as bs
            pseg = bs.load(a.parts_drafts); pc = {}

            def to_parts(text):
                out = []
                for w in tokenize(text):
                    if w not in pc:
                        ps = pseg.split(w); pc[w] = [p["text"] for p in ps if p["slot"] != "tone" and p["text"]] or [w]
                    out += pc[w]
                return " ".join(out)
            hyps = {r: to_parts(t) for r, t in hyps.items()}
        print(f"\nChecker on drafts ({len(refs)} verses with a draft), n >= {a.n}, share >= {a.t}")
        print("| table | confident words | flags | precision strict | precision loose | recall |\n|---|---|---|---|---|---|")
        for src in ("ot", "nt", "ot+nt"):
            k = collections.Counter()
            for r in refs:
                hs = {stem(w.lower()) for w in tokenize(hyps[r])}; rs = {stem(w.lower()) for w in C.verses[r]["words"]}
                for t in C.tok[r]:
                    c, n = table(t["lemma"], src)
                    if not c or n < a.n:
                        continue
                    top, cnt = c.most_common(1)[0]
                    if cnt / n < a.t:
                        continue
                    expected = [w for w, x in c.most_common() if x / n >= a.t]
                    rw = [stem(w.lower()) for w in (C.rendering(r, t) or [])]; rw = [w for w in rw if w not in FUNC]
                    real_miss = bool(rw) and not any(w in hs for w in rw)
                    k["confident"] += 1; k["real"] += real_miss
                    if not any(w in hs for w in expected):
                        k["flags"] += 1; k["right"] += any(w in rs for w in expected); k["fr"] += real_miss
            f = max(1, k["flags"])
            print(f"| {src} | {k['confident']} | {k['flags']} | {k['right'] / f:.2f} | {k['fr'] / f:.2f} | {k['fr'] / max(1, k['real']):.2f} |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--nt-db", required=True); ap.add_argument("--split", default="test"); ap.add_argument("--stem", default="none")
    ap.add_argument("--segmenter", default=""); ap.add_argument("--drafts", nargs="*", default=[])
    ap.add_argument("--parts-drafts", default="", help="segmenter bundle: split the drafts' words into parts (for a parts corpus, with --stem none)")
    ap.add_argument("--min-ot", type=int, default=3); ap.add_argument("--n", type=int, default=5); ap.add_argument("--t", type=float, default=0.8)
    main(ap.parse_args())
