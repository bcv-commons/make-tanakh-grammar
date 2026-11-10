#!/usr/bin/env python3
"""The rule draft: an alternative written by rules counted from the team's text, with no model call. For every source clause
it drafts the team's language from TBTA's propositions (the semantic encoding of the text): a lexicon by TBTA concept (R1),
the affix pieces by TBTA's and the source's features (R2, R4), function parts (R3, R9), order (R5), pronouns (R6), merging and
dropping (R7), and content words no proposition covers (R10). The rules are learned from the team's New Testament
(alternatives/rules_learn.py); a Tanakh chapter is drafted with them from the Hebrew, its constituents matched to the Hebrew
words by TBTA's concept-to-Strong's table. The research drafter at its final state (t2_final), relearned here through
shared/holdout.py; research's head stems from its old engine are replaced by the team's word forms per lexeme
(drafting/lexicon.py: for a Hebrew word its own forms where the team's Tanakh text has them, else those of its usual Greek
equivalents), used only for content words no constituent covers and where no rule has a rendering.

    . ./env.sh; P=~/sil-study/.venv/bin/python
    $P alternatives/rules.py learn --lang zin [--leave-out JHN]               # private/tbta/rules/<lang>/<name>.json
    $P alternatives/rules.py draft --lang kvg --book JOS --chapters 1         # runs/<lang>/draft/JOS/rules/
    $P alternatives/rules.py score --lang zin --book JHN --leave-out JHN      # research's figure: chrF on parts, every TBTA chapter
    python3 drafting/draft.py text --lang kvg --book JOS --label rules

The run is in the main draft's form: groups.json (the evidence's clause groups, drafting/evidence.py), answers/<verse id>.json
(one text per source clause, cut by the source token each drafted word comes from), manifest.json, and trace.json (per clause
the rule that made each word; no text). The rules and the TBTA data are private; the drafts may be published (user,
2026-11-10). Closed and held-out chapters are refused; a drafted chapter, the books left out and the scored chapters are never
in the rules' training or the lexicon's counts."""
import argparse, collections, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import holdout, paths  # noqa: E402
from alternatives import rules_engine as K, rules_learn as L  # noqa: E402

ALL = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
OWN = {"R4": {"subj_pn", "subj_class", "subj_pnc", "obj_pnc", "obj_pn", "obj_class", "poss_pn", "poss_rel", "head_class", "head_number"},
       "R7": {"genre", "sequence", "type", "illoc", "prev_tgroup"}}
CONTENT_CLS = ("noun", "adj", "num", "verb", "adv")


def cap1(p):
    return p[:1].upper() + p[1:]


def norm_form(form):
    """a rule's form as words of [part, slot]; a plain string word is one stem part"""
    return [[[w, "stem"]] if isinstance(w, str) else [[p, "stem"] if isinstance(p, str) else list(p) for p in w] for w in form]


