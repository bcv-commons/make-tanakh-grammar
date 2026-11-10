#!/usr/bin/env python3
"""The segmenter bundle (bcv-segfacts/0.1) built from the register (internal-docs/review-feedback-data-plan-2026-11-10.md,
section 3.5): the settings are the register's morph, word and orthography entries (what the team may edit); the statistics
(vocab: word counts, classes: Greek classes per word) are the text's and stay private; the splitter (morphs.py,
bcv_segment.py) is pinned by its sha256 and copied unchanged from the language's current bundle.

  build   -> $MAKE_TANAKH_PRIVATE/lang/<iso>/segmenter/ (seg_facts.json, morphs.py, bcv_segment.py, PIN.json)
            --stats bundle (default: the current bundle's vocab and classes)
  compare  every word type of the statistics split by the built bundle and by the base one: the exit test of S2 (2026-11-10:
           Kuni 14,623 and Zinza 15,789 word types, none split otherwise)

The configuration's `segmenter` names the built bundle ("segmenter"), `segmenter_base` the published one.

    . ./env.sh; ~/sil-study/.venv/bin/python onboard/segbundle.py build --lang kvg
    ~/sil-study/.venv/bin/python onboard/segbundle.py compare --lang kvg"""
import argparse, hashlib, importlib.util, json, os, shutil, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths, register as RG  # noqa: E402

SPLITTER = ("morphs.py", "bcv_segment.py")
STATUS = {"decided": "decided", "open": "open", "proposed": "observed"}     # the splitter's statuses (morphs.is_confirmed)
STORE_PRE = {"morph": "m", "word": "w"}


def store_entry(e):
    """a register morph or word entry in the store's shape the splitter reads"""
    sid = e["origin"].split("#", 1)[1] if (e.get("origin") or "").startswith("store:") else STORE_PRE[e["kind"]] + ":" + e["id"].split(":", 1)[1]
    x = {"id": sid, "kind": e["kind"], "value": e["value"], "status": STATUS.get(e["status"], "open")}
    for k in RG.KINDS[e["kind"]][1]:
        if k in e:
            x[k] = e[k]
    if e.get("evidence"):
        x["evidence"] = e["evidence"]
    return x


def splits(e):
    """whether an entry reaches the splitter: the seeded ones (the store's, as the published bundle had them), and after the seed
    only what the team or a human decided; a proposal (an affix from one edit, onboard/intake.py) waits for its decision"""
    return (e.get("origin") or "").startswith("store:") or e["status"] == "decided"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def current(lang):
    """the published bundle the built one takes its splitter and statistics from (config segmenter_base)"""
    c = paths.config(lang); return paths.resolve(lang, c.get("segmenter_base") or c["segmenter"])


def build(lang, stats=None, register=None, out=None):
    """the bundle from a register folder (default: the language's) into out (default: private/lang/<iso>/segmenter)"""
    cfg = paths.config(lang); reg = register or cfg["_register"]; E = RG.live(RG.load(reg)); cur = current(lang)
    old = json.load(open(os.path.join(stats or cur, "seg_facts.json"), encoding="utf-8"))
    orth = next((e for e in E if e["kind"] == "orthography"), None)
    facts = {"spec": "bcv-segfacts/0.1", "project": old.get("project"), "date": time.strftime("%Y-%m-%d"),
             "licence": {"morphs, words, orthography": "CC0 (the register)", "vocab, classes": "private: statistics of the text",
                         "code (morphs.py, bcv_segment.py)": "MIT"},
             "morphs": [store_entry(e) for e in E if e["kind"] == "morph" and splits(e)],
             "words": [store_entry(e) for e in E if e["kind"] == "word" and splits(e)],
             "orthography": {k: orth[k] for k in RG.KINDS["orthography"][1] if k in orth and k != "keep_marks"} if orth else old["orthography"],
             "vocab": old["vocab"], "classes": old.get("classes")}
    out = out or paths.lang_dir(lang, "segmenter"); os.makedirs(out, exist_ok=True)
    for f in SPLITTER:
        shutil.copy(os.path.join(cur, f), os.path.join(out, f))
    json.dump(facts, open(os.path.join(out, "seg_facts.json"), "w", encoding="utf-8"), ensure_ascii=False)
    rev = json.load(open(os.path.join(reg, "VERSION.json"), encoding="utf-8")).get("revision")
    json.dump({"splitter": {f: sha(os.path.join(out, f)) for f in SPLITTER}, "settings": f"register-{rev}",
               "statistics": os.path.relpath(stats or cur, paths.private()), "built": facts["date"]},
              open(os.path.join(out, "PIN.json"), "w"), indent=1)
    return out, len(facts["morphs"]), len(facts["words"])


def load(d):
    spec = importlib.util.spec_from_file_location(f"bcv_segment_{abs(hash(d))}", os.path.join(d, "bcv_segment.py"))
    sys.modules.pop("morphs", None); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    s = m.load(d); sys.path.remove(d); return s


def compare(lang, built=None, base=None):
    """(word types, [(word, split by built, split by base)]): built defaults to the language's built bundle, base to segmenter_base"""
    a, b = load(built or paths.lang_dir(lang, "segmenter")), load(base or current(lang))
    words = sorted(set(a.facts["vocab"]) | set(a.facts.get("classes") or {})); diff = []
    for w in words:
        x = [(p["slot"], p["text"]) for p in a.split(w)]; y = [(p["slot"], p["text"]) for p in b.split(w)]
        if x != y:
            diff.append((w, x, y))
    return len(words), diff


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "compare")); ap.add_argument("--lang", required=True); ap.add_argument("--stats")
    a = ap.parse_args()
    if a.cmd == "build":
        print(json.dumps(dict(zip(("out", "morphs", "words"), build(a.lang, a.stats)))))
    else:
        n, diff = compare(a.lang)
        print(json.dumps({"word types": n, "split otherwise": len(diff)}))
        for w, x, y in diff[:15]:
            print(f"  {w}: register {x} | current {y}")


if __name__ == "__main__":
    main()
