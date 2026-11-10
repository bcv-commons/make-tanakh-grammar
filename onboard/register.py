#!/usr/bin/env python3
"""The language's register (shared/register.py): the questionnaire, the seed, the check.

  parameters  register/parameters.tsv from the parameter lists (Grambank, WALS, AutoTyp, APICS: CC BY 4.0; our MT-
              rows), copied from research into $PRIVATE/lists/ (lab/onboard/*.csv)
  seed        $PRIVATE/lang/<iso>/register/ from what the language has today:
                - the language store (cfg "store"): terms, names, formulas, morphs, words, letters, features, claims,
                  gaps and the orthography; superseded entries and statistics (cells, alternation cues) are left out
                - the team's answers (the store's wiki/team-input.md): one `answer` per item, its words verbatim, and
                  `from` on every entry made from it
                - register/seed/known.json (research's register values) as features
                - register/seed/team-questions.md (questions drafted for the team, not sent) as open questions
                - words.db: terms proposed from the team's forms per lexeme where the store has none
  check       the register's rules, the team's terms as the drafter reads them, every team entry tied to its answer

    . ./env.sh; python3 onboard/register.py parameters | seed --lang kvg | check --lang kvg

The register holds forms of the team's text, so before the freeze it is private (`private/lang/<iso>/register/`); after
it, the language repository's `.tanakh/register/` (internal-docs/review-feedback-data-plan-2026-11-10.md)."""
import argparse, collections, csv, json, os, re, sqlite3, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths, register as RG  # noqa: E402

TODAY = time.strftime("%Y-%m-%d")
STRIP = {"term": "term", "name": "name", "formula": "formula", "m": "morph", "w": "word", "letter": "letter",
         "gap": "choice", "claim": "rule", "gb": "feature"}
TERM_MIN, TERM_TOP, TERM_SHARE = 10, 3, 0.05       # words.db: links a lexeme needs; forms proposed; their least share
# the generated MT rows (research's lab/onboard/register.py, 2026-11-01): per grammatical category the morphability measures
# of step C2, per source-side operator how the source analysis exposes it
CATEGORIES = [("PER", "subject person and number"), ("ARGMK", "object marking"), ("NUM", "noun number"),
              ("GEND", "gender / noun class and concord"), ("TENSE", "tense"), ("ASPECT", "aspect"), ("MOOD", "mood / modality"),
              ("POL", "polarity"), ("VOICE", "voice"), ("VALENCY", "valency change (extensions)"), ("DEF", "definiteness / augment"),
              ("CASE", "case"), ("INTERR", "interrogativity"), ("JUNCT", "juncture"), ("REL", "relative"), ("COP", "copula"),
              ("LOC", "locative")]
C2_FIELDS = [("LOAD", "code", "bound;free;none;mixed"), ("EXPOSURE", "share", ""), ("LEAK", "share", ""), ("FILL", "share", ""),
             ("VERDICT", "code", "bound_uncut;mixed;exposed;unmarked_or_unseen")]
OPERATORS = ["ASPECT", "NEG", "DIR", "MODALITY", "STATUS", "TENSE", "EVID", "IF", "PER", "ROLE", "SUBJ", "SPEECH", "LINE",
             "SWITCH", "FOCUS", "NP-NUM", "NP-DEF", "NP-DEIXIS", "NP-CASE"]
SRC_FIELDS = [("EXPOSED", "code", "label;unit;derived;none"), ("COVERAGE", "share", "")]


# ------------------------------------------------------------------ the questionnaire

