#!/usr/bin/env python3
"""E0 again (2026-10-26, after lexeme-aligner's fixes B1-B6): their eng_BSB+manual+bsb-tables layer (full-alignments-manual,
main) against the lab's own rebuild from the BSB tables (data/nt.db, data/ot.db), per source word. Their words: the link
spans of the word's tokens in `main` (content) and `fn` (function tokens), with the `+pos>owner` words that name those
tokens (their note: "read a link's span together with the `+` words that name its token"). OT words = the MACULA word (its
morpheme keys without the last digit), so prefixes, stem and suffix count together, as our rebuild has them.
Files are matched by the text fingerprint of our BSB verse words. Writes results/e0_layercheck_v1b.json.
    /usr/bin/python3 lab/rules/e0/layercheck.py"""
import collections, json, os, sqlite3, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE); R = os.environ["MAKE_TANAKH_WORK"]
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
sys.path.insert(0, os.path.join(R, "scripts"))
import full_align as FA, vrs  # noqa: E402

LAYER = "eng_BSB+manual+bsb-tables"
API = f"https://huggingface.co/api/datasets/bcv-commons/full-alignments-manual/tree/v1.0/e/eng/{LAYER}"
BASE = f"https://huggingface.co/datasets/bcv-commons/full-alignments-manual/resolve/v1.0/e/eng/{LAYER}"
DL = os.path.join(PRIV, "data/bsbfix/v1")


def spans(s, prof=""):
    """main / fn string (with its profile string, one character per entry) -> ({ord: positions}, {("c"|"f", ord): added
    positions}); entries with profile "." are views of a multi-word table row kept in `rows` (the row is keyed on one word, as
    in our rebuild) and are left out"""
    ents = (s or "").split()
    keep = ents   # views included: a row over the morphemes of one word shows on each; cross-word rows: see row_fix
    links = FA.parse(" ".join(keep))
    add = collections.defaultdict(list)
    for e in keep:
        if e.startswith("+"):
            for part in e[1:].split(","):
                pos, _, own = part.partition(">")
                if not own:
                    continue
                a, _, b = pos.partition("-")
                if a.isdigit() and (not b or b.isdigit()):
                    add[("f" if own.startswith("f") else "c", int(own.lstrip("f")))].extend(range(int(a), int(b or a) + 1))
    return links, add


def span_pos(sp):
    out = []
    for part in sp.lstrip("L").split(","):
        a, _, b = part.partition("-")
        if a.isdigit() and (not b or b.isdigit()):
            out += range(int(a), int(b or a) + 1)
    return out


def row_fix(rows_s, word_of):
    """`rows` entries over source tokens of more than one word: {word: positions to take away} for every word but the
    keyed token's (k<i>; a row's views put its span on each token)"""
    out = collections.defaultdict(set)
    for e in (rows_s or "").split():
        f = e.split(":")
        if len(f) < 2:
            continue
        srcs = f[0].split(","); ext = f[3:]
        ws = [word_of.get(x) for x in srcs]
        if len({w for w in ws if w}) < 2:
            continue
        ki = next((int(x[1:]) for x in ext if x[:1] == "k" and x[1:].isdigit()), 0)
        keyed = ws[ki] if ki < len(ws) else None
        for w in set(ws):
            if w and w != keyed:
                out[w].update(span_pos(f[1]))
    return out


