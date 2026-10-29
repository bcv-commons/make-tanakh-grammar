#!/usr/bin/env python3
"""Rung 1b: the same engine on the Hebrew OT -> BSB. Only the corpus adapter is new: the unit is the Hebrew word (its MACULA
morphemes), with the content morpheme's lemma and features and the prefixes and suffix as part of the morph key.
Feature mapping onto the engine's slots: tense <- the verb form (qatal, wayyiqtol, yiqtol, participle, infinitive...),
voice <- the stem (qal, niphal, piel...), mood <- None, gcase <- the state (absolute / construct). Context: subj, neg (לֹא, אַל,
אַיִן, בִּלְתִּי in the clause), q (an interrogative ה prefix or מָה / מִי in the clause), art (the definite article in the word).
    ~/sil-study/.venv/bin/python heb_run.py e1|e2|e3|e5|e6|e7 [dev]"""
import collections, json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import engine as E, cells as CL  # noqa: E402
OT = os.path.join(E.PRIV, "data/ot.db"); H = os.path.join(E.R, "orig/heb.sqlite")
CLS = {"cj": "conj", "art": "det", "om": "ptcl", "rel": "conj", "ij": "ptcl", "x": "ptcl"}
NEG = {"לֹא", "אַל", "אַיִן", "בִּלְתִּי", "בַּל"}
QW = {"מָה", "מִי", "אֵי", "אַיֵּה", "לָמָּה", "מַדּוּעַ", "אֵיךְ"}


def PFX(pre):
    """the word's prefixes as one feature (the engine's mood slot for verbs, part of the case slot for nouns): Hebrew writes
    its conjunction, prepositions and article inside the word, so they decide the English words before it"""
    return ".".join(("R:" + p["lemma"]) if p["class"] == "prep" else p["class"] for p in pre)


class HebCorpus(E.Corpus):
    def __init__(self):
        self.n = sqlite3.connect(OT); self.g = sqlite3.connect(H)
        self.verses = {r[0]: dict(ref=r[0], heb=r[1], book=r[2], ch=r[3], v=r[4], split=r[5], words=json.loads(r[6]))
                       for r in self.n.execute("select ref, heb, book, ch, v, split, words from verse")}
        self.link = {k: (json.loads(p), set(json.loads(s)), c) for k, p, s, c in self.n.execute("select word, positions, supplied, chunk from link")}
        cols = [r[1] for r in self.g.execute("pragma table_info(tokens)")]
        parts = collections.defaultdict(list)
        for r in self.g.execute("select * from tokens order by key"):
            t = dict(zip(cols, r)); parts[t["key"][:-1]].append(t)
        self.tok = collections.defaultdict(list)
        self.word_ref = {}
        wid2ref = dict(self.n.execute("select word, ref from link"))
        import vrs
        for wid, ps in parts.items():
            p0 = ps[0]
            b = vrs.to_bsb(p0["book"].lower(), p0["ch"], p0["v"])
            if not b or b[1] == "title":
                continue
            ref = f"{p0['book']} {b[0]}:{b[1]}"
            if ref not in self.verses:
                continue
            self.tok[ref].append(self.word(wid, ps, ref))
        ncols = [r[1] for r in self.g.execute("pragma table_info(nodes)")]
        self.nodes = collections.defaultdict(list)
        refs_of = collections.defaultdict(set)
        for ref, ts in self.tok.items():
            for t in ts:
                refs_of[(t["hbook"], t["hch"], t["hv"])].add(ref)
        for r in self.g.execute("select * from nodes"):
            d = dict(zip(ncols, r))
            for ref in refs_of.get((d["book"], d["ch"], d["v"]), ()):
                self.nodes[ref].append(d)

    @staticmethod
    def word(wid, ps, ref):
        sfx = [p for p in ps if p["pos"] == "suffix"]
        body = [p for p in ps if p["pos"] != "suffix"]
        content = next((p for p in reversed(body) if p["class"] not in ("cj", "art") and not (p["class"] == "prep" and p is not body[-1])), body[-1] if body else ps[-1])
        pre = [p for p in body if p is not content]
        code = "+".join([("R:" + p["lemma"]) if p["class"] == "prep" else p["morph"] for p in pre] + [content["morph"]] +
                        ["S" + (s["morph"] or "") for s in sfx])
        c = content
        b, ch, v = ref.split()[0], int(ref.split()[1].split(":")[0]), int(ref.split(":")[1])
        return dict(key=wid, book=b, ch=ch, v=v, hbook=c["book"], hch=c["ch"], hv=c["v"], text="".join(p["text"] for p in ps),
                    lemma=c["lemma"], morph=code, cls_raw=c["class"], **{"class": CLS.get(c["class"], c["class"])},
                    tense=c["type"] if c["class"] == "verb" else None, voice=c["stem"], mood=PFX(pre), person=c["person"],
                    number=c["number"], gcase=(c["state"] or "") + "|" + PFX(pre), role=c["role"], node=c["node"], clause=c["clause"],
                    after=ps[-1]["after"], art=any(p["class"] == "art" for p in pre),
                    qh=any(p["morph"] == "Ti" for p in pre) or c["lemma"] in QW, neg=c["lemma"] in NEG)

    def rendering(self, ref, t):
        l = self.link.get(t["key"])
        if not l:
            return None
        w = self.verses[ref]["words"]
        return [w[i] for i in l[0]]


def heb_contexts(C, ref):
    toks = C.tok[ref]
    nodes = C.nodes.get(ref, [])
    subj_clause = {n["parent"] for n in nodes if n["role"] == "s"} | {t["clause"] for t in toks if t["role"] == "s"}
    by_clause = collections.defaultdict(list)
    for t in toks:
        by_clause[t["clause"]].append(t)
    return {t["key"]: dict(subj=t["clause"] in subj_clause, neg=any(x["neg"] for x in by_clause[t["clause"]]),
                           q=any(x["qh"] for x in by_clause[t["clause"]]), art=t["art"]) for t in toks}


def main():
    stage = sys.argv[1]; part = sys.argv[2] if len(sys.argv) > 2 else "dev"
    CL.contexts = heb_contexts
    C = HebCorpus()
    train = C.split("train")
    lex, lem = E.learn_lexicon(C, train)
    order = E.learn_order(C, train) if stage != "e1" else None
    eng = E.Engine(lex, lem, order)
    if stage in ("e3", "e5", "e6", "e7"):
        eng.ctxlex = E.CtxLex(C, train)
    if stage in ("e5", "e6", "e7"):
        eng.factored = E.Factored(C, train, eng.ctxlex); eng.ctx_first = True
    if stage in ("e6", "e7"):
        import gen6
        eng.gen6 = gen6.Gen6(C, train, eng.ctxlex, eng.factored); eng.memory_first = stage == "e7"
    res, hyps = E.measure(C, eng, C.split(part))
    res["train verses"] = len(train)
    if order is not None:
        res["order rules"] = len(order)
    out = os.path.join(E.PRIV, "results"); tag = f"heb_{stage}_{part}"
    json.dump(res, open(os.path.join(out, tag + ".json"), "w"), indent=1, ensure_ascii=False)
    with open(os.path.join(out, tag + ".txt"), "w", encoding="utf-8") as f:
        for ref, h in zip(C.split(part), hyps):
            f.write(f"{ref}\t{h}\n")
    print(json.dumps({k: v for k, v in res.items() if k != "how"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
