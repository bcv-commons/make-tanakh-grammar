#!/usr/bin/env python3
"""Does this box have what the repository runs with? Prints one line per dependency and what to do where one is missing.

    . ./env.sh; python3 tools/setup.py
    python3 tools/setup.py --aligner      # fetches the lexeme-aligner submodule at its pin and makes its .venv (once)

Checked against shared/pins.py: the toolkit (make-tanakh) with its source tables, lexeme-aligner with its own environment,
the aligner's data folder (clause layouts, the lexeme spine), the Hebrew-Greek bridges, the model client (the claude CLI,
or an API key for CLAUDE_BACKEND=api), and the optional packages of the NLLB alternative. Nothing is installed without --aligner."""
import importlib.util, os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths, pins  # noqa: E402


def line(ok, name, what, fix=""):
    print(f"{'ok  ' if ok else 'MISS' if ok is False else 'note'}  {name:22} {what}" + (f"\n      -> {fix}" if fix and not ok else ""))
    return ok is not False


def setup_aligner():
    """the submodule at its pinned commit, and its own .venv with the package installed (eflomal needs a C compiler)"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); pin = pins.PINS["lexeme-aligner"]
    a = os.path.join(root, pin["submodule"])
    subprocess.run(["git", "-C", root, "submodule", "update", "--init", pin["submodule"]], check=True)
    if not pin["commit"].startswith((pins.git_commit(a) or {}).get("commit") or "-"):
        subprocess.run(["git", "-C", a, "checkout", "-q", pin["commit"]], check=True)
    if not os.path.exists(os.path.join(a, ".venv", "bin", "lexeme-aligner")):
        subprocess.run([sys.executable, "-m", "venv", os.path.join(a, ".venv")], check=True)
        subprocess.run([os.path.join(a, ".venv", "bin", "pip"), "install", "-q", "-e", ".[publish]"], cwd=a, check=True)


def main():
    if "--aligner" in sys.argv:
        setup_aligner()
    good = True; P = pins.PINS
    w = os.environ.get("MAKE_TANAKH_WORK", ""); have = all(os.path.exists(os.path.join(w, "orig", f)) for f in ("grc.sqlite", "heb.sqlite"))
    g = pins.git_commit(w) if w else None
    good &= line(have, "make-tanakh", f"{w} ({(g or {}).get('describe', 'no git')}; pin {P['make-tanakh']['tag']})",
                 f"clone {P['make-tanakh']['repo']} at {P['make-tanakh']['tag']}, build its source tables (orig/), set MAKE_TANAKH_WORK")
    good &= line(importlib.util.find_spec("full_align") is not None, "the toolkit's scripts", "on PYTHONPATH (env.sh)", ". ./env.sh")
    a = os.environ.get("LEXEME_ALIGNER") or os.path.join(os.environ.get("BCV_COMMONS", ""), "lexeme-aligner"); g = pins.git_commit(a)
    exe = os.path.exists(os.path.join(a, ".venv", "bin", "lexeme-aligner")); at_pin = bool(g) and P["lexeme-aligner"]["commit"].startswith(g["commit"])
    good &= line(exe and at_pin, "lexeme-aligner", f"{a} ({(g or {}).get('describe', 'not found')}; pin {P['lexeme-aligner']['tag']})" +
                 ("" if at_pin or not g else "; NOT at the pinned commit") + ("" if exe else "; no .venv"),
                 "python3 tools/setup.py --aligner   (the first stage and the drafts' alignment need it)")
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
