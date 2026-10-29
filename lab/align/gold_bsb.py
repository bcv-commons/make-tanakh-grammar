#!/usr/bin/env python3
"""align-text's alignment of the BSB scored against the BSB's own Translation Tables (the lab's gold: data/nt.db, data/ot.db,
built by data/build.py and build_ot.py from bsb_tables.tsv). Per source word (Greek word; Hebrew word = its morphemes): the
BSB word positions align-text links to it (main and function channels) against the table's (its supplied words left out).

  links P / R / F  over (source word, BSB position) pairs, on the verses the gold keeps (its chunks rebuild the verse)
  word exact       a gold word whose predicted positions equal the gold's; word any: they share one
  by class         the source word's class (MACULA: the content morpheme's class)

Content words = the source words of the published content index (_index/<BOOK>_keys). align-text's compact output links
only these (v0.1.0 has no function-word channel); its --jev layer has one, and there the gold's other words are scored
too, as "function" (by their own class in the breakdown).

The lab's held-out test chapters (split = test: MRK 5, 10, 15; GEN 22, 37, 44) are left out.

    . ./env.sh; /usr/bin/python3 lab/align/gold_bsb.py LAYERS EDITION [BOOK ...]
    LAYERS = align-text's OUT/compact (EDITION e.g. eng_bsb4) or OUT/full-alignments-llm (EDITION eng_bsb4+llm+jev-v4)"""
import collections, glob, json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.environ["MAKE_TANAKH_WORK"]
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
sys.path.insert(0, os.path.join(R, "scripts"))
import full_align as FA  # noqa: E402
NT = {"MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT",
      "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"}


def added(s):
    """the "+pos>own" entries of a compact string: {("c"|"f", ordinal): [positions]}"""
    out = collections.defaultdict(list)
    for e in (s or "").split():
        if e.startswith("+"):
            for part in e[1:].split(","):
                pos, _, own = part.partition(">")
                a, _, b = pos.partition("-")
                if own and a.isdigit() and (not b or b.isdigit()):
                    out[("f" if own.startswith("f") else "c", int(own.lstrip("f")))].extend(range(int(a), int(b or a) + 1))
    return out


def predicted(out, edition, book):
    """{source word id: set of positions} from align-text's compact file"""
    f = [p for p in glob.glob(os.path.join(out, "*", "*", edition, f"{book}_*.json")) if not p.endswith((".meta.json", ".extra.json"))]
    assert len(f) == 1, (book, f)
    main = json.load(open(f[0])); meta = json.load(open(f[0][:-5] + ".meta.json"))
    fns = meta.get("fn") or [None] * len(main)
    refs = list(FA.index(book, "lexemes")); keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys")
    assert len(refs) == len(main), (book, len(refs), len(main))
    word = (lambda k: k) if book in NT else (lambda k: k[:-1])
    pos = collections.defaultdict(set)
    for r, m, fs in zip(refs, main, fns):
        add = added(m)
        add.update({k: v for k, v in added(fs).items()})
        for kind, s, ks in (("c", m, keys.get(r, [])), ("f", fs, fkeys.get(r, []))):
            for o, ids in FA.parse(s).items():
                for k in (ks[o].split("+") if o < len(ks) and ks[o] else []):
                    pos[word(k)].update(ids + add.get((kind, o), []))
    return pos, any(fns)


def classes(book):
    """{content word id: class}: the source words of the content index (keys), Greek by token, Hebrew by its content morpheme"""
    db = "orig/grc.sqlite" if book in NT else "orig/heb.sqlite"
    cls = dict(sqlite3.connect(os.path.join(R, db)).execute("select key, class from tokens where book = ?", (book,)))
    word = (lambda k: k) if book in NT else (lambda k: k[:-1])
    return {word(m): cls.get(m, "?") for ks in FA.index(book, "keys").values() for k in ks for m in (k or "").split("+") if m}


class _FCls(dict):
    def __missing__(self, book):
        db = "orig/grc.sqlite" if book in NT else "orig/heb.sqlite"
        rows = sqlite3.connect(os.path.join(R, db)).execute("select key, class from tokens where book = ? order by key", (book,))
        out = {}
        for k, c in rows:
            out.setdefault(k if book in NT else k[:-1], c)
        self[book] = out
        return out


FCLS = _FCls()


def gold(book):
    """{source word id: set of positions} and the kept verses' split, from the lab's gold corpus"""
    db = sqlite3.connect(os.path.join(PRIV, "data", "nt.db" if book in NT else "ot.db"))
    split = dict(db.execute("select ref, split from verse where book = ?", (book,)))
    col = "key" if book in NT else "word"
    out = {}
    for w, ref, p, sup in db.execute(f"select {col}, ref, positions, supplied from link where ref like ?", (book + " %",)):
        if split.get(ref) != "test":
            g = set(json.loads(p)) - set(json.loads(sup))
            if g:
                out[w] = (ref, g)
    return out, split


def main(out, edition, books):
    tot = collections.Counter(); by = collections.defaultdict(collections.Counter)
    for b in books:
        G, split = gold(b); P, has_fn = predicted(out, edition, b); C = classes(b)
        kept = {r for r, s in split.items() if s != "test"}
        for w, (ref, g) in G.items():
            if w not in C and not has_fn:
                tot["gold function words (not scored)"] += 1; continue
            p = P.get(w, set()); c = C.get(w) or "function " + FCLS[b].get(w, "?")
            sets = (tot, by[c], by[b], by["content" if w in C else "function"])
            for t in sets:
                t["gold words"] += 1; t["gold links"] += len(g); t["pred links"] += len(p); t["hit links"] += len(g & p)
                t["word exact"] += g == p; t["word any"] += bool(g & p); t["word unlinked"] += not p
        print(f"{b}: {len(kept)} verses kept, {len(G)} gold words", file=sys.stderr)
    print(f"words scored: {tot['gold words']}; gold function words left out (no fn channel): "
          f"{tot['gold function words (not scored)']}", file=sys.stderr)
    rows = []
    for name, t in [("all", tot)] + sorted(by.items(), key=lambda x: -x[1]["gold words"]):
        P_ = t["hit links"] / max(1, t["pred links"]); R_ = t["hit links"] / max(1, t["gold links"]); F_ = 2 * P_ * R_ / max(1e-9, P_ + R_)
        rows.append({"set": name, "gold words": t["gold words"], "P": round(P_, 3), "R": round(R_, 3), "F": round(F_, 3),
                     "word exact": round(t["word exact"] / max(1, t["gold words"]), 3),
                     "word any": round(t["word any"] / max(1, t["gold words"]), 3),
                     "unlinked": round(t["word unlinked"] / max(1, t["gold words"]), 3)})
    print("| set | gold words | links P | R | F | word exact | word any | unlinked |\n|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['set']} | {r['gold words']} | {r['P']} | {r['R']} | {r['F']} | {r['word exact']} | {r['word any']} | {r['unlinked']} |")
    json.dump(rows, open(os.path.join(out, "..", f"gold.{edition}.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:] or ["RUT", "JON", "MRK", "PHM"])
