#!/usr/bin/env python3
"""Paired bootstrap of the LLM arms against the `alone` arm over several runs: run k of an arm is paired with run k of alone
(same verses), the unit resampled is the VERSE (all its runs go together, 1,000 resamples), the statistic the pooled score of
arm minus alone on the resampled verses. Prints mean difference, 95% interval and the share > 0 per arm and key.

    . ./env.sh; OT_DB=data/dfb_jev+dan.db FUNC_FILE=data/dan_func.txt ~/sil-study/.venv/bin/python lab/bridge/llm_boot.py
        --out bridge/llm2/test [--base alone] [--arms conf ret repair] [--n 1000]"""
import argparse, collections, glob, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score as S  # noqa: E402

KEYS = ("chrF (summary)", "word choice (content, stem)", "form (content, exact)", "function words R", "order tau (mean per verse)")


def runs(d):
    out = {}
    for rd in sorted(glob.glob(os.path.join(d, "run*"))):
        h = {}
        for f in glob.glob(os.path.join(rd, "*.json")):
            h.update(json.load(open(f, encoding="utf-8")))
        out[os.path.basename(rd)] = h
    return out


def main(a):
    C, FUNC = S.corpus(); stem = S.STEMS[a.stem]; P = S.E.PRIV
    base = runs(os.path.join(P, a.base_out or a.out, a.base))
    refs = sorted(r for r, v in C.verses.items() if v["split"] == a.split)
    if a.refs_from_base:                                  # only verses every base run drafted (a subset of the split, e.g. Kuni's 5 chapters)
        refs = [r for r in refs if all(r in h for h in base.values())]
    for arm in a.arms:
        arm_runs = runs(os.path.join(P, a.out, arm))
        ks = sorted(set(base) & set(arm_runs))
        if not ks:
            print(arm, "no common runs"); continue
        rng = random.Random(7); diffs = collections.defaultdict(list)
        pairs = [(base[k], arm_runs[k]) for k in ks]
        for _ in range(a.n):
            s = [rng.choice(refs) for _ in refs]
            # per-run scores on the same resampled verses, pooled by averaging over runs (each run sees the same verse sample)
            acc_a = collections.defaultdict(float); acc_b = collections.defaultdict(float)
            for hb, ha in pairs:
                ra = S.score(C, ha, FUNC, stem, s); rb = S.score(C, hb, FUNC, stem, s)
                for key in KEYS:
                    acc_a[key] += ra[key] / len(pairs); acc_b[key] += rb[key] / len(pairs)
            for key in KEYS:
                diffs[key].append(acc_a[key] - acc_b[key])
        print(f"{arm} vs {a.base} ({len(ks)} runs paired):")
        for key in KEYS:
            d = sorted(diffs[key]); m = sum(d) / len(d)
            print(f"  {key}: {m:+.3f} [{d[int(0.025 * len(d))]:+.3f}, {d[int(0.975 * len(d)) - 1]:+.3f}] share>0 {sum(x > 0 for x in d) / len(d):.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--base", default="alone"); ap.add_argument("--arms", nargs="*", default=["conf", "ret", "repair"])
    ap.add_argument("--split", default="test"); ap.add_argument("--stem", default="dan"); ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--base-out", default="", help="dir of the base arm's runs when not under --out"); ap.add_argument("--refs-from-base", action="store_true")
    ap.add_argument("--segmenter", default="", help="bcv_segment bundle for the stems")
    a = ap.parse_args()
    if a.segmenter:
        sys.path.insert(0, a.segmenter); import bcv_segment
        seg = bcv_segment.load(a.segmenter); cache = {}

        def sstem(w):
            if w not in cache:
                cache[w] = next((p["text"] for p in seg.split(w) if p["slot"] == "stem"), w)
            return cache[w]
        S.STEMS["seg"] = sstem; a.stem = "seg"
    main(a)
