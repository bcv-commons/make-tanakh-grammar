#!/usr/bin/env python3
"""The learner of the rule draft (alternatives/rules.py): counts, over the training chapters' TBTA propositions paired to the
Greek, their matched constituents and the team's linked PARTS, the rules R1-R9, and returns them as rules.json's dict. Ported
from the research drafter's learn.py (lab/tbta_drafter, state t2_final) without its paradigm, root and sense options and
without the loop; no model call.

  R1 lexicon        lex key (cat:concept-sense) -> the lexeme's default rendering as words of [part, slot] with its head word;
                    fallbacks by Strong's, by the source lemma, by (lemma, number); the noun class (a surface proxy); capitals
  R2 spellout       per affix slot of V, N and A: features -> canonical piece ("" = none), decision list with backoff; a slot is
                    used only where its rules beat the lexeme's default piece on the other half of the training verses; the
                    piece's written variant by (slot, piece), overridden by the stem
  R3 insertion      feature trigger -> function part, its side of the anchor and whether it is a word or a clitic
  R4 copying        participant feature -> slot (purity >= 0.7, n >= 20, >= 0.05 over the slot's own majority)
  R5 order          pairwise precedence of a proposition's units and of a noun phrase's parts
  R6 pronouns       realisation of an NP head (full / pron / zero)
  R7 transfer       proposition merging and dropping
  R9 function parts source function tokens no constituent covers -> the team's function part linked to them"""
import collections, json, time

from alternatives import rules_engine as K

DEFAULTS = dict(
    r1_min_sense_n=1,
    r2_min_n=5, r2_min_share=0.5, r2_slot_min=20, r2_infl_margin=0.005,
    r2_base={"V": ["tgroup", "mood", "polarity", "aspect", "stem_init"], "N": ["number", "stem_init"], "A": ["number", "stem_init"]},
    r2_extra={}, r2_surf_min_n=10, r2_surf_min_share=0.8,
    r4_min_purity=0.7, r4_min_n=20, r4_margin=0.05,
    r4_cands={"V": ["subj_pn", "subj_class", "subj_pnc", "obj_pn", "obj_class", "obj_pnc"], "N": ["poss_pn", "poss_rel"], "A": ["head_class", "head_number"]},
    r7_fields=["genre", "sequence", "type", "illoc", "prev_tgroup"],
    r3_min_n=5, r3_min_share=0.5, r3_min_lift=2.0, r5_min_n=5,
    r6_min_n=5, r6_min_share=0.5, r6_fields=["tracking", "person", "number", "role", "type", "greek"],
    r7_merge_min_n=5, r7_merge_share=0.5, r7_drop_share=0.7, r7_drop_min_n=5)
R9_SKIP = {"noun", "adj", "num"}                    # content classes: rendered by R1, never as function parts


def canon(p):
    return K.strip_marks(p.lower())


class Train:
    """the training material: the corpus, the chapters' propositions (Book) matched with the association learned on them, the
    corpus's function parts and the source clause fields"""
    def __init__(self, cfg, chs, S):
        books = sorted({b for b, _ in chs}); self.chs = chs; self.lang = cfg["iso"]
        self.C = K.Corpus(cfg, "grc", books); self.resolved = K.load_resolved(set(books)); self.M = K.Matcher()
        self.B = K.Book(self.C, chs, None, self.resolved, K.Guard(cfg))
        self.M.learn_assoc([(P["cons"], P["toks"]) for P in self.B.props.values() if P["toks"]])
        self.B.rematch(self.M); self.refs = set(self.B.refs())
        self.FUNC = K.function_parts(self.C.db, "grc", set(self.C.verses))
        self.src = K.SourceFields("grc") if S.get("src_feats") else None


# ------------------------------------------------------------------ words as parts

def stem_of(w):
    """the stem part of a word [(pos, part, slot, linked)] or [[part, slot]] (lowercase); the longest part when none is labelled"""
    ps = [(x[1], x[2]) if len(x) == 4 else (x[0], x[1]) for x in w]
    st = [p for p, s in ps if s == "stem"]
    return (st[0] if st else max((p for p, _ in ps), key=len)).lower()


def struct(w):
    """a word as [[part, slot]]: affixes lowercase, the stem as written"""
    return tuple((p if s == "stem" else p.lower(), s) for _, p, s, _ in w)


