#!/usr/bin/env python3
"""Step A clean test (adapted from setup_spot.py, 2026-10-28). Jonah 1-4 is drafted by an agent that
must not see the human Kuni of Jonah:

  edition  import/non-free/kvg/KVG-jontest/   a copy of KVG-KuNT's text/ without jon001-004 (no source/: the
                                            team's SFM holds them); git-ignored through .git/info/exclude
  arms     local_output/kvg/spot_<A|B|C|D>/ copies of export/kvg/kvg_BSB without _eval/ (old Ruth tests, analyses),
           style_from KVG-jontest; the store without what came from those chapters:
             term / formula / name / gap / letter entries that cite them (evidence, ref, note): dropped
             grammar entries (feature, morph, cell, claim): kept, the citing evidence and note sentences removed
           wiki, notes and state lines that cite them: removed

  python3 lab/heldout/setup_spot.py edition | arms A B C D | report
The _learn/ statistics are rebuilt afterwards on the spot edition (align.py, lang.py build, build_units.py), once in
spot_A, then copied."""
import json, os, re, shutil, sys

ROOT = os.environ["MAKE_TANAKH_WORK"]
SRC_ED = os.path.join(ROOT, "import/non-free/kvg/KVG-KuNT")
ED = os.path.join(ROOT, "import/non-free/kvg/KVG-jontest")
SRC_P = os.path.join(ROOT, "export/kvg/kvg_BSB")
HELD = ("jon001", "jon002", "jon003", "jon004")
CITE = re.compile(r"\b(?:JON|Jon|Jonah|jon)\.? ?[1-4]:\d+|\bjon00[1-4]\b|\b(?:JON|Jonah)\b")
DROP_KINDS = {"term", "formula", "name", "gap"}


def edition():
    if os.path.exists(ED):
        shutil.rmtree(ED)
    os.makedirs(os.path.join(ED, "text"))
    n = 0
    for f in sorted(os.listdir(os.path.join(SRC_ED, "text"))):
        if f[:6] in HELD:
            continue
        shutil.copy(os.path.join(SRC_ED, "text", f), os.path.join(ED, "text", f)); n += 1
    shutil.copy(os.path.join(SRC_ED, "glossary.tsv"), ED)
    y = open(os.path.join(SRC_ED, "edition.yaml"), encoding="utf-8").read()
    y = re.sub(r"\nsfm:.*", "\n", y, flags=re.S)                         # the SFM block names the team's files
    y = ("# KVG-jontest: the Step A copy of KVG-KuNT without Jonah 1-4 (private; "
         "lab/heldout/setup_spot.py)\n" + y)
    open(os.path.join(ED, "edition.yaml"), "w", encoding="utf-8").write(y)
    ex = os.path.join(ROOT, ".git/info/exclude")
    if "KVG-jontest" not in open(ex).read():
        open(ex, "a").write("\n# 2026-10-28: the Step A Jonah test's edition copy (private)\nimport/non-free/kvg/KVG-jontest/\n")
    print(f"KVG-jontest: {n} chapter files (without {', '.join(HELD)})")


def strip_text(s):
    """sentences or '; '-parts of a note that cite a held chapter, removed"""
    if not isinstance(s, str) or not CITE.search(s):
        return s
    parts = re.split(r"(?<=[.;])\s+", s)
    return " ".join(p for p in parts if not CITE.search(p)).strip()


def clean_store(pdir, stats):
    dropped = set()
    for f in ("observations.json", "decisions.json"):
        p = os.path.join(pdir, "profile", f)
        d = json.load(open(p, encoding="utf-8"))
        keep = []
        for e in d["entries"]:
            if not CITE.search(json.dumps(e, ensure_ascii=False)):
                keep.append(e); continue
            if e.get("kind") in DROP_KINDS and e.get("method") != "team-decision":   # team decisions are always kept (binding)
                dropped.add(e.get("id")); stats[f"dropped {e.get('kind')}"] += 1; continue
            if isinstance(e.get("evidence"), list):
                e["evidence"] = [x for x in e["evidence"] if not CITE.search(json.dumps(x, ensure_ascii=False))]
            for k in ("note", "value", "source"):
                if k in e:
                    e[k] = strip_text(e[k])
            for k in ("tests", "examples"):
                if isinstance(e.get(k), list):
                    e[k] = [x for x in e[k] if not CITE.search(json.dumps(x, ensure_ascii=False))]
            left = CITE.search(json.dumps(e, ensure_ascii=False))
            if left:                                   # cited somewhere else in a grammar entry: blank that field's strings
                def scrub(x):
                    if isinstance(x, str):
                        return CITE.sub("…", x)
                    if isinstance(x, list):
                        return [scrub(y) for y in x]
                    if isinstance(x, dict):
                        return {k: scrub(v) for k, v in x.items()}
                    return x
                e = scrub(e)
            stats[f"cleaned {e.get('kind')}"] += 1
            keep.append(e)
        d["entries"] = keep
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        open(p, "a").write("\n")
    for f in ("observations.json", "decisions.json"):            # a supersedes link to a dropped entry (in either file) goes
        p = os.path.join(pdir, "profile", f)
        d = json.load(open(p, encoding="utf-8"))
        for e in d["entries"]:
            if e.get("supersedes") in dropped:
                e.pop("supersedes"); stats["supersedes unlinked"] += 1
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        open(p, "a").write("\n")


