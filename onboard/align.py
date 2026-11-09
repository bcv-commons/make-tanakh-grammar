#!/usr/bin/env python3
"""From a team's text to its aligned corpus: the alignment and segmentation steps of the first stage, as one command that
can be stopped and run again (a step whose output is there is not run twice).

    . ./env.sh
    python3 onboard/align.py run --lang xxx [--jev [--books GEN] --max-usd 5]     # every step, in order
    python3 onboard/align.py status --lang xxx
    python3 onboard/align.py published --lang xxx --text DIR --layer DIR [--layer DIR]
                                         # a published layer of the same wording: the token check of each of its verses

The language's configuration names the inputs:

    "code": "zin",                       # only where the language's folder is not named by its ISO 639-3 code
    "text": {"path": "$WORK/import/CC-BY-SA/zin/zin_wbt/text", "edition": "zin_wbt", "licence": "CC BY-SA 4.0"},     # "numbering": "hebrew"
    "segmenter": "$PRIVATE/aligner-data/language-analysis/zin/<version>/bundle",
    "corpora": [{"source": "grc", "db": "corpus/nt_parts.db", "key": "key"}]

Steps, each into $MAKE_TANAKH_PRIVATE/lang/<iso>/align/:
  text    the text as one file per book, one verse per line (`c:v text`, a bridged verse `c:v-w text`). The toolkit's
          chapter files are converted; anything else the aligner reads (USFM, USJ, a vref corpus, plain text) is handed
          over as it is
  words   lexeme-aligner align-text on the written words -> out_words/ (and the text as USJ)
  split   the text divided by the language's segmenter bundle -> split/ (onboard/split_export.py)
  view    the parts view: every divided word written as its parts -> view/ (and units.json: which token and part each unit is)
  parts   align-text again on the parts view -> out_parts/. With --jev the paid pass of TypeSafe's Jev runs on it, with your
          key and only up to --max-usd (without --max-usd it only estimates; nothing is sent)
  corpus  the corpus (onboard/corpus.py) from the split file and the newest parts layer (the Jev layer when there is one)

A published layer (full-alignments-llm, compact-alignments) of an edition with the team's wording can stand in for the
local one: `published` reads that edition's text (USFM, USJ, plain text), and writes beside each layer `_verses.json`, the
token check of every verse (a hash of the aligner's tokens). A corpus entry that names the layer and `"verses"` takes from
it only the verses whose tokens are the team's (onboard/corpus.py, onboard/lexicon.py); `run` leaves such an entry's layer
as it is. Kuni: the NT, Ruth and Jonah from the published Jev layers, Genesis 1-30 from the local run (--books GEN).

The aligner is lexeme-aligner at its pin (shared/pins.py), found through LEXEME_ALIGNER (its checkout, with its .venv);
it runs locally and writes only into the out folders. A protected text never leaves the box in these steps except to Jev,
and only with --jev: check the text's rights first (onboard/rights.py).

A New Testament gives the Greek-side corpus, books of the Tanakh the Hebrew-side one (corpus/tanakh_parts.db); a text with
both gives both. The toolkit's chapter files are taken in the common (English) numbering unless the configuration says
"numbering": "hebrew"; a text handed over as it is must have its Tanakh books in the Hebrew Bible's numbering."""
import argparse, glob, json, os, re, subprocess, sys, time, unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths, pins, rights  # noqa: E402
from source import tokens  # noqa: E402

STEPS = ("text", "words", "split", "view", "parts", "corpus")
HERE = os.path.dirname(os.path.abspath(__file__))


def aligner():
    d = os.environ.get("LEXEME_ALIGNER") or os.path.join(paths.env("BCV_COMMONS"), "lexeme-aligner")
    if not os.path.exists(os.path.join(d, ".venv", "bin", "lexeme-aligner")):
        sys.exit(f"lexeme-aligner is not set up under {d} (LEXEME_ALIGNER; tools/setup.py)")
    return d


def adir(lang, *p):
    return paths.lang_dir(lang, "align", *p)


def run(cmd, log, cwd=None, env=None):
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n$ {' '.join(cmd)}\n"); f.flush()
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=cwd, env=env)
    if r.returncode:
        sys.exit(f"step failed (exit {r.returncode}); see {log}")


def to_hebrew(book):
    """{(chapter, verse) of the common (English) numbering: (chapter, verse) of the Hebrew Bible's} for a book of the Tanakh.
    Of several Hebrew verses that share one verse the first is taken; a psalm's title has no verse of its own."""
    import full_align as FA, vrs
    out = {}
    for r in FA.index(book, "lexemes"):
        c, v = (int(n) for n in r.split(" ")[1].split(":")); e = vrs.to_bsb(book.lower(), c, v)
        if e and e[1] != "title":
            out.setdefault((int(e[0]), int(e[1])), (c, v))
    return out