def head_word(ws, FUNC, prefer=None):
    """the head word of a rendering: the word whose stem is `prefer`, else the one with the longest linked stem part outside the
    function parts, else the first word with a linked part outside them"""
    if prefer is not None:
        for i, w in enumerate(ws):
            if stem_of(w) == prefer:
                return i
    c = [(len(p), -i, i) for i, w in enumerate(ws) for _, p, s, l in w if l and s == "stem" and p.lower() not in FUNC]
    if c:
        return max(c)[2]
    c = [i for i, w in enumerate(ws) if any(l and p.lower() not in FUNC for _, p, s, l in w)]
    return c[0] if c else 0


def word_aff(w):
    """{slot: canonical piece} of a word's affix parts"""
    return {s: canon(p) for p, s in ((x[1], x[2]) if len(x) == 4 else (x[0], x[1]) for x in w) if s != "stem"}


def stem_init(stem):
    s = K.strip_marks(stem[:1].lower())
    return "V" if s and s in "aeiou" else "C"


def renderings(T):
    """(P, c, token, [words of (pos, part, slot, linked)]) per matched constituent with linked parts"""
    out = []
    for P in T.B.props.values():
        for c in P["cons"]:
            t = P["m"].get(c["cid"])
            ws = T.B.linked(P["ref"], t) if t is not None else None
            if ws:
                out.append((P, c, t, ws))
    return out


# ------------------------------------------------------------------ R1

def learn_r1(T, R):
    forms, stems = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    caps, heads = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    c_cat = {}
    for P, c, t, ws in R:
        h = head_word(ws, T.FUNC); st = stem_of(ws[h]); f = (tuple(struct(w) for w in ws), h)
        first = ws[h][0]; cap = first[1][:1].isupper() if first[0] > 0 else None
        for k in (K.lexkey(c), "~" + K.lexkey0(c), "@" + (t.get("lemma") or "")):
            forms[k][f] += 1; stems[k][st] += 1; heads[(k, st)][struct(ws[h])] += 1
            if cap is not None:
                caps[k][cap] += 1
        c_cat.setdefault("@" + (t.get("lemma") or ""), c["cat"])
    rules = []
    for k, fc in forms.items():
        n = sum(fc.values()); sc = stems[k]; top_stem, ns = sc.most_common(1)[0]
        cplx = sum(v for (f, h), v in fc.items() if len(f) >= 2) / n >= 0.6
        cands = [(v, f, h) for (f, h), v in fc.items() if (len(f) >= 2) == cplx and stem_of(f[h]) == top_stem] or [(v, f, h) for (f, h), v in fc.items()]
        v, f, h = max(cands)
        lk = k.lstrip("~"); hw = "".join(p for p, _ in f[h]); cls = K.noun_class(hw) if lk.startswith("N:") else "na"
        hs = heads[(k, top_stem)]
        infl = sum(v2 for w, v2 in hs.items() if word_aff(w)) / max(1, sum(hs.values())) >= 0.5
        sub = "lex0" if k.startswith("~") else ("lemma2" if k.startswith("@") else "lex")
        if sub == "lemma2":
            lk = k[1:]; cls = K.noun_class(hw) if c_cat.get(k) == "N" else "na"
        rules.append(dict(kind="R1", sub=sub, when={sub: lk},
                          do=dict(form=[list(map(list, w)) for w in f], head=h, stem=top_stem, cls=cls, complex=cplx, infl=infl,
                                  cap=caps[k][True] > caps[k][False], alts=[[s, round(x / n, 3)] for s, x in sc.most_common(3)]),
                          n=n, share=round(ns / n, 3), source="counts"))
    st, lm, ln = (collections.defaultdict(collections.Counter) for _ in range(3))     # fallbacks over every linked training token
    for ref in T.refs:
        for t in T.C.tok.get(ref, []):
            if t["class"] not in ("verb", "noun", "adj", "adv"):
                continue
            ws = T.B.linked(ref, t)
            if ws:
                f = (tuple(struct(w) for w in ws), head_word(ws, T.FUNC))
                st["G" + K.norm_strong(t.get("strong"))][f] += 1; lm[t["lemma"]][f] += 1
                if t["class"] in ("noun", "adj") and t.get("number") in ("singular", "plural"):
                    ln[f"{t['lemma']}|{t['number'][:2]}"][struct(ws[f[1]])] += 1
    fb = []
    for k, c in ln.items():
        w, n = c.most_common(1)[0]
        fb.append(dict(kind="R1", sub="lemnum", when={"lemnum": k}, do=dict(form=[list(map(list, w))], head=0, stem=stem_of(w)), n=n,
                       share=round(n / sum(c.values()), 3), source="counts"))
    for name, tab in (("strong", st), ("lemma", lm)):
        for k, c in tab.items():
            (f, h), n = c.most_common(1)[0]
            fb.append(dict(kind="R1", sub=name, when={name: k}, do=dict(form=[list(map(list, w)) for w in f], head=h), n=n,
                           share=round(n / sum(c.values()), 3), source="counts"))
    return rules, fb


