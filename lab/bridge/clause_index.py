#!/usr/bin/env python3
"""The clause index over bcv-commons' two clause layouts ($ALIGNER_DATA/hebrew-clause-layout, greek-nt-clause-layout; `kind`
and `rule` are one vocabulary for both testaments), with each clause's verb lexemes and forms and content lexemes from the
lexeme spine (and MACULA's conjugation for Hebrew), and a retriever: for an OT clause, the NT clauses that are *similar* in
the bridge's sense, i.e. (1) a verb (or, in a nominal clause, the predicate's head) that is a lexeme-bridge equivalent, (2) the
same shape (kind, constituent order), (3) a tense that the grammar bridge expects for the Hebrew conjugation, (4) further bridged
content lexemes. The score keeps its four parts, so the weights can be tuned later on dev.

    . ./env.sh; ~/sil-study/.venv/bin/python -I lab/bridge/clause_index.py build
    ~/sil-study/.venv/bin/python -I lab/bridge/clause_index.py retrieve --refs test [--k 5] [--out bridge/retrieval_test.json]
       --refs: a split name of OT_DB (test/dev) or a file of "BOOK c:v" lines (English numbering, as the layouts' verse_ref_en)
Writes bridge/clauses_ot.json, bridge/clauses_nt.json (build) and the retrieval file (ref -> clauses -> top-k NT clauses with
score parts and texts); prints the match-rate figures."""
import argparse, collections, csv, json, os, sqlite3, sys
import pyarrow.parquet as pq

PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")
DATA = os.environ["ALIGNER_DATA"]
SPINE = os.path.join(DATA, "lexeme-spine-macula.db")
MACULA = os.path.join(PRIV, "data", "orig", "macula-hebrew.tsv")
BR = os.path.join(PRIV, "bridge")
TIER_W = {"macula": 1.0, "lxx": 0.8, "jev": 0.7}


