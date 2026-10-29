#!/usr/bin/env python3
"""Agent-free rounds and engine-gap detectors, calibrated against the two linguist rounds (2026-10-26).
No LLM anywhere. For one frozen engine version (scratch/rules/eng_v0 = before round 1, eng_v1 = after the round-1 engine
change, eng_v2 = now), on two disjoint training samples A (the agents' sample, seed 7) and B (seed 8), and dev:

  auto rules  greedy search in the agents' rule format (rules.py): templates = the lemma or not, plus up to two of the
              version's token and context fields and the engine's own function words; action = the reference's function
              words, or its whole rendering. Kept when it gains on A (>= 5, after >= 1.5 x before), still gains on B, at most
              30 rules (the agents' limit). Then rules.py test, as for the agents' files.
  D1          same-shape rules: lemma-specific candidates grouped by action shape; one shape over many lemmas = an engine gap
  D2/D3       per class, how well the reference function words (verbs, nouns, adjectives) or renderings (other classes) are
              predicted on B from the base cell plus one field: the version's fields (D2), and fields generated from the
              MACULA tree that the version lacks (D3: neighbours' attributes, positions, the previous clause)
  D4          invented forms: engine output words the training BSB never has
The test chapters are never read.
    ~/sil-study/.venv/bin/python auto.py <engine dir> <tag>   -> rules/auto_<tag>.jsonl, results/auto/<tag>.json, .md"""
import collections, itertools, json, os, random, sys
VDIR = os.path.abspath(sys.argv[1]); TAG = sys.argv[2]
sys.path.insert(0, VDIR)
os.environ.setdefault("TRAIN", "nogospels")
import engine as E, cells as CL, rules as RU  # noqa: E402

LAB = E.LAB; PRIV = E.PRIV; OUT = os.path.join(PRIV, "results/auto"); os.makedirs(OUT, exist_ok=True)
TOKF = [f for f in RU.TOKF if f != "lemma"]
CTXF = list(RU.CTXF)
CONTENT = {"verb", "noun", "adj"}
ATTRS = ("class", "lemma", "type", "gcase", "person", "number", "tense", "mood", "role")
MAXR = 30
# PARTS=1: the participant fields (engine/parts.py) join the tree fields; TARGET=full: D2/D3 predict the whole rendering
FULL = os.environ.get("TARGET") == "full"
PARTS = None


# ---------- records ----------

def records(C, eng, refs):
    out = []
    for ref in refs:
        for t in C.tok[ref]:
            g = C.rendering(ref, t)
            if g is None:
                continue
            w, _ = eng.render(t)
            wl = [x.lower() for x in w]; gl = [x.lower() for x in g]
            p, c, q = (tuple(x) for x in CL.split_rendering(wl))
            gp, gc, gq = (tuple(x) for x in CL.split_rendering(gl))
            out.append(dict(t=t, cx=RU.ctx_of(eng, t), w=tuple(wl), g=tuple(gl), p=p, c=c, q=q, gp=gp, gc=gc, gq=gq,
                            ref=ref, right=tuple(wl) == tuple(gl)))
    return out


def val(r, f):
    if f == "pre":
        return " ".join(r["p"])
    if f in r["cx"]:
        return r["cx"][f]
    return r["t"].get(f)


# ---------- auto rules ----------

def templates():
    F = TOKF + CTXF + ["pre"]
    out = [("lemma",)] + [("lemma", f) for f in F] + [("lemma",) + c for c in itertools.combinations(F, 2)]
    out += [(f,) for f in F] + list(itertools.combinations(F, 2))
    return out


def outcome_right(r, act):
    kind, a = act
    if kind == "render":
        return r["g"] == a
    return r["gp"] == a and r["gc"] == r["c"] and r["gq"] == r["q"]


def candidates(A):
    cands = []
    for tp in templates():
        groups = collections.defaultdict(list)
        for i, r in enumerate(A):
            groups[tuple(val(r, f) for f in tp)].append(i)
        for key, idx in groups.items():
            if len(idx) < 5:
                continue
            wrong = [A[i] for i in idx if not A[i]["right"]]
            if len(wrong) < 5:
                continue
            acts = collections.Counter()
            for r in wrong:
                acts[("render", r["g"])] += 1
                if r["gc"] == r["c"] and r["gq"] == r["q"]:
                    acts[("pre", r["gp"])] += 1
            before = sum(A[i]["right"] for i in idx)
            best = None
            for act, _ in acts.most_common(3):
                after = sum(outcome_right(A[i], act) for i in idx)
                if after - before >= 5 and after >= 1.5 * before and (best is None or after - before > best[0]):
                    best = (after - before, act, after)
            if best:
                cands.append(dict(tp=tp, key=key, act=best[1], gain=best[0], gain0=best[0], after=best[2], before=before, idx=set(idx)))
    return cands


