#!/usr/bin/env python3
"""The bridged Hebrew -> target engine (plan phase 2): the E5 engine of eng_v10/heb_run.py on the OT corpus, with a rendering
table BRIDGED from a Greek NT -> target corpus (build_nt_corpus.py / build_kvg_nt.py) through the lexeme bridge
(strong_bridge.json: Hebrew lemma -> Strong's -> Greek lexemes, tier-weighted) and the grammar bridge (grammar_bridge.json:
a Hebrew conjugation -> the Greek tense|mood it expects; nouns by number). Modes, all measured in one process on the same verses:

  ot      E5 as it is (the known figure)
  ot+nt   E5, and where it has NO rendering for a lemma (<unk>), or the lemma was seen < --min-ot times, the bridged rendering
  nt      no OT alignment at all: Hebrew word order, every content word by the bridge, prefixes and words without a bridge dropped

    . ./env.sh; OT_DB=data/dfb_jev+dan.db FUNC_FILE=data/dan_func.txt ~/sil-study/.venv/bin/python lab/bridge/bridge_engine.py
        --nt-db data/dfb_nt_jev.db --split dev [--modes ot ot+nt nt] [--min-ot 1] --out bridge/eng_bridge_dev
    writes <out>.json (measures per mode) and <out>_<mode>.hyps.json ({ref: text}, for paired bootstraps)"""
import argparse, collections, json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "rules", "eng_v10"))
import engine as E, cells as CL, heb_run as HR  # noqa: E402
TIER_W = {"macula": 1.0, "lxx": 0.8, "jev": 0.7}
NUM = {"dual": "plural"}


def nt_tables(nt_db):
    """(strong, feat) -> Counter of rendering tuples; feat '' always, 'V:tense|mood' for verbs, 'N:number' for nouns/adjectives."""
    sp = sqlite3.connect(os.path.join(os.environ["ALIGNER_DATA"], "lexeme-spine-macula.db"))
    feat = {}
    for key, s, tense, mood, number in sp.execute("select key, strong, tense, mood, number from spine_words where lexeme like 'grc:%' and strong is not null"):
        feat[key] = (s, f"V:{tense}|{mood}" if tense else f"N:{number}" if number else None)
    db = sqlite3.connect(os.path.join(E.PRIV, nt_db))
    words = {r: json.loads(w) for r, w, s in db.execute("select ref, words, split from verse") if s == "train"}
    T = collections.defaultdict(collections.Counter)
    for key, ref, pos in db.execute("select key, ref, positions from link"):
        if ref not in words or key not in feat:
            continue
        s, f = feat[key]
        w = tuple(words[ref][p].lower() for p in json.loads(pos) if p < len(words[ref]))
        if w:
            T[(s, "")][w] += 1
            if f:
                T[(s, f)][w] += 1
    return T


class Bridge:
    def __init__(self, nt_db):
        self.T = nt_tables(nt_db)
        B = json.load(open(os.path.join(E.PRIV, "bridge", "strong_bridge.json"), encoding="utf-8"))
        self.lemma2h, self.h2g = B["lemma2h"], B["h2g"]
        G = json.load(open(os.path.join(E.PRIV, "bridge", "grammar_bridge.json"), encoding="utf-8"))
        tm = collections.defaultdict(collections.Counter)
        for hf, gf, c in G["pairs"]:
            t, v, m = gf.split("|"); tm[hf][f"{t}|{m}"] += c
        self.gram = {hf: {k: n / sum(c.values()) for k, n in c.items()} for hf, c in tm.items()}
        self.cache = {}; self.used = collections.Counter()

    def render(self, t):
        """the bridged rendering (list of words) for a Hebrew token, or None"""
        if t["class"] == "verb":
            feats = [(f"V:{gf}", p) for gf, p in sorted(self.gram.get(f"{t['tense']}|{t['voice']}", {}).items(), key=lambda x: -x[1])[:3]]
        elif t["class"] in ("noun", "adj") and t.get("number"):
            feats = [(f"N:{NUM.get(t['number'], t['number'])}", 1.0)]
        else:
            feats = []
        k = (t["lemma"], tuple(feats))
        if k in self.cache:
            return self.cache[k]
        out = collections.Counter(); out0 = collections.Counter()
        for h in self.lemma2h.get(t["lemma"], [])[:1]:
            for g, tier, c, s in self.h2g.get(str(h), []):
                w = TIER_W[tier] * (s if tier != "macula" else min(1.0, 0.5 + s))
                if w < 0.3:
                    continue
                for f, p in feats:
                    for r, n in self.T.get((g, f), {}).items():
                        out[r] += w * p * n
                for r, n in self.T.get((g, ""), {}).items():
                    out0[r] += w * n
        best = out.most_common(1) if sum(out.values()) >= 1 else out0.most_common(1)
        self.cache[k] = list(best[0][0]) if best else None
        return self.cache[k]


