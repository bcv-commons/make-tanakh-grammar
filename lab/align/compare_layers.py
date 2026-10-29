#!/usr/bin/env python3
"""Two align-text layers of one edition (its compact output and its --jev layer, say) side by side, for an edition with no
gold (Den Frie Bibel). Per layer: source words linked (content, function), and the target words covered (any link to them);
between the layers: per content word, the same positions, a subset either way, overlapping, or disjoint. The lab's held-out
test chapters (MRK 5, 10, 15; GEN 22, 37, 44) are left out.

    . ./env.sh; /usr/bin/python3 lab/align/compare_layers.py TEXT_DIR LAYERS_A EDITION_A LAYERS_B EDITION_B [BOOK ...]
    (TEXT_DIR = the plain text given to align-text, in the spine's numbering: our export_edition.py output)"""
import collections, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import gold_bsb as GB  # noqa: E402
FA = GB.FA


def tokens(text_dir, book):
    out = {}
    for l in open(os.path.join(text_dir, f"{book}.txt"), encoding="utf-8"):
        cv, _, t = l.rstrip("\n").partition(" ")
        out[f"{book} {cv}"] = FA.tokenize(t)
    return out


TEST = {"MRK": {5, 10, 15}, "GEN": {22, 37, 44}}   # the lab's held-out test chapters: never read here


def held_out(ref):
    book, _, cv = ref.partition(" ")
    return cv.split(":")[0].isdigit() and int(cv.split(":")[0]) in TEST.get(book, ())


def word_refs(b):
    """{source word id: its spine verse}, content and function words"""
    out = {}
    for kind in ("keys", "fn_keys"):
        for r, ks in FA.index(b, kind).items():
            for k in ks:
                for m in (k or "").split("+"):
                    if m:
                        out.setdefault(m if b in GB.NT else m[:-1], r)
    return out


def layer_stats(root, ed, books, text_dir):
    st = collections.Counter(); P = {}
    for b in books:
        pos, has_fn = GB.predicted(root, ed, b); C = GB.classes(b); P[b] = pos
        word_ref = word_refs(b)
        content = {w for w in C if not held_out(word_ref.get(w, ""))}
        st["content words"] += len(content); st["content linked"] += sum(bool(pos.get(w)) for w in content)
        st["function words linked"] += sum(bool(p) for w, p in pos.items()
                                           if w not in C and not held_out(word_ref.get(w, "")))
        # target coverage: a verse's tokens with any link (positions are per spine verse)
        refs = [r for r in FA.index(b, "lexemes") if not held_out(r)]; toks = tokens(text_dir, b)
        cov = collections.defaultdict(set)
        for w, p in pos.items():
            if w in word_ref:
                cov[word_ref[w]].update(p)
        for r in refs:
            if r in toks:
                st["target tokens"] += len(toks[r]); st["target covered"] += len({i for i in cov[r] if i < len(toks[r])})
    return st, P


def main(text_dir, ra, ea, rb, eb, books):
    sa, pa = layer_stats(ra, ea, books, text_dir); sb, pb = layer_stats(rb, eb, books, text_dir)
    for name, s in ((ea, sa), (eb, sb)):
        print(f"{name}: content linked {s['content linked'] / s['content words']:.3f} of {s['content words']}, "
              f"function words linked {s['function words linked']}, target words covered "
              f"{s['target covered'] / max(1, s['target tokens']):.3f} of {s['target tokens']}")
    agree = collections.defaultdict(collections.Counter)
    for b in books:
        C = GB.classes(b); ref = word_refs(b)
        for w, c in C.items():
            if held_out(ref.get(w, "")):
                continue
            a, x = pa[b].get(w, set()), pb[b].get(w, set())
            if not a and not x:
                k = "neither"
            elif not a or not x:
                k = f"only {'B' if x else 'A'}"
            else:
                k = "same" if a == x else "A within B" if a < x else "B within A" if x < a else "overlap" if a & x else "disjoint"
            for key in ("all", "OT" if b not in GB.NT else "NT", c):
                agree[key][k] += 1
    print(f"content words, A = {ea}, B = {eb}:")
    for key in ("all", "OT", "NT", "verb", "noun", "adj"):
        c = agree.get(key)
        if c:
            n = sum(c.values()); print(f"  {key} ({n}): " + ", ".join(f"{k} {v / n:.3f}" for k, v in c.most_common()))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2], a[3], a[4], a[5:] or ["RUT", "JON", "MRK", "PHM"])
