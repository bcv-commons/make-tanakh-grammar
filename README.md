# make-tanakh-grammar

The production side of the make-tanakh family for languages that have a team translation to learn from: it drafts Tanakh
chapters from the Hebrew (and New Testament chapters from the Greek) in the team's own wording, and it builds the language
analysis that every drafter draws on.

**State (2026-11-05): a fresh start.** This repository restarts with a clean history and a bare minimum. The research that
led here (every experiment, report and run log) lives on in the private repository `make-tanakh-research`, which was this
repository until that date. Code is brought over from there piece by piece, each piece only when it runs here on its own.
What is here today is the frame: the licences, the screening that keeps protected text out of git, and the closed list.

## Two outputs

| output | what | where it is published |
|---|---|---|
| the text | drafts of a chapter by several drafters, their alignment to the source, and sidecar data for reviewers | one repository per language under the `global-tanakh` organisation |
| the language analysis | grammar store, wiki, lexicon, segmenter data, conventions | a second repository per language, same design |

## Layout (planned)

| folder | what |
|---|---|
| `drafting/` | evidence from the team's text, the drafter's prompt and runs, alternative drafts, support marks, the publishing step |
| `analysis/` | onboarding of a language, the morphology profile, conventions, bridges between Hebrew and Greek, analysis publishing |
| `shared/` | what both need: the closed list and hold-out (`holdout.py`, `closed.json`), settings, the model client |
| `tools/` | `screen.py`, the pre-commit screening |

Only `shared/` and `tools/` exist yet.

## Setup

    . ./env.sh                              # MAKE_TANAKH_WORK, MAKE_TANAKH_PRIVATE, BCV_COMMONS, DRAFTER_HOLDOUT
    git config core.hooksPath .githooks     # once per clone: the screening hook
    python3 shared/holdout.py               # prints the closed list and checks the environment

`MAKE_TANAKH_WORK` is a work copy of [make-tanakh](https://github.com/bcv-commons/make-tanakh) with its sources.
`MAKE_TANAKH_PRIVATE` (default `./private`, never tracked) holds corpora, run outputs and everything built from a protected
text. A box's own settings go into `env.local.sh` (never tracked), which `env.sh` reads first.

## What is committed, and the screening

`.gitignore` is an allowlist: code (`*.py`, `*.sh`), docs (`*.md`), the licences and a few data files without text are
admitted; anything else stays local until it is admitted on purpose. Before each commit `tools/screen.py` refuses a file
that holds a corpus or binary, Hebrew-script text beyond a few words that is not the WLC, word forms of a protected
translation, or data of a source that is not free. `python3 tools/screen.py --all` screens the whole tree.

No Bible text is committed here, nor anything built from one.

## The closed list

`shared/closed.json` names the chapters and books that no evidence pool, training set or measurement may read, with the
reason for each; `shared/holdout.py` is the one place code asks. Some of them have never been drafted or scored by the
current drafter and are kept for a later acceptance test.

Licences: code MIT (`LICENSE`), docs CC0 (`LICENSE-docs`).
