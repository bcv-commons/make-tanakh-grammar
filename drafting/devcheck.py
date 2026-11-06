#!/usr/bin/env python3
"""The dev check: how close is a draft to the team's own text, on chapters the team has translated?

A language's yardstick, not an experiment: after the first stage it says whether the drafter works for the language, and later
whether a change of the language's data (more text, new notes) helped. Per run, on the verses every named run answered:

  (a verse, or a stretch of verses where a clause runs over a verse boundary, is one unit)
  chrF3   corpus chrF on characters (orders 1-6, beta 3, whitespace dropped: sacrebleu's definition, from per-verse statistics)
  P, R    mean character n-gram precision and recall
  words   draft words / team words
  new     the share of the draft's words that occur nowhere in the team's text
and for every run after the first, the paired bootstrap difference to the first (1000 resamples of verses, seed 7).

Hyphens count as spaces on both sides (the corpus holds hyphenated clitics as words); case and punctuation count for chrF3 and
not for the word counts. --toneless drops combining marks except those the language's configuration keeps ("keep_marks").
The team's text of a closed or held-out chapter is never read: such verses are refused.

    . ./env.sh; python3 drafting/devcheck.py --lang kvg --book GEN --labels dev [dev-nonotes ...] [--toneless]"""
import argparse, collections, json, os, random, re, sqlite3, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import holdout, paths  # noqa: E402
from drafting import draft  # noqa: E402

PUN = r"[.,;:!?\"'“”‘’()«»\[\]—–]"
ORDER, BETA = 6, 3


def norm_word(w):
    return re.sub(PUN, "", w.lower())


def detone(s, keep=()):
    d = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c) or c in keep)
    return unicodedata.normalize("NFC", d)


def team_text(cfg, source):
    """ref -> the team's verse as words (the corpus's words; a hyphenated clitic is a word of its own); shut chapters left out"""
    x = paths.corpus(cfg, source); shut = holdout.shut(cfg); out = {}
    if x is None:
        return out
    z = sqlite3.connect(x["_db"]); heb = "heb" if "heb" in [r[1] for r in z.execute("pragma table_info(verse)")] else "ref"
    for ref, book, ch, words, wi in z.execute(f"select coalesce({heb}, ref), book, ch, words, wordidx from verse"):   # as the source numbers it
        if not wi or shut(book, ch) or book in x.get("exclude_books", ()):
            continue
        ws, wi = json.loads(words), json.loads(wi); by = collections.defaultdict(str)
        for p, w in zip(ws, wi):
            by[w] += p
        out[ref] = [by[w] for w in sorted(by)]
    return out


def stats(h, g):
    """sacrebleu's chrF statistics of one segment: per order (hypothesis n-grams, reference n-grams, matches), whitespace dropped"""
    h, g = "".join(h.split()), "".join(g.split()); out = []
    for n in range(1, ORDER + 1):
        a = collections.Counter(h[i:i + n] for i in range(len(h) - n + 1)); b = collections.Counter(g[i:i + n] for i in range(len(g) - n + 1))
        out += [sum(a.values()), sum(b.values()), sum((a & b).values())]
    return out


def fscore(rows):
    """(chrF, mean precision, mean recall) from summed statistics"""
    tot = [sum(c) for c in zip(*rows)]; P = R = 0.0; eff = 0
    for n in range(ORDER):
        hn, gn, m = tot[3 * n:3 * n + 3]
        if hn > 0 and gn > 0:
            P += m / hn; R += m / gn; eff += 1
    if not eff:
        return 0.0, 0.0, 0.0
    P /= eff; R /= eff; b2 = BETA ** 2
    return (100 * (1 + b2) * P * R / (b2 * P + R) if P + R else 0.0), P, R


def boot(xs, ys, f, n=1000):
    rng = random.Random(7); N = len(xs); v = []
    for _ in range(n):
        idx = [rng.randrange(N) for _ in range(N)]
        v.append(f([ys[i] for i in idx]) - f([xs[i] for i in idx]))
    v.sort(); return [round(sum(v) / n, 3), round(v[25], 3), round(v[974], 3)]