def all_contexts(T, lexclass):
    ctx = {}
    for ref, pids in T.B.verses.items():
        prev = None
        for pid in pids:
            P = T.B.props[pid]; ctx.update(K.contexts(P, lexclass, prev, T.src))
            v = next((c for c in P["cons"] if c["cat"] == "V"), None)
            if v:
                prev = v["f"].get("tgroup") or "na"
    return ctx


# ------------------------------------------------------------------ R2 / R4

def slot_rows(T, R, ctx, lexdef):
    """per cat: rows (ctx, {slot: canonical piece}, the lexeme's default pieces, half, head word) of V, N, A constituents"""
    rows = collections.defaultdict(list)
    for P, c, t, ws in R:
        if c["cat"] not in ("V", "N", "A"):
            continue
        d = lexdef.get(K.lexkey(c)) or lexdef.get(K.lexkey0(c))
        if not d or not d.get("infl"):              # R2 inflects the lexemes the segmenter inflects (>= half their words have affixes)
            continue
        h = head_word(ws, T.FUNC, d["stem"]); ctx[c["cid"]]["stem_init"] = stem_init(d["stem"])
        rows[c["cat"]].append((ctx[c["cid"]], word_aff(ws[h]), word_aff(d["form"][d["head"]]), int(P["ref"].split(":")[-1]) % 2, struct(ws[h])))
    return rows


def purity(rows, f, slot):
    """the purity of the slot's piece (where the word has one) given the feature and the stem's initial, and given the initial alone"""
    by, allc = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for x, aff, dff, half, w in rows:
        v = x.get(f); p = aff.get(slot, "")
        if v is None or str(v).startswith(("na", "none")) or not p:
            continue
        by[(v, x.get("stem_init"))][p] += 1; allc[x.get("stem_init")][p] += 1
    n = sum(sum(c.values()) for c in allc.values())
    if not n:
        return 0, 0, 0
    return sum(c.most_common(1)[0][1] for c in by.values()) / n, sum(c.most_common(1)[0][1] for c in allc.values()) / n, n


def learn_r2_r4(T, R, ctx, lexdef, S):
    rows = slot_rows(T, R, ctx, lexdef); tables, r4, infl, stats = {}, [], {}, {}
    for cat, rs in rows.items():
        sc = collections.Counter(s for _, aff, _, _, _ in rs for s in aff)
        for slot in sorted((s for s, n in sc.items() if n >= S["r2_slot_min"]), key=K.slot_order):
            copies = []
            for f in S["r4_cands"].get(cat, []):
                pur, base, n = purity(rs, f, slot)
                if n >= S["r4_min_n"] and pur >= S["r4_min_purity"] and pur - base >= S["r4_margin"]:
                    copies.append(f)
                    r4.append(dict(kind="R4", sub="copy", when={"cat": cat, "slot": slot}, do={"copy": f}, n=n, share=round(pur, 3), base=round(base, 3), source="counts"))
            fields = list(S["r2_base"].get(cat, [])) + copies + (S["r7_fields"] if cat == "V" else []) + S["r2_extra"].get(f"{cat}.{slot}", [])
            data = [(x, aff.get(slot, "")) for x, aff, _, _, _ in rs]; levels = K.backoff_levels(data, fields)
            fit = lambda sub: K.learn_dl(f"R2.{cat}.{slot}", "R2", f"slot:{cat}:{slot}", sub, levels, S["r2_min_n"], S["r2_min_share"], extra={"slot": slot})
            acc = collections.Counter()
            for h in (0, 1):                        # is the slot inflectional? its rules against the lexeme's default on the other half
                tb = fit([d for d, r in zip(data, rs) if r[3] != h])
                for (x, v), r in zip(data, rs):
                    if r[3] == h:
                        rule = tb.lookup(x); dv = r[2].get(slot, "")
                        acc["rule"] += (rule["do"]["value"] if rule else dv) == v; acc["def"] += dv == v; acc["n"] += 1
            tables[f"R2.{cat}.{slot}"] = fit(data)
            infl[f"{cat}.{slot}"] = acc["rule"] > acc["def"] + S["r2_infl_margin"] * acc["n"]
            stats[f"{cat}.{slot}"] = dict(n=acc["n"], rule=round(acc["rule"] / acc["n"], 3), default=round(acc["def"] / acc["n"], 3), copies=copies,
                                          rules=len(tables[f"R2.{cat}.{slot}"].rules))
    return tables, r4, infl, stats


