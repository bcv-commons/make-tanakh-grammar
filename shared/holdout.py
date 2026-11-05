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

    python3 shared/holdout.py        # print the list and check the environment"""
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


def check_env():
    """exit unless DRAFTER_HOLDOUT covers every held-out chapter (. ./env.sh sets the default)"""
    missing = HELD_OUT - parse(os.environ.get("DRAFTER_HOLDOUT"))
    if missing:
        sys.exit("DRAFTER_HOLDOUT does not cover " + ", ".join(f"{b} {c}" for b, c in sorted(missing)) + ": source env.sh, or do not open held-out chapters")
    assert all(is_closed(b, c) for b, c in HELD_OUT), "shared/closed.json no longer closes the held-out chapters"


if __name__ == "__main__":
    c = closed(); check_env()
    print("closed list version", c["version"])
    print("books:", ", ".join(sorted(c["books"])))
    print("chapters:", ", ".join(f"{b} {ch}" for b, ch in sorted(c["chapters"])))
    print("held out of every pool and training:", ", ".join(f"{b} {ch}" for b, ch in sorted(HELD_OUT)))
