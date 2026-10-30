#!/usr/bin/env python3
"""Two readings of an alignment layer made on a PARTS VIEW (lexeme-aligner target_parts: each analysed word written as its parts,
units = tokens of the view, `_units.json` {BOOK: {"C:V": [[token, part|null], ...]}}):

  fold   the layer folded to the real tokens: every unit position -> its token, duplicates merged (main string and the meta
         channels fn/wp/fp when present); files renamed to the real text's fingerprint (taken from --real-layer, the whole-word
         run's compact dir, BOOK_<fp>.json)                                 -> OUT/BOOK_<fp>.json (+ .meta.json)
  text   the view's verse texts as align-text plain-text input ('c:v unit unit ...'), so a corpus builder can take the view
         layer unchanged with units as the target tokens                    -> OUT/BOOK.txt

    . ./env.sh; /usr/bin/python3 lab/bridge/fold_view_layer.py fold --layer VIEWLAYER --units VIEW/_units.json --real-layer WORDS_COMPACT --out DIR
    /usr/bin/python3 lab/bridge/fold_view_layer.py text --view VIEW --out DIR"""
import argparse, collections, glob, json, os, re, sys
sys.path.insert(0, os.path.join(os.environ["MAKE_TANAKH_WORK"], "scripts"))
import full_align as FA  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_kvg_nt import parse  # noqa: E402


def refold(s, m):
    """'o:a-b o:c ...' with unit positions -> the same with token positions (sorted, merged into ranges)."""
    out = []
    for o, ps in sorted(parse(s).items()):
        toks = sorted({m[p][0] for p in ps if p < len(m)})
        if not toks:
            continue
        spans, a = [], None
        for t in toks:
            if a is None:
                a = b = t
            elif t == b + 1:
                b = t
            else:
                spans.append((a, b)); a = b = t
        spans.append((a, b))
        out.append(f"{o}:" + ",".join(f"{x}-{y}" if y > x else f"{x}" for x, y in spans))
    return " ".join(out)


def fold(a):
    umap = json.load(open(a.units, encoding="utf-8")); os.makedirs(a.out, exist_ok=True)
    real_fp = {os.path.basename(f).split("_")[0]: os.path.basename(f).split("_")[1][:8] for f in glob.glob(os.path.join(a.real_layer, "*_*.json")) if os.path.basename(f).count(".") == 1}
    n = collections.Counter()
    for lf in sorted(glob.glob(os.path.join(a.layer, "*_*.json"))):
        if os.path.basename(lf).count(".") != 1:
            continue
        book = os.path.basename(lf).split("_")[0]
        if book not in real_fp:
            print("no real fingerprint for", book, file=sys.stderr); continue
        main = json.load(open(lf, encoding="utf-8")); meta_p = lf[:-5] + ".meta.json"
        meta = json.load(open(meta_p, encoding="utf-8")) if os.path.exists(meta_p) else {}
        refs = list(FA.index(book, "lexemes")); bm = umap.get(book, {})
        def fold_channel(strings):
            out = []
            for i, r in enumerate(refs):
                s = strings[i] if i < len(strings) else ""
                m = bm.get(r.split(" ")[1])
                out.append(refold(s, m) if (s and m) else (s if not m else ""))
            return out
        main2 = fold_channel(main); n["books"] += 1; n["links in"] += sum(len(parse(s)) for s in main); n["links out"] += sum(len(parse(s)) for s in main2)
        meta2 = dict(meta)
        for ch in ("fn", "wp", "fp"):
            if isinstance(meta.get(ch), list) and meta[ch] and ":" in "".join(meta[ch][:50]):
                meta2[ch] = fold_channel(meta[ch])
        base = os.path.join(a.out, f"{book}_{real_fp[book]}")
        json.dump(main2, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(meta2, open(base + ".meta.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(dict(n), "->", a.out)


def text(a):
    """the view's verse texts: USJ content -> 'c:v text' lines per book (the view writes ' text ' after each verse marker)"""
    os.makedirs(a.out, exist_ok=True); n = 0
    for f in sorted(glob.glob(os.path.join(a.view, "*.json"))):
        if os.path.basename(f) == "_units.json":
            continue
        book = os.path.basename(f)[3:6]; d = json.load(open(f, encoding="utf-8")); lines = []; ch = None
        def walk(items):
            nonlocal ch
            cur = None
            for it in items:
                if isinstance(it, dict):
                    if it.get("type") == "chapter":
                        ch = int(it["number"])
                    elif it.get("type") == "verse":
                        cur = it["number"].split("-")[0]
                    elif it.get("content"):
                        walk(it["content"])
                elif isinstance(it, str) and cur is not None and it.strip():
                    lines.append(f"{ch}:{cur} {' '.join(it.split())}"); cur = None
        walk(d["content"])
        open(os.path.join(a.out, f"{book}.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n"); n += len(lines)
    print(n, "verses ->", a.out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fold"); f.add_argument("--layer", required=True); f.add_argument("--units", required=True); f.add_argument("--real-layer", required=True); f.add_argument("--out", required=True)
    t = sub.add_parser("text"); t.add_argument("--view", required=True); t.add_argument("--out", required=True)
    a = ap.parse_args(); fold(a) if a.cmd == "fold" else text(a)
