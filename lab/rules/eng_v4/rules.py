#!/usr/bin/env python3
"""The linguist's rules: an explicit rule file applied on top of the learned engine (E6), the difference report the linguist
reads, and the test every rule must pass. The base engine is E6 (choice / pre / form split; consistent under swaps), trained
on the pool TRAIN (default nogospels: no synoptic parallels of Mark).

Rule file: JSON lines, one rule per line:
  {"id": "r1", "when": {...}, "then": {...}, "why": "...", "evidence": "..."}
  when: token fields  class lemma morph tense voice mood person number gcase  (a value, or a list of values; morph may end in *)
        context       subj neg q art  (true/false: an explicit subject in the clause, negation in the clause, a question, an
                      article in the phrase); first ("verse" / "clause" / "no": the token opens the verse or its clause);
                      next_class (the next Greek token's class: noun, verb, det, adj, pron, prep, conj, adv, ptcl, num);
                      prev_class, prev_lemma (the previous Greek token's class and lemma)
        engine        pre  (the function words the engine put before the word, as one string, "" for none)
  then: pre "<words>"  (replace the function words before the word; "" for none)
        head "<word>"  (replace the inflected word)
        render "<words>" (replace the whole rendering; "" renders nothing)
The first matching rule wins; rules apply to every token, verbs and nouns through E6, others through the context lexicon.

  /usr/bin/python3 rules.py diffs [N]            -> results/diffs_dev.md   (the evidence: classes of differences on dev)
  /usr/bin/python3 rules.py test <rulefile>      -> per rule: fires / right on train and on dev; the dev measures with the file
  The test split is never read here."""
import collections, json, os, re, sys
os.environ.setdefault("TRAIN", "nogospels")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import engine as E, cells as CL, gen6  # noqa: E402

TOKF = ("class", "lemma", "morph", "tense", "voice", "mood", "person", "number", "gcase")
CTXF = ("subj", "neg", "q", "art", "first", "next_class", "prev_class", "prev_lemma")


def base_engine(C, train):
    lex, lem = E.learn_lexicon(C, train)
    eng = E.Engine(lex, lem, E.learn_order(C, train))
    eng.ctxlex = E.CtxLex(C, train)
    eng.factored = E.Factored(C, train, eng.ctxlex); eng.ctx_first = True
    eng.gen6 = gen6.Gen6(C, train, eng.ctxlex, eng.factored); eng.memory_first = False
    return eng


def pool(C):
    tr = C.split("train")
    p = os.environ["TRAIN"]
    if p == "nogospels":
        tr = [r for r in tr if C.verses[r]["book"] not in {"MAT", "LUK", "JHN"}]
    return tr


def ctx_of(eng, t):
    return eng.ctxlex.contexts(f"{t['book']} {t['ch']}:{t['v']}")[t["key"]]


def matches(rule, t, cx, pre):
    for k, want in rule["when"].items():
        if k in TOKF:
            v = t[k]
        elif k in CTXF:
            v = cx[k]
        elif k == "pre":
            v = " ".join(pre)
        else:
            return False
        ws = want if isinstance(want, list) else [want]
        ok = False
        for w in ws:
            if k == "morph" and isinstance(w, str) and w.endswith("*"):
                ok |= (v or "").startswith(w[:-1])
            else:
                ok |= v == w
        if not ok:
            return False
    return True


class Ruled:
    """wraps the engine: the rule file acts on each token's rendering"""
    def __init__(self, eng, rules):
        self.eng, self.rules = eng, rules
        self.fired = collections.Counter()
        self.base_render = eng.render
        eng.render = self.render

    def render(self, t):
        w, how = self.base_render(t)
        if not self.rules:
            return w, how
        cx = ctx_of(self.eng, t)
        pre, core, post = CL.split_rendering(w)
        for r in self.rules:
            if matches(r, t, cx, pre):
                self.fired[r["id"]] += 1
                th = r["then"]
                if "render" in th:
                    return th["render"].split(), f"rule {r['id']}"
                if "pre" in th:
                    pre = tuple(th["pre"].split())
                if "head" in th and core:
                    core = list(core)
                    i = 0 if t["class"] == "verb" else len(core) - 1
                    core[i] = th["head"]; core = tuple(core)
                return list(pre) + list(core) + list(post), f"rule {r['id']}"
        return w, how


def load_rules(path):
    out = []
    for i, l in enumerate(open(path, encoding="utf-8")):
        l = l.strip()
        if l and not l.startswith("#"):
            r = json.loads(l); r.setdefault("id", f"line{i + 1}"); out.append(r)
    return out