class Drafter:
    """drafts verses from a Book's propositions with the rules of rules.json. verse(C, ref) -> (parts, at {source key: (position,
    n parts, how)}); beside it self.tagged[ref] (per part: part, word number, slot, constituent, source key, how). lex: a
    drafting/lexicon.Lexicon (or None) with the source language, for R10."""
    def __init__(self, rules, on=ALL, lex=None, source="grc", src=None):
        self.rules = rules; self.on = set(on); self.S = dict(rules["meta"].get("settings", {})); self.lex = lex; self.source = source
        self.T = {k: K.Table(k, t["levels"], t["rules"]) for k, t in rules["tables"].items()}
        self.skip = frozenset(set().union(*[OWN[r] for r in OWN if r not in self.on]))
        self.FUNC = set(rules.get("function_parts", ()))
        self.lexclass = {}
        for k in ("R1.lex", "R1.lex0"):
            for r in self.T[k].rules:
                self.lexclass[r["when"].get("lex") or r["when"].get("lex0")] = r["do"].get("cls", "na")
        self.smap = K.load_smap(); self.src = src
        self.tagged = {}; self.log = collections.Counter(); self.trace = {}; self.orphans = {}; self.B = None
        self.agr = collections.defaultdict(list)    # the slots that carry a participant's agreement (R4): where a zero participant stays expressed
        for r in self.T["R4"].rules:
            cat, slot, f = r["when"].get("cat"), r["when"].get("slot"), r["do"].get("copy", "")
            if cat in ("V", "N") and f.split("_")[0] in ("subj", "obj", "poss"):
                self.agr[(cat, f.split("_")[0])].append(slot)

    def matcher(self):
        M = K.Matcher("G"); M.assoc = {(a, b): v for a, b, v in self.rules["matcher_assoc"]}
        return M

    # -------------------------------------------------------------- lexicon and spellout

    def from_lexicon(self, t):
        """the team's commonest form of a content token's lexeme (drafting/lexicon.py) as words of one stem part each, or None"""
        if self.lex is None or t.get("class") not in CONTENT_CLS or not t.get("strong"):
            return None
        for _, rows, _, _ in self.lex.renderings(self.source, dict(t, cls=t["class"])):
            if rows:
                return [[[w, "stem"]] for w in rows[0][0].split()]
        return None

    def lexicon(self, c, x, tok):
        """R1: (form: [[[part, slot]]], head index, how, entry)"""
        r = self.T["R1.lex"].lookup(x)
        if r and r.get("source", "counts") == "counts" and r["n"] < self.S.get("r1_min_sense_n", 1):
            r = self.T["R1.lex0"].lookup(x) or r
        r = r or self.T["R1.lex0"].lookup(x)
        if r:
            return norm_form(r["do"]["form"]), r["do"].get("head", 0), "R1", r["do"]
        for s in sorted(self.smap.get(c["concept"].lower(), ())):
            if s.startswith("G"):
                r = self.T["R1.strong"].lookup({"strong": s})
                if r:
                    return [list(map(list, w)) for w in r["do"]["form"]], r["do"]["head"], "R1-strong", None
        if tok is not None and tok.get("gstrong"):  # a Hebrew word: its Septuagint Greek Strong's (MACULA Hebrew's greekstrong)
            for gs in str(tok["gstrong"]).replace(",", " ").split():
                r = self.T["R1.strong"].lookup({"strong": "G" + K.norm_strong(gs)})
                if r:
                    return [list(map(list, w)) for w in r["do"]["form"]], r["do"]["head"], "R1-strong", None
        if tok is not None:
            r = self.T["R1.lemma"].lookup({"lemma": tok["lemma"]})
            if r:
                return [list(map(list, w)) for w in r["do"]["form"]], r["do"]["head"], "R1-lemma", None
            f = self.from_lexicon(tok) if self.S.get("r10_lex") else None
            if f:
                return f, 0, "R1-words", None
        return [[[f"<{c['concept']}>", "stem"]]], 0, "unk", None

    def surface(self, slot, canon, stem):
        r = self.T["R2.surface"].lookup({"slot": slot, "canon": canon, "stem": stem})
        return r["do"]["value"] if r else self.rules["surface_default"].get(f"{slot}|{canon}", canon)

    def predict(self, c, x, stem):
        """R2: {slot: canonical piece or ""} from the inflectional slots' rules (and the overrides of the slots left to the default)"""
        x = dict(x); x["stem_init"] = L.stem_init(stem); pred = {}
        for name, t in self.T.items():
            if not name.startswith(f"R2.{c['cat']}.") or name.count(".") < 2:
                continue
            slot = name.split(".", 2)[2]
            if self.rules["inflectional"].get(f"{c['cat']}.{slot}"):
                r = t.lookup(x, self.skip)
            elif t.over:
                r = next((o for o in t.over if (not self.skip or not (set(o.get("when", {})) | set(o.get("unless") or {})) & self.skip)
                          and K.when_match(o, x)), None)
            else:
                continue
            if r:
                pred[slot] = r["do"]["value"]
        return pred

    def spell(self, c, x, form, head, entry):
        """R2 on the head word: each predicted piece its own part, any combination"""
        if "R2" not in self.on or entry is None or c["cat"] not in ("V", "N", "A") or not entry.get("infl", True):
            return form, "R1"
        hw = form[head]; stem = L.stem_of(hw); pred = self.predict(c, x, stem)
        if not pred:
            return form, "R1"
        aff = {s: p for p, s in hw if s != "stem"}; st = next((p for p, s in hw if s == "stem"), hw[0][0])
        for s, v in pred.items():
            if not v:
                aff.pop(s, None)
            elif L.canon(aff.get(s, "")) != v:      # a piece other than the default's: its written variant
                aff[s] = self.surface(s, v, stem)
        pre = sorted((s for s in aff if s[0] == "p"), key=K.slot_order); suf = sorted((s for s in aff if s[0] == "s"), key=K.slot_order)
        out = [list(map(list, w)) for w in form]; out[head] = [[aff[s], s] for s in pre] + [[st, "stem"]] + [[aff[s], s] for s in suf]
        self.log["R2 generated"] += 1
        return out, "R2"

    # -------------------------------------------------------------- one proposition

    def prop(self, P, ctx, prev):
        """[unit] of one proposition, each {words: [[[part, slot]]], cid, how}; prev = the previous drafted proposition (merging)"""
        on = self.on; cons = P["cons"]; drop = set()
        if "R7" in on and prev is not None:
            vb = next((c["concept"] for c in cons if c["cat"] == "V"), "none")
            if self.T["R7.merge"].lookup({"type_a": prev["p"]["type"], "type_b": P["p"]["type"], "verb_b": vb, "illoc_b": P["p"]["illoc"]}):
                seen = {c["concept"] for c in prev["cons"]}
                drop |= {c["cid"] for c in cons if (c["cat"] == "N" and c["f"].get("depth") == 0 and c["concept"] in seen) or c["cat"] == "CONJ"}
                self.log["R7 merge"] += 1
        words = {}
        for c in cons:
            if c["cid"] in drop:
                words[c["cid"]] = ([], "R7-merged"); continue
            x = ctx[c["cid"]]; tok = P["m"].get(c["cid"])
            if c["cat"] == "N" and "R6" in on:
                r = (self.T["R6"] if x.get("greek") != "unpaired" else self.T["R6.nogreek"]).lookup(x, self.skip)
                real = r["do"]["value"] if r else "full"; self.trace[c["cid"]] = real
                if real == "zero":
                    words[c["cid"]] = ([], "R6-zero"); continue
                if real == "pron":
                    rp = self.T["R6.pron"].lookup(x, self.skip)
                    if rp:
                        v = rp["do"]["value"]; words[c["cid"]] = (norm_form(json.loads(v) if v.startswith("[") else v.split()), "R6-pron"); continue
            form, head, how, entry = self.lexicon(c, x, tok)
            if how == "R1":
                form, how = self.spell(c, x, form, head, entry)
                if entry and entry.get("cap") and form[head]:
                    form[head] = [list(p) for p in form[head]]; form[head][0][0] = cap1(form[head][0][0])
            words[c["cid"]] = (form, how)
        us = L.units(P); by = {c["cid"]: c for c in cons}; x0 = ctx[cons[0]["cid"]] if cons else {}
        if "R5" in on:
            us = self.order(us, lambda a, b: self.T["R5.clause"].lookup(dict(x0, a=a, b=b)))
        seq = []
        for lab, cids in us:
            parts = [(L.np_label(by[cid]), [cid]) for cid in cids]
            if "R5" in on and len(parts) > 1:
                parts = self.order(parts, lambda a, b, lab=lab: self.T["R5.np"].lookup(dict(x0, a=a, b=b, role=lab)))
            seq += [cid for _, (cid,) in parts]
        out = [dict(words=words[cid][0], cid=cid, how=words[cid][1]) for cid in seq if cid in words]
        return self.insert(P, ctx, out) if "R3" in on else out

    @staticmethod
    def order(items, rule):
        """labelled items sorted by pairwise precedence (Copeland wins); ties keep TBTA's order"""
        n = len(items)
        if n < 2:
            return items
        wins = [0] * n
        for i in range(n):
            for j in range(i + 1, n):
                a, b = items[i][0], items[j][0]
                if a == b:
                    continue
                lo, hi = (a, b) if a < b else (b, a); r = rule(lo, hi)
                if r:
                    wins[i if (r["do"]["value"] == "ab") == (a == lo) else j] += 1
        return [items[i] for i in sorted(range(n), key=lambda i: (-wins[i], i))]

    def insert(self, P, ctx, out):
        """R3: the function parts the proposition's triggers call for, beside their anchor"""
        present = {p.lower() for u in out for w in u["words"] for p, _ in w}
        for trig, anc in L.triggers(P, ctx, self.S):
            x3 = dict(ctx.get(anc, {})); x3.update(trigger=trig, head_class=ctx[anc].get("class", "na") if anc in ctx else "na")
            r = self.T["R3"].lookup(x3, self.skip); w = (r["do"].get("word") or "") if r else ""
            if not w or w in present:               # an empty part: a blocking rule
                continue
            present.add(w); place = r["do"].get("place", "before"); idx = [i for i, u in enumerate(out) if u["cid"] == anc]
            if place == "start" or not idx:
                pos = 0 if place in ("start", "before") or not out else len(out)
            else:
                pos = idx[0] if place == "before" else idx[-1] + 1
            out.insert(pos, dict(words=[[[w, "stem"]]], cid=None, how=f"R3:{trig}", attach=r["do"].get("attach", "word")))
            self.log["R3 insert"] += 1
        return out

    # -------------------------------------------------------------- one verse

    def r10(self, P, t, us, keyed):
        """R10: a content word no constituent covers, from the lemma tables (a Hebrew word: its Greek Strong's) and else the team's
        forms of its lexeme; head word only, without function parts. True if inserted"""
        r = (self.T["R1.lemma2"].lookup({"lemma2": t.get("lemma")}) if "R1.lemma2" in self.T else None) or self.T["R1.lemma"].lookup({"lemma": t.get("lemma")})
        if not r and t.get("gstrong"):
            for gs in str(t["gstrong"]).replace(",", " ").split():
                r = self.T["R1.strong"].lookup({"strong": "G" + K.norm_strong(gs)})
                if r:
                    break
        ws, how = None, None
        lw = self.S.get("r10_lex")
        if lw == "first" or not r or r["n"] < self.S.get("r10_min_n", 3):
            ws = self.from_lexicon(t) if lw else None; how = "R10-words:"
        if ws is None and r and r["n"] >= self.S.get("r10_min_n", 3):
            ws = [[tuple(p) for p in w] for w in r["do"]["form"]]; how = "R10:"
            if self.S.get("r10_head"):
                ws = [[p for p in ws[min(r["do"].get("head", 0), len(ws) - 1)] if p[0].lower() not in self.FUNC]]
        if not ws or not ws[0]:
            return False
        j = next((k for k, kk in enumerate(keyed) if kk and kk > t["key"]), len(us))
        us.insert(j, {"cid": None, "key": t["key"], "words": ws, "how": how + (t.get("lemma") or ""), "attach": "word", "P": P})
        keyed.insert(j, t["key"]); self.log[how.rstrip(":")] += 1
        return True

    def r9(self, P, us):
        """R9: a unit for each source function token of P no constituent covers whose lemma has a function part, placed before the
        first unit whose token comes later in the source (skipped when P's units already hold the part); R10 first, for the
        content words no constituent covers (the verse's tokens outside every span included)"""
        matched = {t["key"] for t in P["m"].values() if t}
        have = collections.Counter(p.lower() for u in us for w in u["words"] if w for p, _ in w)
        keyed, last = [], ""
        for u in us:
            tok = P["m"].get(u["cid"]) if u.get("cid") else None; last = tok["key"] if tok else last; keyed.append(last)
        orph = self.orphans.get(id(P), []); r10 = self.S.get("r10")
        content = lambda i, t: i < 0 or t["class"] in L.R9_SKIP or (t["class"] == "verb" and bool(r10))
        for i, t in [(i, t) for pass_ in (0, 1) for i, t in list(enumerate(P["toks"])) + [(-1, o) for o in orph] if (pass_ == 0) == content(i, t)]:
            if t["key"] in matched:
                continue
            if content(i, t):
                if r10:
                    self.r10(P, t, us, keyed)
                continue
            if "R9" not in self.T:
                continue
            j = next((k for k, kk in enumerate(keyed) if kk and kk > t["key"]), len(us)); tn = "end"
            for u in us[j:]:
                fp = next((p for w in u["words"] if w for p, _ in w), None)
                if fp:
                    tn = fp.lower()[:2]; break
            r = self.T["R9"].lookup(L.r9_ctx(P, t, i, tn)); w = r and r["do"].get("word")
            if not w:
                if self.S.get("r10_adv") and t["class"] == "adv":
                    self.r10(P, t, us, keyed)
                continue
            if have.get(w, 0) > 0:
                have[w] -= 1; continue
            us.insert(j, {"cid": None, "key": t["key"], "words": [[(w, "stem")]], "how": "R9:" + (t.get("lemma") or ""),
                          "attach": r["do"].get("attach", "word"), "P": P})
            keyed.insert(j, t["key"]); self.log["R9 insert"] += 1
        return us

    def verse(self, C, ref):
        self.orphans = {}
        pids = [pid for pid in self.B.verses.get(ref, []) if self.B.props[pid]["toks"]]
        if self.S.get("r10_orphans") and pids:      # the verse's content tokens outside every proposition's span
            inprop = {t["key"] for pid in pids for t in self.B.props[pid]["toks"]}
            for t in C.tok.get(ref, []):
                if t["key"] not in inprop and t["class"] in CONTENT_CLS:
                    best = next((pid for pid in reversed(pids) if self.B.props[pid]["toks"][0]["key"] <= t["key"]), pids[0])
                    self.orphans.setdefault(id(self.B.props[best]), []).append(t)
        units, zeros, prev_t, prev_p = [], [], None, None
        for pid in self.B.verses.get(ref, []):
            P = self.B.props[pid]; ctx = K.contexts(P, self.lexclass, prev_t, self.src)
            v = next((c for c in P["cons"] if c["cat"] == "V"), None)
            if v:
                prev_t = v["f"].get("tgroup") or "na"
            if "R7" in self.on:
                p = P["p"]; v0 = (p["verbs"] or [{}])[0]; x7 = dict(ctx[v["cid"]]) if v else {}
                x7.update({"implicit_info": p.get("implicit_info"), "location": p.get("location"), "type": p.get("type"),
                           "vp_implicit": v0.get("vp_implicit"), "verb": v0.get("concept") or "none", "paired": bool(P["toks"])})
                if self.T["R7.drop"].lookup(x7):
                    self.log["R7 drop"] += 1; continue
            us = self.prop(P, ctx, prev_p)
            if ("R9" in self.T or self.S.get("r10")) and P["toks"]:
                us = self.r9(P, us)
            prev_p = P
            for u in us:
                u["P"] = P
            units += us
            zeros += [(P, c) for c in P["cons"] if c["cat"] == "N" and self.trace.get(c["cid"]) == "zero"]
        tags, wno, pending_next = [], -1, False     # parts with word numbers; a clitic shares the next (or previous) word's number
        for u in units:
            P = u["P"]; cid = u["cid"]; tok = P["m"].get(cid) if cid else None; key = u.get("key") or (tok["key"] if tok else None)
            att = u.get("attach", "word")
            for k, w in enumerate(u["words"]):
                if not w:
                    continue
                if att == "prev" and tags and k == 0:
                    pass
                elif pending_next:
                    pending_next = False
                else:
                    wno += 1
                tags += [[p, wno, s, cid, key, u["how"]] for p, s in w]
                if att == "next":
                    pending_next = True
        if tags and self.rules.get("caps", 0) >= 0.8:    # the verse's first part capitalised, as the team writes it
            tags[0][0] = cap1(tags[0][0])
        first = {}
        for i, (p, wn, s, cid, key, how) in enumerate(tags):
            if key:
                first.setdefault(key, [i, i, how])[1] = i
        at = {key: (a, z - a + 1, how) for key, (a, z, how) in first.items()}
        for P, c in zeros:                          # R6's zero keeps the agreement part: the participant points at the verb's agreement slot
            t = P["m"].get(c["cid"])
            if t is None or t["key"] in at:
                continue
            role = c["f"].get("role"); hit = None
            if c["f"].get("depth") == 0 and role in ("Most Agent-like", "Most Patient-like"):
                who = "subj" if role == "Most Agent-like" else "obj"
                vc = [v["cid"] for v in P["cons"] if v["cat"] == "V" and v["f"].get(f"{who}_cid") == c["cid"]]
                hit = next((i for i, tg in enumerate(tags) if tg[3] in vc and tg[2] in self.agr.get(("V", who), [])), None)
            elif c.get("of"):
                hit = next((i for i, tg in enumerate(tags) if tg[3] == c["of"] and tg[2] in self.agr.get(("N", "poss"), [])), None)
            at[t["key"]] = (hit, 1, "R6-zero-agreement") if hit is not None else (0, 0, "zero")
        self.tagged[ref] = tags
        return [t[0] for t in tags], at


