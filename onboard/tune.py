#!/usr/bin/env python3
"""Auto-tuning, the optional phase T (internal-docs/review-feedback-data-plan-2026-11-10.md, section 3.12; stage S7), for the
free settings: the rule engine's (alternatives/rules_learn.py DEFAULTS). Every language starts from the code's defaults.

A trial is declared before it runs and not changed while it runs:

  plan     -> $MAKE_TANAKH_PRIVATE/lang/<iso>/tuning/<trial>/plan.json: the start (defaults, or --start research for a
            comparison), the dev chapters and the confirm chapters (one book, left out of every training: the trial's own
            hold-out), the candidate patches (CANDIDATES: research's actions, generic), the guard, the rounds
  run      the search: per round every candidate against the current state, paired by verse on the dev chapters; the
            kept candidate is the one with the largest gain that passes the guard; stop after --rounds rounds or a round
            that keeps nothing. Every evaluation goes to log.jsonl
  confirm  the kept state against the start on the confirm chapters; each kept patch is tested alone there too, and stays
            only if it does not lose (result.json says which and why)
  show     the trial's figures

The guard (research's, two-sided, on this repository's yardstick): chrF3 on the draft's words against the team's text
(drafting/devcheck.py's statistics, paired bootstrap over verses, 1,000 resamples, seed 7) rises: interval above 0, or
mean > 0 with the lower bound above -0.2; and chrF3 on the parts (the words cut into their pieces) does not fall: mean
>= -0.2 and the upper bound >= 0. Nothing here touches the team's register or the language's rules: learned rules stay in
memory; the record is the trial folder. Kept values go into the language's settings only by `take`:

  take     the confirmed settings of a trial -> $MAKE_TANAKH_PRIVATE/lang/<iso>/settings.json {"rules": ..., "trial": ...},
            which alternatives/rules.py reads before research's state (relearn the rules afterwards: rules.py learn)

    . ./env.sh; P=~/sil-study/.venv/bin/python
    $P onboard/tune.py plan --lang zin --trial t1 --dev JHN:1-4 --confirm JHN:5-8
    $P onboard/tune.py run --lang zin --trial t1
    $P onboard/tune.py confirm --lang zin --trial t1"""
import argparse, collections, copy, json, os, random, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import holdout, paths  # noqa: E402
from alternatives import rules as RU, rules_engine as K, rules_learn as L  # noqa: E402
from drafting import devcheck as DC, draft  # noqa: E402

WIDEN = ["type", "illoc", "genre", "sequence", "prev_tgroup", "subj_pn", "obj_pn", "subj_pnc", "obj_pnc"]
CANDIDATES = (                                   # research's actions (lab/tbta_drafter/loop.py ACTIONS, SLOT_PATCHES), generic
    [{"r3_min_share": v} for v in (0.4, 0.3, 0.2)] + [{"r3_min_lift": 1.5}, {"r3_min_share": 0.6}, {"r3_min_lift": 3.0}, {"r3_min_n": 10}]
    + [{"r1_min_sense_n": v} for v in (3, 10)]
    + [{"r6_zero_min": v} for v in (0.6, 0.7, 0.8)] + [{"r6_min_share": 0.6}, {"r6_min_n": 20}]
    + [{"r7_drop_share": v} for v in (0.6, 0.5, 0.8)] + [{"r7_drop_min_n": 3}, {"r7_drop_apply": 0.8}, {"r7_drop_apply": 0.9}]
    + [{"r5_min_n": v} for v in (3, 10, 20)] + [{"r7_merge_share": v} for v in (0.7, 0.9)]
    + [{"r4_min_purity": v} for v in (0.6, 0.5)] + [{"r2_min_share": v} for v in (0.4, 0.6)] + [{"r2_infl_margin": v} for v in (0.0, 0.02)]
    + [{"r2_min_n": 10}] + [{"r2_base_add": f} for f in ("sperson", "sforce", "sneg", "svoice")]
    + [{"r9_min_share": v} for v in (0.4, 0.6)] + [{"src_trig_add": f} for f in ("sperson", "sforce", "sneg", "svoice", "sline")]
    # the engine's switches (rule types and options the defaults leave off)
    + [{"r9": True}, {"r10": True, "r10_lex": "first"}, {"r10_min_n": 2}, {"r10_head": True}, {"r10_orphans": True}, {"r10_adv": True},
       {"lexform_min_n": 2, "lexform_min_share": 0.5}, {"src_fill": True}, {"r2_extra_add": ["V.p2.0", "subj_pnc"]}, {"r6_fields_add": "svoice"}]
)
GUARD = {"target": "chrF3 (words)", "rise": "interval above 0, or mean > 0 and lower bound > -0.2",
         "second": "chrF3 (parts)", "no fall": "mean >= -0.2 and upper bound >= 0"}


