#!/usr/bin/env python3
"""The word alignment of a bundle's drafts to the Hebrew (the `.align` sidecar of the chapter format), made by lexeme-aligner,
the same tool and the same two passes as the first stage (onboard/align.py), on this machine.

A draft chapter is too short to align on its own: the statistical aligner learns from the whole text. So every kind of draft
(main and each alternative) gets one run whose text is the team's own text with the drafted chapters put in: a chapter the
team has translated is replaced by the draft, a chapter it has not is added. Chapters that are closed or held out
(shared/holdout.py) and books the language's corpora leave out are not in the run's text. The run
  words   align-text on the written words (and the text as USJ)
  split   the text divided by the language's segmenter bundle
  view    the parts view, every divided word written as its parts (units.json: which token and part each unit is)
  parts   align-text again on the parts view; with --jev the paid Jev pass on the drafted books only, up to --max-usd
and the drafted chapters' links are read back from the newest layer: the parts' positions become the draft's tokens (the
standard tokeniser, as .units counts them), content words into the main field, function words (the Jev layer has them)
into the fn field. Profile `a` (the aligner's chain) or `j` (the Jev layer).

    . ./env.sh
    python3 publish/align.py --lang kvg --bundle private/publish/kvg/bundle            # every kind of draft in the bundle
    python3 publish/align.py --lang kvg --bundle ... --jev [--max-usd 2]                # Jev: estimate only without --max-usd

publish/bundle.py calls it after writing the drafts. Runs go to $MAKE_TANAKH_PRIVATE/publish/<code>/align/<bundle>/<kind>/
and are reused while the run's text is the same (its sha256). The team's text never leaves the box, except to Jev with
--jev, after the rights table is asked (shared/rights.py)."""
import argparse, collections, glob, hashlib, json, os, re, shutil, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import holdout, paths, pins  # noqa: E402
from onboard import align as OA  # noqa: E402
from publish import chapter_format as CF  # noqa: E402
import full_align as FA  # noqa: E402

ALT = os.path.join(".tanakh", "alternatives")


def kinds(bundle):
    """{kind: {(book, chapter): .md path}} of a bundle: "main" from the book folders, the alternatives from their folders"""
    out = collections.defaultdict(dict)
    for p in glob.glob(os.path.join(bundle, "[A-Z0-9][A-Z0-9][A-Z0-9]", "*_[0-9][0-9][0-9].md")):
        b, c = os.path.basename(p)[:-3].split("_"); out["main"][(b, int(c))] = p
    for p in glob.glob(os.path.join(bundle, ALT, "*", "[A-Z0-9][A-Z0-9][A-Z0-9]", "*_[0-9][0-9][0-9].md")):
        b, c = os.path.basename(p)[:-3].split("_"); out[p.split(os.sep)[-3]][(b, int(c))] = p
    return dict(out)


def team_text(lang, cfg):
    """the team's text as one `c:v text` file per book (the first stage's text step; the Tanakh in the Hebrew numbering)"""
    src = paths.resolve(lang, cfg["text"]["path"]); d = OA.adir(lang, "text")
    if glob.glob(os.path.join(d, "*.txt")):
        return d
    if glob.glob(os.path.join(src, "*[0-9][0-9][0-9].txt")):
        OA.export_chapters(src, d, cfg["text"].get("numbering", "english")); return d
    if glob.glob(os.path.join(src, "[0-9A-Z][A-Z0-9][A-Z0-9].txt")) and cfg["text"].get("numbering") == "hebrew":
        return src
    sys.exit(f"{lang}: the team's text must be the toolkit's chapter files or `c:v text` book files in the Hebrew numbering")


