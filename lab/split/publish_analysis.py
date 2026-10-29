#!/usr/bin/env python3
"""Our language analysis as the Hugging Face dataset bcv-commons/language-analysis (user 2026-10-26; local tool, with
export_split.py and seg_bundle.py). Builds the dataset tree locally; pushing is a separate, explicit step.

    /usr/bin/python3 lab/split/publish_analysis.py build [project ...]     -> private/hf/language-analysis/
    ~/sil-study/.venv/bin/python lab/split/publish_analysis.py push [--yes]  (dry run without --yes)

Tree:
  manifest.json                         per language: the newest version and every version with its files and hashes
  README.md                             the dataset card (licences, credits, what is not here and why)
  <lang>/<version>/store/               the project's profile/ (*.json, *.yaml): the language store, CC0
  <lang>/<version>/bundle/              the segmenter: seg_facts.json (CC0), morphs.py + bcv_segment.py (MIT); only with morph entries
  <lang>/<version>/split/               the style corpus as a split file (bcv-split/0.1), only where the text's licence allows
  <lang>/<version>/conventions.md       the target module for an LLM aligner, generated from the store (conventions.py)
  <lang>/<version>/terms.tsv            the store's names and terms, source -> target
  <lang>/<version>/VERSION.json         project, edition, date, the store's hash, the licence of each folder
  source/<grc|hbo|arc>/<sha8>/module.md the source modules: rules about the source language that hold for every target

<version> = the first 8 hex digits of the sha256 of the store files (sorted by name, each name + content): the same store gives
the same version, a changed store a new one. Built only from tracked, derived data: never a text that is not free."""
import argparse, datetime, glob, hashlib, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.environ["MAKE_TANAKH_WORK"]
OUT = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "hf/language-analysis")   # the dataset's staging tree, never in git (env.sh)
REPO = "bcv-commons/language-analysis"
VENV = os.path.expanduser("~/sil-study/.venv/bin/python")

# project -> (dataset folder, style edition, may the split file be published, the text's licence and credit)
PROJECTS = {
    "zin/zin_BSB": ("zin", "zin_wbt", True, "CC BY-SA 4.0", "Bibilia Endagaano Ensya (Zinza New Testament), Wycliffe Bible Translators, CC BY-SA 4.0"),
    "kvg/kvg_BSB": ("kvg", "KVG-KuNT", False, "non-free (CC BY-NC-ND)", "Kuni New Testament and portions, the Kuni translation team"),
    "dan/dan_BSB": ("dan", "den-frie-bibel", True, "CC0 / public domain", "Den Frie Bibel"),
    "jam/jam_BSB": ("jam", None, False, "non-free", None),
    "ch-de-be/ch-de-be_BSB": ("ch-de-be", None, False, "non-free", "Hans Bietenhard, Ds Nöie Teschtamänt bärndütsch"),
}


def store_files(pname):
    d = os.path.join(R, "export", pname, "profile")
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith((".json", ".yaml")))


FORMAT = 3   # the layout of what is built from a store (2: full conventions.md, jev.md, rules.json, derived names; 3: rule words {words: …}, forms in rules.json); part of the version


SOURCE_FORMAT = 2   # the source modules' layout: unchanged by format 3 (rule words are a target-module change)


def version(files, fmt=None):
    h = hashlib.sha256(); fmt = fmt or FORMAT
    if fmt > 1:
        h.update(f"format {fmt}".encode()); h.update(b"\0")
    for f in files:
        h.update(os.path.basename(f).encode()); h.update(b"\0"); h.update(open(f, "rb").read()); h.update(b"\0")
    return h.hexdigest()[:8]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def has_morphs(files):
    for f in files:
        if f.endswith("observations.json"):
            d = json.load(open(f, encoding="utf-8"))
            return any(e.get("kind") == "morph" and e.get("status") != "superseded" for e in d.get("entries", []))
    return False