def cmd_parameters(a):
    L = paths.private("lists"); rows = []
    codes = collections.defaultdict(list)
    for f in ("grambank_codes.csv", "wals_codes.csv"):
        for r in csv.DictReader(open(os.path.join(L, f), encoding="utf-8")):
            codes[r["Parameter_ID"]].append(f"{r['ID'].rsplit('-', 1)[1]}={r.get('Description') or r['Name']}")
    for f, src, grp in (("grambank_parameters.csv", "Grambank v1.0.2 (CC BY 4.0)", None), ("wals_parameters.csv", "WALS Online (CC BY 4.0)", None),
                        ("autotyp_parameters.csv", "AUTOTYP (CC BY 4.0)", "Module"), ("apics_parameters.csv", "APiCS Online (CC BY 4.0)", "Area"),
                        ("mt_parameters.csv", "make-tanakh (CC0)", "Step")):
        for r in csv.DictReader(open(os.path.join(L, f), encoding="utf-8")):
            c = r.get("Codes") or "; ".join(codes.get(r["ID"], []))
            rows.append({"id": r["ID"], "question": r["Name"], "codes": c.replace("\t", " "), "group": r.get(grp or "", "") or "",
                         "type": r.get("Type", ""), "source": src})
    for cat, name in CATEGORIES:
        for field, typ, c in C2_FIELDS:
            rows.append({"id": f"MT-C2-{field}-{cat}", "question": f"{field.lower()} of {name}", "codes": c, "group": "C2", "type": typ,
                         "source": "make-tanakh (CC0)"})
    for op in OPERATORS:
        for field, typ, c in SRC_FIELDS:
            rows.append({"id": f"MT-SRC-{field}-{op}", "question": f"source side: {field.lower()} of {op}", "codes": c, "group": "C2",
                         "type": typ, "source": "make-tanakh (CC0)"})
    with open(RG.PARAMETERS, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "question", "codes", "group", "type", "source"], delimiter="\t", lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} parameters -> {RG.PARAMETERS}", collections.Counter(r["source"] for r in rows))


# ------------------------------------------------------------------ the seed

def basis_of(e):
    m, by = e.get("method"), str(e.get("by", ""))
    if m == "team-decision":
        return "team"
    if m == "project-decision":
        return "human"
    if m == "external":
        return "external"
    return "model" if by.startswith("agent:") else "derived"


def status_of(e, basis):
    if basis in ("team", "human") and e.get("status") == "decided":
        return "decided"
    return "open" if e.get("status") == "open" else "proposed"


def new_id(e):
    """(kind, register id) of a store entry; None for statistics"""
    sid, k = e["id"], e["kind"]
    if k == "cell" or sid.startswith("alt:"):
        return None
    if sid.startswith("gs:"):
        return "feature", "feature:" + sid
    pre = sid.split(":", 1)[0] if ":" in sid else None
    kind = STRIP.get(pre) or {"feature": "rule", "claim": "rule", "gap": "choice"}.get(k, k)
    if k == "feature" and pre == "gb":
        kind = "feature"
    name = sid.split(":", 1)[1] if pre in STRIP else sid
    return kind, f"{kind}:{name}"


def renderings(e):
    out = [{"form": e["value"], "status": "preferred"}] if isinstance(e.get("value"), str) else []
    for x in e.get("alternatives", []) or []:
        if isinstance(x, dict) and x.get("value"):
            out.append({"form": x["value"], "status": "admitted", **({"n": x["n"]} if x.get("n") else {})})
    return out


