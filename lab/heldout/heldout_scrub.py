#!/usr/bin/env python3
"""Remove a held-out chapter's human text from a project copy's wiki before a held-out test.

The wiki prose quotes the corpus, and the corpus held the chapters we later hold out (e.g. Kuni GEN 27). A test
copy must not show them. Leaks are the held-out chapter's word types and word 3-grams that occur nowhere else in
the corpus; every run of such tokens in wiki/**/*.md and profile/decisions.json is replaced by "[held out]". A second rule catches renderings
whose words occur elsewhere: in a line that cites the held-out chapter (GEN 27:4, or a bare 27:4), every run of
words that occur in the held-out chapter and are not English (the BSB's vocabulary) is replaced too. Store and packs are only reported
(packs are rebuilt per test; the store's evidence cites references, checked separately).

  heldout_scrub.py <project copy> <corpus text dir> <held-out file> [...] [--write]

Without --write it reports what it would change. Run it on the test copy, never on the store it was copied from. HELDOUT_BOOK_ONLY=1: a bare '1:4'
doesn't count as a citation (for a held-out book whose chapter numbers the other books' notes use too, e.g. Jonah 1-4).
"""
import os
import re
import sys
import unicodedata
from pathlib import Path

TOKEN = re.compile(r"[^\W\d_](?:[\ẁ-ͯ꞉ꞌ'ꞌ-]*[\ẁ-ͯ])?", re.UNICODE)


def norm(s):
    return unicodedata.normalize("NFC", s).lower()


def text_tokens(path):
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("!!") or re.match(r"^===.*===$", line):
            continue
        line = re.sub(r"^v\d+[a-z]?\s", "", line)
        out.append([norm(m.group()) for m in TOKEN.finditer(line)])
    return out


def grams(lines, n=3):
    g = set()
    for toks in lines:
        g.update(tuple(toks[i:i + n]) for i in range(len(toks) - n + 1))
    return g


def held_types(held):
    return {t for h in held for toks in text_tokens(Path(h)) for t in toks}


def leaks(corpus_dir, held):
    held = {Path(h).resolve() for h in held}
    rest_types, rest_grams, h_lines = set(), set(), []
    for f in sorted(Path(corpus_dir).glob("*.txt")):
        lines = text_tokens(f)
        if f.resolve() in held:
            h_lines += lines
        else:
            rest_types.update(t for toks in lines for t in toks)
            rest_grams |= grams(lines)
    types = {t for toks in h_lines for t in toks} - rest_types
    return types, grams(h_lines) - rest_grams


def scrub_line(line, types, tri):
    ms = list(TOKEN.finditer(line))
    toks = [norm(m.group()) for m in ms]
    hit = [t in types for t in toks]
    for i in range(len(toks) - 2):
        if tuple(toks[i:i + 3]) in tri:
            hit[i] = hit[i + 1] = hit[i + 2] = True
    if not any(hit):
        return line, 0
    out, pos, i, n = [], 0, 0, 0
    while i < len(ms):
        if not hit[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(ms) and hit[j + 1]:
            j += 1
        out.append(line[pos:ms[i].start()])
        out.append("[held out]")
        pos = ms[j].end()
        n += j - i + 1
        i = j + 1
    out.append(line[pos:])
    return "".join(out), n


def cites(line, book, ch):
    """True if the line cites the held-out chapter: 'GEN 27:4' or a bare '27:4' with no other book code before it."""
    for m in re.finditer(r"(?:\b([A-Z1-3]{3})\s)?\b%d:\d+" % ch, line):
        if m.group(1) == book or (m.group(1) is None and not os.environ.get("HELDOUT_BOOK_ONLY")):
            return True
    return False


def english(root):
    v = set()
    for f in Path(root).rglob("*"):
        if f.is_file():
            v.update(norm(m.group()) for m in TOKEN.finditer(f.read_text(encoding="utf-8", errors="replace")))
    return {t for t in v if t.isascii()}


def main(argv):
    write = "--write" in argv
    args = [a for a in argv if a != "--write"]
    if len(args) < 3:
        sys.exit(__doc__)
    proj, corpus, held = Path(args[0]), args[1], args[2:]
    types, tri = leaks(corpus, held)
    h_types = held_types(held)
    eng = english(Path(__file__).resolve().parents[2] / "reference" / "BSB")
    refs = []
    for h in held:
        m = re.match(r"([a-z1-3]{3})(\d{3})", Path(h).name)
        refs.append((m.group(1).upper(), int(m.group(2))))
    print(f"held-out-only: {len(types)} word types, {len(tri)} word 3-grams")
    total = 0
    targets = sorted((proj / "wiki").rglob("*.md")) + [f for f in [proj / "profile" / "decisions.json"] if f.exists()]
    for f in targets:
        src = f.read_text(encoding="utf-8").splitlines(keepends=True)
        new, n_file = [], 0
        for line in src:
            body = line.rstrip("\n")
            s, n = scrub_line(body, types, tri)
            if any(cites(s, b, c) for b, c in refs):
                s, n2 = scrub_line(s, h_types - eng, set())
                n += n2
            new.append(s + line[len(body):])
            if n:
                n_file += n
                print(f"  {f.relative_to(proj)}: {body.strip()[:90]!r} -> {n} tokens")
        if n_file:
            total += n_file
            if write:
                f.write_text("".join(new), encoding="utf-8")
    for sub in ("_learn/packs", "profile"):
        for f in sorted((proj / sub).rglob("*")):
            if f.is_file() and f.name != "decisions.json" and f.suffix in (".md", ".yaml", ".json", ".txt", ".tsv"):
                n = sum(scrub_line(l, types, tri)[1] for l in f.read_text(encoding="utf-8", errors="replace").splitlines())
                if n:
                    print(f"  report only, {f.relative_to(proj)}: {n} tokens")
    print(f"wiki/decisions tokens {'replaced' if write else 'to replace'}: {total}")


if __name__ == "__main__":
    main(sys.argv[1:])