def main(a):
    CL.contexts = HR.heb_contexts
    C = HR.HebCorpus(); train = C.split("train"); refs = C.split(a.split)
    if a.hold_out:                                        # the reserved final chapters: out of training, the verses to measure
        ho = {tuple(x.split(":")) for x in a.hold_out}
        is_ho = lambda r: (C.verses[r]["book"], str(C.verses[r]["ch"])) in ho
        refs = sorted((r for r in C.verses if is_ho(r)), key=lambda r: (C.verses[r]["book"], C.verses[r]["ch"], C.verses[r]["v"]))
        train = [r for r in train if not is_ho(r)]
        print(f"hold-out {len(refs)} verses; train {len(train)}")
    if a.train_frac < 1:                                   # the low-data condition: a fixed random subset of the training verses
        import random
        train = sorted(random.Random(7).sample(train, int(len(train) * a.train_frac)))
        print(f"train subset {len(train)} verses")
    lex, lem = E.learn_lexicon(C, train); order = E.learn_order(C, train)
    eng = E.Engine(lex, lem, order); eng.ctxlex = E.CtxLex(C, train); eng.factored = E.Factored(C, train, eng.ctxlex); eng.ctx_first = True
    br = Bridge(a.nt_db); seen = {l: sum(c.values()) for l, c in lem.items()}
    res = {}
    for mode in a.modes:
        br.used.clear()
        if mode == "ot":
            e = eng
        elif mode == "ot+nt":
            e = E.Engine(lex, lem, order); e.ctxlex, e.factored, e.ctx_first = eng.ctxlex, eng.factored, True
            orig = eng.render

            def render(t, orig=orig):
                if seen.get(t["lemma"], 0) < a.min_ot:
                    r = br.render(t)
                    if r:
                        br.used["bridged (few OT cases)"] += 1; return r, "bridge"
                r, how = orig(t)
                if how == "unk":
                    b = br.render(t)
                    if b:
                        br.used["bridged (unk)"] += 1; return b, "bridge"
                return r, how
            e.render = render
        else:
            e = E.Engine({}, {}, None)

            def render_nt(t):
                if t["class"] in ("verb", "noun", "adj", "adv"):
                    r = br.render(t)
                    if r:
                        br.used["bridged"] += 1; return r, "bridge"
                    br.used["no bridge"] += 1
                return ["-"], "drop"
            e.render = render_nt
        r, hyps = E.measure(C, e, refs)
        r = {k: v for k, v in r.items() if k != "how"}; r["bridge use"] = dict(br.used); res[mode] = r
        json.dump(dict(zip(refs, hyps)), open(os.path.join(E.PRIV, f"{a.out}_{mode.replace('+', '_')}.hyps.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(mode, json.dumps({k: r[k] for k in r if k in ("word choice (content, stem)", "form (content, exact)", "function words P", "function words R", "order tau (mean per verse)", "chrF (summary)", "coverage (lemma known)", "bridge use")}, ensure_ascii=False))
    json.dump(res, open(os.path.join(E.PRIV, a.out + ".json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--nt-db", required=True); ap.add_argument("--split", default="dev"); ap.add_argument("--modes", nargs="*", default=["ot", "ot+nt", "nt"])
    ap.add_argument("--min-ot", type=int, default=1); ap.add_argument("--train-frac", type=float, default=1.0); ap.add_argument("--out", required=True)
    ap.add_argument("--hold-out", nargs="*", help="BOOK:ch ... held out of training and measured instead of --split (the reserved final set)")
    main(ap.parse_args())