def matches(c, r):
    return all(val(r, f) == v for f, v in zip(c["tp"], c["key"]))


def gain_on(c, recs):
    m = [r for r in recs if matches(c, r)]
    return sum(outcome_right(r, c["act"]) for r in m) - sum(r["right"] for r in m), len(m)


def greedy(A, B, cands):
    """lazy greedy: the rule with the largest gain on the A tokens not yet taken by an earlier rule; it must still gain on B"""
    taken = set(); takenB = set(); chosen = []
    pool = sorted(cands, key=lambda c: -c["gain"])
    Bidx = list(range(len(B)))
    while pool and len(chosen) < MAXR:
        best = None
        for c in pool:
            if best and c["gain"] <= best[0]:
                break
            idx = c["idx"] - taken
            g = sum(outcome_right(A[i], c["act"]) for i in idx) - sum(A[i]["right"] for i in idx)
            c["gain"] = g
            if best is None or g > best[0]:
                best = (g, c)
        pool.sort(key=lambda c: -c["gain"])
        if not best or best[0] < 5:
            break
        g, c = best; pool.remove(c)
        mB = [i for i in Bidx if i not in takenB and matches(c, B[i])]
        gB = sum(outcome_right(B[i], c["act"]) for i in mB) - sum(B[i]["right"] for i in mB)
        c["gainB"], c["firesB"] = gB, len(mB)
        if gB < 1:
            continue
        chosen.append(c); taken |= c["idx"]; takenB |= set(mB)
    return chosen


def to_rule(n, c):
    kind, a = c["act"]
    return {"id": f"auto{n}", "when": dict(zip(c["tp"], c["key"])),
            "then": {"render": " ".join(a)} if kind == "render" else {"pre": " ".join(a)},
            "why": "found by auto.py (no agent)", "evidence": f"A: {c['before']}->{c['after']} right; B gain {c['gainB']} of {c['firesB']} fires"}


# ---------- D1: same-shape rules ----------

def shape(c, A):
    """the action's shape and whether the engine's design can produce it for this class: E6 gives verbs and nouns a content
    word, so a verb or noun rendered with function words only, or with nothing, is a shape no rule of the engine makes"""
    kind, a = c["act"]
    grp = "verb/noun" if A[next(iter(c["idx"]))]["t"]["class"] in ("verb", "noun") else "other"
    if kind == "render":
        s = "nothing" if not a else "function words only" if all(x in E.FUNC for x in a) else "with content words"
    else:
        s = "pre: none" if not a else "pre: set"
    return f"{grp}: {s}"


def d1(cands, A):
    lem = [c for c in cands if c["tp"][0] == "lemma"]
    by = collections.defaultdict(lambda: dict(lemmas=set(), fixed=set(), n=0, ex={}))
    for c in lem:
        s = shape(c, A); d = by[s]
        d["lemmas"].add(c["key"][0]); d["n"] += 1
        d["fixed"] |= {i for i in c["idx"] if not A[i]["right"] and outcome_right(A[i], c["act"])}
        e = d["ex"].get(c["key"][0])
        if e is None or c["gain0"] > e[0]:
            d["ex"][c["key"][0]] = (c["gain0"], f"{c['key'][0]} {dict(zip(c['tp'][1:], c['key'][1:]))} -> {' '.join(c['act'][1]) or '∅'} (+{c['gain0']})")
    rows = sorted(({"shape": s, "lemmas": len(d["lemmas"]), "candidates": d["n"], "tokens fixed on A": len(d["fixed"]),
                    "examples": [x[1] for x in sorted(d["ex"].values(), reverse=True)[:5]]} for s, d in by.items()),
                  key=lambda x: -x["tokens fixed on A"])
    return rows


# ---------- D2/D3: what predicts the reference ----------

def ordered_refs(C):
    return sorted(C.verses, key=lambda r: C.tok[r][0]["key"] if C.tok.get(r) else "")