def learn_surface(T, S):
    """R2's surface step: the commonest written variant of a canonical piece per slot, and by the word's stem where it differs"""
    canon_c, by_stem = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for ref in T.refs:
        v = T.C.verses.get(ref)
        for ix in K.words_of(v["wordidx"]) if v else ():
            w = [(v["words"][i], v["slots"][i]) for i in ix]; st = stem_of(w)
            for p, s in w:
                if s != "stem":
                    canon_c[(s, canon(p))][p.lower()] += 1; by_stem[(s, canon(p), st)][p.lower()] += 1
    default = {f"{s}|{c}": cnt.most_common(1)[0][0] for (s, c), cnt in canon_c.items()}; rules = []
    for (s, c, st), cnt in by_stem.items():
        v, n = cnt.most_common(1)[0]; tot = sum(cnt.values())
        if n >= S["r2_surf_min_n"] and n / tot >= S["r2_surf_min_share"] and v != default.get(f"{s}|{c}"):
            rules.append(dict(kind="R2", sub="surface", when={"slot": s, "canon": c, "stem": st}, do={"value": v}, n=n, share=round(n / tot, 3), source="counts"))
    return K.Table("R2.surface", [["slot", "canon", "stem"]], rules), default


# ------------------------------------------------------------------ R3

def triggers(P, ctx, S=None):
    """[(trigger, anchor cid)] of a proposition: TBTA's, and the source's where S names `src_trig` / `src_fill`"""
    out = []; v = next((c for c in P["cons"] if c["cat"] == "V"), None); va = v["cid"] if v else None
    if v:
        x = ctx[v["cid"]]
        if (x.get("polarity") or "").endswith("Negative"):
            out.append(("neg", va))
        for f, skip in (("illoc", "Declarative"), ("type", "Independent"), ("aspect", "Unmarked"), ("mood", "Indicative")):
            if x.get(f) not in (skip, "na", None, "Not Applicable"):
                out.append((f"{f}={x[f]}", va))
        out.append((f"tgroup={x.get('tgroup')}", va))
    for c in P["cons"]:
        x = ctx[c["cid"]]
        if c["cat"] in ("CONJ", "SUB", "PART"):
            out.append((f"{c['cat'].lower()}={c['concept']}", va or c["cid"]))
        elif c["cat"] == "PA":
            out.append(("pred_adj", va or c["cid"]))
        elif c["cat"] == "N":
            if x.get("depth") == 0 and x.get("role") not in ("Most Agent-like", "Most Patient-like", "Not Applicable", "na", None):
                out.append((f"role={x.get('role')}", c["cid"]))
            if x.get("depth", 0) > 0:
                out.append((f"rel={x.get('rel')}", c["cid"]))
            if x.get("proximity") not in ("na", None, "Not Applicable"):
                out.append((f"prox={x.get('proximity')}", c["cid"]))
    if S and (S.get("src_trig") or S.get("src_fill")):
        out += K.src_triggers(P, ctx, S, va)
    return out


def attach_of(wi, p):
    """a part's place in its word: its own word, a clitic on the next word's parts, or on the previous word's"""
    same_next = p + 1 < len(wi) and wi[p + 1] == wi[p]; same_prev = p > 0 and wi[p - 1] == wi[p]
    return "next" if same_next else ("prev" if same_prev else "word")