# ------------------------------------------------------------------ learning and the run

def settings_of(lang):
    """research's final settings and overrides of the language (private/tbta/research-t2/<lang>/loop_state.json), without
    the old engine's head stems (r10_b0), which the lexicon replaces"""
    st = json.load(open(K.tbta("research-t2", lang, "loop_state.json"), encoding="utf-8"))
    S = json.loads(json.dumps(L.DEFAULTS)); S.update(st["settings"]); S.pop("r10_b0", None); S.setdefault("r10_lex", "first")
    return S, [tuple(x) for x in st.get("overrides", [])]


def team_overrides(reg):
    """the team's decided rules in the register (shared/register.py: kind rule, basis team, with table, conditions and do) as engine
    overrides [(table, rule)]: added when the rules are loaded for a draft, never learned in, so a decision taken in
    (onboard/intake.py) applies at once; tried before every other rule (rules_engine.Table)"""
    if not reg or not os.path.exists(os.path.join(reg, "VERSION.json")):
        return []
    from shared import register as RG
    return [(e["table"], {"kind": e["table"].split(".")[0], "when": e["conditions"], "do": e["do"], "why": e.get("said") or e["value"],
                          "source": f"team:{e['id']}", "n": 0, "share": 0})
            for e in RG.live(RG.load(reg)) if e["kind"] == "rule" and e["basis"] == "team" and e["status"] == "decided"
            and e.get("table") and e.get("conditions") is not None and e.get("do")]


