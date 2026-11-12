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
import datetime, hashlib, importlib.util, json, os, re

from shared import paths

# The envelope, the kinds and the check are make-tanakh's (scripts/register.py, pinned in shared/pins.py; since v0.5.0
# the template's store is this register, plus the 13th kind `spelling` and `orthography.respell`). One source for both.
_TP = paths.work("scripts", "register.py")
if not os.path.exists(_TP):
    raise ImportError(f"make-tanakh's register module is missing ({_TP}): set MAKE_TANAKH_WORK (. ./env.sh) to a copy at the pinned tag")
_spec = importlib.util.spec_from_file_location("make_tanakh_register", _TP)
T = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(T)

KINDS = T.KINDS                       # kind -> (plural, payload keys); rule `conditions` = the engine's `when` (the envelope has `when`, the date)
ENVELOPE, REQUIRED, STATUSES, BASES = T.ENVELOPE, T.REQUIRED, T.STATUSES, T.BASES
RENDERING_STATUS, EVIDENCE_WORDS, DATE = T.RENDERING_STATUS, T.EVIDENCE_WORDS, T.DATE
SLOTS = ("prefix", "suffix", "infix", "clitic", "free", "tone")
PARAMETERS = T.PARAMETERS             # the questionnaire: make-tanakh's docs/register/parameters.tsv (was our register/parameters.tsv)
file_of, digest = T.file_of, T.digest


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


def load(d):
    """all entries of a register folder: kind by kind, by file name"""
    out = []
    for kind in KINDS:
        k = os.path.join(d, kind)
        if os.path.isdir(k):
            out += [json.load(open(os.path.join(k, f), encoding="utf-8")) for f in sorted(os.listdir(k)) if f.endswith(".json")]
    return out


def write(d, entries, note=None, date=None):
    """every entry to its own file (files of entries no longer given are removed), then a new revision (make-tanakh's
    `bump`: VERSION.json register-<n> with every entry's digest, a REVISIONS.jsonl line of the ids changed). note: what
    this revision is (where the entries came from), kept in VERSION.json beside the template's keys"""
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
    return bump(d, note, date)


def bump(d, note=None, date=None):
    """a new revision of the register folder d, in make-tanakh's format (register.bump: VERSION.json {revision
    register-<n>, date, entries, by kind, sha256, digests}, a REVISIONS.jsonl line), for a folder of any name:
    (revision, {id: added|changed|removed}). Nothing changed since the last revision: no new one"""
    v = version(d)
    if v.get("digests") and not changed(d):
        return v["revision"], {}
    E = load(d); dig = {e["id"]: digest(e) for e in E}; old = v.get("digests") or {}
    ch = {i: "added" for i in dig if i not in old} | {i: "changed" for i in dig if i in old and old[i] != dig[i]} \
        | {i: "removed" for i in old if i not in dig}
    rev = f"register-{T.rev_n(v.get('revision')) + 1}"; date = date or datetime.date.today().isoformat()
    whole = hashlib.sha256("".join(f"{i}\t{dig[i]}\n" for i in sorted(dig)).encode()).hexdigest()
    by = {}
    for e in E:
        by[e["kind"]] = by.get(e["kind"], 0) + 1
    x = {"revision": rev, "date": date, "entries": len(E), "by kind": by, "sha256": whole, **({"note": note} if note else {}), "digests": dig}
    json.dump(x, open(os.path.join(d, "VERSION.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(d, "REVISIONS.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"revision": rev, "date": date, "changed": ch, **({"note": note} if note else {})}, ensure_ascii=False) + "\n")
    return rev, ch


def version(d):
    """VERSION.json of a register folder ({} without one)"""
    p = os.path.join(d or "", "VERSION.json")
    return json.load(open(p, encoding="utf-8")) if d and os.path.exists(p) else {}


def changed(d):
    """{id: added|changed|removed} since the folder's last revision"""
    old = version(d).get("digests") or {}; new = {e["id"]: digest(e) for e in load(d)}
    return {i: "added" for i in new if i not in old} | {i: "changed" for i in new if i in old and old[i] != new[i]} \
        | {i: "removed" for i in old if i not in new}