def learn_r3(T, ctx, S):
    N = 0; nt, nw, ntw, nta, ntaw = (collections.Counter() for _ in range(5))
    side, att = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for P in T.B.props.values():
        if not P["toks"]:
            continue
        pos_of = {c["cid"]: [p for p, _ in T.B.target(P["ref"], P["m"][c["cid"]])] for c in P["cons"] if P["m"].get(c["cid"]) is not None}
        allpos = [p for t in P["toks"] for p, _ in T.B.target(P["ref"], t)]
        if not allpos or P["ref"] not in T.C.verses:
            continue
        covered = {p for ps in pos_of.values() for p in ps}
        v = T.C.verses[P["ref"]]; parts = v["words"]; wi = v["wordidx"]; lo, hi = min(allpos), max(allpos)
        fw = [(p, parts[p].lower()) for p in range(lo, hi + 1) if p < len(parts) and p not in covered and parts[p].lower() in T.FUNC]
        N += 1; present = {w for _, w in fw}; nw.update(present)
        for p, w in fw:
            att[w][attach_of(wi, p)] += 1
        for trig, anc in set(triggers(P, ctx, S)):
            hc = ctx[anc].get("class", "na") if anc in ctx else "na"; nt[trig] += 1; nta[(trig, hc)] += 1
            for w in present:
                ntw[(trig, w)] += 1; ntaw[(trig, hc, w)] += 1; ap = pos_of.get(anc)
                wp = min((p for p, x in fw if x == w), key=lambda p: abs(p - min(ap)) if ap else 0)
                if ap:
                    side[(trig, w)]["start" if wp == lo and wp < min(ap) else ("before" if wp < min(ap) else "after")] += 1
    rules, best = [], {}
    for (trig, w), n in ntw.items():
        sh = n / nt[trig]; lift = sh / (nw[w] / N)
        if n >= S["r3_min_n"] and sh >= S["r3_min_share"] and lift >= S["r3_min_lift"] and (trig not in best or n > best[trig][1]):
            best[trig] = (w, n, sh, lift)
    at_of = lambda w: att[w].most_common(1)[0][0] if att[w] else "word"
    place = lambda trig, w: side[(trig, w)].most_common(1)[0][0] if side[(trig, w)] else "before"
    for trig, (w, n, sh, lift) in best.items():
        rules.append(dict(kind="R3", sub="insert", when={"trigger": trig}, do={"word": w, "place": place(trig, w), "attach": at_of(w)}, n=n,
                          share=round(sh, 3), lift=round(lift, 2), source="counts"))
    r4, by_t = [], collections.defaultdict(list)
    for (trig, hc, w), n in ntaw.items():
        by_t[trig].append((hc, w, n))
    for trig, xs in by_t.items():                   # a trigger whose part depends on the anchor's class (agreement)
        if trig in best or nt[trig] < S["r4_min_n"]:
            continue
        top = collections.defaultdict(lambda: (None, 0))
        for hc, w, n in xs:
            if n > top[hc][1]:
                top[hc] = (w, n)
        cov = sum(n for hc, (w, n) in top.items() if hc != "na"); tot = sum(nta[(trig, hc)] for hc in top if hc != "na")
        if tot >= S["r4_min_n"] and cov / tot >= S["r4_min_purity"]:
            r4.append(dict(kind="R4", sub="copy", when={"cat": "R3", "slot": trig}, do={"copy": "head_class"}, n=tot, share=round(cov / tot, 3), source="counts"))
            for hc, (w, n) in top.items():
                if hc != "na" and n >= S["r3_min_n"] and n / nta[(trig, hc)] >= S["r3_min_share"]:
                    rules.append(dict(kind="R3", sub="insert", when={"trigger": trig, "head_class": hc}, do={"word": w, "place": place(trig, w), "attach": at_of(w)},
                                      n=n, share=round(n / nta[(trig, hc)], 3), source="counts"))
    return K.Table("R3", [["trigger", "head_class"], ["trigger"]], rules), r4, {w: dict(c) for w, c in att.items()}


# ------------------------------------------------------------------ R5

def units(P):
    """clause units (label, [cids]) in TBTA order; a noun phrase's parts gathered under its head"""
    out = []; npu = {}
    for c in P["cons"]:
        if c["cat"] == "N" and c["f"].get("depth") == 0:
            u = (f"N:{c['f'].get('role')}", [c["cid"]]); out.append(u); npu[c["cid"]] = u
        elif c["cat"] in ("A", "N") and c.get("of"):
            root = c["of"]
            while root not in npu and root is not None:
                root = next((x.get("of") for x in P["cons"] if x["cid"] == root), None)
            if root in npu:
                npu[root][1].append(c["cid"])
            else:
                out.append((c["cat"], [c["cid"]]))
        else:
            out.append((c["cat"], [c["cid"]]))
    return out


