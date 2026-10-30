#!/usr/bin/env python3
"""The grammar bridge beside the lexeme bridge: Hebrew verb form (MACULA's conjugation `type` and `stem`) against Greek verb form
(GLAUx's tense, voice, mood) wherever a Hebrew verb and a Greek verb stand in the same verse (the Septuagint verse pairs of
strong_bridge.py's lxx tier) and are lexeme-bridge equivalents (any tier). Counts and the two conditionals, so a clause
retriever can score how well an NT clause's tense fits an OT clause's conjugation, and the reverse.

Writes $PRIV/bridge/grammar_bridge.json: {"pairs": [[hebrew form, greek form, count], ...], "h2g": {hebrew form: [[greek form, p],
...]}, "g2h": {...}} with hebrew form = "type|stem" (e.g. "wayyiqtol|qal") and greek form = "tense|voice|mood" (e.g.
"aorist|active|indicative"), and prints the main correspondences.

    . ./env.sh; ~/sil-study/.venv/bin/python -I lab/bridge/grammar_bridge.py [--macula private/rules/data/orig/macula-hebrew.tsv]
        [--bridge strong_bridge_bq.json --tiers macula lxx --out grammar_bridge_bq]   (the reference for bcv-query's build: no jev tier)

No thresholds: every form pair with a count is kept (the conditionals are computed over all of them); a verb pair counts when the
Hebrew verb's Strong's number and the Greek verb's are linked in the lexeme bridge (the chosen tiers) and stand in the same verse
after both are mapped to the English scheme (TVTMS maps from lexeme-aligner's bibles_vrs: org-to-eng, lxx-to-eng). Greek verbs:
GLAUx lxx_words with canonical = 1, a strong, and a morph V.<tense><voice><mood>... (persons and numbers ignored)."""
import argparse, collections, csv, json, os, re, sqlite3

PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")
BCV = os.environ["BCV_COMMONS"]
SPINE = os.path.join(os.environ["ALIGNER_DATA"], "lexeme-spine-macula.db")
GLAUX = os.path.join(BCV, "bcv-query", "shoresh", "lxx", "data", "lxx-glaux.db")
VRS = os.path.join(BCV, "lexeme-aligner", "config", "bibles_vrs")
TENSE = {"P": "present", "I": "imperfect", "F": "future", "A": "aorist", "X": "perfect", "Y": "pluperfect"}
VOICE = {"A": "active", "M": "middle", "P": "passive", "E": "middle/passive", "D": "middle deponent", "O": "passive deponent", "N": "middle/passive deponent"}
MOOD = {"I": "indicative", "S": "subjunctive", "O": "optative", "M": "imperative", "D": "imperative", "N": "infinitive", "P": "participle"}


def vrs_map(name):
    d = json.load(open(os.path.join(VRS, name), encoding="utf-8"))
    return {e["s"]: e["t"] for e in d["map"] if "title" not in e["t"]}


def greek_form(morph):
    """GLAUx 'V.AAI3S' -> 'aorist|active|indicative'; None when not a finite/non-finite verb form we can read."""
    m = re.match(r"V\.([PIFAXY])([AMPEDON])([ISOMDNP])", morph or "")
    return f"{TENSE[m.group(1)]}|{VOICE[m.group(2)]}|{MOOD[m.group(3)]}" if m else None


def main(a):
    B = json.load(open(os.path.join(PRIV, "bridge", a.bridge), encoding="utf-8"))
    h2g = {int(h): {g for g, t, *_ in v if t in a.tiers} for h, v in B["h2g"].items()}
    o2e = vrs_map("org-to-eng.json"); l2e = vrs_map("lxx-to-eng.json")
    # Hebrew verbs per English-scheme verse: (strong, form) from MACULA's type/stem (per occurrence, by the spine's ref)
    hform = {}
    with open(a.macula, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["class"] == "verb":
                hform[row["xml:id"][1:]] = f"{row.get('type') or '?'}|{row.get('stem') or '?'}"
    hv = collections.defaultdict(list)
    db = sqlite3.connect(SPINE)
    for key, b, c, v, s in db.execute("select key, book, chapter, verse, strong from spine_words where lexeme like 'hbo:%' and strong is not null"):
        if key in hform:
            r = f"{b} {c}:{v}"; hv[o2e.get(r, r)].append((s, hform[key]))
    gv = collections.defaultdict(list)
    for b, c, v, s, morph in sqlite3.connect(GLAUX).execute("select book, chapter, verse, strong, morph from lxx_words where canonical = 1 and strong is not null and morph like 'V.%'"):
        gf = greek_form(morph)
        if gf:
            r = f"{b} {c}:{v}"; gv[l2e.get(r, r)].append((s, gf))
    pairs = collections.Counter(); n_verses = 0
    for r in set(hv) & set(gv):
        n_verses += 1
        for hs, hf in hv[r]:
            eq = h2g.get(hs, set())
            for gs, gf in gv[r]:
                if gs in eq:
                    pairs[(hf, gf)] += 1
    print(f"verses with both sides {n_verses:,}; verb pairs (lexeme-bridged, same verse) {sum(pairs.values()):,}; distinct form pairs {len(pairs):,}")
    hcount, gcount = collections.Counter(), collections.Counter()
    for (hf, gf), c in pairs.items():
        hcount[hf] += c; gcount[gf] += c
    out = {"verses": n_verses, "pairs": [[hf, gf, c] for (hf, gf), c in pairs.most_common()],
           "h2g": {hf: [[gf, round(c / hcount[hf], 3)] for (h2, gf), c in pairs.most_common() if h2 == hf] for hf in hcount},
           "g2h": {gf: [[hf, round(c / gcount[gf], 3)] for (hf, g2), c in pairs.most_common() if g2 == gf] for gf in gcount}}
    p = os.path.join(PRIV, "bridge", a.out + ".json"); json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    with open(os.path.join(PRIV, "bridge", a.out + ".tsv"), "w", encoding="utf-8") as f:   # the table form: one row per form pair
        f.write("hebrew_form\tgreek_form\tcount\tp_greek_given_hebrew\tp_hebrew_given_greek\n")
        for (hf, gf), c in sorted(pairs.items(), key=lambda x: (x[0][0], -x[1], x[0][1])):
            f.write(f"{hf}\t{gf}\t{c}\t{c / hcount[hf]:.5f}\t{c / gcount[gf]:.5f}\n")
    print("written", p, "and .tsv")
    for hf, n in hcount.most_common(12):
        print(f"{hf:28s} {n:6,}  " + "; ".join(f"{gf} {p:.2f}" for gf, p in out['h2g'][hf][:3]))
    print("--- Greek -> Hebrew")
    for gf, n in gcount.most_common(10):
        print(f"{gf:36s} {n:6,}  " + "; ".join(f"{hf} {p:.2f}" for hf, p in out['g2h'][gf][:3]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--macula", default=os.path.join(PRIV, "data", "orig", "macula-hebrew.tsv"))
    ap.add_argument("--bridge", default="strong_bridge.json", help="the lexeme bridge (under $PRIV/bridge) whose pairs say which verbs are equivalents")
    ap.add_argument("--tiers", nargs="*", default=["macula", "lxx", "jev"], help="lexeme-bridge tiers that count (bcv-query's build: macula lxx)")
    ap.add_argument("--out", default="grammar_bridge")
    main(ap.parse_args())
