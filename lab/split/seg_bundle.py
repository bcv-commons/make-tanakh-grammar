#!/usr/bin/env python3
"""A project's segmenter as a bundle another repo can run without the project (2026-10-26, local; with export_split.py):

    /usr/bin/python3 lab/split/seg_bundle.py <project> <DIR>
      DIR/seg_facts.json   the fact file (`bcv-segfacts/0.1`): the store's morph entries (the `chain_id`s of the split files),
                           its never-split words, the orthography (tone writing, ignored marks), the attested words with
                           counts (what an affix may leave behind) and the words' Greek classes (host-aware chains)
      DIR/morphs.py        the segmenter's code, a copy of scripts/morphs.py (MIT)
      DIR/bcv_segment.py   the reader: load(DIR) -> Seg; Seg.split(word) -> [{slot, form, text, position, chain_id}]

The fact file is derived from the edition (counts and classes of its words), so it goes where the split file may go:
published with a free text (CC0 as our derived data), kept local with a non-free one."""
import collections, datetime, json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.environ["MAKE_TANAKH_WORK"]
sys.path.insert(0, os.path.join(R, "scripts"))
import langtools as LT, morphs as M, grammar  # noqa: E402

READER = r'''"""Read a bcv-segfacts/0.1 bundle and split words as the producing project's store does.

    import bcv_segment; seg = bcv_segment.load("<bundle dir>"); seg.split("naáyaandika")
    python3 bcv_segment.py <bundle dir> <word> ...

Needs only this folder (morphs.py is the producer's segmenter, MIT). A word's parts rebuild it as written (bcv-split rule)."""
import json, os, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))


class Seg:
    def __init__(self, d):
        f = json.load(open(os.path.join(d, "seg_facts.json"), encoding="utf-8"))
        assert f["spec"] == "bcv-segfacts/0.1", f["spec"]
        sys.modules.setdefault("grammar", types.ModuleType("grammar"))   # morphs.py imports it; unused here
        sys.path.insert(0, d)
        import morphs
        self.M, self.facts = morphs, f
        G = types.SimpleNamespace(morphs=f["morphs"], words=f["words"])
        classes = {w: morphs.collections.Counter(c) for w, c in (f.get("classes") or {}).items()} or None
        self.S = morphs.Segmenter(G, f["orthography"], f["vocab"], classes)
        self.ids = {(e["form"], e.get("position") or 0): e.get("id") for e in f["morphs"]}

    def split(self, word):
        return [{"slot": m.slot, "form": m.form, "text": m.text, "position": m.position,
                 "chain_id": self.ids.get((m.form, m.position)) if m.slot != "stem" else None} for m in self.S.split(word)]


def load(d=HERE):
    return Seg(d)


if __name__ == "__main__":
    s = load(sys.argv[1])
    for w in sys.argv[2:]:
        print(w, s.split(w))
'''


def main():
    pname, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    P = LT.Project(pname); G = grammar.load(pname); S = M.load(pname, P, G)
    if S is None:
        sys.exit(f"{pname}: no morph entries")
    orth = {}
    f = os.path.join(P.profile, "observations.json")
    if os.path.exists(f):
        orth = json.load(open(f, encoding="utf-8")).get("orthography") or {}
    vocab = collections.Counter()
    for r in P.corpus():
        vocab.update(P.tok.tokens(r[4], exact=True))
    cl = M.word_classes(pname, P)
    lic = None
    import yaml
    for e in P.editions:
        y = os.path.join(R, e["dir"], "edition.yaml")
        if os.path.exists(y):
            lic = " ".join(str((yaml.safe_load(open(y, encoding="utf-8")) or {}).get("licence") or "").split()) or None
            break
    facts = {"spec": "bcv-segfacts/0.1", "project": pname, "date": str(datetime.date.today()),
             "licence": {"morphs, orthography": "CC0 (the project's language store)",
                         "vocab, classes": "CC0 (statistics of the edition's words: counts and Greek classes, not its wording; docs/licensing.md)",
                         "code (morphs.py, bcv_segment.py)": "MIT"},
             "morphs": [{k: v for k, v in e.items() if k != "evidence"} for e in G.morphs],   # all the segmenter may read
             "words": list(getattr(G, "words", []) or []),
             "orthography": orth,
             "vocab": {w: n for w, n in vocab.items() if n >= 2},
             "classes": {w: dict(c) for w, c in (cl or {}).items()}}
    json.dump(facts, open(os.path.join(out, "seg_facts.json"), "w", encoding="utf-8"), ensure_ascii=False)
    shutil.copy(os.path.join(R, "scripts", "morphs.py"), os.path.join(out, "morphs.py"))
    open(os.path.join(out, "bcv_segment.py"), "w", encoding="utf-8").write(READER)
    # the bundle must split as the store does: every corpus word, in a separate isolated Python run from another folder
    import subprocess, tempfile
    words = sorted(vocab)
    tmp = tempfile.mkdtemp()
    json.dump(words, open(os.path.join(tmp, "words.json"), "w", encoding="utf-8"), ensure_ascii=False)
    code = ("import json,sys; sys.path.insert(0, sys.argv[1]); import bcv_segment as B; s = B.load(sys.argv[1]); "
            "ws = json.load(open(sys.argv[2], encoding='utf-8')); "
            "json.dump([[[p['slot'], p['form'], p['text'], p['position']] for p in s.split(w)] for w in ws], open(sys.argv[3], 'w'))")
    subprocess.run([sys.executable, "-I", "-B", "-c", code, os.path.abspath(out), os.path.join(tmp, "words.json"), os.path.join(tmp, "out.json")],
                   cwd=tmp, check=True)
    got = json.load(open(os.path.join(tmp, "out.json")))
    same = diff = 0; ex = []
    for w, b in zip(words, got):
        a = [[m.slot, m.form, m.text, m.position] for m in S.split(w)]
        if a == b:
            same += 1
        else:
            diff += 1
            if len(ex) < 5:
                ex.append((w, a, b))
    print(out, "morphs", len(facts["morphs"]), "never-split words", len(facts["words"]), "vocab", len(facts["vocab"]),
          "classes", len(facts["classes"]), "| bundle vs store on every corpus word: same", same, "different", diff, ex)


if __name__ == "__main__":
    main()