def np_label(c):
    return "A" if c["cat"] == "A" else ("G:" + str(c["f"].get("rel")) if c.get("of") else "HEAD")


def pairs_of(items):
    """precedence rows of labelled positions: [((a, b), 'ab' | 'ba')] with a < b"""
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (la, pa), (lb, pb) = items[i], items[j]
            if la != lb and pa != pb:
                a, b, first = (la, lb, pa < pb) if la < lb else (lb, la, pb < pa)
                out.append(((a, b), "ab" if first else "ba"))
    return out


def learn_r5(T, ctx, S):
    rows, nprows = [], []
    for P in T.B.props.values():
        if not P["toks"]:
            continue
        pos = {}
        for c in P["cons"]:
            t = P["m"].get(c["cid"])
            ps = [p for p, _ in T.B.target(P["ref"], t)] if t is not None else []
            if ps:
                pos[c["cid"]] = min(ps)
        x0 = ctx[P["cons"][0]["cid"]] if P["cons"] else {}
        us = [(l, [pos[cid] for cid in cids if cid in pos]) for l, cids in units(P)]
        for (a, b), y in pairs_of([(l, min(ps)) for l, ps in us if ps]):
            rows.append(({"a": a, "b": b, "type": x0.get("type"), "illoc": x0.get("illoc")}, y))
        by = {c["cid"]: c for c in P["cons"]}
        for l, cids in units(P):
            for (a, b), y in pairs_of([(np_label(by[cid]), pos[cid]) for cid in cids if cid in pos]):
                nprows.append(({"a": a, "b": b, "role": l}, y))
    return (K.learn_dl("R5.clause", "R5", "clause", rows, [["a", "b", "type", "illoc"], ["a", "b", "type"], ["a", "b"]], S["r5_min_n"], 0.5),
            K.learn_dl("R5.np", "R5", "np", nprows, [["a", "b", "role"], ["a", "b"]], S["r5_min_n"], 0.5))


# ------------------------------------------------------------------ R6, R7

def free_stems(B, ref, cache):
    """the verse's stem parts that no matched constituent accounts for"""
    if ref not in cache:
        cov = {p for pid in B.verses.get(ref, []) for t in B.props[pid]["m"].values() for p, _ in B.target(ref, t)}
        v = B.C.verses.get(ref)
        cache[ref] = {p.lower() for i, (p, s) in enumerate(zip(v["words"], v["slots"])) if s == "stem" and i not in cov} if v else set()
    return cache[ref]


def realisation(B, P, c, lexdef, cache):
    """an NP head as the team renders it: full / pron / zero (a head linked only to affix parts, or only to parts other
    constituents hold, is zero; one the source does not name is full where its lexicon stem is free in the verse)"""
    t = P["m"].get(c["cid"])
    if t is None:
        d = lexdef.get(K.lexkey(c)) or lexdef.get(K.lexkey0(c))
        return "full" if d and d["stem"] in free_stems(B, P["ref"], cache) else "zero"
    ws = B.linked(P["ref"], t); stems = {i for w in ws for i, p, s, l in w if l and s == "stem"}
    if not stems:
        return "zero"
    others = {p for d in P["cons"] if d["cid"] != c["cid"] and d["cid"] in P["m"] for p, _ in B.target(P["ref"], P["m"][d["cid"]])}
    return "zero" if stems <= others else ("pron" if t["class"] == "pron" else "full")


def learn_r6(T, ctx, S, lexdef, cache):
    rows, prow = [], []
    for P in T.B.props.values():
        for c in (P["cons"] if P["toks"] else ()):
            if c["cat"] != "N":
                continue
            r = realisation(T.B, P, c, lexdef, cache); x = ctx[c["cid"]]; rows.append((x, r))
            if r == "pron":
                prow.append((x, json.dumps([list(map(list, struct(w))) for w in T.B.linked(P["ref"], P["m"][c["cid"]])], ensure_ascii=False)))
    F = S["r6_fields"]; F2 = [f for f in F if f != "greek"]
    return (K.learn_dl("R6", "R6", "realise", rows, K.backoff_levels(rows, F), S["r6_min_n"], S["r6_min_share"]),
            K.learn_dl("R6.nogreek", "R6", "realise-tbta", rows, K.backoff_levels(rows, F2), S["r6_min_n"], S["r6_min_share"]),
            K.learn_dl("R6.pron", "R6", "pronoun", prow, [["person", "number", "role", "class"], ["person", "number", "role"], ["person", "number"]], 3, 0.4))


