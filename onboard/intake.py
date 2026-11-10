#!/usr/bin/env python3
"""The intake: a tagged revision of a language repository taken back in (internal-docs/review-feedback-data-plan-2026-11-10.md,
sections 3.4, 3.11; stage S4). Two steps, so that what came back can be read before it is used:

  take   the repository at a ref (a tag register-<n>) -> $MAKE_TANAKH_PRIVATE/lang/<iso>/intake/<ref>/
           register/        the merged register: the repository's entries win on a shared id, ours alone are kept (the ones
                            not pushed yet); the repository's register is checked first (shared/register.py), errors stop
           repo-register/   the repository's register as it came
           edits.jsonl      every edit record (make-tanakh-review FORMAT.md section 10), checked; SPELL and WORD rows on one
                            word re-split with the language's splitter: same stem, other affixes -> intake_cat AFFIX
           proposed.json    morph entries proposed from those rows (an affix the register lacks; status open: the splitter
                            uses an open affix only with enough evidence) - added to register/ as proposed
           triples.jsonl    per edited clause (draft, edited): the chapter as we first put it in, against the ref; private
                            (NLLB fine-tuning and few-shot hints), never published
           overrides.json   the team's decided rules as rule-engine overrides (alternatives/rules.py team_overrides)
           segmenter/       the splitter bundle from the merged register, and how many word types now split otherwise
           report.md        all of it, with the chain to rerun
  apply  the taken register becomes the language's register (the old one kept as intake/<ref>/before/), the segmenter
         bundle is rebuilt; then rerun the chain the report lists (split, align, corpus, words.db, rules, checks)

    . ./env.sh
    ~/sil-study/.venv/bin/python onboard/intake.py take --lang zin --repo /path/to/bare.git|org/name --ref register-1
    ~/sil-study/.venv/bin/python onboard/intake.py apply --lang zin --ref register-1"""
import argparse, collections, glob, json, os, shutil, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths, register as RG  # noqa: E402
from onboard import register as OR, segbundle as SB  # noqa: E402
from publish import chapter_format as CF  # noqa: E402
from alternatives import rules as RU  # noqa: E402
FA = CF.FA

OPS = ("M", "R", "U", "WO")
CATS = ("SPELL", "TONE", "AFFIX", "FUNC", "WORD", "NEW", "ORDER", "SPLIT", "JOIN", "CHOICE", "OTHER")
NEEDS = ("ref", "who", "when", "op", "cat")


def clone(repo, ref, d):
    url = repo if os.path.exists(repo) else f"https://github.com/{repo}.git"
    subprocess.run(["git", "clone", "-q", url, d], check=True)
    subprocess.run(["git", "-C", d, "checkout", "-q", ref], check=True)


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, check=True).stdout


def merge(ours, theirs):
    """theirs win on a shared id; ours alone are kept -> (entries, {changed, new, ours only})"""
    by = {e["id"]: e for e in ours}; st = collections.Counter()
    for e in theirs:
        if e["id"] not in by:
            st["new from the repository"] += 1
        elif by[e["id"]] != e:
            st["changed in the repository"] += 1
        by[e["id"]] = e
    st["ours only (kept)"] = len(set(by) - {e["id"] for e in theirs})
    return list(by.values()), dict(st)


def read_edits(w):
    """(rows, problems) of every edit file under .tanakh/edits/"""
    rows, bad = [], []
    for f in sorted(glob.glob(os.path.join(w, ".tanakh", "edits", "*", "*", "*.jsonl"))):
        rel = os.path.relpath(f, w); ch = os.path.basename(os.path.dirname(f))
        for n, l in enumerate(open(f, encoding="utf-8"), 1):
            if not l.strip():
                continue
            try:
                r = json.loads(l)
            except ValueError:
                bad.append(f"{rel}:{n}: not JSON"); continue
            miss = [k for k in NEEDS if k not in r]
            if miss or r.get("op") not in OPS or r.get("cat") not in CATS:
                bad.append(f"{rel}:{n}: " + (f"missing {miss}" if miss else f"op {r.get('op')} / cat {r.get('cat')}")); continue
            rows.append(dict(r, chapter=ch, file=rel))
    return rows, bad