def from_store(e, kind, rid, src, team_of):
    b = basis_of(e); st = status_of(e, b)
    env = dict(supersedes=None, evidence=[{k: v for k, v in x.items() if k in ("ref", "form", "n")} for x in e.get("evidence", []) or [] if isinstance(x, dict)],
               origin=f"store:{src}#{e['id']}", note=e.get("note"), **({"from": [team_of[e["team_source"]]]} if e.get("team_source") in team_of else {}))
    by = e.get("by") or "unknown"
    when = e.get("date") or TODAY
    if kind in ("term", "name", "formula"):
        pay = dict(source=e.get("source"), renderings=renderings(e) if kind != "formula" else None, gloss=e.get("gloss"), words=e.get("words"),
                   attested=e.get("attested"), replaces=e.get("replaces") if kind != "formula" else None)
        if kind == "formula":
            pay["pattern"] = e.get("pattern"); pay["renderings"] = renderings(e) if isinstance(e.get("value"), str) else None
        pay = {k: v for k, v in pay.items() if v is not None}
    elif kind == "morph":
        pay = {k: e[k] for k in RG.KINDS["morph"][1] if k in e}
    elif kind == "word":
        pay = dict(form=e.get("form"), parts=e.get("parts"), gloss=e.get("gloss"), affixes=e.get("affixes"), never_split=e.get("value") in ("WORD", "NAME"))
    elif kind == "feature":
        codes = e.get("codes") or []
        pay = dict(parameter=next((c for c in codes if re.match(r"GB\d", c)), None) or (rid.split(":", 1)[1] if rid.startswith("feature:GB") else None),
                   confidence=e.get("confidence"))
        if e.get("external_source"):
            env["note"] = (env["note"] + "; " if env["note"] else "") + f"external: {e['external_source']}"
    elif kind == "rule":
        pay = dict(said=e["value"] if isinstance(e.get("value"), str) else json.dumps(e.get("value"), ensure_ascii=False),
                   verdict=e.get("verdict"), pattern=e.get("pattern"))
    elif kind == "choice":
        pay = dict(ref=None, source=e.get("source"))
    elif kind == "letter":
        pay = {}
    else:
        pay = {}
    pay = {k: v for k, v in pay.items() if v not in (None, [], {}, "")}
    value = e["value"] if not isinstance(e.get("value"), (dict, list)) or kind == "formula" else json.dumps(e["value"], ensure_ascii=False)
    return RG.entry(kind, rid.split(":", 1)[1], value, st, b, by, when, **env, **pay)


def answers(team_input):
    """team-input.md -> [(T id, date, who, status line, text)]"""
    ITEM = re.compile(r"^### (T\d+) · (\d{4}-\d{2}-\d{2}) · ([^\n]+?)[ \t]*\n(?:Status: ([^\n]*)\n)?(.*?)(?=^### T\d+ · |^## |\Z)", re.M | re.S)
    if not os.path.exists(team_input):
        return []
    return [(m.group(1), m.group(2), m.group(3), m.group(4) or "", m.group(5).strip()) for m in ITEM.finditer(open(team_input, encoding="utf-8").read())]


def questions(p):
    """team-questions.md -> [(n, group, title, text)]"""
    if not os.path.exists(p):
        return []
    out, group = [], None
    s = open(p, encoding="utf-8").read()
    for blk in re.split(r"^(?=## |\d+\. )", s, flags=re.M):
        if blk.startswith("## "):
            group = blk.splitlines()[0][3:].strip(); continue
        m = re.match(r"(\d+)\. (.*)", blk, re.S)
        if m:
            t = m.group(2).strip(); tm = re.match(r"\*\*(.+?)\*\*\s*(.*)", t, re.S)
            out.append((int(m.group(1)), group, tm.group(1).strip(" .") if tm else t[:60], re.sub(r"\s+", " ", t)))
    return out


def known(p):
    if not os.path.exists(p):
        return []
    d = json.load(open(p, encoding="utf-8")); src = d.get("sources", {}); out = []
    for r in d.get("values", []):
        s = r.get("src") or ""
        basis = {"team-input": "team", "handover": "human", "review": "human", "morph": "derived", "corpus": "derived"}.get(s, "external")
        status = "decided" if basis == "team" else ("open" if r.get("status") == "unseen" else "proposed")
        note = "; ".join(x for x in (r.get("comment"), r.get("src_comment"), (src.get(s) or {}).get("title")) if x) or None
        out.append(RG.entry("feature", r["p"], r["v"] if isinstance(r["v"], str) else json.dumps(r["v"]), status, basis,
                            "team:" + s if basis == "team" else f"external:{s}" if basis == "external" else f"script:{s or 'register'}",
                            r.get("date") or TODAY, parameter=r["p"], origin=f"research-register:known.json#{r['p']}", note=note,
                            evidence=[{"ref": r["evidence"]}] if isinstance(r.get("evidence"), str) and re.match(r"^[1-3A-Z]{3} \d", r["evidence"]) else None))
    return out