def learn_r7(T, S, lexdef, cache):
    mrows, drows = [], []
    for ref, pids in T.B.verses.items():
        Ps = [T.B.props[p] for p in pids]
        for a, b in zip(Ps, Ps[1:]):
            if a["toks"] and b["toks"]:
                vb = next((c["concept"] for c in b["cons"] if c["cat"] == "V"), "none")
                same = a["anchor"] is not None and a["anchor"] == b["anchor"]
                mrows.append(({"type_a": a["p"]["type"], "type_b": b["p"]["type"], "verb_b": vb, "illoc_b": b["p"]["illoc"]}, "merge" if same else "keep"))
        for P in Ps:
            p = P["p"]; v = (p["verbs"] or [{}])[0]; vc = next((c for c in P["cons"] if c["cat"] == "V"), None)
            d = (lexdef.get(K.lexkey(vc)) or lexdef.get(K.lexkey0(vc))) if vc else None
            ex = "expressed" if P["toks"] or (d and d["stem"] in free_stems(T.B, P["ref"], cache)) else "not expressed"
            drows.append(({"implicit_info": p.get("implicit_info"), "location": p.get("location"), "type": p.get("type"),
                           "vp_implicit": v.get("vp_implicit"), "verb": v.get("concept") or "none"}, ex))
    tm = K.learn_dl("R7.merge", "R7", "merge", mrows, [["type_a", "type_b", "verb_b"], ["type_a", "type_b", "illoc_b"], ["type_a", "type_b"]],
                    S["r7_merge_min_n"], S["r7_merge_share"])
    td = K.learn_dl("R7.drop", "R7", "express", drows, [["implicit_info", "location", "type", "vp_implicit", "verb"], ["implicit_info", "location", "type", "vp_implicit"],
                                                         ["implicit_info", "location", "type"], ["implicit_info", "location"]], S["r7_drop_min_n"], S["r7_drop_share"])
    return (K.Table("R7.merge", tm.levels, [r for r in tm.rules if r["do"]["value"] == "merge"]),
            K.Table("R7.drop", td.levels, [r for r in td.rules if r["do"]["value"] == "not expressed"]))


# ------------------------------------------------------------------ R9

def r9_ctx(P, t, i, tnext=""):
    """R9's context of span token t (index i in P["toks"]): its lemma (a Hebrew word: none), the next span token's class, its
    Strong's (a Hebrew word: its Septuagint Greek Strong's), and the first two letters of the target word that follows"""
    nxt = P["toks"][i + 1]["class"] if i + 1 < len(P["toks"]) else "end"
    gs = str(t.get("gstrong") or "").replace(",", " ").split()
    strong = "G" + K.norm_strong(gs[0]) if gs else ("G" + K.norm_strong(t.get("strong")) if t.get("strong") else "")
    return {"lemma": "" if gs else (t.get("lemma") or ""), "nxt": nxt or "", "strong": strong, "tnext": tnext}


