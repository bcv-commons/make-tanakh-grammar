#!/usr/bin/env python3
"""Draft chapters of a book in a language's own wording, verse by verse, from the Hebrew or the Greek.

    . ./env.sh
    python3 drafting/draft.py build --lang kvg --book EXO --chapters 1-3        # the prompts (free: no model call)
    python3 drafting/draft.py send  --lang kvg --book EXO                       # the answers; stop and rerun: it goes on
    python3 drafting/draft.py text  --lang kvg --book EXO                       # the verses of each chapter, from the answers
    python3 drafting/draft.py status --lang kvg --book EXO

A run lives in $MAKE_TANAKH_PRIVATE/runs/<lang>/draft/<book>/<label>/ (label: main unless --label): prompts/, answers/,
text/<book><chapter>.json, manifest.json (what it was drafted with: model, code commit, the prompts' hash, the pool, the notes).

Options of build: --source grc|hbo (default: by the book), --leave-out BOOK,... (books kept out of the pool: a dev check leaves
its dev book out), --no-notes (without the language's grammar pages), --lexicon (with the content words' forms from
lexicon/words.db). Closed and held-out chapters are refused."""
import argparse, collections, glob, hashlib, json, os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import llm, paths, rights  # noqa: E402
from source import tokens  # noqa: E402
from drafting import evidence, prompt  # noqa: E402


def chapters_arg(s):
    out = []
    for x in s.split(","):
        a, _, b = x.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return sorted(set(out))


def source_of(book):
    if book in tokens.books("grc"):
        return "grc"
    if book in tokens.books("hbo"):
        return "hbo"
    sys.exit(f"unknown book {book}")


def vid(ref):
    return ref.replace(" ", "_").replace(":", "_")