def proposed_terms(cfg, have):
    """terms proposed from words.db: per source lexeme with TERM_MIN links and no store term, the TERM_TOP forms"""
    p = paths.lang_dir(cfg["iso"], "lexicon", "words.db")
    if not os.path.exists(p):
        return []
    db = sqlite3.connect(p); built = db.execute("select value from meta where name='built'").fetchone()[0]
    forms = dict(db.execute("select id, form from form")); lem = dict(db.execute("select id, lemma from lexeme"))
    by = collections.defaultdict(list)
    for lx, fm, n, share in db.execute("select lexeme, form, n, share from link"):
        by[lx].append((n, share, forms[fm]))
    out = []
    for lx, rows in sorted(by.items()):
        lang, s = lx.split(":"); strong = ("H" if lang == "hbo" else "G") + re.sub(r"\D", "", s)
        tot = sum(n for n, _, _ in rows)
        if tot < TERM_MIN or strong in have:
            continue
        top = [(n, sh, f) for n, sh, f in sorted(rows, reverse=True)[:TERM_TOP] if sh >= TERM_SHARE]
        if not top:
            continue
        out.append(RG.entry("term", f"{lx}.words", top[0][2], "proposed", "derived", "script:onboard/lexicon.py", built[:10],
                            source=strong, renderings=[{"form": f, "status": "preferred" if i == 0 else "admitted", "n": n} for i, (n, _, f) in enumerate(top)],
                            gloss=[{"lang": lang, "lemma": lem.get(lx)}], origin=f"words.db#{lx}", note=f"{tot} links in the team's text"))
    return out


