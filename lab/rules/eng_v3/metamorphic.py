"""§4a kind 3: swap tests. Every dev verb in the present active indicative 3S (statements) is put into the 2S in the source
(person, morph code), re-rendered, and checked: (a) the head word has no +s; (b) 'you' comes before it unless the clause has
an explicit subject; (c) nothing else in the rendering changed except that pronoun and the suffix. Also 3S -> 3P.
Run per engine stage on the TRAIN pool (env TRAIN, default nogospels)."""
import collections, copy, json, os, sys
os.environ.setdefault("TRAIN", "nogospels")
import engine as E, cells as CL
CL_vocab = None


def build(stage, C, train):
    if stage.startswith("e8"):
        import final_eval
        return final_eval.build(C, train, stage)
    lex, lem = E.learn_lexicon(C, train)
    eng = E.Engine(lex, lem, E.learn_order(C, train))
    if stage in ("e3", "e5", "e6", "e7"):
        eng.ctxlex = E.CtxLex(C, train)
    if stage in ("e5", "e6", "e7"):
        eng.factored = E.Factored(C, train, eng.ctxlex); eng.ctx_first = True
    if stage in ("e6", "e7"):
        import gen6
        eng.gen6 = gen6.Gen6(C, train, eng.ctxlex, eng.factored); eng.memory_first = stage == "e7"
    return eng


def main():
    C = E.Corpus(); train = [r for r in C.split("train") if C.verses[r]["book"] not in {"MAT", "LUK", "JHN"}]
    out = {}
    for stage in os.environ.get("STAGES", "e1,e3,e5,e6,e7").split(","):
        eng = build(stage, C, train)
        if CL.VOCAB is None:
            CL.VOCAB = collections.Counter(w.lower() for v in C.verses.values() for w in v["words"])
        res = collections.Counter(); ex = []
        for ref in C.split("dev"):
            cx = CL.contexts(C, ref)
            for t in C.tok[ref]:
                if t["class"] != "verb" or (t["tense"], t["voice"], t["mood"], t["person"], t["number"]) != ("present", "active", "indicative", "third", "singular") or cx[t["key"]]["q"]:
                    continue
                for target, code in (("2S", ("second", "singular", "2S")), ("3P", ("third", "plural", "3P"))):
                    t2 = copy.copy(t); t2["person"], t2["number"] = code[0], code[1]; t2["morph"] = t["morph"][:-2] + code[2]
                    w1, _ = eng.render(t); w2, how = eng.render(t2)
                    pre, core, post = CL.split_rendering(w2)
                    if not core:
                        res[f"{target} no core"] += 1; continue
                    h = CL.head(t2, core); suf = CL.lemmatize(h)[1]
                    subj = cx[t["key"]]["subj"]
                    res[f"{target} n"] += 1
                    res[f"{target} no +s"] += suf != "+s"
                    want = "you" if target == "2S" else "they"
                    if not subj:
                        res[f"{target} n no-subject"] += 1; res[f"{target} pronoun"] += want in pre
                    p1, c1, _ = CL.split_rendering(w1)
                    res[f"{target} same verb"] += bool(c1) and CL.lemmatize(CL.head(t, c1))[0] == CL.lemmatize(h)[0]
                    if len(ex) < 8 and target == "2S":
                        ex.append((ref, " ".join(w1), "->", " ".join(w2), how))
        r = {k: v for k, v in res.items()}
        for tg in ("2S", "3P"):
            n = res[f"{tg} n"]
            r[f"{tg}: head without +s"] = round(res[f"{tg} no +s"] / max(1, n), 3)
            r[f"{tg}: pronoun where no subject"] = round(res[f"{tg} pronoun"] / max(1, res[f"{tg} n no-subject"]), 3)
            r[f"{tg}: same English verb as the 3S"] = round(res[f"{tg} same verb"] / max(1, n), 3)
        r["examples"] = ex
        out[stage] = r
        print(stage, {k: v for k, v in r.items() if ":" in k})
    json.dump(out, open(os.path.join(E.PRIV, "results/metamorphic_person" + ("_" + os.environ["STAGES"].replace(",", "_") if os.environ.get("STAGES") else "") + ".json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