def affix_of(seg, old, new):
    """(stem, affixes of old, affixes of new, a candidate new affix or None) of a one-word change, or None when the stems differ"""
    so, sn = seg.split(old), seg.split(new)
    stem = lambda s: "".join(p["text"] or "" for p in s if p["slot"] == "stem")
    aff = lambda s: [(p["slot"], p["text"]) for p in s if p["slot"] not in ("stem", "whole")]
    if stem(so) and stem(so) == stem(sn) and aff(so) != aff(sn):
        return stem(so), aff(so), aff(sn), None
    for base in (old, stem(so)):                              # an affix the splitter does not know: the old word (or stem) inside the new
        lo, ln = (base or "").lower(), new.lower()
        if len(lo) >= 3 and lo in ln and lo != ln:
            i = ln.index(lo); pre, suf = new[:i], new[i + len(lo):]
            if bool(pre) != bool(suf):
                return base, aff(so), [("prefix", pre)] if pre else [("suffix", suf)], (pre + "-") if pre else ("-" + suf)
    return None


def classify(rows, seg, morphs):
    """intake_cat on SPELL / WORD rows of one word; proposed morph entries for affixes the register lacks"""
    known = {e.get("form") for e in morphs}; prop = {}
    for r in rows:
        old, new = str(r.get("old") or ""), str(r.get("new") or "")
        r["intake_cat"] = r["cat"]
        if r["cat"] not in ("SPELL", "WORD") or len(old.split()) != 1 or len(new.split()) != 1:
            continue
        a = affix_of(seg, old, new)
        if not a:
            continue
        r["intake_cat"] = "AFFIX"; r["affix"] = {"stem": a[0], "old": a[1], "new": a[2]}
        form = a[3]
        if form and form not in known:
            slot = "prefix" if form.endswith("-") else "suffix"
            e = prop.get(form) or RG.entry("morph", f"{form}:intake", form, "open", "derived", "script:intake", time.strftime("%Y-%m-%d"),
                                           form=form, slot=slot, note="an affix in the team's edits the splitter does not know (onboard/intake.py)")
            ev = e.setdefault("evidence", []); ev.append({"ref": f"{r['chapter'].replace('_', ' ')}:{r['ref']}", "form": new}); prop[form] = e
    return list(prop.values())


def chapter_versions(w, rel):
    """(our first version, the version at the ref) of a chapter's .md and .units, as texts"""
    first = git(w, "log", "--format=%H", "--diff-filter=A", "--", rel + ".md").split()
    if not first:
        return None
    show = lambda c, f: subprocess.run(["git", "-C", w, "show", f"{c}:{f}"], capture_output=True, text=True).stdout
    c0 = first[-1]
    return (show(c0, rel + ".md"), show(c0, rel + ".units")), (open(os.path.join(w, rel + ".md"), encoding="utf-8").read(),
                                                              open(os.path.join(w, rel + ".units"), encoding="utf-8").read())


