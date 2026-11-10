#!/usr/bin/env python3
"""The pinned dependencies: public repositories and data this repository runs with, by tag or revision. tools/setup.py
checks a box against this list. Nothing of them is copied into this repository."""
import os, subprocess

PINS = {
    "make-tanakh": {"what": "the toolkit: the source tables (orig/), the language store, the standard tokeniser, the chapter tools",
                    "where": "MAKE_TANAKH_WORK", "repo": "https://github.com/bcv-commons/make-tanakh", "tag": "v0.3.1"},
    "lexeme-aligner": {"what": "the aligner (align-text), the segmenter runtime and the parts view",
                       "where": "LEXEME_ALIGNER", "repo": "https://github.com/bcv-commons/lexeme-aligner", "tag": "v0.1.0",
                       "commit": "aa60a9c26a0a29ceb2660b2370361d0778feda68", "submodule": "external/lexeme-aligner"},
    "hebrew-clause-layout": {"what": "the clause layout of the Hebrew Bible (the units of a published chapter)",
                             "where": "aligner-data/hebrew-clause-layout", "dataset": "bcv-commons/hebrew-clause-layout",
                             "revision": "514a88320ab6556e0f7fd2e686c9637fcf39bd62"},
    "make-tanakh-review": {"what": "the review tool; its template/ folder is what every language repository starts from",
                           "repo": "https://github.com/bcv-commons/make-tanakh-review", "gh": "bcv-commons/make-tanakh-review",
                           "commit": "5458c319b75dda789c9dca0d40b80e7256ce7ae4"},
    "nllb": {"what": "the base model of the NLLB alternative (CC BY-NC 4.0)", "model": "facebook/nllb-200-distilled-600M"},
}


def git_commit(d):
    try:
        h = subprocess.run(["git", "-C", d, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        t = subprocess.run(["git", "-C", d, "describe", "--tags"], capture_output=True, text=True).stdout.strip()
        return {"commit": h, "describe": t} if h else None
    except OSError:
        return None
