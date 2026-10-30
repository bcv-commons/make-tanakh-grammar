#!/usr/bin/env python3
"""Third tier of the Hebrew <-> Greek bridge (strong_bridge.py): a judgment per lexeme the two data tiers leave out. Code
proposes the candidates, Jev (TypeSafe's System One model) chooses one or "none"; nothing is generated. Candidates for an
uncovered Greek lexeme are Hebrew lexemes that share an English gloss word with it (MACULA's and the spine's glosses, used
only to find candidates, never as the bridge) plus the weak co-occurrence pairs (Dice >= 0.08) of the Septuagint tier; the
other direction the same way round. Jev sees the lexeme, its glosses, its frequency and up to three verses where it stands
(the spine's own text), and the candidates with their glosses and frequencies.

    . ./env.sh; ~/sil-study/.venv/bin/python -I lab/bridge/bridge_jev.py candidates --macula macula-hebrew.tsv --weak bridge/probe/strong_bridge_d008.json
    set -a; . $MAKE_TANAKH_WORK/.env; set +a; ~/sil-study/.venv/bin/python -I lab/bridge/bridge_jev.py judge [--limit N] [--min-p 0.5]
Writes bridge/jev_candidates.json, bridge/jev_answers.json and bridge/strong_bridge_jev.tsv (hebrew, greek, tier=jev, count=NT or OT
tokens, score=Jev's probability), the rows to append to strong_bridge.tsv."""
import argparse, collections, csv, json, os, re, sqlite3, sys, time, urllib.request

PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")
SPINE = os.path.join(os.environ["ALIGNER_DATA"], "lexeme-spine-macula.db")
BRIDGE = os.path.join(PRIV, "bridge", "strong_bridge.json")
STOP = {"the", "a", "an", "of", "to", "and", "in", "on", "for", "be", "is", "he", "she", "it", "they", "i", "you", "with", "by", "at",
        "from", "as", "that", "this", "his", "her", "its", "their", "my", "your", "not", "no", "who", "which", "what", "one", "one's",
        "up", "out", "do", "did", "make", "go", "come", "give", "say", "thing", "things", "man", "men", "person", "s", "so", "or", "if",
        "will", "was", "were", "are", "am", "been", "being", "have", "has", "had", "about", "off", "round", "before", "after", "over",
        "under", "into", "unto", "than", "then", "there", "here", "shall", "may", "might", "can", "could", "would", "should", "let",
        "him", "them", "us", "we", "me", "myself", "himself", "themselves", "yourself", "own", "all", "any", "some", "also", "even",
        "very", "more", "most", "much", "many", "when", "where", "how", "but", "yet", "again", "away", "down", "upon", "against",
        "through", "among", "between", "toward", "towards", "because", "while", "until", "till", "whom", "whose", "each", "every",
        "other", "another", "same", "such", "these", "those", "both", "either", "neither", "only", "just", "now", "ever", "never"}