def cmd_seed(a):
    cfg = paths.config(a.lang); d = paths.lang_dir(a.lang, "register"); E = []; st = collections.Counter()
    store = cfg["_store"]; wiki = os.path.join(os.path.dirname(store), "wiki") if store else None
    # the team's answers first: the entries made from them point back
    team_of = {}
    for t, date, who, status, text in answers(os.path.join(wiki, "team-input.md")) if wiki else []:
        team_of[f"wiki/team-input.md#{t}"] = f"answer:{t}"
        E.append(RG.entry("answer", t, text.splitlines()[0][:120] if text else "", "decided", "team", f"team:{who.split('(')[0].strip().lower().replace(' ', '-')}",
                          date, text=text, who=who, origin=f"store-wiki:team-input.md#{t}", note=f"curation: {status}" if status else None))
        st["answers"] += 1
    ans = {e["id"]: e for e in E}
    if store:
        ids = set(); edition = os.path.basename(os.path.dirname(store))
        for f in ("observations.json", "decisions.json"):
            fp = os.path.join(store, f)
            if not os.path.exists(fp):
                continue
            S = json.load(open(fp, encoding="utf-8"))
            for e in S.get("entries", []):
                if e.get("status") == "superseded":
                    st["superseded, left out"] += 1; continue
                k = new_id(e)
                if not k:
                    st["statistics, left out"] += 1; continue
                kind, rid = k
                if rid in ids:
                    n = 2
                    while f"{rid}.{n}" in ids:
                        n += 1
                    rid = f"{rid}.{n}"
                ids.add(rid)
                x = from_store(e, kind, rid, f"{edition}/{f}", team_of); E.append(x); st[kind] += 1
                for fr in x.get("from", []):
                    ans[fr].setdefault("entries", []).append(x["id"])
            if f == "observations.json" and S.get("orthography"):
                o = S["orthography"]; t = dict(o.get("tone") or {}); t.pop("derived", None)
                E.append(RG.entry("orthography", "main", "the language's writing", "proposed", "derived", "script:morphs.py", TODAY,
                                  normalization=o.get("normalization"), ignore_marks=o.get("ignore_marks"), tone=t or None,
                                  keep_marks=cfg.get("keep_marks"), origin=f"store:{edition}/{f}#orthography"))
                st["orthography"] += 1
    byid = {e["id"]: e for e in E}
    for x in known(paths.lang_dir(a.lang, "register", "seed", "known.json")):
        refs = [f"answer:{t}" for t in re.findall(r"\bT\d+\b", x.get("note") or "") if f"answer:{t}" in ans]
        if x["basis"] == "team" and refs:
            x["from"] = sorted(set(refs))
            for r in x["from"]:
                ans[r].setdefault("entries", []).append(x["id"])
        if x["id"] in byid:            # the store has the feature: research's value goes into its note
            y = byid[x["id"]]; y["note"] = ((y.get("note") or "") + f"; research register: {x['value']} ({x['basis']}, {x['by']})").lstrip("; ")
            st["features (research register), merged"] += 1; continue
        E.append(x); byid[x["id"]] = x; st["features (research register)"] += 1
    have_ids = {e["id"] for e in E}
    for n, group, title, text in questions(paths.lang_dir(a.lang, "register", "seed", "team-questions.md")):
        E.append(RG.entry("question", f"q{n}", title, "open", "derived", "agent:research", "2026-11-03", text=text, group=group,
                          origin=f"research:private/profile/{a.lang}/team-questions.md#{n}", note="drafted 2026-11-03, not sent"))
        st["questions"] += 1
    have = {e.get("source") for e in E if e["kind"] == "term"}
    pt = proposed_terms(cfg, have); E += [e for e in pt if e["id"] not in have_ids]; st["terms proposed from words.db"] += len(pt)
    RG.write(d, E, {"revision": "0.0-seed", "date": TODAY, "language": a.lang,
                    "seeded from": {"store": cfg.get("store"), "known": "register/seed/known.json (research)", "questions": "register/seed/team-questions.md (research)",
                                    "words.db": "lexicon/words.db"}, "left out": {k: v for k, v in st.items() if "left out" in k}})
    print(json.dumps(dict(st), ensure_ascii=False), "->", d)


# ------------------------------------------------------------------ the check

def protected(cfg):
    lic = (cfg.get("rights") or {}).get("licence", "") + " " + ((cfg.get("text") or {}).get("licence") or "")
    return bool(re.search(r"\bN[CD]\b|protected|non-free", lic))


def cmd_check(a):
    cfg = paths.config(a.lang); d = paths.lang_dir(a.lang, "register"); E = RG.load(d)
    err, warn = RG.check(E, protected=protected(cfg)); out = {"entries": len(E), "errors": len(err), "warnings": len(warn)}
    from drafting import prompt
    old = prompt.team_terms_store(cfg); new = RG.team_terms(E)
    out["team terms: store / register / same set"] = [len(old), len(new), sorted(old) == sorted(new)]
    out["team terms: same order"] = old == new
    team = [e for e in E if e["basis"] == "team" and e["kind"] != "answer"]
    out["team entries / with an answer"] = [len(team), sum(bool(e.get("from")) for e in team)]
    ans = [e for e in E if e["kind"] == "answer"]
    out["answers / with entries"] = [len(ans), sum(bool(e.get("entries")) for e in ans)]
    out["team entries outside terms and names, with an answer"] = sum(bool(e.get("from")) for e in team if e["kind"] not in ("term", "name"))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    for x in err[:20]:
        print("ERROR", x)
    sys.exit(1 if err else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("parameters", "seed", "check")); ap.add_argument("--lang")
    a = ap.parse_args()
    if a.cmd != "parameters" and not a.lang:
        sys.exit("seed and check need --lang")
    {"parameters": cmd_parameters, "seed": cmd_seed, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
