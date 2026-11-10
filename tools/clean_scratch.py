#!/usr/bin/env python3
"""The scratch folder (MAKE_TANAKH_PRIVATE/scratch): throwaway work, deleted when a check is done. This lists what is there,
and with --yes deletes it; it also names throwaway runs left outside it (a label tmp-* under runs/), which it does not touch.

    . ./env.sh; python3 tools/clean_scratch.py [--older DAYS] [--yes]"""
import argparse, glob, os, shutil, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths  # noqa: E402


def size(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs if not os.path.islink(os.path.join(d, f)))


def entries(root):
    """the scratch's items: a run folder (runs/<iso>/draft/<book>/<label>), else what a top-level folder holds"""
    out = []
    for top in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        p = os.path.join(root, top)
        if top == "runs" and os.path.isdir(p):
            runs = [r for r in glob.glob(os.path.join(p, "*", "*", "*", "*")) if os.path.isdir(r)]
            out += sorted(runs) or [p]
        elif os.path.isdir(p) and not os.path.islink(p) and os.listdir(p):
            out += sorted(os.path.join(p, x) for x in os.listdir(p))
        else:
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--older", type=float, default=0, help="only items not changed for this many days")
    ap.add_argument("--yes", action="store_true", help="delete the items listed")
    a = ap.parse_args(); root = paths.scratch(); now = time.time(); tot = 0
    items = [p for p in entries(root) if (now - os.path.getmtime(p)) / 86400 >= a.older]
    for p in items:
        n = size(p); tot += n
        print(f"{n / 1e6:9.1f} MB  {os.path.relpath(p, root)}")
    print(f"{len(items)} items, {tot / 1e6:.1f} MB in {root}" + ("" if a.yes else ("; --yes deletes them" if items else "")))
    stray = sorted(glob.glob(paths.private("runs", "*", "*", "*", paths.SCRATCH_PREFIX + "*")))
    for p in stray:
        print(f"outside the scratch (not touched): {os.path.relpath(p, paths.private())}")
    if a.yes:
        for p in items:
            shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
        print(f"deleted {len(items)} items")


if __name__ == "__main__":
    main()