def rules_name(leave_out):
    return "nt" + "".join(f"-{b}" for b in sorted(leave_out))


def train_chapters(cfg, leave_out):
    """the TBTA NT chapters with team text, outside the shut chapters, the corpus's excluded books and the books left out"""
    x = paths.corpus(cfg, "grc"); excl = set(x.get("exclude_books", ())) | set(leave_out); shut = holdout.shut(cfg)
    return [(b, c) for b, c in K.chapters(set(K.NT_BOOKS), shut) if b not in excl]


def cmd_learn(a, leave=None):
    cfg = paths.config(a.lang); leave = sorted(leave if leave is not None else (x for x in (a.leave_out or "").split(",") if x))
    S, ov = settings_of(a.lang); t0 = time.time(); chs = train_chapters(cfg, leave)
    T = L.Train(cfg, chs, S); rules = L.learn(T, S, ov); rules["function_parts"] = sorted(T.FUNC); rules["meta"]["left out"] = leave
    d = K.tbta("rules", a.lang); os.makedirs(d, exist_ok=True); p = os.path.join(d, rules_name(leave) + ".json")
    json.dump(rules, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{a.lang}: {len(chs)} chapters, {len(T.B.props)} propositions, {len(rules['function_parts'])} function parts, "
          f"{sum(len(t['rules']) for t in rules['tables'].values())} rules, {time.time() - t0:.0f}s -> {p}")
    return p


