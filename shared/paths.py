#!/usr/bin/env python3
"""Where things are: the settings of env.sh, the private data folder and a language's configuration.

    MAKE_TANAKH_PRIVATE/
        lang/<iso>/config.json      one configuration per language (below)
        lang/<iso>/corpus/*.db      the team's text as parts with links to the source (the corpus chain's product)
        source/bridges/*.json       the Hebrew-Greek lexeme and grammar bridges
        aligner-data/               clause layouts and other inputs fetched at the aligner's pin
        runs/<iso>/...              prompts, answers, chapters, manifests

A language's config.json:

    {"iso": "xxx", "name": "Language name",
     "closed_list": true,                         # the research closed list (shared/closed.json) applies to this language
     "held_out": ["LUK:1,2,15", "PHP:3"],         # the language's own held-out chapters (never in a pool)
     "corpora": [{"source": "grc", "db": "corpus/nt_parts.db", "key": "key",          # split, layer: what onboard/corpus.py builds it from
                  "split": "inputs/split", "layer": "inputs/layer"},
                 {"source": "hbo", "db": "corpus/tanakh_parts.db", "key": "word", "exclude_books": ["RUT"]}],
     "store": "$WORK/export/xxx/xxx_BSB/profile", # optional: the language store (team decisions on terms and names)
     "notes": {"dir": "...", "pages": ["verbs", "word-order"]},   # optional: grammar pages shown to the drafter
     "dev": {"grc": {"book": "JHN", "chapters": [1, 2, 3, 4], "leave_out_books": ["JHN"]}}}

Paths in a configuration are relative to the language's folder; a leading $WORK, $PRIVATE or $IMPORT names the work copy of
make-tanakh, the private data folder or the imported editions (import/README.md)."""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = ("grc", "hbo")                       # the Greek NT and the Hebrew Bible, by their language codes
SOURCE_NAME = {"grc": "Greek", "hbo": "Hebrew"}


def env(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(f"{name} is not set: source env.sh first (. ./env.sh)")
    return v


def private(*p):
    return os.path.join(env("MAKE_TANAKH_PRIVATE"), *p)


def work(*p):
    return os.path.join(env("MAKE_TANAKH_WORK"), *p)


def imports(*p):
    """the imported editions, filed by licence (import/README.md)"""
    return os.path.join(os.environ.get("MAKE_TANAKH_IMPORT") or os.path.join(ROOT, "import"), *p)


def aligner_data(*p):
    return os.path.join(os.environ.get("ALIGNER_DATA") or private("aligner-data"), *p)


def lang_dir(iso, *p):
    return private("lang", iso, *p)


def run_dir(iso, *p, make=True):
    d = private("runs", iso, *p)
    if make:
        os.makedirs(d, exist_ok=True)
    return d


def resolve(iso, path):
    """a configuration path -> an absolute path"""
    if path.startswith("$WORK"):
        return work(path[len("$WORK"):].lstrip("/"))
    if path.startswith("$PRIVATE"):
        return private(path[len("$PRIVATE"):].lstrip("/"))
    if path.startswith("$IMPORT"):
        return imports(path[len("$IMPORT"):].lstrip("/"))
    return path if os.path.isabs(path) else lang_dir(iso, path)


_CFG = {}


def config(iso, built=True):
    """the language's configuration, checked; paths resolved under "_db" (corpora), "_store", "_notes_dir". built=False: the
    corpora need not exist yet (the first stage builds them)"""
    if iso in _CFG and built:
        return _CFG[iso]
    p = lang_dir(iso, "config.json")
    if not os.path.exists(p):
        sys.exit(f"no configuration for language '{iso}': {p} (the first stage writes it: onboard)")
    c = json.load(open(p, encoding="utf-8"))
    for k in ("iso", "name", "corpora"):
        if k not in c:
            sys.exit(f"{p}: '{k}' is missing")
    if c["iso"] != iso:
        sys.exit(f"{p}: iso is '{c['iso']}', the folder says '{iso}'")
    for x in c["corpora"]:
        if x.get("source") not in SOURCES or x.get("key") not in ("key", "word"):
            sys.exit(f"{p}: a corpus needs source grc|hbo and key key|word: {x}")
        x["_db"] = resolve(iso, x["db"])
        if built and not os.path.exists(x["_db"]):
            sys.exit(f"{p}: corpus {x['_db']} does not exist (the first stage builds it: onboard/corpus.py)")
    c["_store"] = resolve(iso, c["store"]) if c.get("store") else None
    c["_notes_dir"] = resolve(iso, c["notes"]["dir"]) if c.get("notes") else None
    if built:
        _CFG[iso] = c
    return c


def corpus(cfg, source):
    """the language's corpus of one source language, or None"""
    return next((x for x in cfg["corpora"] if x["source"] == source), None)
