#!/usr/bin/env python3
"""Does this box have what the repository runs with? Prints one line per dependency and what to do where one is missing.

    . ./env.sh; python3 tools/setup.py

Checked against shared/pins.py: the toolkit (make-tanakh) with its source tables, lexeme-aligner with its own environment,
the aligner's data folder (clause layouts, the lexeme spine), the Hebrew-Greek bridges, the model client (the claude CLI,
or an API key for CLAUDE_BACKEND=api), and the optional packages of the NLLB alternative. Nothing is installed here."""
import importlib.util, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths, pins  # noqa: E402


def line(ok, name, what, fix=""):
    print(f"{'ok  ' if ok else 'MISS' if ok is False else 'note'}  {name:22} {what}" + (f"\n      -> {fix}" if fix and not ok else ""))
    return ok is not False


def main():
    good = True; P = pins.PINS
    w = os.environ.get("MAKE_TANAKH_WORK", ""); have = all(os.path.exists(os.path.join(w, "orig", f)) for f in ("grc.sqlite", "heb.sqlite"))
    g = pins.git_commit(w) if w else None
    good &= line(have, "make-tanakh", f"{w} ({(g or {}).get('describe', 'no git')}; pin {P['make-tanakh']['tag']})",
                 f"clone {P['make-tanakh']['repo']} at {P['make-tanakh']['tag']}, build its source tables (orig/), set MAKE_TANAKH_WORK")
    good &= line(importlib.util.find_spec("full_align") is not None, "the toolkit's scripts", "on PYTHONPATH (env.sh)", ". ./env.sh")
    a = os.environ.get("LEXEME_ALIGNER") or os.path.join(os.environ.get("BCV_COMMONS", ""), "lexeme-aligner"); g = pins.git_commit(a)
    exe = os.path.exists(os.path.join(a, ".venv", "bin", "lexeme-aligner"))
    line(exe if exe else None, "lexeme-aligner", f"{a} ({(g or {}).get('describe', 'not found')}; pin {P['lexeme-aligner']['tag']})" +
         ("" if exe else "; needed only for the first stage (onboard/align.py)"),
         f"clone {P['lexeme-aligner']['repo']} at {P['lexeme-aligner']['tag']} (e.g. under ./external/), make its .venv, set LEXEME_ALIGNER")
    d = paths.aligner_data()
    good &= line(os.path.isdir(os.path.join(d, "hebrew-clause-layout")) and os.path.isdir(os.path.join(d, "greek-nt-clause-layout")), "clause layouts", d,
                 "lexeme-aligner fetch-inputs --iso <iso> --data " + d)
    b = paths.private("source", "bridges")
    good &= line(all(os.path.exists(os.path.join(b, f)) for f in ("strong_bridge.json", "grammar_bridge.json")), "Hebrew-Greek bridges", b,
                 "the bridges' builder is not brought over yet: copy the two files from where they were built")
    cli = shutil.which("claude"); key = os.environ.get("ANTHROPIC_KEY_FILE", "")
    good &= line(bool(cli) or os.path.exists(key), "model client", f"claude CLI: {cli or 'not found'}; API key file: {'there' if os.path.exists(key) else 'none'}",
                 "install the claude CLI and log in, or put an API key where ANTHROPIC_KEY_FILE points and set CLAUDE_BACKEND=api")
    for mod in ("pyarrow",):
        good &= line(importlib.util.find_spec(mod) is not None, mod, "python package", "pip install -r requirements.txt")
    miss = [m for m in ("ctranslate2", "transformers", "sacrebleu") if importlib.util.find_spec(m) is None]
    line(None if miss else True, "NLLB alternative", "packages there" if not miss else f"optional; missing: {', '.join(miss)}", "pip install -r requirements-nllb.txt")
    langs = sorted(os.path.basename(os.path.dirname(p)) for p in __import__("glob").glob(paths.lang_dir("*", "config.json")))
    line(None, "languages", ", ".join(langs) or "none yet (the first stage: onboard/)")
    print("\nthe box is set up for drafting" if good else "\nsomething the drafter needs is missing (MISS above)")
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