def build(projects):
    man_p = os.path.join(OUT, "manifest.json")
    man = json.load(open(man_p, encoding="utf-8")) if os.path.exists(man_p) else {"dataset": REPO, "languages": {}}
    for pname in projects:
        lang, edition, split_ok, text_lic, credit = PROJECTS[pname]
        files = store_files(pname); v = version(files)
        d = os.path.join(OUT, lang, v)
        if os.path.exists(os.path.join(d, "VERSION.json")):
            print(f"{lang} {v}: already built"); continue
        os.makedirs(os.path.join(d, "store"), exist_ok=True)
        for f in files:
            shutil.copy(f, os.path.join(d, "store", os.path.basename(f)))
        lic = {"store/": "CC0 1.0 (our analysis of the language: docs/licensing.md, 'Ours, CC0')"}
        if has_morphs(files):
            subprocess.run([sys.executable, os.path.join(HERE, "seg_bundle.py"), pname, os.path.join(d, "bundle")], check=True,
                           stdout=subprocess.DEVNULL)
            lic["bundle/seg_facts.json"] = "CC0 1.0 (the store's morphs and statistics of the edition's words)"
            lic["bundle/*.py"] = "MIT"
        subprocess.run([sys.executable, os.path.join(HERE, "conventions.py"), pname, d], check=True, stdout=subprocess.DEVNULL)
        lic["conventions.md, rules.json, terms.tsv"] = "CC0 1.0 (generated from the store: the target module for an LLM aligner)"
        if split_ok and edition and has_morphs(files):
            subprocess.run([VENV, os.path.join(HERE, "export_split.py"), pname, edition, "--out", os.path.join(d, "split")], check=True,
                           stdout=subprocess.DEVNULL)
            lic["split/"] = f"{text_lic}: it holds the edition's text, cut into parts. Credit: {credit}"
        meta = {"language": lang, "project": pname, "version": v, "date": str(datetime.date.today()), "style_edition": edition,
                "text_licence": text_lic, "text_published_here": bool(split_ok and edition and has_morphs(files)),
                "licence": lic, "source": "make-tanakh (larsgson/make-tanakh-work), the project's language store"}
        json.dump(meta, open(os.path.join(d, "VERSION.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        hashes = {os.path.relpath(os.path.join(a, f), d): sha(os.path.join(a, f)) for a, _, fs in os.walk(d) for f in fs}
        L = man["languages"].setdefault(lang, {"versions": {}})
        L["versions"][v] = {"date": meta["date"], "licence": lic, "files": dict(sorted(hashes.items()))}
        L["latest"] = v
        print(f"{lang} {v}: {len(hashes)} files")
    # the source modules (rules about Greek, Hebrew, Aramaic that hold for every target), each versioned by its own hash
    src = man.setdefault("source_modules", {})
    for f in sorted(g for g in glob.glob(os.path.join(HERE, "source_modules", "*.md")) if not g.endswith("_jev.md")):
        lang = os.path.basename(f)[:-3]; jf = source_jev(lang, f); v = version([f, jf], SOURCE_FORMAT)
        d = os.path.join(OUT, "source", lang, v)
        os.makedirs(d, exist_ok=True); shutil.copy(f, os.path.join(d, "module.md"))
        shutil.copy(jf, os.path.join(d, "jev.md"))
        S = src.setdefault(lang, {"versions": {}})
        S["versions"].setdefault(v, {"date": str(datetime.date.today()), "files": {"module.md": sha(f), "jev.md": sha(jf)},
                                     "licence": "CC0 1.0; written by an LLM (Claude) in a bsb-add-books session, from MACULA's analysis (CC BY 4.0)"})
        S["latest"] = v
        print(f"source {lang} {v}")
    man["docs"] = {f: sha(os.path.join(OUT, f)) for f in ("README.md", "CLAUSES.md") if os.path.exists(os.path.join(OUT, f))}
    json.dump(man, open(man_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def source_jev(lang, f):
    """a source module's short form for an aligner: source_modules/<lang>_jev.md, written beside it with the same ids (an
    automatic cut loses the link instruction); refused when its ids differ from the module's"""
    import re
    jf = f[:-3] + "_jev.md"
    ids = lambda t: re.findall(r"^- `(%s\.\d\d)`" % lang, t, flags=re.M)
    a, b = ids(open(f, encoding="utf-8").read()), ids(open(jf, encoding="utf-8").read())
    if a != b:
        sys.exit(f"{jf}: ids differ from {f}: {sorted(set(a) ^ set(b))}")
    return jf


def push(yes):
    from huggingface_hub import HfApi
    api = HfApi()
    if not yes:
        n = sum(len(fs) for _, _, fs in os.walk(OUT))
        print(f"dry run: would upload {OUT} ({n} files) to datasets/{REPO}; rerun with --yes"); return
    api.create_repo(REPO, repo_type="dataset", exist_ok=True)
    api.upload_folder(folder_path=OUT, repo_id=REPO, repo_type="dataset", commit_message=f"language-analysis {datetime.date.today()}")
    print("pushed", REPO)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "push"]); ap.add_argument("projects", nargs="*"); ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.projects or list(PROJECTS))
    else:
        push(a.yes)