def tdir(lang, trial, *p):
    return paths.lang_dir(lang, "tuning", trial, *p)


def patch(S, p):
    """S with one candidate applied (r2_base_add adds a field to the verb's base key, src_trig_add one to the source triggers)"""
    S = copy.deepcopy(S)
    for k, v in p.items():
        if k == "r2_base_add":
            S["r2_base"]["V"] = S["r2_base"]["V"] + ([v] if v not in S["r2_base"]["V"] else [])
        elif k == "r2_extra_add":
            S.setdefault("r2_extra", {}); S["r2_extra"][v[0]] = S["r2_extra"].get(v[0], []) + ([v[1]] if v[1] not in S["r2_extra"].get(v[0], []) else [])
        elif k == "r6_fields_add":
            S["r6_fields"] = S["r6_fields"] + ([v] if v not in S["r6_fields"] else [])
        elif k == "src_trig_add":
            S["src_feats"] = True; S["src_trig"] = list(S.get("src_trig") or []) + ([v] if v not in (S.get("src_trig") or []) else [])
        else:
            S[k] = v
    return S


def applies(S, p):
    """whether the candidate changes S"""
    return patch(S, p) != S


def spec(s):
    b, _, c = s.partition(":"); return b.upper(), draft.chapters_arg(c)


class Bench:
    """the trial's fixed material: the training (all TBTA NT chapters but the trial's book), the team's text, and per chapter set
    the drafting book; evaluate(S, chapters) -> per verse (words stats, parts stats)"""
    def __init__(self, lang, book, leave):
        self.cfg = paths.config(lang); self.lang, self.book = lang, book; self.leave = sorted(set(leave) | {book})
        self.chs = RU.train_chapters(self.cfg, self.leave); self.T = {}
        self.V = DC.team_text(self.cfg, "grc"); self.books = {}
        from drafting import lexicon as LX
        a = argparse.Namespace(lang=lang, book=book)
        self.lex = LX.Lexicon(self.cfg, {(book, c) for c in range(1, 200)}, self.leave); self.lex = self.lex if self.lex.ok else None
        self.C = K.Corpus(self.cfg, "grc", [book], text=False); self.Ct = K.Corpus(self.cfg, "grc", [book]); self.a = a

    def train(self, S):
        k = bool(S.get("src_feats"))
        if k not in self.T:
            self.T[k] = L.Train(self.cfg, self.chs, S)
        return self.T[k]

    def evaluate(self, S, chapters):
        T = self.train(S); rules = L.learn(T, S, ()); rules["function_parts"] = sorted(T.FUNC)
        D = RU.Drafter(rules, lex=self.lex, source="grc", src=K.SourceFields("grc") if S.get("src_feats") else None)
        key = tuple(chapters)
        if key not in self.books:
            M = D.matcher(); self.books[key] = K.Book(self.C, [(self.book, c) for c in chapters], M, K.load_resolved({self.book}), K.Guard(self.cfg))
        D.B = self.books[key]; out = {}
        for r in D.B.refs(text=False):
            v = self.Ct.verses.get(r)
            if not v or v["ch"] not in chapters or r not in self.V:
                continue
            D.verse(self.C, r); tg = D.tagged[r]; parts, idx = [t[0] for t in tg], [t[1] for t in tg]
            out[r] = (DC.stats(K.marked(parts, idx, ""), " ".join(self.V[r])),
                      DC.stats(K.marked(parts, idx, "|"), K.marked(v["words"], v["wordidx"], "|")))
        return out


