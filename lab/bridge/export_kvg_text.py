#!/usr/bin/env python3
"""The team's Kuni edition (the work repo's import/non-free/kvg/KVG-KuNT, repo chapter format) as align-text's plain-text input:
one BOOK.txt per book, 'c:v text' lines, headings, cross references and header lines left out, NFC. Protected text: the output
stays under $MAKE_TANAKH_PRIVATE and never leaves the box.

    . ./env.sh; /usr/bin/python3 lab/bridge/export_kvg_text.py --out private/align/kvg_all/text [--books GEN MAT ...]"""
import argparse, glob, os, re, unicodedata, sys
R = os.environ["MAKE_TANAKH_WORK"]; K = os.path.join(R, "import/non-free/kvg/KVG-KuNT/text")
# --src: another edition's text dir in the same chapter format (e.g. import/CC-BY-SA/zin/zin_wbt/text)


def main(a):
    os.makedirs(a.out, exist_ok=True); n = {}
    K = a.src or globals()["K"]
    chapters = sorted(glob.glob(os.path.join(K, "*[0-9][0-9][0-9].txt")))
    books = sorted({os.path.basename(f)[:3].upper() for f in chapters})
    for book in books:
        if a.books and book not in a.books:
            continue
        lines = []
        for f in sorted(glob.glob(os.path.join(K, f"{book.lower()}[0-9][0-9][0-9].txt"))):
            ch = int(os.path.basename(f)[3:6])
            body = "\n".join(l for l in open(f, encoding="utf-8") if not l.startswith(("!!<", "==", "#")))
            body = re.sub(r"\{[A-Z]:[^}]*\}", "", body)            # {H: ...} {T: ...} notes
            ms = list(re.finditer(r"(?:^|(?<=\s))v(\d+)\s", body))
            for m, nxt in zip(ms, ms[1:] + [None]):
                t = " ".join(body[m.end():nxt.start() if nxt else None].split())
                if t:
                    lines.append(f"{ch}:{int(m.group(1))} {unicodedata.normalize('NFC', t)}")
        open(os.path.join(a.out, f"{book}.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
        n[book] = len(lines)
    print(sum(n.values()), "verses;", " ".join(f"{b} {c}" for b, c in n.items()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--src", default=""); ap.add_argument("--books", nargs="*")
    main(ap.parse_args())