def main():
    os.makedirs(DL, exist_ok=True)
    tree = [os.path.basename(f["path"]) for f in json.load(urllib.request.urlopen(API))]
    out = {}; full = []
    for test, db in (("NT", "nt.db"), ("OT", "ot.db")):
        c = sqlite3.connect(os.path.join(PRIV, "data", db))
        kcol = "key" if test == "NT" else "word"
        words = {r: json.loads(w) for r, w in c.execute("select ref, words from verse")}
        ours = {k: (r, set(json.loads(p))) for k, r, p in c.execute(f"select {kcol}, ref, positions from link")}
        books = sorted({r.split()[0] for r in words})
        # Psalm headings: our BSB verse 1 starts with the heading, their verse text leaves it out (fingerprint rule), so
        # their positions there are ours minus the heading's length (the leading words linked to the Hebrew title verse)
        head_off = {}
        if test == "OT":   # the heading's length: verse 1's prose line before its first poetry line in the BSB reference text
            import glob, re as _re
            for f in glob.glob(os.path.join(R, "reference/BSB/psa*.txt")):
                ch = int(os.path.basename(f)[3:6]); lines = open(f, encoding="utf-8").read().splitlines()
                for k, l in enumerate(lines):
                    if l.startswith("v1 "):
                        nxt = next((x for x in lines[k + 1:] if x.strip()), "")
                        if nxt.startswith("//"):
                            head = _re.sub(r"\{[^}]*\}", "", l[3:])
                            head_off[f"PSA {ch}:1"] = len(FA.tokenize(head))
                        break
        st = collections.Counter(); diffs = collections.Counter(); ex = []
        for book in books:
            rows = [(int(r.split()[1].split(":")[0]), int(r.split(":")[1]), " ".join(w)) for r, w in words.items() if r.split()[0] == book]
            fp = FA.text_fingerprint(rows)[0][:8]
            name = f"{book}_{fp}.json"
            if name not in tree:
                # our db leaves out the verses the rebuild could not match, so its fingerprint differs: take the book's
                # 8-hex file by name (a text difference would show as shifted positions)
                cand = [f for f in tree if f.startswith(book + "_") and f.endswith(".json") and not f.endswith(".meta.json") and len(f) == len(book) + 14]
                if len(cand) != 1:
                    st["books without a file"] += 1; continue
                name = cand[0]; st["books matched by name only"] += 1; byname = True
            else:
                st["books matched by fingerprint"] += 1; byname = False
            for n in (name, name[:-5] + ".meta.json"):
                if not os.path.exists(os.path.join(DL, n)):
                    urllib.request.urlretrieve(f"{BASE}/{n}", os.path.join(DL, n))
            main_s = json.load(open(os.path.join(DL, name), encoding="utf-8"))
            meta = json.load(open(os.path.join(DL, name[:-5] + ".meta.json"), encoding="utf-8"))
            fn_s = meta.get("fn") or [""] * len(main_s); wp = meta.get("wp") or [""] * len(main_s); fp_ = meta.get("fp") or [""] * len(main_s)
            refs = list(FA.index(book, "lexemes")); keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys")
            for i, r in enumerate(refs):
                if test == "OT":
                    ch, v = (int(x) for x in r.split(" ")[1].split(":"))
                    e = vrs.to_bsb(book.lower(), ch, v)
                    if not e or e[1] == "title":
                        continue
                    ref = f"{book} {int(e[0])}:{int(e[1])}"
                else:
                    ref = r
                if ref not in words:
                    continue
                theirs = collections.defaultdict(set)
                ml, ma = spans(main_s[i], wp[i] or ""); fl, fa = spans(fn_s[i] if i < len(fn_s) else "", fp_[i] or "")
                off = head_off.get(ref, 0)
                if off:
                    ml = {o: [x + off for x in ids] for o, ids in ml.items()}; fl = {o: [x + off for x in ids] for o, ids in fl.items()}
                    ma = {k: [x + off for x in v] for k, v in ma.items()}; fa = {k: [x + off for x in v] for k, v in fa.items()}
                    st["Psalm verses with the heading offset"] += 1
                fa_all = collections.defaultdict(list); joined_w = set()
                for k, v in list(ma.items()) + list(fa.items()):
                    fa_all[k] += v
                for kind, ks_ in (("c", keys.get(r, [])), ("f", fkeys.get(r, []))):
                    for kk in ks_:
                        if kk and "+" in kk:
                            for k in kk.split("+"):
                                joined_w.add(k.lstrip("n") if test == "NT" else k[:-1])
                for kind, links, ks in (("c", ml, keys.get(r, [])), ("f", fl, fkeys.get(r, []))):
                    for o, ids in links.items():
                        for k in (ks[o].split("+") if o < len(ks) and ks[o] else []):
                            w = k.lstrip("n") if test == "NT" else k[:-1]
                            theirs[w].update(ids); theirs[w].update(fa_all.get((kind, o), []))
                    word_of = {}
                for kind, ks in (("c", keys.get(r, [])), ("f", fkeys.get(r, []))):
                    for o, kk in enumerate(ks):
                        if kk:
                            word_of[f"{kind}{o}"] = (kk.split("+")[0].lstrip("n") if test == "NT" else kk.split("+")[0][:-1])
                for (kk, o), ids in fa_all.items():   # + words of a token with no link of its own
                        if kk == kind and o not in links and o < len(ks) and ks[o]:
                            for k in ks[o].split("+"):
                                theirs[k.lstrip("n") if test == "NT" else k[:-1]].update(ids)
                for w, take in row_fix(meta.get("rows", [""] * len(main_s))[i] if meta.get("rows") else "", word_of).items():
                    take = {x + off for x in take}
                    if w in theirs:
                        theirs[w] -= take
                        if not theirs[w]:
                            del theirs[w]
                for w, p in theirs.items():
                    o = ours.get(w)
                    if not o or o[0] != ref:
                        st["their word, not linked in ours"] += 1; continue
                    if w in joined_w:
                        st["words of joined tokens (not compared)"] += 1; continue
                    st["words compared"] += 1; st["compared, books by name" if byname else "compared, books by fingerprint"] += 1
                    if o[1] == p:
                        st["exact"] += 1; st["exact, books by name" if byname else "exact, books by fingerprint"] += 1
                    else:
                        kind = "they have more" if p > o[1] else "we have more" if p < o[1] else "different"
                        diffs[kind] += 1
                        wl = words[ref]; tw = [wl[x] for x in sorted(p) if x < len(wl)]
                        if not o[1] and any(x[:1].isupper() for x in tw):
                            diffs["of which: ours empty, theirs a name (the joined-token case)"] += 1
                        elif not o[1]:
                            diffs["of which: ours empty, theirs words"] += 1
                        joined = not o[1] and any(x[:1].isupper() for x in tw)
                        full.append((test, ref, w, "joined-name" if joined else kind, " ".join(wl[x] for x in sorted(p) if x < len(wl)),
                                     " ".join(wl[x] for x in sorted(o[1])), ",".join(map(str, sorted(p))), ",".join(map(str, sorted(o[1])))))
                        if len(ex) < 400 and not joined:
                            ex.append(f"{ref} {w}: theirs «{full[-1][4]}» ours «{full[-1][5]}»")
        n = st["words compared"]
        out[test] = {**st, "exact share": round(st["exact"] / max(1, n), 4), "differences": dict(diffs), "examples": ex}
        print(test, json.dumps({k: v for k, v in out[test].items() if k != "examples"}, ensure_ascii=False), *ex[:12], sep="\n  ")
    json.dump(out, open(os.path.join(PRIV, "results/e0_layercheck_v1b.json"), "w"), indent=1, ensure_ascii=False)
    with open(os.path.join(PRIV, "results/e0_layercheck_v1b_differences.tsv"), "w", encoding="utf-8") as f:
        f.write("testament\tref\tword_key\tkind\ttheirs\tours\ttheir_positions\tour_positions\n")
        for r in full:
            f.write("\t".join(r) + "\n")


if __name__ == "__main__":
    main()
