#!/usr/bin/env python3
"""The parity test: do the prompts built here equal the prompts measured in research, byte for byte?

Needs the research checkout and its private run folder (not part of the ordinary tests). For a dev set it rebuilds the evidence
in legacy mode over the verse set the research harness ranked together, builds every verse's prompt and compares it with the
research prompt of the arm (L13: no grammar notes; L135g: with them).

    . ./env.sh; PYTHONHASHSEED=0 python3 tests/parity.py --research ~/dev/make-tanakh-research --lang kvg --source hbo --arm L135g
    sets: zin grc (JHN 1-4), kvg grc (JHN 1-4), kvg hbo (GEN 2, 4, 6, 8)"""
import argparse, difflib, glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths  # noqa: E402
from drafting import evidence, prompt  # noqa: E402

SCOPE = {("zin", "grc"): "zin_jhn", ("kvg", "grc"): "kvg_jhn", ("kvg", "hbo"): "kvg_gen"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--research", required=True); ap.add_argument("--lang", required=True); ap.add_argument("--source", required=True, choices=paths.SOURCES)
    ap.add_argument("--arm", default="L13", choices=("L13", "L135g")); ap.add_argument("--show", type=int, default=3)
    a = ap.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit("run with PYTHONHASHSEED=0: the research harness broke ties in set order")
    cfg = paths.config(a.lang); dev = cfg["dev"][a.source]; scope = SCOPE[(a.lang, a.source)]
    rp = os.path.join(a.research, "private", "rules", "harmony")
    rk = json.load(open(os.path.join(rp, f"{a.lang}_{'nt' if a.source == 'grc' else 'ot'}", "evidence_c4p", "ranking_dev.json"), encoding="utf-8"))
    if a.source == "grc":                                   # the harness ranked every dev chapter's clauses together
        chs = {(q["tokens"][0]["key"][:2], int(q["tokens"][0]["key"][2:5])) for q in rk["queries"]}; books = {"43": "JHN"}
        verses, _, _ = evidence.read_corpus(cfg, "grc")
        qv = {r for r in verses if r.split()[0] == dev["book"] and ("43", int(r.split()[1].split(":")[0])) in chs}
    else:                                                   # ... and every Genesis verse with team text
        verses, _, _ = evidence.read_corpus(cfg, "hbo")
        qv = {r for r in verses if r.startswith(dev["book"] + " ")}
    E = evidence.build(cfg, a.source, dev["book"], dev["chapters"], dev.get("leave_out_books", ()), legacy=True, query_verses=qv)
    print("pool clauses", len(E.pool), "(research", rk["meta"]["pool clauses"], ") queries ranked", len(E.queries), "(research", len({q["id"] for q in rk["queries"]}), ") job clauses", len(E.order))
    B = prompt.Builder(cfg, E, dev["book"], dev["chapters"], notes=(a.arm == "L135g"))
    rd = os.path.join(rp, "free_c4p", scope, "prompts_" + a.arm); files = sorted(glob.glob(os.path.join(rd, "*.md")))
    same = diff = 0; seen = set(); bad = []
    for v, cl in B.groups().items():
        txt, refs = B.verse(cl); vid = v.replace(" ", "_").replace(":", "_"); seen.add(vid)
        f = os.path.join(rd, vid + ".md")
        if not os.path.exists(f):
            bad.append((vid, "no research prompt")); continue
        r = open(f, encoding="utf-8").read()
        if r == txt and json.load(open(f[:-3] + ".clauses.json")) == [q["id"] for q in cl]:
            same += 1
        else:
            diff += 1
            if len(bad) < a.show:
                d = [l for l in difflib.unified_diff(r.splitlines(), txt.splitlines(), "research", "here", lineterm="", n=0)]
                bad.append((vid, f"{sum(1 for l in d if l[:1] in '+-' and l[:3] not in ('+++', '---'))} changed lines; first: " + " || ".join(x[:150] for x in d[2:6])))
    missing = sorted({os.path.basename(f)[:-3] for f in files} - seen)
    print(f"{scope} {a.arm}: research prompts {len(files)}, built here {len(seen)}, identical {same}, different {diff}, not built here {len(missing)}")
    for x in bad:
        print("  ", x[0], "|", x[1])
    sys.exit(0 if not diff and not missing and same == len(files) else 1)


if __name__ == "__main__":
    main()