def tree_feats(C):
    """per token key: fields generated from the tree, none of them chosen by hand for a construction"""
    refs = ordered_refs(C); out = {}; prev_last = None
    for ref in refs:
        toks = C.tok.get(ref) or []
        if not toks:
            continue
        nodes = {n["id"]: n for n in C.nodes.get(ref, [])}
        cls = []
        for t in toks:
            if not cls or cls[-1] != t["clause"]:
                cls.append(t["clause"])
        by = collections.defaultdict(list)
        for t in toks:
            by[t["clause"]].append(t)
        verb = {c: next((x for x in by[c] if x["class"] == "verb"), None) for c in by}
        subj = {c: any(x["role"] == "s" for x in by[c]) or any(n["role"] == "s" and n["parent"] == c for n in nodes.values()) for c in by}
        for i, t in enumerate(toks):
            ci = cls.index(t["clause"])
            pv, ps = (verb[cls[ci - 1]], subj[cls[ci - 1]]) if ci > 0 else (prev_last or (None, None))
            cv = verb[t["clause"]]
            node = nodes.get(t["node"]) or {}
            par = nodes.get(node.get("parent")) or {}
            same_node = [x for x in toks if x["node"] == t["node"] and x is not t]
            nh = next((x for x in same_node if x["class"] == "noun"), same_node[0] if same_node else None)
            nb = {"prev": toks[i - 1] if i else None, "next": toks[i + 1] if i + 1 < len(toks) else None,
                  "cverb": cv if cv is not t else None, "nhead": nh, "pcverb": pv}
            f = {}
            for name, x in nb.items():
                for a in ATTRS:
                    f[f"{name}.{a}"] = x[a] if x else None
            f["pos.verse"] = i == 0
            f["pos.clause"] = by[t["clause"]][0] is t
            f["pcl.subj"] = ps
            f["pcl.same_pn"] = (pv["person"], pv["number"]) == (cv["person"], cv["number"]) if pv and cv else None
            f["node.rule"], f["node.role"] = node.get("rule"), node.get("role")
            f["par.rule"], f["par.role"], f["par.clausetype"] = par.get("rule"), par.get("role"), par.get("clausetype")
            if PARTS:
                f.update({f"part.{k}": v for k, v in PARTS[t["key"]].items()})
            out[t["key"]] = f
        last = cls[-1]
        prev_last = (verb[last], subj[last])
    return out


def target(r):
    if FULL:
        return " ".join(r["g"]).lower()
    return " ".join(r["gp"]) if r["t"]["class"] in CONTENT else " ".join(r["g"])


def basekey(r):
    t = r["t"]
    if t["class"] in CONTENT:
        return (t["class"], t["tense"], t["voice"], t["mood"], t["person"], t["number"], t["gcase"])
    return (t["lemma"], t["morph"])


def ctxall(r):
    return tuple(r["cx"].get(f) for f in CTXF)


def acc(A, B, fa):
    """accuracy on B of the commonest target for (cell, the version's context[, field]), backing off to (cell, context),
    then the cell"""
    m = collections.defaultdict(collections.Counter); m2 = collections.defaultdict(collections.Counter)
    b = collections.defaultdict(collections.Counter)
    for r in A:
        y = target(r); bk = basekey(r); cx = ctxall(r)
        b[bk][y] += 1; m2[(bk, cx)][y] += 1
        if fa:
            m[(bk, cx, fa(r))][y] += 1
    ok = 0
    for r in B:
        bk = basekey(r); cx = ctxall(r)
        c = m.get((bk, cx, fa(r))) if fa else None
        if not c or sum(c.values()) < 2:
            c = m2.get((bk, cx))
            if not c or sum(c.values()) < 2:
                c = b.get(bk)
        ok += bool(c) and c.most_common(1)[0][0] == target(r)
    return ok / max(1, len(B))