def figure(rows):
    return round(DC.fscore(rows)[0], 2)


def compare(base, new):
    """{figure: (base, new, [mean, lower, upper] of new - base)} on the verses both have"""
    refs = sorted(set(base) & set(new)); out = {}
    for i, name in ((0, "chrF3 (words)"), (1, "chrF3 (parts)")):
        xs, ys = [base[r][i] for r in refs], [new[r][i] for r in refs]
        f = lambda rows: DC.fscore(rows)[0]
        out[name] = (figure(xs), figure(ys), DC.boot(xs, ys, f))
    return out


def passes(c):
    m, lo, hi = c["chrF3 (words)"][2]; m2, lo2, hi2 = c["chrF3 (parts)"][2]
    return (lo > 0 or (m > 0 and lo > -0.2)) and m2 >= -0.2 and hi2 >= 0


def start_settings(lang, start):
    S = copy.deepcopy(L.DEFAULTS)
    if start == "research":
        S, _ = RU.settings_of(lang)
    return S


def cmd_plan(a):
    d = tdir(a.lang, a.trial)
    if os.path.exists(os.path.join(d, "plan.json")):
        sys.exit(f"{d}: a trial of that name exists; a trial is not changed once declared")
    os.makedirs(d); db, dc = spec(a.dev); cb, cc = spec(a.confirm)
    if db != cb:
        sys.exit("dev and confirm chapters are of one book (the trial leaves that book out of every training)")
    shut = holdout.shut(paths.config(a.lang)); bad = [c for c in dc + cc if shut(db, c)]
    if bad or set(dc) & set(cc):
        sys.exit(f"closed or held-out chapters {bad}, or dev and confirm overlap")
    have = {c for _, c in K.chapters({db})}; none = [c for c in dc + cc if c not in have]
    if none:
        sys.exit(f"{db} {none}: no TBTA propositions (chapters with them: {sorted(have)})")
    S = start_settings(a.lang, a.start)
    plan = {"language": a.lang, "trial": a.trial, "declared": time.strftime("%Y-%m-%d %H:%M"), "start": a.start, "settings": S,
            "book": db, "dev": dc, "confirm": cc, "left out of training": sorted({db} | set(x for x in (a.leave_out or "").split(",") if x)),
            "candidates": CANDIDATES, "guard": GUARD, "rounds": a.rounds, "code": draft.commit()}
    json.dump(plan, open(os.path.join(d, "plan.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"declared {d}/plan.json: {len(CANDIDATES)} candidates, dev {db} {dc}, confirm {db} {cc}, start {a.start}")


def cmd_run(a):
    d = tdir(a.lang, a.trial); plan = json.load(open(os.path.join(d, "plan.json"), encoding="utf-8"))
    B = Bench(a.lang, plan["book"], plan["left out of training"]); S = plan["settings"]; kept = []; log = open(os.path.join(d, "log.jsonl"), "a")
    t0 = time.time(); base = B.evaluate(S, plan["dev"]); w0 = figure([x[0] for x in base.values()])
    print(f"start: chrF3 (words) {w0}, parts {figure([x[1] for x in base.values()])}, {len(base)} verses ({time.time() - t0:.0f} s)", flush=True)
    for rnd in range(1, plan["rounds"] + 1):
        best = None
        for p in plan["candidates"]:
            if not applies(S, p):
                continue
            t1 = time.time(); c = compare(base, B.evaluate(patch(S, p), plan["dev"])); ok = passes(c)
            row = {"round": rnd, "patch": p, "words": c["chrF3 (words)"], "parts": c["chrF3 (parts)"], "passes": ok, "s": round(time.time() - t1)}
            log.write(json.dumps(row) + "\n"); log.flush()
            print(f"  r{rnd} {json.dumps(p)}: words {c['chrF3 (words)'][2]} parts {c['chrF3 (parts)'][2]} {'PASS' if ok else ''}", flush=True)
            if ok and (best is None or c["chrF3 (words)"][2][0] > best[1]["chrF3 (words)"][2][0]):
                best = (p, c)
        if not best:
            print(f"round {rnd}: nothing kept; the search stops", flush=True); break
        S = patch(S, best[0]); kept.append({"round": rnd, "patch": best[0], "dev": best[1]}); base = B.evaluate(S, plan["dev"])
        print(f"round {rnd}: kept {json.dumps(best[0])} -> chrF3 (words) {figure([x[0] for x in base.values()])}", flush=True)
        json.dump({"settings": S, "kept": kept}, open(os.path.join(d, "state.json"), "w", encoding="utf-8"), indent=1)
    json.dump({"settings": S, "kept": kept, "dev chrF3 (words)": [w0, figure([x[0] for x in base.values()])], "minutes": round((time.time() - t0) / 60)},
              open(os.path.join(d, "state.json"), "w", encoding="utf-8"), indent=1)


def cmd_confirm(a):
    d = tdir(a.lang, a.trial); plan = json.load(open(os.path.join(d, "plan.json"), encoding="utf-8"))
    st = json.load(open(os.path.join(d, "state.json"), encoding="utf-8")); B = Bench(a.lang, plan["book"], plan["left out of training"])
    have = {c for _, c in K.chapters({plan["book"]})}; chs = [c for c in plan["confirm"] if c in have]
    # a plan declared before plan checked for TBTA data: only the declared chapters that have it, never others
    S0 = plan["settings"]; base = B.evaluate(S0, chs)
    res = {"chapters": chs, "declared without TBTA data": [c for c in plan["confirm"] if c not in have], "verses": len(base),
           "all kept": compare(base, B.evaluate(st["settings"], chs)), "each": []}
    for k in st["kept"]:
        c = compare(base, B.evaluate(patch(S0, k["patch"]), chs))
        res["each"].append({"patch": k["patch"], "confirm": c, "stays": c["chrF3 (words)"][2][0] >= 0})
    S = copy.deepcopy(S0)
    for e in res["each"]:
        if e["stays"]:
            S = patch(S, e["patch"])
    res["settings"] = S; res["final on confirm"] = compare(base, B.evaluate(S, chs)) if S != st["settings"] else res["all kept"]
    json.dump(res, open(os.path.join(d, "result.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({"all kept": res["all kept"], "each": [(e["patch"], e["confirm"]["chrF3 (words)"][2], e["stays"]) for e in res["each"]],
                      "final": res["final on confirm"]}, indent=0))


def cmd_take(a):
    d = tdir(a.lang, a.trial); r = os.path.join(d, "result.json")
    if not os.path.exists(r):
        sys.exit(f"{a.trial}: not confirmed (run confirm first)")
    res = json.load(open(r, encoding="utf-8")); p = paths.lang_dir(a.lang, "settings.json")
    cur = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    if cur.get("rules"):
        json.dump(cur, open(os.path.join(d, "settings.before.json"), "w", encoding="utf-8"), indent=1)
    cur["rules"] = res["settings"]; cur["rules trial"] = {"trial": a.trial, "taken": time.strftime("%Y-%m-%d"),
                                                          "confirm": res["final on confirm"]["chrF3 (words)"]}
    json.dump(cur, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{a.lang}: the rule settings of trial {a.trial} taken -> {p}; relearn: rules.py learn --lang {a.lang}")


def cmd_show(a):
    d = tdir(a.lang, a.trial)
    for f in ("plan.json", "state.json", "result.json"):
        if os.path.exists(os.path.join(d, f)):
            x = json.load(open(os.path.join(d, f), encoding="utf-8")); x.pop("candidates", None); print(f, json.dumps(x, ensure_ascii=False)[:1500])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("plan", "run", "confirm", "take", "show")); ap.add_argument("--lang", required=True); ap.add_argument("--trial", required=True)
    ap.add_argument("--dev", default="JHN:1-4"); ap.add_argument("--confirm", default="JHN:5-8"); ap.add_argument("--leave-out")
    ap.add_argument("--start", choices=("defaults", "research"), default="defaults"); ap.add_argument("--rounds", type=int, default=12)
    a = ap.parse_args()
    {"plan": cmd_plan, "run": cmd_run, "confirm": cmd_confirm, "take": cmd_take, "show": cmd_show}[a.cmd](a)


if __name__ == "__main__":
    main()
