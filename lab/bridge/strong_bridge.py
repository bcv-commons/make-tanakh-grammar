#!/usr/bin/env python3
"""The Hebrew <-> Greek lexeme bridge, both ways, for every target language (one Strong's lexeme on each side; no English, no
LLM). Three tiers, each marked in the output so a consumer can choose how far to trust it:

  macula  MACULA Hebrew's curated per-occurrence `greekstrong` column (Clear-Bible/macula-hebrew, WLC TSV, CC BY 4.0): every
          (Hebrew, Greek) pair with its occurrence count, no cut (bcv-query's resources/lxx_bridge.tsv keeps the top 4 per
          Hebrew lexeme with count >= 3; this keeps all, and so has the Greek -> Hebrew direction whole).
  lxx     verse co-occurrence of the Hebrew text (the lexeme spine, Hebrew numbering) with the Septuagint (bcv-query's GLAUx
          store, CC BY-SA 4.0; Septuagint numbering), both mapped to the English scheme by lexeme-aligner's bibles_vrs maps
          (TVTMS, CC BY 4.0); Dice over verse sets, content words only, canonical books. A top-up for lexemes macula has no
          pair for (names among them), and a second opinion elsewhere.
  jev     bridge_jev.py: for each frequent lexeme the two tiers leave out, code proposes candidates (shared gloss words, weak
          co-occurrence) and Jev (TypeSafe's System One model) picks one or none; its probability is the score. Passed in with
          --jev bridge/strong_bridge_jev.tsv.

Writes $PRIV/bridge/strong_bridge.tsv (hebrew, greek, tier, count, score: macula p(greek|hebrew), lxx Dice) and
strong_bridge.json ({"h2g": {H: [[G, tier, count, score], ...]}, "g2h": {...}, "lemma2h": {Hebrew lemma text: [H, ...]},
"names": {"h": [...], "g": [...]}}); prints each testament's coverage by content token after each tier and the frequent gaps
left. The output is share-alike (GLAUx) where the lxx tier is used; the macula tier alone is CC BY.

    . ./env.sh; ~/sil-study/.venv/bin/python -I lab/bridge/strong_bridge.py --macula /path/to/macula-hebrew.tsv
        [--min-count 3] [--min-dice 0.3] [--out bridge/strong_bridge]"""
import argparse, collections, csv, json, os, re, sqlite3

PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")
BCV = os.environ["BCV_COMMONS"]
SPINE = os.path.join(os.environ["ALIGNER_DATA"], "lexeme-spine-macula.db")
GLAUX = os.path.join(BCV, "bcv-query", "shoresh", "lxx", "data", "lxx-glaux.db")
VRS = os.path.join(BCV, "lexeme-aligner", "config", "bibles_vrs")


def vrs_map(name):
    """{source ref: target ref} for the renumbered verses of a bibles_vrs map (identity elsewhere; titles dropped)."""
    d = json.load(open(os.path.join(VRS, name), encoding="utf-8"))
    return {e["s"]: e["t"] for e in d["map"] if "title" not in e["t"]}


def ref(book, ch, v):
    return f"{book} {ch}:{v}"


def macula_tier(path, min_count):
    """(Hebrew strong, Greek strong) -> count from MACULA's greekstrong column; Hebrew names from its `type` column."""
    pairs = collections.Counter(); names = set(); hnum = collections.Counter(); types = collections.Counter()
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            mh = re.match(r"(\d+)", (row.get("strongnumberx") or "").strip())
            if not mh:
                continue
            h = int(mh.group(1)); hnum[h] += 1
            t = (row.get("type") or "").strip(); types[t] += 1
            if t == "proper":
                names.add(h)
            mg = re.match(r"(\d+)", (row.get("greekstrong") or "").strip())
            if mg:
                pairs[(h, int(mg.group(1)))] += 1
    print("macula: Hebrew `type` values", dict(types.most_common(8)))
    tot = collections.Counter()
    for (h, g), c in pairs.items():
        tot[h] += c
    return {(h, g): (c, round(c / tot[h], 3)) for (h, g), c in pairs.items() if c >= min_count}, names


