#!/usr/bin/env python3
"""The KJV text (helloAO eng_kjv = eBible eng-kjv2006, public domain outside the UK) as rows [(c, v, text)] per book, in its
own numbering, and the check against the alignment layers' fingerprints (compact-alignments' text fingerprint v1).
    /usr/bin/python3 lab/rules/kjv/text.py check"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.environ["MAKE_TANAKH_WORK"]
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
sys.path.insert(0, os.path.join(R, "scripts"))
DL = os.path.join(PRIV, "data/kjv/dl")
_B = {}


def books():
    if not _B:
        for b in json.load(open(os.path.join(DL, "eng_kjv_complete.json"), encoding="utf-8"))["books"]:
            _B[b["id"]] = b
    return _B


def rows(code):
    out = []
    for ch in books()[code]["chapters"]:
        c = ch["chapter"]
        for b in c["content"]:
            if b.get("type") == "verse":
                t = " ".join(x if isinstance(x, str) else x.get("text", "") for x in b["content"] if isinstance(x, str) or "text" in x)
                out.append((c["number"], b["number"], t))
    return out


if __name__ == "__main__":
    import full_align as FA
    for code, want in (("RUT", "40e9e45a"), ("GEN", "0f9ba2b3"), ("PSA", "214c94be"), ("PHM", "014fd5a6"), ("MRK", "46d73247")):
        fp = FA.text_fingerprint(rows(code))[0][:8]
        print(code, fp, want, fp == want)
