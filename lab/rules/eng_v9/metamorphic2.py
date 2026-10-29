"""§4a kind 3, the other features: swap tests for tense, voice and noun number (person: metamorphic.py). Each dev token of the
base cell is changed in the source (its feature and morph code), rendered again, and checked against what the swap should do
in English and nothing more. The checks are the linguist's expectations of English, written here as tests; the engine never
sees them.

  aorist    V present active indicative 3S statement -> aorist: the head is marked past (a suffix +ed/+d/+ied, or another word
            than the present's head that is not the present with +s), no "will" before it
  future    the same verbs -> future: "will" or "shall" before the head, the head without +s
  passive   the same verbs -> present passive: a form of "be" before the head
  plural    nouns nominative/accusative singular -> plural: the head changes (+s/+es/+ies or another word), no "a"/"an" before it
  right form: the future's head is a base form (a word the BSB has after will/shall/to), the passive's a participle (after
            been/be/being), the aorist's and the plural's a corpus word; rates over the swaps with a content word ("no core": the
            engine rendered function words only, as εἰμί "is")
  only to forms the lemma has in the training pool (εἰμί has no aorist or passive; a deponent's future is middle)
  every swap: "same rest" = the rendering minus the function words and the head is unchanged (no other word moves in)

Negation is a source word (οὐ, μή) rendered by its own entry, not a feature of the verb: a swap would insert a word, which
the order rules cannot place yet; it is left out.
    [HOLD=1] ~/sil-study/.venv/bin/python metamorphic2.py   -> results/metamorphic_features[_B].json (HOLD: see hold())"""
import collections, copy, json, os, sys
os.environ.setdefault("TRAIN", "nogospels")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import engine as E, cells as CL, metamorphic as M  # noqa: E402

BE = {"is", "are", "was", "were", "be", "been", "being", "am"}
BASE, PPART = set(), set()   # English words the BSB uses after will/shall/to (base forms), after been/be/being (participles)


def learn_forms(C):
    a, b = collections.Counter(), collections.Counter()
    for v in C.verses.values():
        w = [x.lower() for x in v["words"]]
        for x, y in zip(w, w[1:]):
            if x in ("will", "shall", "to"):
                a[y] += 1
            if x in ("been", "be", "being"):
                b[y] += 1
    BASE.update(k for k, n in a.items() if n >= 2); PPART.update(k for k, n in b.items() if n >= 2)


ATTESTED = set()   # (lemma, morph) in the training pool: a swap goes only to a form the lemma has


def verb_swaps(t):
    m = t["morph"]
    for name, tense, voice, codes in (("aorist", "aorist", "active", ("AAI", "2AAI", "ADI", "2ADI", "AMI", "2AMI")),
                                      ("future", "future", "active", ("FAI", "FMI", "FDI")),
                                      ("passive", "present", "passive", ("PPI",))):
        for code in codes:
            m2 = m.replace("PAI", code)
            if (t["lemma"], m2) in ATTESTED:
                t2 = copy.copy(t); t2["tense"], t2["voice"] = tense, voice; t2["morph"] = m2
                yield name, t2
                break


def check(name, t, w1, w2):
    p1, c1, _ = CL.split_rendering(w1); p2, c2, q2 = CL.split_rendering(w2)
    if not c2:
        return None
    h1 = CL.head(t, c1) if c1 else ""; h2 = CL.head(t, c2)
    stem2, suf2 = CL.lemmatize(h2)
    r = {"same rest": CL.rest(t, c1) == CL.rest(t, c2) if c1 else False}
    if name == "aorist":
        stem1 = CL.lemmatize(h1)[0] if h1 else ""
        r["marked"] = (suf2 in ("+ed", "+d", "+ied") or (h2 != h1 and h2 != stem1 and suf2 != "+s")) and not {"will", "shall"} & set(p2)
        r["right form"] = r["marked"] and CL.VOCAB.get(h2, 0) >= 1 and (h2 not in BASE or h2 in PPART)
    elif name == "future":
        r["marked"] = bool({"will", "shall"} & set(p2)) and suf2 != "+s"
        r["right form"] = r["marked"] and h2 in BASE
    elif name == "passive":
        r["marked"] = bool(BE & set(p2))
        r["right form"] = r["marked"] and h2 in PPART and h2 not in BASE - PPART
    elif name == "plural":
        r["marked"] = h2 != h1 and not {"a", "an"} & set(p2)
        r["right form"] = r["marked"] and CL.VOCAB.get(h2, 0) >= 1
    return r


def hold(C):
    """env HOLD=1: train on the nogospels pool minus sample B (1,500 verses, seed 8 as in auto.py) and test on B; else the
    pool and dev"""
    import random
    train = [r for r in C.split("train") if C.verses[r]["book"] not in {"MAT", "LUK", "JHN"}]
    if os.environ.get("HOLD"):
        sA = set(random.Random(7).sample(train, 1500))
        B = random.Random(8).sample([r for r in train if r not in sA], 1500)
        return [r for r in train if r not in set(B)], B
    return train, C.split("dev")


def main():
    C = E.Corpus(); train, refs = hold(C)
    CL.VOCAB = collections.Counter(w.lower() for v in C.verses.values() for w in v["words"]); learn_forms(C)
    ATTESTED.update((t["lemma"], t["morph"]) for r in train for t in C.tok[r])
    out = {}
    for stage in os.environ.get("STAGES", "e1,e3,e5,e6,e7").split(","):
        eng = M.build(stage, C, train)
        res = collections.defaultdict(collections.Counter); ex = collections.defaultdict(list)
        for ref in refs:
            cx = CL.contexts(C, ref)
            for t in C.tok[ref]:
                swaps = []
                if t["class"] == "verb" and (t["tense"], t["voice"], t["mood"], t["person"], t["number"]) == \
                        ("present", "active", "indicative", "third", "singular") and not cx[t["key"]]["q"] and "PAI" in t["morph"]:
                    swaps = list(verb_swaps(t))
                elif t["class"] == "noun" and t["number"] == "singular" and t["gcase"] in ("nominative", "accusative") and len(t["morph"]) == 5 and t["morph"][-2] == "S":
                    t2 = copy.copy(t); t2["number"] = "plural"; t2["morph"] = t["morph"][:-2] + "P" + t["morph"][-1]
                    swaps = [("plural", t2)] if (t["lemma"], t2["morph"]) in ATTESTED else []
                for name, t2 in swaps:
                    w1, _ = eng.render(t); w2, how = eng.render(t2)
                    r = check(name, t, w1, w2)
                    s = res[name]; s["n"] += 1
                    if r is None:
                        s["no core"] += 1; continue
                    for k, v in r.items():
                        s[k] += v
                    if len(ex[name]) < 5:
                        ex[name].append(f"{ref} {t['text']}: «{' '.join(w1)}» -> «{' '.join(w2)}» ({how})")
        out[stage] = {}
        for n, s in res.items():
            k = max(1, s["n"] - s["no core"])
            out[stage][n] = {"n": s["n"], "no core": s["no core"], "marked": round(s["marked"] / k, 3),
                             "right form": round(s["right form"] / k, 3), "same rest": round(s["same rest"] / k, 3), "examples": ex[n]}
        print(stage, {n: (v["n"], v["no core"], v["marked"], v["right form"], v["same rest"]) for n, v in out[stage].items()}, flush=True)
    json.dump(out, open(os.path.join(E.PRIV, "results/metamorphic_features" + ("_B" if os.environ.get("HOLD") else "") + ("_" + os.environ["STAGES"].replace(",", "_") if os.environ.get("STAGES") else "") + ".json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
