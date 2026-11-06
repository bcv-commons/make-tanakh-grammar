#!/usr/bin/env python3
"""The first stage of a language, step by step: what is done, what is open, and whether the language is ready to draft.

    . ./env.sh
    python3 onboard/ladder.py status --lang xxx       # the ladder
    python3 onboard/ladder.py dev    --lang xxx       # the dev check's commands for this language, then its figures
    python3 onboard/ladder.py ready  --lang xxx       # writes the "ready to draft" record when nothing blocks

The ladder (docs: README, "The first stage"):

  A  identity and rights   the configuration: name, ISO code, the text's licence, what may be sent where (shared/rights.py)
  B  text                  the team's text, one verse per line, every verse placed against the source (onboard/align.py: text)
  C  the knife             the segmenter and its cut of the text (split), the alignment by words and by parts, the corpus
                           (onboard/align.py, onboard/corpus.py); the corpus's figures say how sharp the cut is
  G  grammar notes         pages written from the corpus (onboard/notes.py) and, better, the team's own answers; optional
  E  splits and dev check  held-out chapters written down; the drafter run on the dev chapters the team has translated,
                           scored against the team's text (drafting/devcheck.py), with and without the notes

Ready to draft = A, B, C done and the dev check run. The record ($MAKE_TANAKH_PRIVATE/lang/<iso>/ready.json) holds the
figures and what they were made with."""
import argparse, glob, json, os, sqlite3, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import holdout, paths, pins, rights  # noqa: E402
from onboard import align  # noqa: E402


def corpus_figures(x):
    z = sqlite3.connect(x["_db"]); m = dict(z.execute("select name, value from meta"))
    n = z.execute("select count(*) from verse where wordidx is not null").fetchone()[0]; l = z.execute("select count(*) from link").fetchone()[0]
    out = {"verses": n, "source words linked": l}
    for k in ("parts", "words", "layer"):
        if k in m:
            out[k] = m[k].strip('"')
    return out


def dev_runs(lang, cfg):
    """per source language with a dev set: the runs under the dev book and how far each is"""
    out = {}
    for src, d in (cfg.get("dev") or {}).items():
        runs = {}
        for rd in sorted(glob.glob(paths.run_dir(lang, "draft", d["book"], "*", make=False))):
            n = len(glob.glob(os.path.join(rd, "prompts", "*.md"))) or len(json.load(open(os.path.join(rd, "groups.json")))) if os.path.exists(os.path.join(rd, "groups.json")) or glob.glob(os.path.join(rd, "prompts", "*.md")) else 0
            runs[os.path.basename(rd)] = (len(glob.glob(os.path.join(rd, "answers", "*.json"))), n)
        out[src] = (d, runs)
    return out


def ladder(lang):
    cfg = paths.config(lang, built=False); rows = []; blocks = []
    r = cfg.get("rights") or {}
    ok = bool(r.get("licence")) and "llm" in r
    rows.append(("A", "identity and rights", ok, f"{cfg['name']} ({cfg.get('code', cfg['iso'])}); licence: {r.get('licence', 'not stated')}; "
                 f"to the model: {'yes' if rights.allowed(cfg, 'llm') else 'no'}; to Jev: {'yes' if rights.allowed(cfg, 'jev') else 'no'}"))
    if not ok:
        blocks.append("A: the rights table (\"rights\": licence, llm, jev)")
    elif not rights.allowed(cfg, "llm"):
        blocks.append("A: the text may not be shown to the drafting model, so nothing can be drafted from it")
    st = align.state(lang, cfg) if "text" in cfg else {}
    x = paths.corpus(cfg, "grc"); have = bool(x and os.path.exists(x["_db"]))
    if "text" in cfg:
        rows.append(("B", "text", bool(st.get("text")), st.get("text") or "onboard/align.py run"))
        for s in ("words", "split", "view", "parts"):
            rows.append(("C", s, bool(st.get(s)), st.get(s) or "onboard/align.py run"))
        if st.get("layer"):
            rows.append(("C", "layer", True, ("Jev pass" if "+jev" in st["layer"] else "base run; the Jev pass (onboard/align.py run --jev --max-usd N) links far more words")))
    else:
        rows.append(("B", "text", have, "the corpus was built elsewhere (no \"text\" in the configuration)" if have else "name the text in the configuration"))
    fig = corpus_figures(x) if have else {}
    rows.append(("C", "corpus", have, (json.dumps(fig) + ("; a small text: nothing was measured below a whole New Testament" if fig["verses"] < 5000 else ""))
                 if have else "onboard/align.py run"))
    if not have:
        blocks.append("C: the corpus")
    hbo = paths.corpus(cfg, "hbo")
    rows.append(("C", "Tanakh text", None, "the team's own Tanakh text is in the pool: " + json.dumps(corpus_figures(hbo)) if hbo and os.path.exists(hbo["_db"]) else
                 "none: Tanakh chapters are drafted from the team's New Testament through the Hebrew-Greek bridges"))
    n = cfg.get("notes")
    pages = glob.glob(paths.lang_dir(lang, "notes", "grammar", "*.md"))
    rows.append(("G", "grammar notes", None, (f"{len(n['pages'])} pages shown to the drafter" if n else f"{len(pages)} pages written, not shown to the drafter"
                                               if pages else "none (optional: onboard/notes.py)")))
    shut = holdout.shut(cfg)
    rows.append(("E", "held-out chapters", True, f"{len(shut.chapters)} chapters and {len(shut.books)} books are never read"
                 + (" (the research closed list applies)" if cfg.get("closed_list") else "")))
    dv = dev_runs(lang, cfg) if have else {}
    if not cfg.get("dev"):
        rows.append(("E", "dev check", False, "name dev chapters the team has translated (\"dev\" in the configuration)")); blocks.append("E: the dev set")
    for src, (d, runs) in dv.items():
        full = [k for k, (a_, n_) in runs.items() if n_ and a_ >= n_]
        rows.append(("E", f"dev check ({d['book']} {d['chapters']})", bool(full), ", ".join(f"{k}: {a_}/{n_}" for k, (a_, n_) in runs.items()) or "not run: ladder.py dev"))
        if not full:
            blocks.append(f"E: the dev check on {d['book']}")
    return cfg, rows, blocks, dv