def stamp(d):
    """what a draft records of the register it was drafted against: {revision, sha256, unreleased}. sha256 is the
    template's (over every entry's digest), so it names the entries exactly; unreleased: entries changed since the revision"""
    if not d or not os.path.exists(os.path.join(d, "VERSION.json")):
        return None
    dig = {e["id"]: digest(e) for e in load(d)}
    whole = hashlib.sha256("".join(f"{i}\t{dig[i]}\n" for i in sorted(dig)).encode()).hexdigest()
    v = version(d); old = v.get("digests") or {}
    return {"revision": v.get("revision"), "sha256": whole,
            "unreleased": sum(1 for i in set(dig) | set(old) if dig.get(i) != old.get(i)) if old else None,
            "when": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def parameters(p=PARAMETERS):
    """{id: {question, codes, group, type, source}} of the shared questionnaire"""
    return T.parameters(p)


def live(entries):
    return [e for e in entries if e["status"] not in ("superseded", "retired")]


def check(entries, params=None, protected=False):
    """(errors, warnings): make-tanakh's check (envelope, kinds, ids, dates, evidence length, renderings, supersedes and the
    team's binding decisions, spelling patterns, respell), and our stricter rules on top: a `from` that is no answer or
    question is an error (the template warns), a morph's slot, an answer's `entries` and a question's `answer` exist.
    protected: the language's text is not free (the evidence-length rule)"""
    params = parameters() if params is None else params
    err, warn = T.check(entries, protected=protected, params=params)
    fr = [w for w in warn if ": from " in w and "which is no answer or question" in w]
    err += fr; warn = [w for w in warn if w not in fr]
    ids = {e["id"]: e for e in entries if isinstance(e, dict) and e.get("id") and e.get("kind") in KINDS}
    for e in ids.values():
        if e["kind"] == "morph" and e.get("slot") not in SLOTS:
            err.append(f"{e['id']}: slot {e.get('slot')}")
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


def binding(entries):
    """the team's decided entries (basis team, status decided, not superseded): what every drafter follows"""
    return [e for e in live(entries) if e["basis"] == "team" and e["status"] == "decided"]


def forms(e, *status):
    """an entry's renderings of the given statuses, in its order (the value first when it is among them)"""
    fs = [r["form"] for r in e.get("renderings", []) if r.get("status") in status]
    return fs or ([e["value"]] if "preferred" in status and isinstance(e.get("value"), str) and not e.get("renderings") else [])


def source_keys(e):
    """the source lexemes a term, name or formula names in its `source`: ("hbo", n) for H<n>, ("grc", lemma) for a Greek word"""
    s = str(e.get("source") or "")
    return {("hbo", m.lstrip("0")) for m in re.findall(r"\bH0*(\d+)", s)} | {("grc", w) for w in re.findall(r"[\u0370-\u03ff\u1f00-\u1fff]{2,}", s)}


STEMS = ("qal", "niphal", "piel", "pual", "hiphil", "hophal", "hithpael")


def applies(e, source, t):
    """does a term or name apply to a source token? A Hebrew stem its `source` names ("H3205 (hiphil, fathered)") restricts it
    to tokens of that stem (Hebrew tokens carry the stem as `mood`, source/tokens.py)"""
    st = [x for x in STEMS if re.search(rf"\b{x}\b", str(e.get("source") or "").lower())]
    return not (st and source == "hbo" and str(t.get("mood") or "").lower() not in st)


def by_lexeme(entries):
    """{(source, strong digits | Greek lemma): [entry]} of the team's decided terms and names that name their lexemes"""
    out = {}
    for e in binding(entries):
        if e["kind"] in ("term", "name"):
            for k in source_keys(e):
                out.setdefault(k, []).append(e)
    return out


def deprecated(entries):
    """the forms the team's decided terms and names deprecate or deny, lowercase"""
    return {f.lower() for e in binding(entries) if e["kind"] in ("term", "name") for f in forms(e, "deprecated") + list(e.get("denials") or [])
            if isinstance(f, str)}


def decision_lines(entries):
    """the drafter's lines for the team's decided formulas, rules, morphs and spelling rules: {section: [line]} (empty sections
    left out). Terms and names are team_terms()'s; features reach the drafter through the grammar pages"""
    B = binding(entries); out = {}
    f = [f"- {e.get('source') or e['id'].split(':', 1)[1]}: {e['value']}" + (f" (also {', '.join(x for x in forms(e, 'admitted'))})" if forms(e, "admitted") else "")
         for e in B if e["kind"] == "formula"]
    r = [f"- {e.get('said') or e['value']}" for e in B if e["kind"] == "rule"]
    r += [f"- {e['id'].split(':')[1]} ({e.get('slot')}, on a {e.get('host')}): {e['value']}" for e in B if e["kind"] == "morph"]
    sp = [f"- {e['value']}" for e in B if e["kind"] in ("letter", "orthography")]
    sp += [f"- {e.get('said') or e['value']}" for e in sorted((e for e in B if e["kind"] == "spelling"), key=lambda e: (e.get("order") or 0, e["id"]))]
    for k, v in (("set phrases", f), ("rules", r), ("spelling", sp)):
        if v:
            out[k] = v
    return out


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