# a major section heading (USFM \ms with its \mr range) that the toolkit's chapter files leave at the end of a verse:
# "... last sentence. Heading words 15:36–18:22"
MAJOR = re.compile(r"(?<=[.!?”’»\"\)])\s+[^.!?”’»\"\n{}]*?\s\d+:\d+[–-]\d+:\d+(?=\s|$)")


def export_chapters(src, out, numbering="english"):
    """the toolkit's chapter files (<book>NNN.txt with vN markers) -> one <BOOK>.txt per book, `c:v text`, NFC. A book of the
    Tanakh is written in the Hebrew Bible's numbering (the aligner and the corpus builder read it by the Hebrew verse)."""
    os.makedirs(out, exist_ok=True); n = 0; tanakh = set(tokens.books("hbo"))
    for book in sorted({os.path.basename(f)[:3].upper() for f in glob.glob(os.path.join(src, "*[0-9][0-9][0-9].txt"))}):
        lines = []; heb = to_hebrew(book) if book in tanakh and numbering != "hebrew" else None
        for f in sorted(glob.glob(os.path.join(src, f"{book.lower()}[0-9][0-9][0-9].txt"))):
            ch = int(os.path.basename(f)[3:6])
            body = "\n".join(l for l in open(f, encoding="utf-8") if not l.startswith(("!!<", "==", "#")))
            body = MAJOR.sub("", re.sub(r"\{[A-Z]:[^}]*\}", "", body)); ms = list(re.finditer(r"(?:^|(?<=\s))v(\d+)(?:-(\d+))?\s", body))
            for m, nxt in zip(ms, ms[1:] + [None]):
                t = " ".join(body[m.end():nxt.start() if nxt else None].split()); v1 = int(m.group(1)); v2 = int(m.group(2) or 0)
                c, v = heb.get((ch, v1), (None, None)) if heb is not None else (ch, v1)
                c2, w = (heb.get((ch, v2), (None, None)) if heb is not None else (ch, v2)) if v2 > v1 else (None, None)
                if t and c is not None:                                  # a bridged verse (v27-28) is written `c:v-w text`
                    lines.append(f"{c}:{v}{f'-{w}' if c2 == c and w > v else ''} {unicodedata.normalize('NFC', t)}")
        lines.sort(key=lambda l: tuple(int(x) for x in re.split(r"[:-]", l.split(" ", 1)[0])[:2]))
        open(os.path.join(out, f"{book}.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n"); n += len(lines)
    return n


def split_step(L, bundle, split, edition, usj, licence, log):
    """the text divided by the segmenter bundle (onboard/split_export.py, run by the aligner's Python)"""
    run([os.path.join(L, ".venv", "bin", "python"), "-I", os.path.join(HERE, "split_export.py"), bundle, split, edition, usj,
         f"segmenter bundle {os.path.relpath(bundle, paths.aligner_data()) if bundle.startswith(paths.aligner_data()) else os.path.basename(os.path.dirname(bundle))}, "
         f"run by make-tanakh-grammar onboard/split_export.py", licence], log, cwd=L)


def view_step(L, usj, view, words, units, log):
    """the parts view (every divided word written as its parts) and its unit map, kept outside the view"""
    code = ("from pathlib import Path; import sys; import lexeme_aligner.target_parts as tp\n"
            "m = tp.write_view(Path(sys.argv[1]), Path(sys.argv[2]), tp.load_parts(sys.argv[3]))\n"
            "print('view books', len(m), 'verses', sum(len(v) for v in m.values()))")
    run([os.path.join(L, ".venv", "bin", "python"), "-c", code, usj, view, words], log, cwd=os.path.join(L, "pipeline"))
    os.replace(os.path.join(view, "_units.json"), units)                 # the aligner reads every .json of the view as a book


def jev_env(cfg):
    """the environment for a Jev pass: the rights row asked first, the key read from the toolkit's work copy (never printed)"""
    rights.check(cfg, "jev"); env = dict(os.environ); kf = paths.work(".env")
    if os.path.exists(kf):
        for line in open(kf, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == "TYPESAFE_API_KEY" and v:
                env[k] = v.strip("'\"")
    return env


def finished(d):
    """an align-text out folder whose run record says it ended well"""
    p = os.path.join(d, "align-text-run.json")
    try:
        return json.load(open(p, encoding="utf-8")).get("ok") is True
    except (OSError, ValueError):
        return False


def state(lang, cfg):
    """{step: its output, when it is there}"""
    ed = cfg["text"]["edition"]; a = lambda *p: adir(lang, *p); x = paths.corpus(cfg, "grc") or paths.corpus(cfg, "hbo")
    done = {"text": a("text") if glob.glob(a("text", "*")) else None,
            "words": a("out_words") if finished(a("out_words")) else None,
            "split": a("split") if os.path.exists(a("split", "_split.json")) else None,
            "view": a("view") if os.path.exists(a("units.json")) else None,
            "parts": a("out_parts") if finished(a("out_parts")) else None,
            "corpus": x["_db"] if x and os.path.exists(x["_db"]) else None}
    code = cfg.get("code", cfg["iso"])
    jev = glob.glob(a("out_parts", "full-alignments-llm", "*", code, f"{ed}-m+llm+jev-*"))
    base = glob.glob(a("out_parts", "compact", "*", code, f"{ed}-m"))
    done["layer"] = (sorted(jev)[-1] if jev else base[0] if base else None); done["layers"] = sorted(jev)[-1:] + base[:1]
    return done


def layer_for(st, source):
    """the newest parts layer that holds a book of this source language: the Jev layer where the pass ran on it, else the base"""
    mine = set(tokens.books(source))
    for d in st["layers"]:
        if any(os.path.basename(f).split("_")[0] in mine for f in glob.glob(os.path.join(d, "*_*.json"))):
            return d
    return None


def cmd_status(a):
    cfg = paths.config(a.lang, built=False); st = state(a.lang, cfg)
    for s in STEPS:
        print(f"{s:7} {'done' if st[s] else 'to do':6} {st[s] or ''}")
    if st["layer"]:
        print("layer   " + ("Jev pass" if "+jev" in st["layer"] else "base run (no Jev pass)") + f"  {st['layer']}")


def cmd_run(a):
    cfg = paths.config(a.lang, built=False)
    for k in ("text", "segmenter"):
        if k not in cfg:
            sys.exit(f"{a.lang}: the configuration names no \"{k}\" (module docstring)")
    L = aligner(); exe = os.path.join(L, ".venv", "bin", "lexeme-aligner")
    ed = cfg["text"]["edition"]; src = paths.resolve(a.lang, cfg["text"]["path"]); bundle = paths.resolve(a.lang, cfg["segmenter"])
    data = paths.aligner_data(); os.makedirs(adir(a.lang), exist_ok=True); log = adir(a.lang, "align.log"); st = state(a.lang, cfg)
    code = cfg.get("code", cfg["iso"])                            # the ISO 639-3 code, where the folder's name is not it
    common = ["--iso", code, "--lang-name", cfg["name"], "--data", data]
    isos = json.load(open(os.path.join(data, "inputs.json"))).get("isos", []) if os.path.exists(os.path.join(data, "inputs.json")) else []
    if code not in isos:
        sys.exit(f"the aligner's inputs for '{code}' are not fetched: {exe} fetch-inputs --iso {code} --data {data}")
    rec = {"when": time.strftime("%Y-%m-%d %H:%M"), "aligner": pins.git_commit(L), "steps": []}
    if not st["text"]:
        if glob.glob(os.path.join(src, "*[0-9][0-9][0-9].txt")):
            n = export_chapters(src, adir(a.lang, "text"), cfg["text"].get("numbering", "english")); print(f"text: {n} verses", flush=True)
        else:
            names = {os.path.basename(f).split(".")[0][-3:].upper() for f in glob.glob(os.path.join(src, "*"))}
            if names & set(tokens.books("hbo")) and cfg["text"].get("numbering") != "hebrew":
                sys.exit("a text handed over as it is must have its Tanakh books in the Hebrew Bible's numbering "
                         "(\"text\": {\"numbering\": \"hebrew\"}); the toolkit's chapter files are converted here")
            os.symlink(src, adir(a.lang, "text")); print("text: handed over as it is")
        rec["steps"].append("text")
    if not st["words"]:
        run([exe, "align-text", "--text", adir(a.lang, "text"), "--edition", ed, "--out", adir(a.lang, "out_words")] + common, log)
        print("words: aligned", flush=True); rec["steps"].append("words")
    usj = adir(a.lang, "out_words", "text-usj")
    if not st["split"]:
        split_step(L, bundle, adir(a.lang, "split"), ed, usj, cfg["text"].get("licence", "not stated"), log)
        print("split: written", flush=True); rec["steps"].append("split")
    if not st["view"]:
        view_step(L, usj, adir(a.lang, "view"), adir(a.lang, "split", "words.parquet"), adir(a.lang, "units.json"), log)
        print("view: written", flush=True); rec["steps"].append("view")
    want_jev = a.jev and not (st["layer"] and "+jev" in st["layer"])
    if not st["parts"] or want_jev:
        cmd = [exe, "align-text", "--usj", adir(a.lang, "view"), "--edition", ed + "-m", "--out", adir(a.lang, "out_parts"), "--force"] + common
        env = dict(os.environ)
        if a.jev:
            env = jev_env(cfg); cmd += ["--jev"] + (["--max-usd", str(a.max_usd)] if a.max_usd else []) + (["--books", a.books] if a.books else [])
        run(cmd, log, env=env); rec["steps"].append("parts"); print("parts: aligned", flush=True)
        j = json.load(open(adir(a.lang, "out_parts", "align-text-run.json"), encoding="utf-8")).get("jev") or {}
        if a.jev and j:
            rec["jev"] = {k: v for k, v in j.items() if k != "per_book"}
            print(f"Jev: {j.get('requests_to_send')} requests, about ${j.get('estimate_usd_high_side')} (the aligner's estimate, high side); "
                  + (f"sent up to ${a.max_usd}" if a.max_usd else "nothing sent: give --max-usd to run the pass"), flush=True)
    st = state(a.lang, cfg)
    if not st["layer"]:
        sys.exit("no parts layer was written; see " + log)
    p = paths.lang_dir(a.lang, "config.json"); raw = json.load(open(p, encoding="utf-8")); built = []
    for source, db, key in (("grc", "corpus/nt_parts.db", "key"), ("hbo", "corpus/tanakh_parts.db", "word")):
        layer = layer_for(st, source)
        if not layer:
            continue                                                  # the text has no book of this testament
        c = next((c for c in raw.setdefault("corpora", []) if c["source"] == source), None)
        if c is None:
            c = {"source": source, "db": db, "key": key}; raw["corpora"].append(c)
        if c.get("verses"):                                           # a published layer stands in: only the split is ours
            c["split"] = "align/split"
        else:
            c.update(split="align/split", layer=os.path.relpath(layer, paths.lang_dir(a.lang)), units="align/units.json", view="align/view")
        built.append((source, paths.resolve(a.lang, c["layer"]) if c.get("verses") else layer))
    json.dump(raw, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False); c_pub = {c["source"]: c.get("verses") for c in raw["corpora"]}
    for source, layer in built:
        run([sys.executable, os.path.join(HERE, "corpus.py"), "build", "--lang", a.lang, "--source", source], log)
        print(f"corpus ({'the New Testament' if source == 'grc' else 'the Tanakh'}): built from "
              + (("the published layer " if c_pub.get(source) else "the Jev layer ") + os.path.basename(layer) if "+jev" in layer
                 else "the base layer (no Jev pass)"), flush=True)
    rec["steps"].append("corpus"); rec["layers"] = dict(built)
    hist = adir(a.lang, "runs.json"); h = json.load(open(hist)) if os.path.exists(hist) else []
    h.append(rec); json.dump(h, open(hist, "w"), indent=1); cmd_status(a)


def cmd_published(a):
    """the token check of every verse of a published layer's text, written beside each layer (_verses.json)"""
    cfg = paths.config(a.lang, built=False); L = aligner(); log = adir(a.lang, "align.log"); os.makedirs(adir(a.lang), exist_ok=True)
    code = ("import hashlib, json, sys, tempfile; from pathlib import Path\n"
            "from lexeme_aligner import text_input, usj_source; from lexeme_aligner.text_fingerprint import usj_verses\n"
            "out = {}\n"
            "with tempfile.TemporaryDirectory() as d:\n"
            "    d = Path(d); text_input.prepare(Path(sys.argv[1]), d)\n"
            "    for f in sorted(d.glob('*.json')):\n"
            "        b = f.stem.split('-', 1)[1]\n"
            "        for (c, v), t in usj_verses(f).items():\n"
            "            out[f'{b} {c}:{v}'] = hashlib.sha1(' '.join(usj_source.tokenize(t)).encode()).hexdigest()[:16]\n"
            "for p in sys.argv[2:]:\n"
            "    json.dump(out, open(Path(p) / '_verses.json', 'w'), indent=0)\n"
            "print('verses', len(out), 'books', len({k.split()[0] for k in out}))")
    run([os.path.join(L, ".venv", "bin", "python"), "-c", code, paths.resolve(a.lang, a.text)] + [paths.resolve(a.lang, x) for x in a.layer],
        log, cwd=os.path.join(L, "pipeline"))
    print("written:", ", ".join(os.path.join(x, "_verses.json") for x in a.layer))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("run", "status", "published")); ap.add_argument("--lang", required=True)
    ap.add_argument("--jev", action="store_true"); ap.add_argument("--max-usd", type=float)
    ap.add_argument("--books", help="with --jev: only these books (comma-separated)")
    ap.add_argument("--text", help="published: the published layer's text"); ap.add_argument("--layer", action="append", default=[])
    a = ap.parse_args(); {"run": cmd_run, "status": cmd_status, "published": cmd_published}[a.cmd](a)


if __name__ == "__main__":
    main()