def cmd_status(a):
    cfg, rows, blocks, _ = ladder(a.lang)
    for step, name, ok, what in rows:
        print(f"{step}  {name:28} {'done ' if ok else '     ' if ok is None else 'OPEN '} {what}")
    print("\nready to draft" if not blocks else "\nnot ready; open: " + "; ".join(blocks))


def cmd_dev(a):
    cfg, rows, blocks, dv = ladder(a.lang); from drafting import devcheck
    for src, (d, runs) in dv.items():
        ch = ",".join(str(c) for c in d["chapters"]); lo = ",".join(d.get("leave_out_books", []))
        print(f"# the dev check on {d['book']} {ch}" + (f" (pool without {lo})" if lo else ""))
        print(f"python3 drafting/draft.py build --lang {a.lang} --book {d['book']} --chapters {ch} --label dev" + (f" --leave-out {lo}" if lo else ""))
        print(f"python3 drafting/draft.py send  --lang {a.lang} --book {d['book']} --label dev")
        full = [k for k, (a_, n_) in runs.items() if n_ and a_ >= n_ and k.startswith("dev")]
        if full:
            res = devcheck.check(a.lang, d["book"], sorted(full, key=lambda k: (k != "dev", k)))
            print(json.dumps(res, indent=1, ensure_ascii=False) if res else "no verse with both a draft and the team's text")


def cmd_ready(a):
    cfg, rows, blocks, dv = ladder(a.lang); from drafting import devcheck, draft
    if blocks:
        sys.exit("not ready; open: " + "; ".join(blocks))
    rec = {"language": cfg["name"], "iso": cfg.get("code", cfg["iso"]), "when": time.strftime("%Y-%m-%d %H:%M"), "code": draft.commit(),
           "pins": {k: v.get("tag") or v.get("revision") or v.get("model") for k, v in pins.PINS.items()},
           "ladder": [{"step": s, "name": n, "done": ok, "what": w} for s, n, ok, w in rows], "dev": {}}
    for src, (d, runs) in dv.items():
        full = sorted((k for k, (a_, n_) in runs.items() if n_ and a_ >= n_ and k.startswith("dev")), key=lambda k: (k != "dev", k))
        rec["dev"][src] = devcheck.check(a.lang, d["book"], full) if full else None
    p = paths.lang_dir(a.lang, "ready.json"); json.dump(rec, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for src, r in rec["dev"].items():
        for lb, f in (r or {}).get("runs", {}).items():
            print(f"{src} {r['book']} {lb}: chrF3 {f['chrF3']}, words {f['words (draft / team)']} ({r['verses']} verses)")
    print("ready to draft ->", p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("status", "dev", "ready")); ap.add_argument("--lang", required=True)
    a = ap.parse_args(); {"status": cmd_status, "dev": cmd_dev, "ready": cmd_ready}[a.cmd](a)


if __name__ == "__main__":
    main()
