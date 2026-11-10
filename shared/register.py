#!/usr/bin/env python3
"""The register: every fact about a language that its team may decide, in one structure (the review-feedback data plan,
internal-docs/review-feedback-data-plan-2026-11-10.md, section 3.2). After the
freeze the files live in the language repository (`.tanakh/register/`), before it in `private/lang/<iso>/register/`. One file
per entry, `<kind>/<slug>-<hex6>.json` (agreed with the review project, 2026-11-10: appends to one file conflict between
branches); `file_of(id)` gives the name.

Every entry has the same envelope:

    id          <kind>:<name>, no white space; stable for the life of the fact
    kind        one of KINDS
    value       the fact (a string; an object for a formula)
    status      proposed | decided | open | superseded | retired
    basis       team | human | derived | external | model        (strongest first)
    by          a GitHub login, team:<who>, script:<name> or agent:<name>
    when        YYYY-MM-DD
    supersedes  the id of the entry this one replaces, or null
    scope       null | "ALL" | a book or chapter | a feature bundle {feature: value}
    evidence    [{ref, unit, form}]; a form of at most EVIDENCE_WORDS words
    from        [answer or question ids this entry was made from]
    origin      where a seeded entry came from (e.g. "store:kvg_BSB/observations.json#m:abc-:verb"), or null
    note        free text, or null

and a payload of its kind (KINDS). Decided team entries are binding: no entry of another basis may supersede one."""
import csv, hashlib, json, os, re

KINDS = {   # kind -> (plural, payload keys)
    "feature": ("features", ("parameter", "confidence", "frequency", "examples")),
    "rule": ("rules", ("table", "conditions", "do", "said", "verdict", "pattern")),   # conditions: the engine's `when` (the envelope has `when`, the date)
    "choice": ("choices", ("unit", "ref", "rule", "parameter", "source")),
    "term": ("terms", ("source", "renderings", "denials", "replaces", "gloss", "words", "attested")),
    "name": ("names", ("source", "renderings", "denials", "replaces", "gloss", "words", "attested", "letters")),
    "formula": ("formulas", ("source", "renderings", "gloss", "words", "attested", "pattern")),
    "word": ("words", ("form", "class", "parts", "gloss", "lexemes", "affixes", "never_split")),
    "morph": ("morphs", ("form", "slot", "host", "position", "unimorph", "written", "variants", "tone_pattern", "with",
                         "productive", "greek", "agree", "class")),
    "letter": ("letters", ("examples",)),
    "orthography": ("orthography", ("normalization", "ignore_marks", "tone", "keep_marks")),
    "answer": ("answers", ("text", "ref", "entries", "who")),
    "question": ("questions", ("text", "ref", "unit", "group", "asked", "answer")),
}
ENVELOPE = ("id", "kind", "value", "status", "basis", "by", "when", "supersedes", "scope", "evidence", "from", "origin", "note")
REQUIRED = ("id", "kind", "value", "status", "basis", "by", "when")
STATUSES = ("proposed", "decided", "open", "superseded", "retired")
BASES = ("team", "human", "derived", "external", "model")
SLOTS = ("prefix", "suffix", "infix", "clitic", "free", "tone")
RENDERING_STATUS = ("preferred", "admitted", "deprecated")
EVIDENCE_WORDS = 4                    # the store's licensing rule: short quotations of a protected text
PARAMETERS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "register", "parameters.tsv")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def entry(kind, name, value, status, basis, by, when, **kw):
    """a new entry with the envelope in its order, the payload after it; empty keys left out"""
    e = {"id": f"{kind}:{name}", "kind": kind, "value": value, "status": status, "basis": basis, "by": by, "when": when}
    for k in ENVELOPE[7:] + KINDS[kind][1]:
        if kw.get(k) not in (None, [], {}, ""):
            e[k] = kw[k]
    extra = set(kw) - set(ENVELOPE) - set(KINDS[kind][1])
    if extra:
        raise ValueError(f"{kind}: unknown keys {sorted(extra)}")
    return e


def file_of(eid):
    """an entry's file, relative to the register: <kind>/<slug>-<first 6 hex of sha256(id)>.json"""
    kind, name = eid.split(":", 1)
    slug = re.sub(r"[^a-z0-9.-]", "-", name.lower())[:40].strip("-.") or "x"
    return f"{kind}/{slug}-{hashlib.sha256(eid.encode('utf-8')).hexdigest()[:6]}.json"


def load(d):
    """all entries of a register folder: kind by kind, by file name"""
    out = []
    for kind in KINDS:
        k = os.path.join(d, kind)
        if os.path.isdir(k):
            out += [json.load(open(os.path.join(k, f), encoding="utf-8")) for f in sorted(os.listdir(k)) if f.endswith(".json")]
    return out


