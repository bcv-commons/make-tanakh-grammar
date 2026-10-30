#!/usr/bin/env python3
"""An NLLB run's test predictions (train_nllb.py: <model dir>/test.pred, one line per verse of <data>/test.vref, spine refs)
scored with the common scorer on a corpus (OT_DB, FUNC_FILE), per split, and saved as {BSB ref: text} for the bootstraps.

    . ./env.sh; OT_DB=data/dfb_base.db FUNC_FILE=data/dan_func.txt ~/sil-study/.venv/bin/python lab/bridge/score_nllb.py
        --data nllb/dfb_cons --model ~/models/nllb-finetuned/heb-dan-dfb --out bridge/nllb_dfb.json [--split test dev]"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score as S  # noqa: E402
sys.path.insert(0, os.path.join(S.E.R, "scripts"))
import vrs  # noqa: E402


def main(a):
    C, FUNC = S.corpus()
    vref = open(os.path.join(S.E.PRIV, a.data, "test.vref"), encoding="utf-8").read().rstrip("\n").split("\n")
    pred = open(os.path.join(os.path.expanduser(a.model), "test.pred"), encoding="utf-8").read().rstrip("\n").split("\n")
    assert len(vref) == len(pred), (len(vref), len(pred))
    hyps = {}
    for r, p in zip(vref, pred):
        book, cv = r.split(); ch, v = (int(x) for x in cv.split(":"))
        e = vrs.to_bsb(book.lower(), ch, v)
        if e and e[1] != "title":
            hyps[f"{book} {int(e[0])}:{int(e[1])}"] = p
    out = os.path.join(S.E.PRIV, a.out); os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(hyps, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    for split in a.split:
        refs = sorted(r for r, v in C.verses.items() if v["split"] == split and r in hyps)
        print(split, json.dumps(S.score(C, hyps, FUNC, S.STEMS[a.stem], refs), ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--model", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--split", nargs="*", default=["test", "dev"]); ap.add_argument("--stem", default="dan")
    main(ap.parse_args())