def lxx_tier(min_count, min_dice):
    """Dice over verse sets between the Hebrew spine's content lexemes and GLAUx's, both in the English scheme."""
    o2e = vrs_map("org-to-eng.json"); l2e = vrs_map("lxx-to-eng.json")
    hv = collections.defaultdict(set)     # eng ref -> Hebrew strongs
    db = sqlite3.connect(SPINE)
    for b, c, v, s in db.execute("select book, chapter, verse, strong from spine_words where lexeme like 'hbo:%' and is_content = 1 "
                                 "and strong is not null"):
        r = ref(b, c, v); hv[o2e.get(r, r)].add(s)
    cap = collections.defaultdict(lambda: [0, 0])    # Greek names: lexemes whose NT surfaces are capitalised (SQLite's upper() is ASCII-only)
    for s, surf in db.execute("select strong, surface from spine_words where lexeme like 'grc:%' and strong is not null"):
        cap[s][0] += surf[:1].isupper(); cap[s][1] += 1
    gnames = {s for s, (u, n) in cap.items() if u / n > 0.8}
    gv = collections.defaultdict(set)
    db = sqlite3.connect(GLAUX)
    for b, c, v, s in db.execute("select book, chapter, verse, strong from lxx_words where canonical = 1 and is_content = 1 "
                                 "and strong is not null"):
        r = ref(b, c, v); gv[l2e.get(r, r)].add(s)
    both = set(hv) & set(gv)
    print(f"lxx: Hebrew verses {len(hv):,}, Septuagint verses {len(gv):,}, matched {len(both):,}")
    ch, cg, chg = collections.Counter(), collections.Counter(), collections.Counter()
    for r in both:
        for h in hv[r]:
            ch[h] += 1
        for g in gv[r]:
            cg[g] += 1
        for h in hv[r]:
            for g in gv[r]:
                chg[(h, g)] += 1
    out = {}
    for (h, g), c in chg.items():
        if c >= min_count:
            d = 2 * c / (ch[h] + cg[g])
            if d >= min_dice:
                out[(h, g)] = (c, round(d, 3))
    return out, gnames


def coverage(db, lang, side, names, label):
    tok = collections.Counter(); lemma_of = {}
    for strong, lemma, n in db.execute("select strong, lemma, count(*) from spine_words where lexeme like ? and is_content = 1 "
                                       "and strong is not null group by strong, lemma", (f"{lang}:%",)):
        tok[strong] += n; lemma_of[strong] = lemma
    total = sum(tok.values()); hit = sum(n for s, n in tok.items() if s in side)
    gaps = [(s, n) for s, n in tok.most_common() if s not in side]
    gaps_nn = [(s, n) for s, n in gaps if s not in names]
    print(f"{label}: content tokens {total:,}, bridged {hit:,} ({hit / total:.3f}); lexemes {len(tok):,}, bridged "
          f"{sum(1 for s in tok if s in side):,}; unbridged tokens that are names {sum(n for s, n in gaps if s in names):,}; "
          f"frequent unbridged non-names: " + ", ".join(f"{lemma_of[s]} ({n})" for s, n in gaps_nn[:12]))
    return [[s, lemma_of[s], n, s in names] for s, n in gaps]


SPINE_MERGES = {}   # MACULA's Hebrew number -> the spine's strong where they differ (derived in main; 8 numbers in the 2026-10-12 spine)


