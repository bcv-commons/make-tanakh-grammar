#!/usr/bin/env python3
"""An edition in the work repo's import/ (or a project's drafts) as align-text's plain-text input: one verse per line,
"1:1 text", a file per book, verses read by the toolkit's draft reader (full_align.draft_texts: headings, notes, quote marks
out) in the edition's own numbering; colometry marks ("//2") dropped.

    . ./env.sh; /usr/bin/python3 lab/align/export_edition.py TEXT_DIR OUTDIR RUT JON MRK PHM
    (TEXT_DIR relative to MAKE_TANAKH_WORK, e.g. import/CC0/dan/den-frie-bibel/text)"""
import glob, os, re, sys
R = os.environ["MAKE_TANAKH_WORK"]; sys.path.insert(0, os.path.join(R, "scripts"))
import full_align as FA  # noqa: E402


def main(src, out, books):
    os.makedirs(out, exist_ok=True)
    for b in books:
        lines = []
        for p in sorted(glob.glob(os.path.join(R, src, f"{b.lower()}[0-9][0-9][0-9].txt"))):
            ch = int(os.path.basename(p)[-7:-4])
            for v, t in FA.draft_texts(p):
                t = " ".join(re.sub(r"//\d*", " ", t).split())
                if t:
                    lines.append(f"{ch}:{v} {t}")
        open(os.path.join(out, f"{b}.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print(b, len(lines), "verses")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