def run_text(lang, cfg, drafts, out):
    """the team's text with the drafted chapters in, written to out/ -> its sha256"""
    shut = holdout.shut(cfg); excl = {b for c in cfg.get("corpora", []) for b in c.get("exclude_books") or []}
    books = collections.defaultdict(list); h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(team_text(lang, cfg), "*.txt"))):
        b = os.path.basename(f)[:-4][-3:]
        if b in excl:
            continue
        for l in open(f, encoding="utf-8"):
            m = re.match(r"(\d+):(\d+) ", l)
            if m and not shut(b, int(m.group(1))) and (b, int(m.group(1))) not in drafts:
                books[b].append((int(m.group(1)), int(m.group(2)), l.rstrip("\n")))
    for (b, c), p in drafts.items():
        for v, t in CF.read_md(p)[4].items():
            if t.strip():
                books[b].append((c, int(v), f"{c}:{v} {t}"))
    os.makedirs(out, exist_ok=True)
    for b, rows in sorted(books.items()):
        rows.sort(); txt = "\n".join(r[2] for r in rows) + "\n"; h.update(b.encode() + txt.encode("utf-8"))
        open(os.path.join(out, f"{b}.txt"), "w", encoding="utf-8").write(txt)
    return h.hexdigest()


def chain(lang, cfg, work, edition, log, jev_books=None, max_usd=None):
    """the four steps in work/ -> the newest layer's folder"""
    L = OA.aligner(); exe = os.path.join(L, ".venv", "bin", "lexeme-aligner"); code = cfg.get("code", cfg["iso"])
    common = ["--iso", code, "--lang-name", cfg["name"], "--data", paths.aligner_data()]
    w = lambda *p: os.path.join(work, *p)
    if not OA.finished(w("out_words")):
        shutil.rmtree(w("out_words"), ignore_errors=True)
        OA.run([exe, "align-text", "--text", w("text"), "--edition", edition, "--out", w("out_words")] + common, log)
    usj = w("out_words", "text-usj")
    if not os.path.exists(w("split", "_split.json")):
        OA.split_step(L, paths.resolve(lang, cfg["segmenter"]), w("split"), edition, usj, "CC0-1.0 (machine drafts) with the team's text", log)
    if not os.path.exists(w("units.json")):
        OA.view_step(L, usj, w("view"), w("split", "words.parquet"), w("units.json"), log)
    jev = glob.glob(w("out_parts", "full-alignments-llm", "*", code, f"{edition}-m+llm+jev-*"))
    if not OA.finished(w("out_parts")) or (jev_books and not jev):
        cmd = [exe, "align-text", "--usj", w("view"), "--edition", edition + "-m", "--out", w("out_parts"), "--force"] + common; env = None
        if jev_books:
            env = OA.jev_env(cfg); cmd += ["--jev", "--books", ",".join(sorted(jev_books))] + (["--max-usd", str(max_usd)] if max_usd else [])
        OA.run(cmd, log, env=env)
        if jev_books:
            j = json.load(open(w("out_parts", "align-text-run.json"), encoding="utf-8")).get("jev") or {}
            print(f"  Jev: {j.get('requests_to_send')} requests, about ${j.get('estimate_usd_high_side')} (high side); "
                  + (f"sent up to ${max_usd}" if max_usd else "nothing sent: give --max-usd to run the pass"), flush=True)
    jev = glob.glob(w("out_parts", "full-alignments-llm", "*", code, f"{edition}-m+llm+jev-*"))
    base = glob.glob(w("out_parts", "compact", "*", code, f"{edition}-m"))
    return sorted(jev)[-1] if jev else base[0] if base else None


def read_layer(layer, units, book, ch, verses):
    """{verse: (main, fn)} for one drafted chapter: the layer's view positions turned into the draft's token positions"""
    f = [p for p in glob.glob(os.path.join(layer, f"{book}_*.json")) if os.path.basename(p).count(".") == 1]
    if not f:
        return {}
    main_s = json.load(open(f[0], encoding="utf-8")); meta = json.load(open(f[0][:-5] + ".meta.json", encoding="utf-8"))
    fn_s = meta.get("fn") or [""] * len(main_s); refs = {r: i for i, r in enumerate(FA.index(book, "lexemes"))}; out = {}
    from onboard.corpus import parse
    for v, text in verses.items():
        r = f"{book} {ch}:{v}"; i = refs.get(r); un = (units.get(book) or {}).get(f"{ch}:{v}")
        if i is None or un is None:
            continue
        n = len(FA.tokenize(text)); res = []
        if un and max(t for t, _ in un) + 1 != n:              # the aligner tokenised the verse otherwise: no links rather than wrong ones
            out[v] = None; continue
        for s in (main_s[i] if i < len(main_s) else "", fn_s[i] if i < len(fn_s) else ""):
            d = {o: sorted({un[p][0] for p in ps if p < len(un) and un[p][0] < n}) for o, ps in parse(s).items()}
            res.append(" ".join(f"{o}:{FA.span(t)}" for o, t in sorted(d.items()) if t))
        out[v] = tuple(res)
    return out