def spine_merges(macula_path):
    """Every MACULA strongnumberx that the spine files under another strong (H2009->H2005, H0977->H0970, H8055->H8056, ...),
    by the tokens both carry: the spine's key = MACULA's xml:id without its first letter. bcv-query's note, 2026-10-30."""
    sk = dict(sqlite3.connect(SPINE).execute("select key, strong from spine_words where lexeme like 'hbo:%' and strong is not null"))
    c = collections.Counter()
    with open(macula_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            m = re.match(r"(\d+)", row.get("strongnumberx") or ""); k = row["xml:id"][1:]
            if m and k in sk and int(m.group(1)) != int(str(sk[k]).lstrip("H")):
                c[(int(m.group(1)), int(str(sk[k]).lstrip("H")))] += 1
    out = {}
    for (a, b), n in c.most_common():
        out.setdefault(a, b)
    return out


def read_tiers(d):
    """bcv-query's resources/lxx_bridge_tiers (macula.tsv CC BY 4.0, glaux.tsv CC BY-SA 4.0): hebrew_strong greek_strong tier count score"""
    out = {}
    for name in ("macula", "glaux"):
        pairs = {}
        with open(os.path.join(d, f"{name}.tsv"), encoding="utf-8") as f:
            next(f)
            for line in f:
                h, g, t, c, sc = line.rstrip("\n").split("\t"); pairs[(int(h[1:]), int(g[1:]))] = (int(c), float(sc))
        out[name] = pairs
    return out["macula"], out["glaux"]


def merge_spine(pairs):
    """pairs keyed by MACULA's Hebrew number -> keyed as the spine looks them up (merged numbers: counts summed, best score kept)"""
    out = {}
    for (h, g), (c, sc) in pairs.items():
        k = (SPINE_MERGES.get(h, h), g)
        if k in out:
            out[k] = (out[k][0] + c, max(out[k][1], sc))
        else:
            out[k] = (c, sc)
    return out


def main(a):
    SPINE_MERGES.update(spine_merges(a.macula)); print("spine merges:", {f"H{k:04d}": f"H{v:04d}" for k, v in SPINE_MERGES.items()})
    mac, hnames = macula_tier(a.macula, a.min_count)
    if a.tiers:                                       # bcv-query's published tiers replace our own build of the same two
        mac2, lxx = read_tiers(a.tiers); gnames = lxx_tier(a.min_count, a.min_dice)[1] if a.lxx_names else set()
        print(f"tiers from {a.tiers}: macula {len(mac2):,} pairs (ours {len(mac):,}, identical: {mac2.keys() == mac.keys()}), glaux {len(lxx):,}")
        mac = mac2
    else:
        lxx, gnames = lxx_tier(a.min_count, a.min_dice)
    mac, lxx = merge_spine(mac), merge_spine(lxx)
    print(f"macula pairs {len(mac):,} (Hebrew {len({h for h, g in mac}):,}, Greek {len({g for h, g in mac}):,}); "
          f"lxx pairs {len(lxx):,} (Hebrew {len({h for h, g in lxx}):,}, Greek {len({g for h, g in lxx}):,}); "
          f"in both {len(set(mac) & set(lxx)):,}")
    jev = {}
    if a.jev:
        with open(os.path.join(PRIV, a.jev), encoding="utf-8") as f:
            next(f)
            for line in f:
                h, g, t, c, s = line.rstrip("\n").split("\t"); jev[(int(h[1:]), int(g[1:]))] = (int(c), float(s))
        jev = merge_spine(jev); print(f"jev pairs {len(jev):,}")
    h2g, g2h = collections.defaultdict(list), collections.defaultdict(list)
    rows = []
    for tier, pairs in (("macula", mac), ("lxx", lxx), ("jev", jev)):
        for (h, g), (c, s) in sorted(pairs.items()):
            rows.append((h, g, tier, c, s)); h2g[h].append([g, tier, c, s]); g2h[g].append([h, tier, c, s])
    db = sqlite3.connect(SPINE)
    lemma2h = collections.defaultdict(collections.Counter)
    for lemma, strong in db.execute("select lemma, strong from spine_words where lexeme like 'hbo:%' and strong is not null"):
        lemma2h[lemma][strong] += 1
    mac_h = {h for h, g in mac}; mac_g = {g for h, g in mac}
    coverage(db, "hbo", mac_h, hnames, "OT, Hebrew -> Greek, macula only")
    gaps_ot = coverage(db, "hbo", set(h2g), hnames, "OT, Hebrew -> Greek, all tiers")
    coverage(db, "grc", mac_g, gnames, "NT, Greek -> Hebrew, macula only")
    gaps_nt = coverage(db, "grc", set(g2h), gnames, "NT, Greek -> Hebrew, all tiers")
    todo = {"nt": [g for g in gaps_nt if g[2] >= a.min_todo and not g[3]], "ot": [g for g in gaps_ot if g[2] >= a.min_todo and not g[3]]}
    print(f"to do for a third tier (>= {a.min_todo} tokens, no name): NT {len(todo['nt'])} lexemes, {sum(g[2] for g in todo['nt']):,} tokens; "
          f"OT {len(todo['ot'])} lexemes, {sum(g[2] for g in todo['ot']):,} tokens")
    out = os.path.join(PRIV, a.out); os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out + ".tsv", "w", encoding="utf-8") as f:
        f.write("hebrew\tgreek\ttier\tcount\tscore\n")
        for h, g, t, c, s in rows:
            f.write(f"H{h:04d}\tG{g:04d}\t{t}\t{c}\t{s}\n")
    json.dump({"h2g": {h: sorted(v, key=lambda x: (-x[2])) for h, v in h2g.items()},
               "g2h": {g: sorted(v, key=lambda x: (-x[2])) for g, v in g2h.items()},
               "lemma2h": {l: [s for s, _ in c.most_common()] for l, c in lemma2h.items()},
               "names": {"h": sorted(hnames), "g": sorted(gnames)}, "gaps": {"ot": gaps_ot[:1000], "nt": gaps_nt[:1000]}, "todo": todo,
               "sources": {"macula": "Clear-Bible/macula-hebrew WLC greekstrong, CC BY 4.0" + (" (bcv-query resources/lxx_bridge_tiers/macula.tsv)" if a.tiers else ""),
                           "lxx": ("bcv-query resources/lxx_bridge_tiers/glaux.tsv (GLAUx, CC BY-SA 4.0; bcv-query vrsmap)" if a.tiers else
                                   "GLAUx via bcv-query lxx-glaux.db, CC BY-SA 4.0; verse maps TVTMS via lexeme-aligner bibles_vrs, CC BY 4.0"),
                           "jev": "bridge_jev.py: Jev's choice among gloss-matched candidates; score = its probability"}},
              open(out + ".json", "w", encoding="utf-8"), ensure_ascii=False)
    print("written", out + ".tsv", out + ".json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--macula", required=True, help="macula-hebrew.tsv (WLC/tsv in Clear-Bible/macula-hebrew)")
    ap.add_argument("--min-count", type=int, default=3); ap.add_argument("--min-dice", type=float, default=0.3)
    ap.add_argument("--out", default="bridge/strong_bridge"); ap.add_argument("--min-todo", type=int, default=10)
    ap.add_argument("--tiers", default="", help="bcv-query's resources/lxx_bridge_tiers dir: read its macula and glaux tiers (the jev tier stays ours)")
    ap.add_argument("--lxx-names", action="store_true", help="with --tiers: still build our lxx tier once, only for the Greek name list")
    ap.add_argument("--jev", default="", help="bridge/strong_bridge_jev.tsv from bridge_jev.py judge, as a third tier")
    main(ap.parse_args())