def clean_lines(path, stats):
    t = open(path, encoding="utf-8").read()
    lines = t.split("\n")
    out = [l for l in lines if not CITE.search(l)]
    if len(out) != len(lines):
        stats["lines removed"] += len(lines) - len(out)
        open(path, "w", encoding="utf-8").write("\n".join(out))


def held_runs(n=5):
    """n-word runs of the held-out chapters that the spot corpus doesn't have (so a line holding one quotes them)"""
    import glob, unicodedata as U
    norm = lambda t: U.normalize("NFC", t).lower()
    corpus = set()
    for g in glob.glob(os.path.join(ED, "text", "*.txt")):
        w = norm(open(g, encoding="utf-8").read()).split()
        corpus |= {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}
    runs = set()
    for f in HELD:
        t = norm(open(os.path.join(SRC_ED, "text", f + ".txt"), encoding="utf-8").read())
        for m in re.finditer(r"(?:^|\s)v\d+\s+(.*?)(?=\sv\d+\s|\n\n|$)", t, re.S):
            w = m[1].split()
            runs |= {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)} - corpus
    return runs, norm


def arm(name):
    import collections
    dst = os.path.join(ROOT, "local_output/kvg", f"jon_{name}")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(SRC_P, dst, ignore=shutil.ignore_patterns("_eval", "wiki-view.html", "packs", "*.tagged",
                                                              "style_norms*.json", "lang.sqlite", "links_*", "lexicon_*",
                                                              "units_*", "usage.tsv", "probe.json"))
    os.makedirs(os.path.join(dst, "_learn", "packs"), exist_ok=True)
    stats = collections.Counter()
    clean_store(dst, stats)
    for dp, _, fs in os.walk(dst):
        for f in fs:
            if f.endswith(".md") and "/profile" not in dp:
                clean_lines(os.path.join(dp, f), stats)
    runs, norm = held_runs()                     # lines (and store entries) quoting them without a reference
    for dp, _, fs in os.walk(dst):
        for f in fs:
            p = os.path.join(dp, f)
            if f.endswith(".md"):
                lines = open(p, encoding="utf-8").read().split("\n")
                out = [l for l in lines if not any(r in norm(l) for r in runs)]
                if len(out) != len(lines):
                    stats["quoting lines removed"] += len(lines) - len(out)
                    open(p, "w", encoding="utf-8").write("\n".join(out))
            elif f.endswith(".json") and "/profile" in dp:
                d = json.load(open(p, encoding="utf-8"))
                n0 = len(d["entries"])
                d["entries"] = [e for e in d["entries"] if not any(r in norm(json.dumps(e, ensure_ascii=False)) for r in runs)]
                if len(d["entries"]) != n0:
                    stats["quoting entries dropped"] += n0 - len(d["entries"])
                    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                    open(p, "a").write("\n")
    y = open(os.path.join(dst, "project.yaml"), encoding="utf-8").read()
    y = y.replace("style_from: [KVG-KuNT]", "style_from: [KVG-jontest]")
    y = re.sub(r"style_model:\n(?:  - .*\n)+", "style_model:\n  - import/non-free/kvg/KVG-jontest/text/rut002.txt\n"
               "  - import/non-free/kvg/KVG-jontest/text/rut003.txt\n  - import/non-free/kvg/KVG-jontest/text/rut001.txt\n", y)
    y = y.replace("do_not_open: [download/, scratch/]",
                  "do_not_open: [download/, scratch/, import/non-free/kvg/KVG-KuNT/, export/kvg/, ~/bsb-nllb/, /tmp/]")
    y = ("# Step A clean test " + name + " (make-tanakh-grammar lab/heldout/setup_jon.py, 2026-10-28): Jonah 1-4 held out\n" + y)
    open(os.path.join(dst, "project.yaml"), "w", encoding="utf-8").write(y)
    print(f"jon_{name}:", dict(stats))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "edition":
        edition()
    elif a[0] in ("arms", "arm"):
        for n in a[1:]:
            arm(n)