def rule_precision(C, eng, rules, refs):
    """per rule: on these verses, how often it fires, how often its output equals the reference, and how often the engine
    was already right where it fired (a rule that fires on right renderings breaks them)"""
    st = {r["id"]: collections.Counter() for r in rules}
    R = Ruled(eng, [])
    for ref in refs:
        for t in C.tok[ref]:
            g = C.rendering(ref, t)
            if g is None:
                continue
            gw = [x.lower() for x in g]
            w, _ = R.base_render(t)
            cx = ctx_of(eng, t); pre, core, post = CL.split_rendering(w)
            for r in rules:
                if matches(r, t, cx, pre):
                    R.rules = [r]
                    w2, _ = R.render(t)
                    s = st[r["id"]]; s["fires"] += 1; s["right after"] += [x.lower() for x in w2] == gw
                    s["right before"] += [x.lower() for x in w] == gw
                    s["pre right after"] += CL.split_rendering(w2)[0] == CL.split_rendering(g)[0]
                    s["pre right before"] += pre == CL.split_rendering(g)[0]
                    break
    eng.render = R.base_render
    return st


def diffs(n=40):
    C = E.Corpus(); train = pool(C); eng = base_engine(C, train)
    cls = collections.defaultdict(lambda: [0, collections.Counter(), []])
    for ref in C.split("dev"):
        for t in C.tok[ref]:
            g = C.rendering(ref, t)
            if g is None:
                continue
            w, how = eng.render(t)
            gp, gc, gq = CL.split_rendering(g); ep, ec, eq = CL.split_rendering(w)
            cx = ctx_of(eng, t)
            if ep != gp:
                key = ("pre", t["class"], t["tense"], t["mood"], t["person"], t["number"], t["gcase"],
                       f"subj={cx['subj']} neg={cx['neg']} q={cx['q']} art={cx['art']}")
                d = cls[key]; d[0] += 1; d[1][(" ".join(ep) or "–") + " → " + (" ".join(gp) or "–")] += 1
                if len(d[2]) < 3:
                    d[2].append(f"{ref} {t['text']} ({t['lemma']} {t['morph']}): engine «{' '.join(w)}», BSB «{' '.join(g)}»")
            if ec != tuple(x.lower() for x in gc) and gc and ec and CL.lemmatize(CL.head(t, ec) if t["class"] in ("verb", "noun") else ec[-1])[0] == CL.lemmatize(CL.head(t, tuple(x.lower() for x in gc)) if t["class"] in ("verb", "noun") else gc[-1].lower())[0]:
                key = ("form", t["class"], t["tense"], t["voice"], t["mood"], t["person"], t["number"], t["gcase"])
                d = cls[key]; d[0] += 1; d[1][" ".join(ec) + " → " + " ".join(gc).lower()] += 1
                if len(d[2]) < 3:
                    d[2].append(f"{ref} {t['text']} ({t['lemma']} {t['morph']}): engine «{' '.join(w)}», BSB «{' '.join(g)}»")
    lines = ["# Differences on dev (Mark 3, 9, 12), engine E6 trained on " + os.environ["TRAIN"], "",
             "Two kinds: **pre** (the function words before the word differ) and **form** (same English word, other form).",
             "Each class: the token's features and context, its count, the commonest changes (engine → BSB), examples.", ""]
    for key, (k, ch, ex) in sorted(cls.items(), key=lambda kv: -kv[1][0])[:n]:
        lines.append(f"## {k} × {' / '.join(str(x) for x in key)}")
        lines.append("changes: " + "; ".join(f"{a} ({b})" for a, b in ch.most_common(5)))
        lines += [f"- {e}" for e in ex]; lines.append("")
    out = os.path.join(E.PRIV, "results/diffs_dev.md"); open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(out, len(cls), "classes")


def test(path):
    C = E.Corpus(); train = pool(C); eng = base_engine(C, train)
    rules = load_rules(path)
    import random
    rnd = random.Random(7); sample = rnd.sample(train, min(1500, len(train)))
    pt = rule_precision(C, eng, rules, sample)
    pdv = rule_precision(C, eng, rules, C.split("dev"))
    base, _ = E.measure(C, eng, C.split("dev"))
    R = Ruled(eng, rules)
    withr, _ = E.measure(C, eng, C.split("dev"))
    keys = ["word choice (content, stem)", "form (content, exact)", "rendering exact (all tokens)", "function words P",
            "function words R", "order tau (mean per verse)", "chrF (summary)"]
    print("rule | train: fires, right before -> after, pre right before -> after | dev: same")
    rep = {"rules": {}, "dev": {}}
    for r in rules:
        a, b = pt[r["id"]], pdv[r["id"]]
        f = lambda s: f"{s['fires']}, {s['right before']}->{s['right after']}, pre {s['pre right before']}->{s['pre right after']}"
        print(f"{r['id']} | {f(a)} | {f(b)}")
        rep["rules"][r["id"]] = {"train": dict(a), "dev": dict(b)}
    for k in keys:
        print(f"{k}: {base[k]} -> {withr[k]}")
        rep["dev"][k] = [base[k], withr[k]]
    json.dump(rep, open(os.path.join(E.PRIV, "results", "ruletest_" + os.path.basename(path) + ".json"), "w"), indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "diffs":
        diffs(int(sys.argv[2]) if len(sys.argv) > 2 else 40)
    else:
        test(sys.argv[2])
