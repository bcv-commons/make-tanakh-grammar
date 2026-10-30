#!/usr/bin/env python3
"""NLLB fine-tuning data, Hebrew OT -> an edition's text (train_nllb.py's layout: train/val/test .src .trg .vref), from the
plain text given to align-text (export_edition.py: "c:v text" per line in the spine's numbering) and MACULA Hebrew
(orig/heb.sqlite tokens: text + after, one line per verse). The Hebrew is written pointed without accents (--form pointed,
the default) or consonantal (--form cons). Test = the books or chapters named; val = N random train verses; --extra adds
synthetic pairs ({spine ref: text} JSON files, the engine's renderings) to train only.

    . ./env.sh; /usr/bin/python3 lab/bridge/build_nllb_data.py --text TEXT_DIR --out DIR [--form pointed|cons]
        [--test RUT JON JDG:6 ...] [--exclude GEN:22 ...] [--val 250] [--extra FILE.json ...]"""
import argparse, glob, json, os, random, sqlite3, unicodedata
R = os.environ["MAKE_TANAKH_WORK"]
ACCENTS = {c for c in range(0x0591, 0x05B0)} | {0x05BD, 0x05BF, 0x05C0, 0x05C3, 0x05C4, 0x05C5, 0x05C6, 0x05F4}


def hebrew(form):
    """{spine ref: Hebrew verse text}"""
    h = sqlite3.connect(os.path.join(R, "orig/heb.sqlite")); out = {}
    for book, ch, v, text, after in h.execute("select book, ch, v, text, coalesce(after, '') from tokens order by key"):
        out[f"{book} {ch}:{v}"] = out.get(f"{book} {ch}:{v}", "") + text + after
    def norm(s):
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if ord(c) not in ACCENTS)
        if form == "cons":
            s = "".join(c for c in s if not unicodedata.combining(c))
        return " ".join(unicodedata.normalize("NFC", s).replace("־", " ־ ").split())
    return {r: norm(t) for r, t in out.items()}


def edition(text_dir):
    out = {}
    for f in glob.glob(os.path.join(text_dir, "*.txt")):
        book = os.path.basename(f)[:-4]
        for l in open(f, encoding="utf-8"):
            cv, _, t = l.rstrip("\n").partition(" ")
            if t.strip():
                out[f"{book} {cv}"] = " ".join(t.split())
    return out


def sel(ref, items):
    b, cv = ref.split(); ch = cv.split(":")[0]
    return b in items or f"{b}:{ch}" in items


def main(a):
    heb = hebrew(a.form); ed = edition(a.text)
    pairs = {r: (heb[r], t) for r, t in ed.items() if r in heb}
    test = sorted(r for r in pairs if sel(r, set(a.test)))
    pool = [r for r in pairs if r not in set(test) and not sel(r, set(a.exclude))]
    random.Random(111).shuffle(pool); va, tr = pool[:a.val], sorted(pool[a.val:])
    extra = []
    for f in a.extra:
        for r, t in json.load(open(f, encoding="utf-8")).items():
            if r in heb and r not in set(test) and r not in set(va) and not sel(r, set(a.exclude)) and t.strip():
                extra.append((r, heb[r], t))
    os.makedirs(a.out, exist_ok=True)
    for name, rows in (("train", [(r, *pairs[r]) for r in tr] + extra), ("val", [(r, *pairs[r]) for r in sorted(va)]), ("test", [(r, *pairs[r]) for r in test])):
        for ext, i in (("vref", 0), ("src", 1), ("trg", 2)):
            open(os.path.join(a.out, f"{name}.{ext}"), "w", encoding="utf-8").write("\n".join(x[i] for x in rows) + "\n")
        print(name, len(rows), f"(extra {len(extra)})" if name == "train" and extra else "")
    json.dump({"text": a.text, "form": a.form, "src_code": "heb_Hebr", "trg_code": "dan_Latn", "test": a.test, "exclude": a.exclude,
               "extra": a.extra, "val": a.val}, open(os.path.join(a.out, "meta.json"), "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True); ap.add_argument("--out", required=True); ap.add_argument("--form", default="pointed")
    ap.add_argument("--test", nargs="*", default=["RUT", "JON"]); ap.add_argument("--exclude", nargs="*", default=["GEN:22", "GEN:37", "GEN:44"])
    ap.add_argument("--val", type=int, default=250); ap.add_argument("--extra", nargs="*", default=[])
    main(ap.parse_args())