def spine_words():
    """key -> (strong, is_content, form) for both testaments; Greek form 'tense|mood' from the spine, Hebrew 'type|stem' from MACULA."""
    hform = {}
    with open(MACULA, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["class"] == "verb":
                hform[row["xml:id"][1:]] = f"{row.get('type') or '?'}|{row.get('stem') or '?'}"
    W = {}
    db = sqlite3.connect(SPINE)
    for key, lex, s, ic, tense, mood in db.execute("select key, lexeme, strong, is_content, tense, mood from spine_words where strong is not null"):
        if lex.startswith("grc:"):
            W[key] = (s, ic, f"{tense}|{mood}" if tense else None)
        else:
            W[key] = (s, ic, hform.get(key))
    return W


def clause_rows(path):
    return pq.read_table(path).to_pylist()


def build(a):
    W = spine_words()
    out = {}
    for side, files in (("ot", sorted(f for f in os.listdir(os.path.join(DATA, "hebrew-clause-layout")) if f.endswith(".parquet"))),
                        ("nt", ["clauses.parquet"])):
        rows = []
        for f in files:
            for r in clause_rows(os.path.join(DATA, "hebrew-clause-layout" if side == "ot" else "greek-nt-clause-layout", f)):
                w = r.get("words") or []
                words = list(w) if isinstance(w, list) else json.loads(str(w).replace("'", '"'))
                verbs, content = [], []
                for k in words:
                    s, ic, form = W.get(k, (None, 0, None))
                    if s is None:
                        continue
                    if form:
                        verbs.append([s, form])
                    elif ic:
                        content.append(s)
                ref = r.get("verse_ref_en") or f"{r['book']} {r['chapter']}:{r['verse']}"
                rows.append({"ref": ref, "seg": r.get("seg"), "kind": r.get("kind") or None, "rule": r.get("rule") or None,
                             "verbs": verbs, "content": content, "text": r.get("text") or ""})
        out[side] = rows
        print(side, len(rows), "clauses;", sum(1 for x in rows if x["verbs"]), "with a verb form;", sum(1 for x in rows if x["kind"] == "VC"), "VC")
        json.dump(rows, open(os.path.join(BR, f"clauses_{side}.json"), "w", encoding="utf-8"), ensure_ascii=False)


def load_bridges():
    B = json.load(open(os.path.join(BR, "strong_bridge.json"), encoding="utf-8"))
    h2g = collections.defaultdict(dict)
    for h, v in B["h2g"].items():
        for g, tier, c, s in v:
            w = TIER_W[tier] * (s if tier != "macula" else min(1.0, 0.5 + s))   # macula: a frequent equivalent counts fully
            h2g[int(h)][g] = max(h2g[int(h)].get(g, 0), w)
    G = json.load(open(os.path.join(BR, "grammar_bridge.json"), encoding="utf-8"))
    tm = collections.defaultdict(collections.Counter)                               # hebrew form -> greek 'tense|mood' -> count (voice collapsed)
    for hf, gf, c in G["pairs"]:
        t, v, m = gf.split("|"); tm[hf][f"{t}|{m}"] += c
    gram = {hf: {k: n / sum(c.values()) for k, n in c.items()} for hf, c in tm.items()}
    return h2g, gram


def shape(q, c):
    if q["kind"] != c["kind"]:
        return 0.0
    if not q["rule"] or not c["rule"]:
        return 0.5
    a, b = q["rule"].split("-"), c["rule"].split("-")
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        for j in range(len(b) + 1):
            d[i][j] = i if j == 0 else j if i == 0 else min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    return 1 - d[len(a)][len(b)] / max(len(a), len(b))


def retrieve_one(q, NT, by_verb, h2g, gram, k, max_cands=0):
    """Top-k NT clauses for an OT clause q. Candidates share a bridged verb (or, verbless, a bridged content lexeme);
    max_cands > 0 keeps only the best-weighted (then same-kind) candidates before the full scoring, for bulk runs."""
    cands = collections.Counter()                       # nt index -> best verb weight
    anchors = [s for s, _ in q["verbs"]] or q["content"]
    for hs in anchors:
        for g, w in h2g.get(hs, {}).items():
            for i in by_verb.get(g, ()):
                cands[i] = max(cands[i], w)
    if max_cands and len(cands) > max_cands:
        order = sorted(cands, key=lambda i: (-cands[i], NT[i]["kind"] != q["kind"], NT[i]["rule"] != q["rule"]))
        cands = {i: cands[i] for i in order[:max_cands]}
    scored = []
    for i, wv in cands.items():
        c = NT[i]
        sh = shape(q, c)
        tf = 0.0
        if q["verbs"] and c["verbs"]:
            tf = max(gram.get(hf, {}).get(gf, 0.0) for _, hf in q["verbs"] for _, gf in c["verbs"])
        others = [s for s in q["content"] if s not in anchors] if q["verbs"] else []
        lx = (sum(1 for s in others if any(g in {s2 for s2 in c["content"]} for g in h2g.get(s, {}))) / len(others)) if others else 0.0
        scored.append((0.4 * wv + 0.25 * sh + 0.2 * tf + 0.15 * lx, wv, sh, tf, lx, i))
    scored.sort(reverse=True)
    return [{"score": round(s, 3), "verb": round(wv, 2), "shape": round(sh, 2), "tense": round(tf, 2), "lex": round(lx, 2),
             "ref": NT[i]["ref"], "rule": NT[i]["rule"], "kind": NT[i]["kind"], "text": NT[i]["text"]} for s, wv, sh, tf, lx, i in scored[:k]]


def retrieve(a):
    OT = json.load(open(os.path.join(BR, "clauses_ot.json"), encoding="utf-8")); NT = json.load(open(os.path.join(BR, "clauses_nt.json"), encoding="utf-8"))
    h2g, gram = load_bridges()
    by_verb = collections.defaultdict(list)
    for i, c in enumerate(NT):
        for s, _ in (c["verbs"] or []):
            by_verb[s].append(i)
        if not c["verbs"]:
            for s in c["content"]:
                by_verb[s].append(i)
    if os.path.exists(a.refs):
        refs = {l.strip() for l in open(a.refs, encoding="utf-8") if l.strip()}
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import score as S
        C, _ = S.corpus(); refs = {r for r, v in C.verses.items() if v["split"] == a.refs}
    qs = [q for q in OT if q["ref"] in refs]
    out = collections.defaultdict(list); n = collections.Counter(); best = []
    for q in qs:
        top = retrieve_one(q, NT, by_verb, h2g, gram, a.k)
        out[q["ref"]].append({"seg": q["seg"], "kind": q["kind"], "rule": q["rule"], "text": q["text"], "verbs": q["verbs"], "top": top})
        n["clauses"] += 1
        if q["verbs"]:
            n["with verb"] += 1
        if top:
            n["any candidate (bridged anchor)"] += 1; best.append(top[0]["score"])
            if top[0]["shape"] >= 0.99:
                n["best has same kind and rule"] += 1
            if top[0]["verb"] >= 0.9 and top[0]["shape"] >= 0.5 and top[0]["tense"] >= 0.3:
                n["best: strong verb, near shape, expected tense"] += 1
    tot = max(1, n["clauses"])
    print(f"OT clauses in {a.refs}: {n['clauses']} ({n['with verb']} with a verb form)")
    for key in ("any candidate (bridged anchor)", "best has same kind and rule", "best: strong verb, near shape, expected tense"):
        print(f"  {key}: {n[key]} ({n[key] / tot:.2f})")
    if best:
        best.sort(); print(f"  best score quartiles: {best[len(best) // 4]:.2f} / {best[len(best) // 2]:.2f} / {best[3 * len(best) // 4]:.2f}")
    p = os.path.join(PRIV, a.out); json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0); print("written", p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    r = sub.add_parser("retrieve"); r.add_argument("--refs", default="test"); r.add_argument("--k", type=int, default=5); r.add_argument("--out", default="bridge/retrieval_test.json")
    a = ap.parse_args(); build(a) if a.cmd == "build" else retrieve(a)
