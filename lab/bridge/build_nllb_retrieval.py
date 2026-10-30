#!/usr/bin/env python3
"""NLLB data with a retrieved hint (plan phase 4, the fuzzy-match / retrieval-augmented form): from a build_nllb_data.py data
dir, the same splits with each source line extended by the Danish text of the most similar clause's verse, found by the clause
index (clause_index.py) through the lexeme and grammar bridges:

    <consonantal Hebrew verse> ||| <Danish verse of the best-matching NT clause>      (--memory nt)
    ... or of the best-matching NT or OT-training clause                                (--memory ot+nt)

The NT side needs no OT alignment: the Danish NT verse text (align-text's plain-text export) is the hint. The OT side's memory
is the training split's own verses (never the verse itself, never dev or test verses). hints.json records what was retrieved
for every verse (matched ref, score, side), so the gain can be read against the match quality.

    . ./env.sh; OT_DB=data/dfb_jev.db FUNC_FILE=data/dan_func.txt ~/sil-study/.venv/bin/python lab/bridge/build_nllb_retrieval.py
        --data nllb/dfb_cons --nt-text private/align/dfb_nt/text --memory nt --out nllb/dfb_cons+ret_nt [--max-cands 400]"""
import argparse, collections, json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import clause_index as CI  # noqa: E402
import score as S  # noqa: E402
sys.path.insert(0, os.path.join(S.E.R, "scripts"))
import vrs  # noqa: E402
PRIV = S.E.PRIV
SEP = " ||| "


def read_lines(d, split, ext):
    return open(os.path.join(d, f"{split}.{ext}"), encoding="utf-8").read().rstrip("\n").split("\n")


def to_en(vref):
    book, cv = vref.split(); ch, v = (int(x) for x in cv.split(":"))
    e = vrs.to_bsb(book.lower(), ch, v)
    return f"{book} {int(e[0])}:{int(e[1])}" if e and e[1] != "title" else None


def nt_text(d):
    """{'MAT 1:1': Danish} from align-text's plain-text export (BOOK.txt, 'c:v text')."""
    out = {}
    for f in os.listdir(d):
        if f.endswith(".txt"):
            for line in open(os.path.join(d, f), encoding="utf-8"):
                cv, _, t = line.rstrip("\n").partition(" ")
                if ":" in cv and t:
                    out[f"{f[:-4]} {cv}"] = t
    return out


def retrieve_ot(q, OT, by_verb_ot, memory, max_cands):
    """Best OT-training clause for q: same verb lexeme, shape, same conjugation, shared content lexemes (no bridge needed)."""
    anchors = [s for s, _ in q["verbs"]] or q["content"]
    cands = set()
    for s in anchors:
        cands.update(i for i in by_verb_ot.get(s, ()) if OT[i]["ref"] in memory and OT[i]["ref"] != q["ref"])
    if max_cands and len(cands) > max_cands:
        cands = sorted(cands, key=lambda i: (OT[i]["kind"] != q["kind"], OT[i]["rule"] != q["rule"]))[:max_cands]
    best = None
    for i in cands:
        c = OT[i]; sh = CI.shape(q, c)
        tf = 1.0 if (q["verbs"] and c["verbs"] and {f for _, f in q["verbs"]} & {f for _, f in c["verbs"]}) else 0.5 if q["verbs"] and c["verbs"] else 0.0
        others = [s for s in q["content"] if s not in anchors]
        lx = (sum(1 for s in others if s in c["content"]) / len(others)) if others else 0.0
        sc = 0.4 + 0.25 * sh + 0.2 * tf + 0.15 * lx
        if best is None or sc > best[0]:
            best = (sc, i)
    return best


def main(a):
    d = os.path.join(PRIV, a.data); out = os.path.join(PRIV, a.out); os.makedirs(out, exist_ok=True)
    OT = json.load(open(os.path.join(CI.BR, "clauses_ot.json"), encoding="utf-8")); NT = json.load(open(os.path.join(CI.BR, "clauses_nt.json"), encoding="utf-8"))
    h2g, gram = CI.load_bridges()
    by_verb = collections.defaultdict(list); by_verb_ot = collections.defaultdict(list)
    for i, c in enumerate(NT):
        for s in ([s for s, _ in c["verbs"]] or c["content"]):
            by_verb[s].append(i)
    for i, c in enumerate(OT):
        for s in ([s for s, _ in c["verbs"]] or c["content"]):
            by_verb_ot[s].append(i)
    ot_by_ref = collections.defaultdict(list)
    for q in OT:
        ot_by_ref[q["ref"]].append(q)
    NTD = nt_text(a.nt_text)
    train_vref = read_lines(d, "train", "vref"); train_trg = read_lines(d, "train", "trg")
    en_of = {}; dan_of_en = {}
    for v, t in zip(train_vref, train_trg):
        e = to_en(v)
        if e:
            en_of[v] = e; dan_of_en[e] = t
    memory = set(dan_of_en)                      # OT memory = training verses only
    hints = {}; stats = collections.Counter()
    for split in ("train", "val", "test"):
        src = read_lines(d, split, "src"); vref = read_lines(d, split, "vref"); trg = read_lines(d, split, "trg")
        new = []
        for s, v, t in zip(src, vref, trg):
            e = to_en(v); best = None
            for q in (ot_by_ref.get(e, []) if e else []):
                top = CI.retrieve_one(q, NT, by_verb, h2g, gram, 1, max_cands=a.max_cands)
                if top and (best is None or top[0]["score"] > best["score"]):
                    best = {"side": "nt", "ref": top[0]["ref"], "score": top[0]["score"]}
                if a.memory == "ot+nt":
                    b = retrieve_ot(q, OT, by_verb_ot, memory, a.max_cands)
                    if b and (best is None or b[0] > best["score"]):
                        best = {"side": "ot", "ref": OT[b[1]]["ref"], "score": round(b[0], 3)}
            hint = ""
            if best:
                hint = NTD.get(best["ref"], "") if best["side"] == "nt" else dan_of_en.get(best["ref"], "")
                if not hint:
                    best["missing_text"] = True
            hints[v] = best or {}
            stats[f"{split} {best['side'] if best else 'none'}"] += 1
            new.append(s + SEP + hint)
        open(os.path.join(out, f"{split}.src"), "w", encoding="utf-8").write("\n".join(new) + "\n")
        shutil.copy(os.path.join(d, f"{split}.trg"), out); shutil.copy(os.path.join(d, f"{split}.vref"), out)
        print(split, len(new), "lines;", dict(c for c in stats.items() if c[0].startswith(split)))
    json.dump(hints, open(os.path.join(out, "hints.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if os.path.exists(os.path.join(d, "meta.json")):
        m = json.load(open(os.path.join(d, "meta.json"))); m["retrieval"] = {"memory": a.memory, "sep": SEP, "from": a.data}
        json.dump(m, open(os.path.join(out, "meta.json"), "w"), indent=1)
    print("written", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--nt-text", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--memory", choices=["nt", "ot+nt"], default="nt"); ap.add_argument("--max-cands", type=int, default=400)
    main(ap.parse_args())