def learn_r9(T, S):
    """source function tokens no constituent covers -> the function part the alignment links them to (lemma + next class ->
    lemma -> Strong's); a part is inserted when share >= r9_min_share and n >= r9_min_n; where nothing wins, a blocking rule"""
    ms, mn = S.get("r9_min_share", 0.4), S.get("r9_min_n", 5)
    cnt = {lv: collections.defaultdict(collections.Counter) for lv in ("full", "lemma", "strong")}; att = collections.defaultdict(collections.Counter)
    kref = {t["key"]: r for r, ts in T.C.tok.items() for t in ts}
    for P in T.B.props.values():
        matched = {t["key"] for t in P["m"].values() if t}
        for i, t in enumerate(P["toks"]):
            if t["key"] in matched or t["class"] in R9_SKIP:
                continue
            l = T.C.link.get(t["key"]); y = "none"; vv = T.C.verses.get(kref.get(t["key"])) if l else None
            if vv:
                P_, WI = vv["words"], vv["wordidx"]; fx = [j for j in l[0] if j < len(P_) and P_[j].lower() in T.FUNC]
                if fx:
                    j = fx[0]; y = P_[j].lower(); att[y][attach_of(WI, j)] += 1
            x = r9_ctx(P, t, i)
            cnt["full"][(x["lemma"], x["nxt"])][y] += 1; cnt["lemma"][(x["lemma"],)][y] += 1
            if x["strong"]:
                cnt["strong"][(x["strong"],)][y] += 1
    rules = []
    for lv, fields in (("full", ("lemma", "nxt")), ("lemma", ("lemma",)), ("strong", ("strong",))):
        for k, c in cnt[lv].items():
            n = sum(c.values()); y, m = c.most_common(1)[0]
            if n < mn:
                continue
            if y != "none" and m / n >= ms:
                rules.append({"kind": "R9", "when": dict(zip(fields, k)), "do": {"word": y, "attach": att[y].most_common(1)[0][0]}, "n": n,
                              "share": round(m / n, 3), "source": "counts"})
            elif lv == "full" and y == "none":
                rules.append({"kind": "R9", "when": dict(zip(fields, k)), "do": {"word": None}, "n": n, "share": round(m / n, 3), "source": "counts"})
    return K.Table("R9", [["lemma", "tnext"], ["lemma", "nxt"], ["lemma"], ["strong"]], rules)


# ------------------------------------------------------------------ all

def learn(T, S, overrides=()):
    """rules.json's dict; overrides [(table, rule)] are added after learning (Zinza's 19 from research's LLM linguist)"""
    R = renderings(T); r1, fb = learn_r1(T, R)
    r1_lemma2 = [r for r in r1 if r["sub"] == "lemma2"]; r1 = [r for r in r1 if r["sub"] != "lemma2"]
    lexclass = {r["when"].get("lex") or r["when"].get("lex0"): r["do"]["cls"] for r in r1}
    lexdef = {r["when"].get("lex") or r["when"].get("lex0"): r["do"] for r in r1}
    ctx = all_contexts(T, lexclass); cache = {}
    slot_tabs, r4, infl, sstats = learn_r2_r4(T, R, ctx, lexdef, S)
    surf, surf_def = learn_surface(T, S)
    r3, r4b, attach = learn_r3(T, ctx, S)
    r5c, r5n = learn_r5(T, ctx, S)
    r6, r6b, r6p = learn_r6(T, ctx, S, lexdef, cache)
    r7m, r7d = learn_r7(T, S, lexdef, cache)
    caps = collections.Counter(T.C.verses[r]["words"][0][:1].isupper() for r in T.refs if T.C.verses[r]["words"])
    sub = lambda rs, s: [r for r in rs if r["sub"] == s]
    tables = {"R1.lex": K.Table("R1.lex", [["lex"]], sub(r1, "lex")), "R1.lex0": K.Table("R1.lex0", [["lex0"]], sub(r1, "lex0")),
              "R1.strong": K.Table("R1.strong", [["strong"]], sub(fb, "strong")), "R1.lemnum": K.Table("R1.lemnum", [["lemnum"]], sub(fb, "lemnum")),
              "R1.lemma": K.Table("R1.lemma", [["lemma"]], sub(fb, "lemma")), "R1.lemma2": K.Table("R1.lemma2", [["lemma2"]], r1_lemma2),
              "R2.surface": surf, "R4": K.Table("R4", [["cat", "slot"]], r4 + r4b), "R3": r3, "R5.clause": r5c, "R5.np": r5n,
              "R6": r6, "R6.nogreek": r6b, "R6.pron": r6p, "R7.merge": r7m, "R7.drop": r7d, **slot_tabs}
    if S.get("r9"):
        tables["R9"] = learn_r9(T, S)
    out = {"meta": dict(lang=T.lang, unit="part", train=sorted({b for b, _ in T.chs}), chapters=[f"{b} {c}" for b, c in T.chs],
                        date=time.strftime("%Y-%m-%d"), settings=S, overrides=len(overrides), function_parts=len(T.FUNC)),
           "inflectional": infl, "slot_stats": sstats, "surface_default": surf_def, "attach": attach,
           "caps": round(caps[True] / max(1, sum(caps.values())), 3),
           "matcher_assoc": [[a, b, round(v, 4)] for (a, b), v in T.M.assoc.items()],
           "tables": {k: v.dump() for k, v in tables.items()}}
    for tname, r in overrides:
        out["tables"].setdefault(tname, {"levels": [], "rules": []})["rules"].append(r)
    return out
