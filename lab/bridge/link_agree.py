#!/usr/bin/env python3
"""Agreement of two alignment layers of the same book and text (compact main files, 'srcOrd:span ...' per spine verse): links as
(source key, target token) pairs; precision / recall of layer A against layer B (B = the reference, e.g. a published Jev layer),
for content and function source words. A parts-view layer (units = word parts) is folded to tokens with its view's _units.json
(--units-a / --units-b) before comparing. Same text fingerprint required (both file names carry it).

    . ./env.sh; /usr/bin/python3 lab/bridge/link_agree.py --book RUT --a DIR_A/RUT_fp.json --b DIR_B/RUT_fp.json [--units-a VIEW/_units.json]"""
import argparse, collections, json, os, sys
sys.path.insert(0, os.path.join(os.environ["MAKE_TANAKH_WORK"], "scripts"))
import full_align as FA  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_kvg_nt import parse  # noqa: E402


def links(path, book, units=None):
    """{(kind, key, token)} over the book; kind c/f from the main (c) and the meta fn channel (f)."""
    main = json.load(open(path, encoding="utf-8")); meta_p = path[:-5] + ".meta.json"
    meta = json.load(open(meta_p, encoding="utf-8")) if os.path.exists(meta_p) else {}
    fn = meta.get("fn") or [""] * len(main)
    refs = list(FA.index(book, "lexemes")); keys = FA.index(book, "keys"); fkeys = FA.index(book, "fn_keys")
    umap = json.load(open(units, encoding="utf-8")).get(book, {}) if units else None
    out = set()
    for i, r in enumerate(refs):
        cv = r.split(" ")[1]
        fold = (lambda p: umap[cv][p][0] if umap is not None and cv in umap and p < len(umap[cv]) else p)
        for kind, s, ks in (("c", main[i] if i < len(main) else "", keys.get(r, [])), ("f", fn[i] if i < len(fn) else "", fkeys.get(r, []))):
            for o, ps in parse(s).items():
                k = ks[o] if o < len(ks) else None
                if k:
                    for p in ps:
                        out.add((kind, r, k.split("+")[0].lstrip("n"), fold(p)))
    return out


def main(a):
    A = links(a.a, a.book, a.units_a); B = links(a.b, a.book, a.units_b)
    fa = os.path.basename(a.a).split("_")[1][:8]; fb = os.path.basename(a.b).split("_")[1][:8]
    print(f"{a.book}: A {len(A)} links, B {len(B)} links; fingerprints {fa} / {fb}{'' if fa == fb else '  (DIFFERENT TEXT)'}")
    print("| words | A links | B links | precision (A in B) | recall (B in A) |\n|---|---|---|---|---|")
    for kind, name in (("c", "content"), ("f", "function"), (None, "all")):
        sa = {x for x in A if kind is None or x[0] == kind}; sb = {x for x in B if kind is None or x[0] == kind}
        inter = len(sa & sb)
        print(f"| {name} | {len(sa)} | {len(sb)} | {inter / max(1, len(sa)):.3f} | {inter / max(1, len(sb)):.3f} |")
    # source words linked at all (by key), regardless of the token
    ka = {(x[0], x[1], x[2]) for x in A}; kb = {(x[0], x[1], x[2]) for x in B}
    print(f"source words linked: A {len(ka)}, B {len(kb)}, both {len(ka & kb)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True); ap.add_argument("--a", required=True); ap.add_argument("--b", required=True)
    ap.add_argument("--units-a"); ap.add_argument("--units-b")
    main(ap.parse_args())