def clause_texts(md, units):
    """{(verse, unit key): text} from a chapter's .md and .units (the tokens of the unit's range)"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(md)
    verses = CF.read_md(f.name)[4]; os.remove(f.name); out = {}
    for l in units.splitlines():
        if l.startswith("#") or not l.strip():
            continue
        cv, _, rest = l.partition("\t"); v = int(cv.split(":")[1]); toks = FA.tokenize(verses.get(v, ""))
        for e in rest.split():
            k, _, rng = e.rpartition(":")
            out[(v, k)] = "" if rng == "=" else " ".join(toks[i] for i in FA.ids_of(rng) if i < len(toks))
    return out


def triples(w, chapters):
    out = []
    for ch in sorted(chapters):
        b = ch.split("_")[0]; vs = chapter_versions(w, f"{b}/{ch}")
        if not vs:
            continue
        a, z = clause_texts(*vs[0]), clause_texts(*vs[1])
        for k in sorted(set(a) | set(z), key=lambda x: (x[0], x[1])):
            if a.get(k, "") != z.get(k, ""):
                out.append({"chapter": ch, "verse": k[0], "unit": k[1], "draft": a.get(k, ""), "edited": z.get(k, "")})
    return out


def take(lang, repo, ref, out=None):
    cfg = paths.config(lang); out = out or paths.lang_dir(lang, "intake", ref)
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out); rep = {"language": lang, "repository": repo, "ref": ref, "taken": time.strftime("%Y-%m-%d %H:%M")}
    with tempfile.TemporaryDirectory() as tmp:
        w = os.path.join(tmp, "w"); clone(repo, ref, w); rep["commit"] = git(w, "rev-parse", "HEAD").strip()
        # 1. the register
        rd = os.path.join(w, ".tanakh", "register"); theirs = RG.load(rd) if os.path.isdir(rd) else []
        err, _ = RG.check(theirs, protected=OR.protected(cfg))
        err += RG.check_files(rd) if os.path.isdir(rd) else []
        if err:
            open(os.path.join(out, "errors.txt"), "w").write("\n".join(err))
            sys.exit(f"the repository's register has {len(err)} errors: {os.path.join(out, 'errors.txt')}")
        if theirs:
            shutil.copytree(rd, os.path.join(out, "repo-register"))
        ours = RG.load(cfg["_register"]); E, rep["register"] = merge(ours, theirs)
        # 2. the edits
        rows, bad = read_edits(w); rep["edit files problems"] = bad
        reg = os.path.join(out, "register"); stamp = {"revision": ref, "taken from": repo, "commit": rep["commit"], "date": time.strftime("%Y-%m-%d")}
        RG.write(reg, E, stamp); SB.build(lang, register=reg, out=os.path.join(out, "segmenter"))
        seg = SB.load(os.path.join(out, "segmenter"))                       # the taken register's splitter: the team's new affixes count
        prop = classify(rows, seg, [e for e in E if e["kind"] == "morph"])
        have = {e["id"] for e in E}; E += [e for e in prop if e["id"] not in have]
        with open(os.path.join(out, "edits.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        json.dump(prop, open(os.path.join(out, "proposed.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        rep["edits"] = {"rows": len(rows), "by category (theirs)": dict(collections.Counter(r["cat"] for r in rows)),
                        "by category (after intake)": dict(collections.Counter(r["intake_cat"] for r in rows)),
                        "scope similar": sum(1 for r in rows if r.get("scope") == "similar"),
                        "from an alternative": dict(collections.Counter(r["from_alt"] for r in rows if r.get("from_alt"))),
                        "morphs proposed": [e["form"] for e in prop]}
        # 3. the triples
        T = triples(w, {r["chapter"] for r in rows})
        with open(os.path.join(out, "triples.jsonl"), "w", encoding="utf-8") as f:
            for t in T:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        rep["triples"] = len(T)
    # 4. the merged register, the overrides, the splitter
    RG.write(reg, E, stamp)
    ov = RU.team_overrides(reg); json.dump(ov, open(os.path.join(out, "overrides.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep["rule overrides (team)"] = len(ov)
    rep["team terms and names"] = len(RG.team_terms(E))
    SB.build(lang, register=reg, out=os.path.join(out, "segmenter"))
    n, diff = SB.compare(lang, built=os.path.join(out, "segmenter"), base=paths.resolve(lang, cfg["segmenter"]))
    rep["splitter"] = {"word types": n, "split otherwise than now": len(diff), "examples": [w for w, _, _ in diff[:10]]}
    now, new = SB.load(paths.resolve(lang, cfg["segmenter"])), SB.load(os.path.join(out, "segmenter")); show = lambda S, w: "+".join(p["text"] or "" for p in S.split(w) if p["slot"] != "tone")
    ew = sorted({str(r.get("new")) for r in rows if r.get("new") and len(str(r["new"]).split()) == 1 and "|" not in str(r["new"])})
    rep["edited words split otherwise"] = {w: [show(now, w), show(new, w)] for w in ew if show(now, w) != show(new, w)}
    rep["chain to rerun after apply"] = ["onboard/align.py (split, view, parts)", "onboard/corpus.py", "onboard/lexicon.py words",
                                         "alternatives/rules.py learn", "drafting/lexcheck.py", "the dev check"]
    json.dump(rep, open(os.path.join(out, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(out, "report.md"), "w", encoding="utf-8").write(report_md(rep))
    return out, rep


def report_md(r):
    L = [f"# Intake of {r['language']} at {r['ref']}", "", f"Taken {r['taken']} from {r['repository']} (commit {r['commit'][:12]}).", "",
         "## Register", ""] + [f"- {k}: {v}" for k, v in r["register"].items()] + [
         f"- team terms and names: {r['team terms and names']}", f"- team rules as engine overrides: {r['rule overrides (team)']}", "",
         "## Edits", "", f"- rows: {r['edits']['rows']}; with scope similar: {r['edits']['scope similar']}",
         "- by category, theirs: " + ", ".join(f"{k} {v}" for k, v in sorted(r["edits"]["by category (theirs)"].items())),
         "- after our affix check: " + ", ".join(f"{k} {v}" for k, v in sorted(r["edits"]["by category (after intake)"].items())),
         "- from an alternative: " + (", ".join(f"{k} {v}" for k, v in r["edits"]["from an alternative"].items()) or "none"),
         "- affixes proposed (open): " + (", ".join(r["edits"]["morphs proposed"]) or "none"),
         f"- problems in edit files: {len(r['edit files problems'])}"] + [f"  - {p}" for p in r["edit files problems"][:20]] + [
         "", "## Clauses edited (triples)", "", f"{r['triples']} clauses differ from our draft.", "", "## Splitter", "",
         f"{r['splitter']['split otherwise than now']} of {r['splitter']['word types']} word types of the text split otherwise with the taken register"
         + (": " + ", ".join(r["splitter"]["examples"]) if r["splitter"]["examples"] else "."),
         "Words of the edits split otherwise: " + (", ".join(f"{w} {a} -> {b}" for w, (a, b) in r["edited words split otherwise"].items()) or "none"),
         "", "## Next", "",
         "`onboard/intake.py apply`, then: " + "; ".join(r["chain to rerun after apply"]) + "."]
    return "\n".join(L) + "\n"


def apply(lang, ref):
    cfg = paths.config(lang); d = paths.lang_dir(lang, "intake", ref); reg = cfg["_register"]
    if not os.path.isdir(os.path.join(d, "register")):
        sys.exit(f"nothing taken at {d}: run take first")
    before = os.path.join(d, "before")
    if not os.path.exists(before):
        shutil.copytree(reg, before, ignore=shutil.ignore_patterns("seed"))
    E = RG.load(os.path.join(d, "register")); v = json.load(open(os.path.join(d, "register", "VERSION.json"), encoding="utf-8"))
    RG.write(reg, E, v); SB.build(lang)
    print(f"{lang}: the register is now {ref} ({len(E)} entries; the old one in {before}); the segmenter bundle rebuilt")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("take", "apply")); ap.add_argument("--lang", required=True); ap.add_argument("--ref", required=True)
    ap.add_argument("--repo"); ap.add_argument("--out", help="take: another folder than private/lang/<iso>/intake/<ref>/ (a trial)")
    a = ap.parse_args()
    if a.cmd == "take":
        if not a.repo:
            sys.exit("take needs --repo")
        out, rep = take(a.lang, a.repo, a.ref, a.out); print(open(os.path.join(out, "report.md"), encoding="utf-8").read())
    else:
        apply(a.lang, a.ref)


if __name__ == "__main__":
    main()