def commit():
    try:
        h = subprocess.run(["git", "-C", paths.ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", paths.ROOT, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True).stdout.strip())
        return h + ("+changes" if dirty else "")
    except OSError:
        return None


def job_dir(a, *sub, make=True):
    return paths.run_dir(a.lang, "draft", a.book, a.label, *sub, make=make)


def load_manifest(a):
    p = os.path.join(job_dir(a), "manifest.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"language": a.lang, "book": a.book, "label": a.label, "builds": [], "sends": []}


def save_manifest(a, m):
    json.dump(m, open(os.path.join(job_dir(a), "manifest.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def save_groups(a, groups):
    """groups.json of a run: {verse id: {"refs": [...], "clauses": [clause ids]}}, added to what is there"""
    p = os.path.join(job_dir(a), "groups.json"); g = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    g.update(groups); json.dump(g, open(p, "w", encoding="utf-8"), indent=0)


def load_groups(a):
    """the run's verse groups in text order: [(verse id, refs, clause ids)]; runs built before groups.json: from the prompts"""
    p = os.path.join(job_dir(a), "groups.json")
    if os.path.exists(p):
        g = json.load(open(p, encoding="utf-8"))
    else:
        g = {}
        for f in glob.glob(os.path.join(job_dir(a, "prompts"), "*.md")):
            cj = f[:-3] + ".clauses.json"
            g[os.path.basename(f)[:-3]] = {"refs": open(f, encoding="utf-8").readline().strip("# \n").rsplit(" (", 1)[0].split(" / "),
                                           "clauses": json.load(open(cj)) if os.path.exists(cj) else []}
    return [(i, x["refs"], x["clauses"], x.get("order")) for i, x in sorted(g.items(), key=lambda kv: prompt.ref_key(kv[1]["refs"][0]))]


def register_stamp(cfg):
    """the register a build ran against (shared/register.stamp: revision, sha256 of the entries, changes not yet in a
    revision), recorded at draft time; publish/derived.py carries it into .tanakh/runs/"""
    from shared import register
    return register.stamp(cfg.get("_register"))


def use_pages(cfg, name):
    """cfg with the grammar pages of notes/<name> (onboard/notes.py build --out <name>)"""
    d = paths.lang_dir(cfg["iso"], "notes", name)
    pages = [p for p in json.load(open(os.path.join(os.path.dirname(d), f"build-{name}.json" if name != "grammar" else "build.json"), encoding="utf-8"))["pages"]
             if os.path.exists(os.path.join(d, p + ".md"))] if os.path.isdir(d) else []
    if not pages:
        sys.exit(f"{d}: no pages")
    cfg["notes"] = {"dir": f"notes/{name}", "pages": pages, "intro": f"Notes on {cfg['name']} grammar, written from the team's translation and its decisions:"}
    cfg["_notes_dir"] = d
    return cfg


def cmd_build(a):
    cfg = paths.config(a.lang); src = a.source or source_of(a.book); chs = chapters_arg(a.chapters)
    if a.pages:
        cfg = use_pages(cfg, a.pages)
    a.decisions = (a.decisions or bool(cfg.get("decisions"))) and not a.no_decisions
    leave = tuple(x for x in (a.leave_out or "").split(",") if x)
    E = evidence.build(cfg, src, a.book, chs, leave)
    B = prompt.Builder(cfg, E, a.book, chs, notes=not a.no_notes, lexicon=a.lexicon, pieces="mark" if a.pieces else "select" if a.only_pieces else False,
                       decisions=a.decisions)
    d = job_dir(a, "prompts"); n = chars = 0; h = hashlib.sha256(); groups = {}
    for v, cl in B.groups().items():
        txt, refs = B.verse(cl)
        if a.only_pieces and not B.order:
            continue
        open(os.path.join(d, vid(v) + ".md"), "w", encoding="utf-8").write(txt)
        json.dump([q["id"] for q in cl], open(os.path.join(d, vid(v) + ".clauses.json"), "w"))
        groups[vid(v)] = {"refs": refs, "clauses": [q["id"] for q in cl], **({"order": B.order} if B.order and a.pieces else {})}
        n += 1; chars += len(txt); h.update(txt.encode("utf-8"))
    save_groups(a, groups)
    m = load_manifest(a)
    m["builds"].append({"when": time.strftime("%Y-%m-%d %H:%M"), "code": commit(), "source": src, "chapters": chs, "verses": n, "clauses": len(E.order),
                        "characters": chars, "prompts sha256": h.hexdigest(), "evidence": E.meta, "terms": len(B.terms),
                        "team words per source word": B.ratio and round(B.ratio, 3),
                        "notes": {"pages": cfg["notes"]["pages"], "lines dropped": B.notes_dropped} if B.notes else None,
                        "pieces": a.pieces or None, "only groups with a cut clause": a.only_pieces or None,
                        "lexicon": {"words.db built": B.lexi.built} if B.lexi else None,
                        "decisions": {k: len(v) for k, v in B.decisions.items()} if a.decisions else None,
                        "register": register_stamp(cfg)})
    save_manifest(a, m)
    print(f"{a.lang} {a.book} {chs}: {n} verses, {len(E.order)} clauses, {chars} characters (about {chars // 3} input tokens) -> {d}")


def todo(a):
    d = job_dir(a, "prompts"); od = job_dir(a, "answers")
    return [f for f in sorted(glob.glob(os.path.join(d, "*.md"))) if not os.path.exists(os.path.join(od, os.path.basename(f)[:-3] + ".json"))]


def cmd_send(a):
    cfg = paths.config(a.lang); od = job_dir(a, "answers"); files = todo(a); m = load_manifest(a); rights.check(cfg, "llm")
    if not files:
        print("nothing to send: every prompt has its answer"); return
    items = [(os.path.basename(f)[:-3], open(f, encoding="utf-8").read()) for f in files]
    rec = {"when": time.strftime("%Y-%m-%d %H:%M"), "backend": llm.BACKEND, "model": llm.MODEL, "effort": "medium", "code": commit(),
           "prompts": len(items), "answered": 0, "unparsable": [], "errors": [], "batch": None}
    if llm.BACKEND == "api":
        est = llm.estimate([p for _, p in items]); spent = sum(s.get("USD", 0) for s in m["sends"])
        if spent + est > a.cap:
            sys.exit(f"refused: spent {spent:.2f} + estimate {est:.2f} USD > cap {a.cap}")
        open_ = next((s for s in m["sends"] if s.get("batch")), None)           # a batch that was sent and not yet collected
        if open_:
            rec = open_
        else:
            m["sends"].append(rec)
    else:
        m["sends"].append(rec)
    rec["save"] = lambda: save_manifest(a, {**m, "sends": [{k: v for k, v in s.items() if k != "save"} for s in m["sends"]]})
    usd = "USD" if llm.BACKEND == "api" else "list USD"; rec.setdefault(usd, 0.0)
    print(f"{llm.BACKEND}: {len(items)} prompts, model {llm.MODEL}", flush=True)
    for i, r in llm.run(items, prompt.SYSTEM.format(lang=cfg["name"]), prompt.SCHEMA, state=rec):
        if not r["ok"]:
            rec["errors"].append([i, r.get("error")])
        else:
            rec[usd] = round(rec[usd] + (r.get("usd") or r.get("list_usd") or 0.0), 4)
            try:
                o = json.loads(r["text"]); assert isinstance(o.get("clauses"), list)
                json.dump(o, open(os.path.join(od, i + ".json"), "w", encoding="utf-8"), ensure_ascii=False); rec["answered"] += 1
            except (ValueError, AssertionError, AttributeError):
                rec["unparsable"].append(i); open(os.path.join(od, i + ".raw.txt"), "w", encoding="utf-8").write(r["text"])
        done = rec["answered"] + len(rec["errors"]) + len(rec["unparsable"])
        if done % 10 == 0 or done == len(items):
            rec["save"](); print(f"{done}/{len(items)}", flush=True)
    rec["finished"] = time.strftime("%Y-%m-%d %H:%M"); rec["save"]()
    print(json.dumps({k: v for k, v in rec.items() if k != "save"}))


def answers(a):
    """{first ref: {"refs", "text", "clauses"}} of the run's answered verse groups, in text order; a group's text is its clauses joined"""
    od = job_dir(a, "answers"); out = collections.OrderedDict()
    for i, refs, _, order in load_groups(a):
        p = os.path.join(od, i + ".json")
        if not os.path.exists(p):
            continue
        xs = [x for x in json.load(open(p, encoding="utf-8")).get("clauses", []) if isinstance(x, dict)]
        cl = [str(x.get("text", "")) for x in xs]
        parts = in_order({x.get("c"): str(x.get("text", "")) for x in xs}, order) if order else [c.replace("|", " ") for c in cl]
        out[refs[0]] = {"refs": refs, "text": " ".join(" ".join(c.split()) for c in parts if c.strip()), "clauses": cl}
    return out


def in_order(by, order):
    """the clause texts of a verse group with cut clauses, piece by piece in the Hebrew order: a clause written with one '|' per
    cut gives its pieces; one written otherwise stands whole at its first piece"""
    n = collections.Counter(k for k, _ in order); out = []
    for k, j in order:
        t = by.get(k, ""); ps = t.split("|")
        out.append(ps[j] if len(ps) == n[k] else (t.replace("|", " ") if j == 0 else ""))
    return out


def clause_texts(a):
    """{clause id: its text} of the run: an answer's clause k is the k-th clause of its verse group"""
    od = job_dir(a, "answers"); out = {}
    for i, _, ids, _ in load_groups(a):
        p = os.path.join(od, i + ".json")
        if not os.path.exists(p):
            continue
        by = {x.get("c"): str(x.get("text", "")) for x in json.load(open(p, encoding="utf-8")).get("clauses", []) if isinstance(x, dict)}
        for k, qid in enumerate(ids, 1):
            out[qid] = " ".join(by.get(k, "").replace("|", " ").split())
    return out


def cmd_text(a):
    A = answers(a); by = collections.defaultdict(list)
    for r, x in A.items():
        by[int(r.split()[1].split(":")[0])].append(x)
    d = job_dir(a, "text")
    for ch, xs in sorted(by.items()):
        json.dump({"language": a.lang, "book": a.book, "chapter": ch, "verses": xs}, open(os.path.join(d, f"{a.book.lower()}{ch:03d}.json"), "w", encoding="utf-8"),
                  indent=1, ensure_ascii=False)
    print(f"{a.lang} {a.book}: {len(A)} verse groups in {len(by)} chapters -> {d}; without an answer: {len(todo(a))}")


def cmd_status(a):
    m = load_manifest(a); n = len(glob.glob(os.path.join(job_dir(a, "prompts"), "*.md"))); t = len(todo(a))
    print(json.dumps({"language": a.lang, "book": a.book, "label": a.label, "prompts": n, "answered": n - t, "to send": t,
                      "builds": [{k: b[k] for k in ("when", "code", "chapters", "verses")} for b in m["builds"]],
                      "sends": [{k: v for k, v in s.items() if k in ("when", "finished", "backend", "model", "answered", "errors", "unparsable", "USD", "list USD")} for s in m["sends"]]},
                     indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "send", "text", "status")); ap.add_argument("--lang", required=True); ap.add_argument("--book", required=True)
    ap.add_argument("--chapters"); ap.add_argument("--label", default="main"); ap.add_argument("--source", choices=paths.SOURCES)
    ap.add_argument("--leave-out"); ap.add_argument("--no-notes", action="store_true")
    ap.add_argument("--lexicon", action="store_true", help="build: show the content words' forms from lexicon/words.db")
    ap.add_argument("--pieces", action="store_true", help="build: say where another clause cuts a clause, and let the drafter place it")
    ap.add_argument("--only-pieces", action="store_true", help="build: only the verse groups with a cut clause (a measurement)")
    ap.add_argument("--decisions", action="store_true", help="build: the team's decided formulas, rules and spelling from the register "
                    "(on by default where the configuration says \"decisions\": true)")
    ap.add_argument("--no-decisions", action="store_true", help="build: without the team's decisions, whatever the configuration says")
    ap.add_argument("--pages", help="build: the grammar pages of $MAKE_TANAKH_PRIVATE/lang/<iso>/notes/<pages> instead of the configuration's")
    ap.add_argument("--cap", type=float, default=0.0, help="api backend: the most this run may spend in all, USD")
    a = ap.parse_args(); a.book = a.book.upper()
    if a.cmd == "build" and not a.chapters:
        sys.exit("build needs --chapters (e.g. 1-3 or 2,4,6)")
    {"build": cmd_build, "send": cmd_send, "text": cmd_text, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main()
