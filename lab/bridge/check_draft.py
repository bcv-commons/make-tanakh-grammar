#!/usr/bin/env python3
"""H3, the engine as a checker: for each Hebrew content word of a verse, the engine's rendering (engine_render.py's
.glosses.json) is looked for in a draft (by stem); a miss is a FLAG ("the draft does not render X as the engine would").
Against the reference, a flag is RIGHT when the reference does render the word as the engine does (the draft is wrong) and
WRONG when the reference does not either (the engine's choice is the odd one). Precision of the flags = how far a checker
built from the engine can be trusted on a draft; its recall = the share of the draft's real misses (reference word missing
from the draft) that it flags.

    . ./env.sh; OT_DB=data/dfb_base.db FUNC_FILE=data/dan_func.txt ~/sil-study/.venv/bin/python lab/bridge/check_draft.py
        --glosses bridge/dev_e5_dan_ot.glosses.json --draft bridge/llm/dev/alone/run1 [--split dev] [--min-how ctx0]"""
import argparse, collections, glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score as S  # noqa: E402
from score import tokenize  # noqa: E402
E = S.E


def main(a):
    C, FUNC = S.corpus(); stem = S.STEMS[a.stem]
    gl = json.load(open(os.path.join(E.PRIV, a.glosses), encoding="utf-8"))
    hyps = {}
    for f in glob.glob(os.path.join(E.PRIV, a.draft, "*.json")):
        hyps.update(json.load(open(f, encoding="utf-8")))
    refs = sorted(r for r, v in C.verses.items() if v["split"] == a.split and r in hyps and r in gl)
    n = collections.Counter(); by_how = collections.defaultdict(collections.Counter); by_freq = collections.defaultdict(collections.Counter)
    lf = collections.Counter(t["lemma"] for r0 in C.split("train") for t in C.tok[r0])   # lemma frequency in this corpus's training split
    bucket = lambda k: "<5" if k < 5 else "5-49" if k < 50 else "50-499" if k < 500 else ">=500"
    for r in refs:
        hs = {stem(w.lower()) for w in tokenize(hyps[r])}; rs = {stem(w.lower()) for w in C.verses[r]["words"]}
        toks = {t["text"]: t for t in C.tok[r]}
        for heb, d, how in gl[r]:
            ds = [stem(w.lower()) for w in d.split() if w.lower() not in FUNC and not w.startswith("<")]
            if not ds:
                continue
            n["words with an engine rendering"] += 1
            in_ref = any(s in rs for s in ds); in_hyp = any(s in hs for s in ds)
            # the reference's own rendering of this Hebrew word (its linked positions), to count the draft's real misses
            t = toks.get(heb)
            ref_words = [stem(w.lower()) for w in ((C.rendering(r, t) or []) if t else [])]
            ref_words = [w for w in ref_words if w not in FUNC]
            real_miss = bool(ref_words) and not any(w in hs for w in ref_words)
            fb = bucket(lf[t["lemma"]]) if t else "?"
            if not in_hyp:
                n["flags"] += 1; by_how[how]["flags"] += 1; by_freq[fb]["flags"] += 1
                if in_ref:
                    n["flags right (reference has the engine's word, the draft not)"] += 1; by_how[how]["right"] += 1; by_freq[fb]["right"] += 1
                if real_miss:
                    n["flags on a real miss"] += 1
            if real_miss:
                n["real misses (reference's word absent from the draft)"] += 1
            if in_hyp and not in_ref:
                n["agreed by engine and draft, not the reference"] += 1
    out = dict(n)
    out["flag precision (right / flags)"] = round(n["flags right (reference has the engine's word, the draft not)"] / max(1, n["flags"]), 3)
    out["flag precision (real miss / flags)"] = round(n["flags on a real miss"] / max(1, n["flags"]), 3)
    out["flag recall (flagged real misses / real misses)"] = round(n["flags on a real miss"] / max(1, n["real misses (reference's word absent from the draft)"]), 3)
    out["by how"] = {h: dict(c, precision=round(c["right"] / max(1, c["flags"]), 3)) for h, c in sorted(by_how.items())}
    out["by lemma frequency (train)"] = {h: dict(c, precision=round(c["right"] / max(1, c["flags"]), 3)) for h, c in sorted(by_freq.items())}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--glosses", required=True); ap.add_argument("--draft", required=True); ap.add_argument("--split", default="dev")
    ap.add_argument("--stem", default="dan")
    main(ap.parse_args())
