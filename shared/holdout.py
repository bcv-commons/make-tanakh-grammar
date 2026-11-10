#!/usr/bin/env python3
"""The closed list and the hold-out: what no evidence pool, training set or measurement may read.

shared/closed.json names chapters and books and the reason for each. Every step that builds a pool of the team's text, trains
a model or scores a draft asks here first:

    from shared import holdout
    if holdout.is_closed(book, chapter): ...      # leave the chapter out
    holdout.check_env()                           # at start-up: DRAFTER_HOLDOUT must cover the held-out chapters

Some of the closed chapters have never been drafted or scored by the current drafter (Philippians 3, Acts 1, Matthew 21 in
Zinza and Kuni; Genesis 22 in Kuni). They are kept for a later acceptance test, run from the research repository: nothing
here reads them, and a pool that holds them is a defect.

A tuning trial's chapters (onboard/tune.py, plan section 3.12) are a softer hold-out: `trial_chapters(lang)` names the dev and
confirm chapters of every declared trial of a language. Drafting, pools and publishing may read them; a later trial may not
tune on an earlier trial's confirm chapters (they would no longer confirm anything), and tune.py refuses that.

    python3 shared/holdout.py [--lang zin]   # print the list (and a language's trial chapters) and check the environment"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HELD_OUT = {("LUK", 1), ("LUK", 2), ("LUK", 15), ("PHP", 3), ("ACT", 1), ("MAT", 21)}     # never in a training set or a pool


def closed():
    """{"version", "chapters": {(book, chapter)}, "books": {book}, "reasons": {...}}"""
    d = json.load(open(os.path.join(HERE, "closed.json"), encoding="utf-8"))
    return {"version": d["version"], "chapters": {(b, int(c)) for b, c in d["chapters"]}, "books": set(d["books"]), "reasons": d.get("reasons", {})}


def is_closed(book, chapter):
    c = closed()
    return book in c["books"] or (book, int(chapter)) in c["chapters"]


def parse(spec):
    """'LUK:1,2,15;PHP:3' -> {(book, chapter)}"""
    out = set()
    for part in filter(None, (spec or "").split(";")):
        b, chs = part.split(":")
        out |= {(b.strip().upper(), int(c)) for c in chs.split(",") if c.strip()}
    return out


def shut(cfg):
    """(book, chapter) -> True when no pool, training set or measurement of this language may read the chapter: the language's own
    held-out chapters, DRAFTER_HOLDOUT, and the closed list where the language's configuration says it applies"""
    held = parse(os.environ.get("DRAFTER_HOLDOUT")) | parse(";".join(cfg.get("held_out", [])))
    c = closed() if cfg.get("closed_list") else {"books": set(), "chapters": set()}

    def f(book, chapter):
        return book in c["books"] or (book, int(chapter)) in c["chapters"] or (book, int(chapter)) in held
    f.books = set(c["books"]); f.chapters = set(c["chapters"]) | held
    return f


def trial_chapters(lang):
    """{(book, chapter): [(trial, "dev" | "confirm")]} of the language's declared tuning trials
    ($MAKE_TANAKH_PRIVATE/lang/<iso>/tuning/<trial>/plan.json)"""
    from shared import paths
    d = paths.lang_dir(lang, "tuning"); out = {}
    for t in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        p = os.path.join(d, t, "plan.json")
        if os.path.exists(p):
            plan = json.load(open(p, encoding="utf-8"))
            for role in ("dev", "confirm"):
                for c in plan.get(role, []):
                    out.setdefault((plan["book"], int(c)), []).append((t, role))
    return out


def check_env():
    """exit unless DRAFTER_HOLDOUT covers every held-out chapter (. ./env.sh sets the default)"""
    missing = HELD_OUT - parse(os.environ.get("DRAFTER_HOLDOUT"))
    if missing:
        sys.exit("DRAFTER_HOLDOUT does not cover " + ", ".join(f"{b} {c}" for b, c in sorted(missing)) + ": source env.sh, or do not open held-out chapters")
    assert all(is_closed(b, c) for b, c in HELD_OUT), "shared/closed.json no longer closes the held-out chapters"


if __name__ == "__main__":
    c = closed(); check_env()
    if "--lang" in sys.argv:
        sys.path.insert(0, os.path.dirname(HERE)); lang = sys.argv[sys.argv.index("--lang") + 1]
        for (b, ch), uses in sorted(trial_chapters(lang).items()):
            print(f"{lang} trial chapter {b} {ch}: " + ", ".join(f"{t} {r}" for t, r in uses))
    print("closed list version", c["version"])
    print("books:", ", ".join(sorted(c["books"])))
    print("chapters:", ", ".join(f"{b} {ch}" for b, ch in sorted(c["chapters"])))
    print("held out of every pool and training:", ", ".join(f"{b} {ch}" for b, ch in sorted(HELD_OUT)))
