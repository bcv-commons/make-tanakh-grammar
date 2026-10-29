#!/usr/bin/env python3
"""The BSB as align-text's plain-text input (one verse per line, "1:1 text", a file per book), read as the lab's gold corpus
reads it (data/build.py bsb_verses: headings and footnotes out), so align-text's target tokens are the gold's.

    . ./env.sh; /usr/bin/python3 lab/align/export_bsb.py OUTDIR RUT JON MRK PHM"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.environ["MAKE_TANAKH_WORK"]
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "rules", "data"))
from build import bsb_verses  # noqa: E402


def main(out, books):
    os.makedirs(out, exist_ok=True)
    for b in books:
        lines, ch = [], 1
        while os.path.exists(os.path.join(R, "reference/BSB", f"{b.lower()}{ch:03d}.txt")):
            lines += [f"{ch}:{v} {' '.join(t.split())}" for v, t in sorted(bsb_verses(b, ch).items()) if t.strip()]
            ch += 1
        open(os.path.join(out, f"{b}.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print(b, ch - 1, "chapters", len(lines), "verses")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