def align_bundle(lang, bundle, jev=False, max_usd=None, only=None):
    """every kind of draft in the bundle aligned; .align written beside each .md -> {kind: (tokens, linked)}"""
    cfg = paths.config(lang); code = cfg.get("code", cfg["iso"]); res = {}
    for k in ("text", "segmenter"):
        if k not in cfg:
            sys.exit(f"{lang}: the configuration names no \"{k}\": the drafts are aligned with the team's text (onboard/align.py)")
    for kind, drafts in sorted(kinds(bundle).items()):
        if only and kind not in only:
            continue
        work = paths.private("publish", code, "align", os.path.basename(os.path.normpath(bundle)), kind); os.makedirs(work, exist_ok=True)
        tmp = os.path.join(work, "text.new"); shutil.rmtree(tmp, ignore_errors=True); sha = run_text(lang, cfg, drafts, tmp)
        rec_p = os.path.join(work, "run.json"); rec = json.load(open(rec_p)) if os.path.exists(rec_p) else {}
        if rec.get("text_sha256") != sha:                                      # another text: the run starts again
            for d in ("text", "out_words", "split", "view", "units.json", "out_parts"):
                p = os.path.join(work, d); shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.path.exists(p) and os.remove(p)
        else:
            shutil.rmtree(os.path.join(work, "text"), ignore_errors=True)
        os.replace(tmp, os.path.join(work, "text"))
        t0 = time.time(); print(f"{kind}: aligning {len(drafts)} chapters with the team's text ...", flush=True)
        layer = chain(lang, cfg, work, f"{code}_draft_{kind.replace('-', '_')}", os.path.join(work, "align.log"),
                      jev_books={b for b, _ in drafts} if jev else None, max_usd=max_usd)
        if not layer:
            sys.exit(f"{kind}: no layer written; see {os.path.join(work, 'align.log')}")
        profile = "j" if "+jev" in os.path.basename(layer) else "a"
        units = json.load(open(os.path.join(work, "units.json"), encoding="utf-8")); tok = lnk = 0; odd = []
        for (b, c), p in sorted(drafts.items()):
            verses = CF.read_md(p)[4]; got = read_layer(layer, units, b, c, verses); rows = []
            for v in sorted(verses, key=int):
                if got.get(v, ()) is None:
                    odd.append(f"{b} {c}:{v}")
                mn, fn = got.get(v) or ("", ""); rows.append((v, mn, fn, profile))
                tok += len(FA.tokenize(verses[v])); lnk += len({t for s in (mn, fn) for e in s.split() for t in FA.ids_of(e.partition(":")[2])})
            FA.write_chapter(p[:-3] + ".align", c, rows, sorted(verses.items(), key=lambda x: int(x[0])))
        res[kind] = (tok, lnk)
        json.dump({"text_sha256": sha, "layer": os.path.relpath(layer, work), "profile": profile, "aligner": pins.git_commit(OA.aligner()),
                   "chapters": [f"{b} {c}" for b, c in sorted(drafts)], "tokens": tok, "linked": lnk, "when": time.strftime("%Y-%m-%d %H:%M")},
                  open(rec_p, "w"), indent=1)
        if odd:
            print(f"{kind}: {len(odd)} verses left unlinked, the aligner's tokens differ from the draft's: {', '.join(odd[:5])}", flush=True)
        print(f"{kind}: {lnk / max(1, tok):.3f} of {tok} draft words linked ({'Jev layer' if profile == 'j' else 'base layer'}; {time.time() - t0:.0f} s)", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", required=True); ap.add_argument("--bundle", required=True)
    ap.add_argument("--kind", action="append", help="only these kinds (main, nllb, shape, ...)")
    ap.add_argument("--jev", action="store_true"); ap.add_argument("--max-usd", type=float)
    a = ap.parse_args(); align_bundle(a.lang, a.bundle, a.jev, a.max_usd, a.kind)


if __name__ == "__main__":
    main()