def d23(A, B, tf):
    cand = sorted({k for f in tf.values() for k in f})
    res = []
    for cls in sorted({r["t"]["class"] for r in A}):
        a = [r for r in A if r["t"]["class"] == cls]; b = [r for r in B if r["t"]["class"] == cls]
        if len(b) < 150:
            continue
        eng = sum((r["gp"] == r["p"]) if cls in CONTENT else r["right"] for r in b) / len(b)
        base = acc(a, b, None)
        allf = sorted(((round(acc(a, b, lambda r, f=f: tf[r["t"]["key"]][f]), 4), f) for f in cand), reverse=True)
        cd = allf[:6]; pf = [x for x in allf if x[1].startswith("part.")][:2]
        res.append({"class": cls, "target": "function words before" if cls in CONTENT else "rendering", "B tokens": len(b),
                    "engine": round(eng, 4), "cell + version context": round(base, 4), "best tree fields": cd,
                    "tokens gained on B": round((cd[0][0] - base) * len(b)),
                    "best participant fields": [(a, f, round((a - base) * len(b))) for a, f in pf]})
    return sorted(res, key=lambda x: -x["tokens gained on B"])


# ---------- D4 ----------

def d4(C, train, A):
    V = collections.Counter(w.lower() for r in train for w in C.verses[r]["words"])
    bad = collections.Counter(); n = 0
    for r in A:
        for w in r["w"]:
            n += 1
            if V[w] < 1:
                bad[w] += 1
    return {"output words": n, "not in the training BSB": sum(bad.values()), "per 1000": round(1000 * sum(bad.values()) / max(1, n), 2),
            "commonest": bad.most_common(15)}


def main():
    C = E.Corpus(); train = RU.pool(C); eng = RU.base_engine(C, train)
    sA = random.Random(7).sample(train, min(1500, len(train)))
    rest = [r for r in train if r not in set(sA)]
    sB = random.Random(8).sample(rest, 1500)
    A, B = records(C, eng, sA), records(C, eng, sB)
    cands = candidates(A)
    D1 = d1(cands, A)
    chosen = greedy(A, B, cands)
    rp = os.path.join(PRIV, f"rules/auto_{TAG}.jsonl")
    with open(rp, "w", encoding="utf-8") as f:
        for n, c in enumerate(chosen, 1):
            f.write(json.dumps(to_rule(n, c), ensure_ascii=False) + "\n")
    global PARTS
    if os.environ.get("PARTS"):
        sys.path.insert(0, os.path.join(LAB, "engine")); import parts
        PARTS = parts.load(C)
    tf = tree_feats(C)
    rep = {"version": VDIR, "A tokens": len(A), "B tokens": len(B), "candidates": len(cands), "auto rules": len(chosen),
           "D1": D1, "D2/D3": d23(A, B, tf), "D4": d4(C, train, A)}
    json.dump(rep, open(os.path.join(OUT, f"{TAG}.json"), "w"), indent=1, ensure_ascii=False, default=str)
    L = [f"# Detectors and auto rules, engine {os.path.basename(VDIR)}", "",
         f"A {len(A)} tokens, B {len(B)}; {len(cands)} candidate rules, {len(chosen)} kept (rules/auto_{TAG}.jsonl)", "",
         "## D1 same-shape rules (lemma-specific candidates by action shape)", "", "| shape | lemmas | candidates | tokens fixed on A | best per lemma |", "|---|---|---|---|---|"]
    for x in rep["D1"]:
        L.append(f"| {x['shape']} | {x['lemmas']} | {x['candidates']} | {x['tokens fixed on A']} | {'; '.join(x['examples'][:4])} |")
    L += ["", "## D2/D3 what predicts the reference on B (accuracy): the cell plus the version's context, then one tree field more", "",
          "| class | target | B | engine | cell + context | best tree fields | B tokens gained |", "|---|---|---|---|---|---|---|"]
    for x in rep["D2/D3"]:
        L.append(f"| {x['class']} | {x['target']} | {x['B tokens']} | {x['engine']} | {x['cell + version context']} | "
                 f"{', '.join(f'{f} {a}' for a, f in x['best tree fields'][:4])} | {x['tokens gained on B']} |"
                 + (f" {'; '.join(f'{f} {g:+d}' for a, f, g in x['best participant fields'])} |" if x["best participant fields"] else ""))
    d = rep["D4"]
    L += ["", "## D4 invented forms", "", f"{d['not in the training BSB']} of {d['output words']} output words ({d['per 1000']} per 1000): "
          + ", ".join(f"{w} {n}" for w, n in d["commonest"])]
    open(os.path.join(OUT, f"{TAG}.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(TAG, "candidates", len(cands), "kept", len(chosen), flush=True)


if __name__ == "__main__":
    main()