def stem(w):
    for suf in ("ness", "ment", "ing", "ed", "es", "s", "ly", "d"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def gloss_words(g):
    return {stem(w) for w in re.split(r"[^a-z']+", g.lower()) if len(w) > 1 and w not in STOP}


def hebrew_glosses(macula):
    """Strong's -> Counter of gloss words, and the lemma, from MACULA's per-occurrence gloss column."""
    gl = collections.defaultdict(collections.Counter)
    with open(macula, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            m = re.match(r"(\d+)", (row.get("strongnumberx") or "").strip())
            if m:
                gl[int(m.group(1))].update(gloss_words(row.get("gloss") or ""))
    return gl


def spine_glosses(db, lang):
    gl = collections.defaultdict(collections.Counter); lemma = {}; freq = collections.Counter()
    for s, l, g in db.execute("select strong, lemma, gloss from spine_words where lexeme like ? and strong is not null", (f"{lang}:%",)):
        gl[s].update(gloss_words(g or "")); lemma[s] = l; freq[s] += 1
    return gl, lemma, freq


def verses(db, lang, strong, n=3):
    out = []
    for b, c, v in db.execute("select distinct book, chapter, verse from spine_words where lexeme like ? and strong = ? limit ?",
                              (f"{lang}:%", strong, n)):
        words = [w for w, in db.execute("select surface from spine_words where book=? and chapter=? and verse=? order by idx", (b, c, v))]
        out.append(f"{b} {c}:{v}: " + " ".join(words))
    return out


def candidates(a):
    db = sqlite3.connect(SPINE)
    B = json.load(open(BRIDGE, encoding="utf-8")); weak = json.load(open(os.path.join(PRIV, a.weak), encoding="utf-8"))
    hg = hebrew_glosses(a.macula); hg2, hlemma, hfreq = spine_glosses(db, "hbo"); gg, glemma, gfreq = spine_glosses(db, "grc")
    for s, c in hg2.items():
        hg[s].update(c)
    hnames = set(B["names"]["h"]); gnames = set(B["names"]["g"])
    inv_h = collections.defaultdict(set); inv_g = collections.defaultdict(set)   # gloss word -> lexemes
    for s, c in hg.items():
        if s not in hnames:
            for w in c:
                inv_h[w].add(s)
    for s, c in gg.items():
        if s not in gnames:
            for w in c:
                inv_g[w].add(s)
    import math
    idf = {w: math.log((len(hg) + len(gg)) / (len(inv_h.get(w, ())) + len(inv_g.get(w, ())) + 1)) for w in set(inv_h) | set(inv_g)}
    out = {"nt": [], "ot": []}
    for side, todo, mine, inv, other_g, other_l, other_f, weak_side, lang in (
            ("nt", B["todo"]["nt"], gg, inv_h, hg, hlemma, hfreq, weak["g2h"], "grc"),
            ("ot", B["todo"]["ot"], hg, inv_g, gg, glemma, gfreq, weak["h2g"], "hbo")):
        for s, lemma, n, _ in todo:
            score = collections.Counter()
            tot = max(1, sum(mine[s].values()))
            for w, k in mine[s].most_common(6):
                for t in inv.get(w, ()):
                    score[t] += (k / tot) * (other_g[t][w] / max(1, sum(other_g[t].values()))) * idf.get(w, 1.0)
            cands = [t for t, _ in score.most_common(a.top)]
            for t, tier, c, d in weak_side.get(str(s), [])[:3]:
                if t not in cands:
                    cands.append(t)
            if not cands:
                continue
            out[side].append({"strong": s, "lemma": lemma, "tokens": n, "glosses": [w for w, _ in mine[s].most_common(5)],
                              "verses": verses(db, lang, s),
                              "candidates": [{"strong": t, "lemma": other_l.get(t, "?"), "tokens": other_f[t],
                                              "glosses": [w for w, _ in other_g[t].most_common(4)]} for t in cands]})
    p = os.path.join(PRIV, "bridge", "jev_candidates.json"); json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print({k: len(v) for k, v in out.items()}, "written", p)
    for side in out:
        for e in out[side][:4]:
            print(side, e["lemma"], e["glosses"], "->", [(c["lemma"], c["glosses"][:2]) for c in e["candidates"]][:6])


def ask(state, question, model):
    body = json.dumps({"model": model, "state": state, "questions": {"q": question}}).encode("utf-8")
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"], "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:                        # noqa: BLE001
            if attempt == 3:
                raise
            print("retry", attempt, e, file=sys.stderr); time.sleep(2 * (attempt + 1))


def judge(a):
    C = json.load(open(os.path.join(PRIV, "bridge", "jev_candidates.json"), encoding="utf-8"))
    p_ans = os.path.join(PRIV, "bridge", "jev_answers.json")
    answers = json.load(open(p_ans, encoding="utf-8")) if os.path.exists(p_ans) else {}
    usage = collections.Counter(); n = 0
    for side in ("nt", "ot"):
        src, tgt = ("Greek (New Testament)", "Biblical Hebrew") if side == "nt" else ("Biblical Hebrew", "Greek (New Testament)")
        for e in C[side]:
            key = f"{side}:{e['strong']}"
            if key in answers or (a.limit and n >= a.limit):
                continue
            crit = {f"c{i}": f"{c['lemma']} (glossed: {', '.join(c['glosses'])}; {c['tokens']} occurrences)" for i, c in enumerate(e["candidates"])}
            crit["none"] = "none of the candidates is a lexical equivalent; the word has no counterpart among them"
            state = {"source_language": src, "target_language": tgt, "lexeme": e["lemma"], "glosses": e["glosses"], "occurrences": e["tokens"],
                     "verses": e["verses"], "candidates": {f"c{i}": c for i, c in enumerate(e["candidates"])}}
            q = {"type": "choice", "criteria": crit,
                 "instructions": f"`lexeme` is a {src} word (see `glosses` and `verses`). Which candidate {tgt} lexeme in `candidates` is its "
                                 "lexical equivalent, i.e. the word a translator of the Bible into any language would normally render with "
                                 "the same target word? Judge by meaning in the biblical usage, not by the English gloss wording. Choose "
                                 "'none' if no candidate is a true equivalent (a mere related or collocated word is not one)."}
            r = ask(state, q, a.model); ans = r["answers"]["q"]
            answers[key] = {"side": side, "strong": e["strong"], "lemma": e["lemma"], "tokens": e["tokens"], "choice": ans["choice"],
                            "confidence": ans.get("confidence"), "probabilities": ans.get("probabilities"),
                            "candidates": {f"c{i}": c["strong"] for i, c in enumerate(e["candidates"])}, "model": r.get("model")}
            usage.update(r.get("usage", {})); n += 1
            if n % 25 == 0:
                json.dump(answers, open(p_ans, "w", encoding="utf-8"), ensure_ascii=False, indent=0); print(n, dict(usage), file=sys.stderr)
    json.dump(answers, open(p_ans, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("asked", n, "usage", dict(usage))
    rows = []
    for key, x in answers.items():
        if x["choice"] != "none":
            p = x["probabilities"].get(x["choice"], 0)
            if p >= a.min_p:
                t = x["candidates"][x["choice"]]
                h, g = (t, x["strong"]) if x["side"] == "nt" else (x["strong"], t)
                rows.append((h, g, x["tokens"], p))
    p_tsv = os.path.join(PRIV, "bridge", "strong_bridge_jev.tsv")
    with open(p_tsv, "w", encoding="utf-8") as f:
        f.write("hebrew\tgreek\ttier\tcount\tscore\n")
        for h, g, c, p in sorted(rows):
            f.write(f"H{h:04d}\tG{g:04d}\tjev\t{c}\t{p}\n")
    kept = len(rows); none = sum(1 for x in answers.values() if x["choice"] == "none")
    print(f"answers {len(answers)}: none {none}, kept (p >= {a.min_p}) {kept}, dropped for low p {len(answers) - none - kept}; written {p_tsv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidates"); c.add_argument("--macula", required=True); c.add_argument("--weak", required=True); c.add_argument("--top", type=int, default=6)
    j = sub.add_parser("judge"); j.add_argument("--limit", type=int, default=0); j.add_argument("--min-p", type=float, default=0.5); j.add_argument("--model", default="jev-latest")
    a = ap.parse_args(); candidates(a) if a.cmd == "candidates" else judge(a)