def load_rules(a, cfg, leave, chs):
    p = K.tbta("rules", a.lang, rules_name(leave) + ".json")
    if not os.path.exists(p):
        cmd_learn(a, leave)
    rules = json.load(open(p, encoding="utf-8")); team = team_overrides(getattr(a, "register", None) or cfg.get("_register"))
    for tname, r in team:
        rules["tables"].setdefault(tname, {"levels": [], "rules": []})["rules"].append(r)
    rules["meta"]["team rules"] = len(team)
    bad = sorted({f"{a.book} {c}" for c in chs} & set(rules["meta"]["chapters"]))
    if bad:
        sys.exit(f"{', '.join(bad)} in the rules' training: leave {a.book} out (--leave-out {a.book})")
    return rules, p


def prepare(a, cfg, chs, leave, rules, source):
    """(Corpus of the job's book, Drafter with its Book) for the chapters chs; a Hebrew job's matcher learns its concept-lemma
    association on Genesis's TBTA spans (source side only), the job's chapters left out"""
    guard = K.Guard(cfg); shut = holdout.shut(cfg); skip = {(a.book, c) for c in chs}
    from drafting import lexicon as LX
    lex = LX.Lexicon(cfg, skip, leave)
    lex = lex if lex.ok else None
    if source == "grc":
        C = K.Corpus(cfg, "grc", [a.book], text=False); D = Drafter(rules, lex=lex, source="grc", src=K.SourceFields("grc") if rules["meta"]["settings"].get("src_feats") else None)
        M = D.matcher()
    else:
        C = K.Corpus(cfg, "hbo", sorted({a.book, "GEN"}), text=False)
        D = Drafter(rules, lex=lex, source="hbo", src=K.SourceFields("hbo") if rules["meta"]["settings"].get("src_feats") else None)
        M = K.Matcher("H"); gen = [x for x in K.chapters({"GEN"}, shut) if x not in skip]
        Bg = K.Book(C, gen, None, K.load_resolved({"GEN"}), guard); M.learn_assoc([(P["cons"], P["toks"]) for P in Bg.props.values() if P["toks"]])
    D.B = K.Book(C, [(a.book, c) for c in chs], M, K.load_resolved({a.book}), guard)
    return C, D