def write(d, entries, version):
    """every entry to its own file (files of entries no longer given are removed), and VERSION.json"""
    os.makedirs(d, exist_ok=True); keep = set()
    for e in entries:
        f = file_of(e["id"]); keep.add(f); p = os.path.join(d, f); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False, indent=1) + "\n")
    for kind in KINDS:
        k = os.path.join(d, kind)
        for f in os.listdir(k) if os.path.isdir(k) else []:
            if f.endswith(".json") and f"{kind}/{f}" not in keep:
                os.remove(os.path.join(k, f))
    by = {}
    for e in entries:
        by[e["kind"]] = by.get(e["kind"], 0) + 1
    json.dump({**version, "entries": len(entries), "by kind": by}, open(os.path.join(d, "VERSION.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)


def parameters(p=PARAMETERS):
    """{id: {question, codes, group, source}} of the shared questionnaire"""
    if not os.path.exists(p):
        return {}
    return {r["id"]: r for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t")}


def live(entries):
    return [e for e in entries if e["status"] not in ("superseded", "retired")]


def check(entries, params=None, protected=False):
    """(errors, warnings): the register's rules. protected: the language's text is not free (the evidence-length rule)"""
    params = parameters() if params is None else params
    err, warn = [], []
    ids = {}
    for i, e in enumerate(entries):
        where = e.get("id") or f"line {i + 1}"
        miss = [k for k in REQUIRED if k not in e]
        if miss:
            err.append(f"{where}: missing {miss}"); continue
        k = e["kind"]
        if k not in KINDS:
            err.append(f"{where}: unknown kind {k}"); continue
        if not e["id"].startswith(k + ":") or re.search(r"\s", e["id"]):
            err.append(f"{where}: an id is <kind>:<name> without white space")
        if e["id"] in ids:
            err.append(f"{where}: id used twice")
        ids[e["id"]] = e
        if e["status"] not in STATUSES:
            err.append(f"{where}: status {e['status']}")
        if e["basis"] not in BASES:
            err.append(f"{where}: basis {e['basis']}")
        if not DATE.match(str(e["when"])):
            err.append(f"{where}: when {e['when']}")
        extra = set(e) - set(ENVELOPE) - set(KINDS[k][1])
        if extra:
            err.append(f"{where}: unknown keys {sorted(extra)}")
        for ev in e.get("evidence", []):
            if protected and len(str(ev.get("form") or "").split()) > EVIDENCE_WORDS:
                err.append(f"{where}: an evidence form of more than {EVIDENCE_WORDS} words")
        if k == "feature" and e.get("parameter") and params and e["parameter"] not in params:
            err.append(f"{where}: parameter {e['parameter']} is not in the questionnaire")
        if k == "morph" and e.get("slot") not in SLOTS:
            err.append(f"{where}: slot {e.get('slot')}")
        for r in e.get("renderings", []):
            if r.get("status") not in RENDERING_STATUS:
                err.append(f"{where}: a rendering's status {r.get('status')}")
        pref = [r.get("form") for r in e.get("renderings", []) if r.get("status") == "preferred"]
        if pref and e["value"] not in pref:
            err.append(f"{where}: the value is the preferred rendering ({pref[0]}), not {e['value']}")
    for e in ids.values():
        s = e.get("supersedes")
        if s and s not in ids:
            err.append(f"{e['id']}: supersedes {s}, which is not in the register")
        elif s and ids[s]["basis"] == "team" and ids[s]["status"] == "decided" and e["basis"] != "team":
            err.append(f"{e['id']}: only the team may supersede the team's decision {s}")
        for f in e.get("from", []):
            if f not in ids or ids[f]["kind"] not in ("answer", "question"):
                err.append(f"{e['id']}: from {f}, which is no answer or question of the register")
        for x in e.get("entries", []):
            if x not in ids:
                err.append(f"{e['id']}: entry {x} is not in the register")
        if e["kind"] == "question" and e.get("answer") and e["answer"] not in ids:
            err.append(f"{e['id']}: answer {e['answer']} is not in the register")
    return err, warn


def team_terms(entries):
    """the team's decided terms and names [(id, value)]: terms, then names, each in the register's order. A seeded entry keeps
    the store's id, so the drafter's lines read as before"""
    not_ = lambda e: [r["form"] for r in e.get("renderings", []) if r.get("status") == "deprecated"]
    return [(e["origin"].split("#", 1)[1] if e.get("origin", "").startswith("store:") else e["id"],
             e["value"] + (f" (not {', '.join(not_(e))})" if not_(e) else ""))
            for e in entries if e["kind"] in ("term", "name") and e["status"] == "decided" and e["basis"] == "team"]


def check_files(d):
    """errors: a file whose name is not file_of(its id)"""
    err = []
    for kind in KINDS:
        k = os.path.join(d, kind)
        for f in sorted(os.listdir(k)) if os.path.isdir(k) else []:
            e = json.load(open(os.path.join(k, f), encoding="utf-8"))
            if file_of(e.get("id", "x:x")) != f"{kind}/{f}":
                err.append(f"{kind}/{f}: the name does not match the id {e.get('id')}")
    return err
