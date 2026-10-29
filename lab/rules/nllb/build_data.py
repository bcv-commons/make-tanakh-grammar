#!/usr/bin/env python3
"""BSB NLLB as an instrument for the rules-engine lab (user 2026-10-26: not a drafter to score). Greek -> English on the
engine's own verses (scratch/rules/data/nt.db): source = the MACULA Greek tokens of the verse (text + after, monotonic, as
srcpivot did for ell_Grek), target = the BSB verse. Two pools as for the engine: nogospels (no MAT/LUK/JHN) and nt.
train = the engine's train verses of the pool minus 250 for validation; "test" = the engine's dev chapters (MRK 3, 9, 12).
The engine's test chapters (MRK 5, 10, 15) are left out entirely.
    /usr/bin/python3 build_data.py   -> ~/bsb-nllb/rules-en/<pool>/data/"""
import json, os, random, sqlite3, sys, unicodedata
R = os.environ["MAKE_TANAKH_WORK"]; LAB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
sys.path.insert(0, R + "/scripts"); sys.path.insert(0, LAB + "/data")
from build import bsb_verses  # noqa: E402
OUT = os.path.expanduser("~/bsb-nllb/rules-en")


def monotonic(s):
    out = []
    for ch in unicodedata.normalize("NFD", s):
        if ch in "̀͂́":
            ch = "́"
        elif unicodedata.combining(ch) and ch != "̈":
            continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


n = sqlite3.connect(PRIV + "/data/nt.db"); g = sqlite3.connect(R + "/orig/grc.sqlite")
verses = {r[0]: (r[1], r[2], r[3], r[4]) for r in n.execute("select ref, book, ch, v, split from verse")}
src = {}
for book, ch, v, text, after in g.execute("select book, ch, v, text, coalesce(after, '') from tokens order by key"):
    ref = f"{book} {ch}:{v}"
    if ref in verses:
        src[ref] = src.get(ref, "") + text + after + " "
cache = {}
def trg(ref):
    b, c, v, _ = verses[ref]
    if (b, c) not in cache:
        cache[(b, c)] = bsb_verses(b.lower(), c)
    return " ".join(cache[(b, c)][v].split())
for pool in ("nogospels", "nt"):
    tr = [r for r, x in verses.items() if x[3] == "train" and (pool == "nt" or x[0] not in {"MAT", "LUK", "JHN"})]
    dev = sorted((r for r, x in verses.items() if x[3] == "dev"), key=lambda r: (verses[r][1], verses[r][2]))
    random.Random(111).shuffle(tr); va, tr = tr[:250], tr[250:]
    d = f"{OUT}/{pool}/data"; os.makedirs(d, exist_ok=True)
    for name, refs in (("train", tr), ("val", va), ("test", dev)):
        rows = [(r, monotonic(" ".join(src[r].split())), trg(r)) for r in refs if src.get(r, "").strip()]
        for ext, i in (("vref", 0), ("src", 1), ("trg", 2)):
            open(f"{d}/{name}.{ext}", "w", encoding="utf-8").write("\n".join(x[i] for x in rows) + "\n")
        print(pool, name, len(rows))
    json.dump({"project": "rules-lab en BSB", "trg_code": "eng_Latn", "src_code": "ell_Grek", "test": ["MRK 3, 9, 12 (engine dev)"],
               "nt_only": True, "pool": pool, "note": "instrument for the rules-engine lab; engine test chapters MRK 5, 10, 15 excluded"},
              open(f"{d}/meta.json", "w"), indent=1)