def check(lang, book, labels, toneless=False):
    """the dev check's figures for the named runs of one book (module docstring), or None when no verse has both a draft and the
    team's text"""
    a = argparse.Namespace(lang=lang, book=book.upper()); cfg = paths.config(lang); src = draft.source_of(a.book)
    f = (lambda s: detone(s, tuple(cfg.get("keep_marks", ())))) if toneless else (lambda s: s)
    V = team_text(cfg, src); vocab = {f(norm_word(w)) for ws in V.values() for w in ws}
    G = {}; parent = {}

    def find(r):
        while parent.setdefault(r, r) != r:
            parent[r] = parent[parent[r]]; r = parent[r]
        return r
    for lb in labels:                                   # a clause may run over a verse boundary, so a run's verse groups may share
        a.label = lb; G[lb] = list(draft.answers(a).values())      # a verse: verses joined by any group of any run are scored as one stretch
        for x in G[lb]:
            for r in x["refs"]:
                parent[find(r)] = find(x["refs"][0])
    block = collections.defaultdict(list)
    for r in sorted(parent, key=draft.prompt.ref_key):
        block[find(r)].append(r)
    T = {lb: collections.defaultdict(list) for lb in labels}
    for lb in labels:
        for x in G[lb]:
            T[lb][" / ".join(block[find(x["refs"][0])])].append(x["text"])
        T[lb] = {k: " ".join(t for t in v if t.strip()) for k, v in T[lb].items()}

    def gold_of(key):
        rs = key.split(" / ")
        return " ".join(" ".join(V[r]) for r in rs) if all(r in V for r in rs) else None
    keys = sorted(set.intersection(*(set(k for k, v in T[lb].items() if v.strip()) for lb in labels)), key=lambda k: draft.prompt.ref_key(k.split(" / ")[0]))
    keys = [k for k in keys if gold_of(k)]
    if not keys:
        return None
    gold = {k: f(gold_of(k)) for k in keys}
    res = {"language": lang, "book": a.book, "verses": len(keys), "toneless": toneless, "runs": {}}; S = {}; WR = {}
    for lb in labels:
        hyp = {k: f(T[lb][k].replace("-", " ")) for k in keys}
        S[lb] = [stats(hyp[k], gold[k]) for k in keys]; F, P, R = fscore(S[lb]); WR[lb] = []; new = 0
        for k in keys:
            dw = [norm_word(w) for w in hyp[k].split() if norm_word(w)]; tw = [w for w in (norm_word(y) for y in gold[k].split()) if w]
            WR[lb].append((len(dw), len(tw))); new += sum(w not in vocab for w in dw)
        res["runs"][lb] = {"chrF3": round(F, 2), "P": round(P, 3), "R": round(R, 3),
                           "words (draft / team)": round(sum(d for d, _ in WR[lb]) / sum(t for _, t in WR[lb]), 3),
                           "draft words nowhere in the team's text": round(new / max(1, sum(d for d, _ in WR[lb])), 3)}
    base = labels[0]; ratio = lambda rows: sum(d for d, _ in rows) / sum(t for _, t in rows)
    for lb in labels[1:]:
        res["runs"][lb][f"chrF3 - {base}"] = boot(S[base], S[lb], lambda rows: fscore(rows)[0])
        res["runs"][lb][f"words - {base}"] = boot(WR[base], WR[lb], ratio)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", required=True); ap.add_argument("--book", required=True); ap.add_argument("--labels", nargs="+", required=True)
    ap.add_argument("--toneless", action="store_true"); ap.add_argument("--out")
    a = ap.parse_args(); res = check(a.lang, a.book, a.labels, a.toneless)
    if res is None:
        sys.exit("no verse with both a draft and the team's text (closed and held-out chapters are never read)")
    print(json.dumps(res, indent=1, ensure_ascii=False))
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