def cut(words, keys_of):
    """drafted words [(text, source key | None, how)] of a verse group -> per clause [(text, how)]: a word goes to the clause
    holding its source token; a word without one (an inserted function part) to the clause of the word before it (the first
    clause at the start)"""
    by_key = {k: i for i, ks in enumerate(keys_of) for k in ks}; out = [[] for _ in keys_of]; cur = 0
    for text, key, how in words:
        cur = by_key.get(key, cur) if key else cur
        out[cur].append((text, how))
    return out


def verse_words(tags):
    """a verse's tags -> [(word, source key of its stem part (else its first keyed part), how)]; unknown concepts dropped"""
    by = collections.OrderedDict()
    for p, wn, s, cid, key, how in tags:
        by.setdefault(wn, []).append((p, s, key, how))
    out = []
    for ps in by.values():
        w = "".join(p for p, _, _, _ in ps)
        if "<" in w:
            continue
        k = next((x for p, s, x, h in ps if s == "stem" and x), None) or next((x for _, _, x, _ in ps if x), None)
        out.append((w, k, next((h for _, s, _, h in ps if s == "stem"), ps[0][3])))
    return out


def cmd_draft(a):
    from drafting import draft, evidence, prompt
    cfg = paths.config(a.lang); chs = draft.chapters_arg(a.chapters); source = draft.source_of(a.book)
    leave = sorted(x for x in (a.leave_out or "").split(",") if x); shut = holdout.shut(cfg)
    if any(shut(a.book, c) for c in chs):
        sys.exit(f"{a.book} {[c for c in chs if shut(a.book, c)]}: closed or held out; not drafted without the user's go")
    rules, rp = load_rules(a, cfg, leave, chs); rules["meta"]["settings"].update(json.loads(a.set or "{}"))
    E = evidence.build(cfg, source, a.book, chs, tuple(leave))
    C, D = prepare(a, cfg, chs, leave, rules, source)
    groups = collections.OrderedDict()
    for qid in E.order:
        q = E.queries[qid]; groups.setdefault(sorted(q["refs"], key=prompt.ref_key)[0], []).append(q)
    od = draft.job_dir(a, "answers"); gj, trace = {}, {}; st = collections.Counter()
    for v, cl in groups.items():
        refs = sorted({r for q in cl for r in q["refs"]}, key=prompt.ref_key); words = []
        for r in refs:
            r2 = C.heb2ref.get(r, r) if source == "hbo" else r
            if r2 in D.B.verses:
                D.verse(C, r2); words += verse_words(D.tagged[r2]); st["verses drafted"] += 1
            else:
                st["verses without TBTA"] += 1
        per = cut(words, [{t["key"] for t in q["tokens"]} for q in cl])
        json.dump({"clauses": [{"c": k, "text": " ".join(w for w, _ in ws)} for k, ws in enumerate(per, 1)]},
                  open(os.path.join(od, draft.vid(v) + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
        gj[draft.vid(v)] = {"refs": refs, "clauses": [q["id"] for q in cl]}
        for q, ws in zip(cl, per):
            trace[q["id"]] = [h for _, h in ws]; st["clauses"] += 1; st["clauses without words"] += not ws; st["words"] += len(ws)
    draft.save_groups(a, gj); m = draft.load_manifest(a)
    m["builds"].append({"when": time.strftime("%Y-%m-%d %H:%M"), "code": draft.commit(), "kind": "rules", "source": source, "chapters": chs,
                        "verses": len(groups), "clauses": len(E.order), "evidence": E.meta, "leave out": leave,
                        "model": "rules learned from the team's New Testament", "rules": {"file": os.path.basename(rp), "date": rules["meta"]["date"],
                        "training chapters": len(rules["meta"]["chapters"]), "settings": rules["meta"]["settings"], "overrides": rules["meta"].get("overrides", 0), "team rules": rules["meta"].get("team rules", 0)},
                        "lexicon": {"words.db built": D.lex.built} if D.lex else None, "figures": dict(st), "log": dict(D.log)})
    draft.save_manifest(a, m)
    json.dump(trace, open(os.path.join(draft.job_dir(a), "trace.json"), "w"), indent=0)
    print(json.dumps(dict(st)), "->", od)


def cmd_score(a):
    """research's figure on the book's TBTA chapters with team text: per verse the drafted parts against the team's parts as
    marked strings (words by spaces, parts by '@@ '), corpus chrF (sacrebleu's default, beta 2); --on for the ladder"""
    from sacrebleu.metrics import CHRF
    from drafting import draft
    cfg = paths.config(a.lang); source = "grc" if a.book in K.NT_BOOKS else "hbo"; shut = holdout.shut(cfg)
    leave = sorted(x for x in (a.leave_out or "").split(",") if x)
    chs = [c for b, c in K.chapters({a.book}, shut)] if not a.chapters else draft.chapters_arg(a.chapters)
    rules, _ = load_rules(a, cfg, leave, chs)
    rules["meta"]["settings"].update(json.loads(a.set or "{}"))
    C, D = prepare(a, cfg, chs, leave, rules, source); D.on = set(a.on or ALL)
    T = K.Corpus(cfg, source, [a.book]); hyp, ref, n = [], [], 0
    for r in D.B.refs(text=False):
        if r not in T.verses or T.verses[r]["ch"] not in chs:
            continue
        D.verse(C, r); tg = D.tagged[r]; v = T.verses[r]; n += 1
        hyp.append(K.marked([t[0] for t in tg], [t[1] for t in tg])); ref.append(K.marked(v["words"], v["wordidx"]))
    s = CHRF().corpus_score(hyp, [ref]).score
    print(json.dumps({"language": a.lang, "book": a.book, "chapters": chs, "verses": n, "chrF (parts)": round(s, 2), "on": sorted(D.on),
                      "settings": json.loads(a.set or "{}"), "log": dict(D.log)}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("learn", "draft", "score")); ap.add_argument("--lang", required=True); ap.add_argument("--book")
    ap.add_argument("--chapters"); ap.add_argument("--label", default="rules"); ap.add_argument("--leave-out")
    ap.add_argument("--on", nargs="*", help="score: the rule types in use (default all)"); ap.add_argument("--set", help="settings over the rules' (JSON)")
    ap.add_argument("--register", help="draft: the team's rules from this register folder (a trial; default the language's)")
    a = ap.parse_args(); a.book = (a.book or "").upper()
    if a.cmd != "learn" and not a.book:
        sys.exit("draft and score need --book")
    if a.cmd == "draft" and not a.chapters:
        sys.exit("draft needs --chapters")
    {"learn": cmd_learn, "draft": cmd_draft, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    main()
