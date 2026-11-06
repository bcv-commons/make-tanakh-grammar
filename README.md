# make-tanakh-grammar

Drafts Tanakh chapters from the Hebrew in a translation team's own wording, for a language that has a team translation
to learn from (usually a New Testament). It takes a language from its text to "ready to draft" (the first stage), drafts
any chapter of any book, makes alternative drafts beside the main one, and packs them for reviewers.

The research that led here (every experiment, report and run log) is in the private repository `make-tanakh-research`.
This repository restarted on 2026-11-05 with a clean history; it holds only what runs on its own.

No Bible text is committed here, nor anything built from one.

## What it does

| step | command | what comes out |
|---|---|---|
| is the box set up? | `tools/setup.py` | one line per dependency, and what to do where one is missing |
| the first stage | `onboard/ladder.py status`, `onboard/align.py run`, `onboard/notes.py`, `onboard/ladder.py ready` | the corpus of the team's text (parts, word boundaries, links to the source), optional grammar notes, the dev check, the "ready to draft" record |
| the main draft | `drafting/draft.py build`, `send`, `text` | a chapter drafted verse by verse, clause by clause |
| the yardstick | `drafting/devcheck.py` | how close a draft is to the team's own text, on chapters the team has translated |
| alternatives | `alternatives/nllb.py`, `alternatives/shape.py` | a second and a third draft of the same clauses, by other means |
| the reviewer's bundle | `publish/bundle.py` | main draft, alternatives and support marks in the published chapter format, behind the verbatim gate |
| publishing | `publish/push.py` | a dry run by default; with `--seed` or `--propose` the bundle goes to the language's text repository |

Every command prints its usage with `--help`; the module docstrings are the reference.

## How a verse is drafted

For each clause of the source verse the prompt shows the drafting model the team's translation of the 20 most similar
clauses (word by word, divided into parts, with links to the source words), the team's commonest rendering of each
function word, the three most similar whole verses, how full the team's translation is against the source, and the
language's grammar notes where it has them. The model writes the clause; the verse is its clauses in order. A Tanakh
chapter of a language with a New Testament only is drafted from that New Testament through Hebrew-Greek bridges.

The team's text is the measure of everything: similar clauses come from it, and the dev check scores drafts against it.
A chapter being drafted is never among its own examples, and held-out chapters are never read.

## The first stage ("sharpening the knife")

`python3 onboard/ladder.py status --lang <iso>` prints the ladder and what is open:

| step | what | how |
|---|---|---|
| A | identity and rights: name, ISO code, the text's licence, what may be sent where | the language's `config.json` (`shared/paths.py`, `shared/rights.py`) |
| B | the team's text, one verse per line | `onboard/align.py run` (step `text`) |
| C | the knife: the segmenter's cut of every word, the alignment by words and by parts, the corpus (of the New Testament, and of the team's Tanakh books where it has some) | `onboard/align.py run`, `onboard/corpus.py` |
| G | grammar notes written from the corpus, and the team's own answers | `onboard/notes.py` (optional) |
| E | held-out chapters; the dev check with and without the notes | `onboard/ladder.py dev`, `drafting/devcheck.py` |

The aligner (lexeme-aligner) runs locally, so a protected text never leaves the box. Its paid pass (TypeSafe's Jev,
`--jev --max-usd N`) links about twice as many words as the base run; it runs only when the language's rights table
allows it and only up to the budget given.

A language needs a segmenter bundle (the language-analysis dataset) before step C. Making one for a language that has
none is the work of the toolkit's language store and is not automated here yet.

## What is measured, and what is not

Dev figures: verse chrF3 against the team's text, one run each, on chapters the team has translated and that were kept
out of the pool. They are not figures for unseen books.

| language | chapters | drafter | chrF3 |
|---|---|---|---|
| Zinza | John 1-4 (from the Greek) | main draft | 49.9 |
| Zinza | John 1-4 | main draft with grammar pages written from the text alone | 52.4 |
| Zinza | John 1-4 | NLLB alternative | 48.7 |
| Kuni | John 1-4 (from the Greek) | main draft | 44.7 |
| Kuni | John 1-4 | main draft with the team's grammar pages | 46.8 |
| Kuni | John 1-4 | main draft with grammar pages written from the text alone | 47.9 |
| Kuni | Genesis 2, 4, 6, 8 (from the Hebrew) | main draft with the team's grammar pages | 43.6 |
| Kuni | Genesis 2, 4, 6, 8 | the same, drafted as if the language had a New Testament only | 40.3 |
| Kuni | Genesis 2, 4, 6, 8 | NLLB alternative | 37.4 |
| Kuni | Genesis 2, 4, 6, 8 | shape draft (it writes 0.63 of the team's words) | 32.2 |

What these say:

- **Grammar pages help.** Pages a model writes from the aligned corpus alone (`onboard/notes.py`) lifted Zinza by 2.4
  [1.7, 3.2] and Kuni by 3.2 [2.3, 4.1]. Kuni's own pages, which also hold the team's answers, gave 2.1 on the same
  chapters. The prompt becomes about three times as long.
- **The paid alignment pass helps.** Zinza drafted on the base alignment scores 47.1 against 49.9 with the Jev pass.
- **A Tanakh chapter drafted from a New Testament only** loses about 3 points against having some of the team's own
  Tanakh text in the pool (one language, one set).
- **The alternatives are weaker drafts** than the main one. They are there for reviewers and for the support marks.

Not known yet:

- **Unseen books.** An acceptance read on chapters never drafted before is still to come.
- **A language without a New Testament**, or with very little text: every step assumes an aligned New Testament.
- **The base alignment is not repeatable link for link**: two runs on the same text agree on the words and their cut
  exactly, and on about seven links in ten.
- **Grammar pages on the Hebrew path**, and the two kinds of pages together, are not measured.

## Setup

    . ./env.sh                              # MAKE_TANAKH_WORK, MAKE_TANAKH_PRIVATE, BCV_COMMONS, DRAFTER_HOLDOUT
    git config core.hooksPath .githooks     # once per clone: the screening hook
    pip install -r requirements.txt         # and requirements-nllb.txt for the NLLB alternative
    python3 tools/setup.py                  # what is there, what is missing

Dependencies are public repositories and datasets at a pin (`shared/pins.py`); nothing of them is copied in:
[make-tanakh](https://github.com/bcv-commons/make-tanakh) (the toolkit: source tables, tokeniser, language store),
lexeme-aligner (alignment, segmenter runtime), the clause layouts, and NLLB-200 for the NLLB alternative.
`MAKE_TANAKH_PRIVATE` (default `./private`, never tracked) holds the languages' configurations, corpora, models and run
outputs. A box's own settings go into `env.local.sh` (never tracked), which `env.sh` reads first.

The drafting model runs through the `claude` CLI by default; `CLAUDE_BACKEND=api` switches to API batches with a
spending cap.

## Layout

| folder | what |
|---|---|
| `shared/` | paths and the language configuration, the rights table, the hold-out and the closed list, pins, the model client |
| `source/` | the Hebrew and Greek tokens, the clause layouts, the Hebrew-Greek bridges |
| `onboard/` | the first stage: the ladder, the alignment chain, the corpus builder, the grammar notes |
| `drafting/` | evidence from the team's text, the prompt, the runs, the dev check |
| `alternatives/` | the NLLB alternative with its trainer, the shape draft |
| `publish/` | the chapter format, the verbatim gate, the reviewer's bundle, the publishing step |
| `tools/` | the screening, the setup check |
| `tests/` | unit tests (no text, no private data); `parity.py` compares prompts with the research repository where it is present |

## Rights, the closed list, the screening

- **Rights before data moves.** A language's configuration says what may be sent to the drafting model and to Jev, and
  whether drafts made from the team's text may be published; every step that sends or publishes asks it. A missing row
  means no.
- **The verbatim gate.** A draft made with a team's text among its inputs must not reproduce the team's own verse; the
  bundle rewords, replaces or withholds such a clause.
- **The closed list.** `shared/closed.json` names chapters and books that no pool, training set or measurement may
  read; `shared/holdout.py` is the one place code asks. A language's own held-out chapters go into its configuration.
- **The screening.** `.gitignore` is an allowlist, and before each commit `tools/screen.py` refuses a file that holds a
  corpus or binary, Hebrew-script text beyond a few words that is not the WLC, word forms of a protected translation,
  or data of a source that is not free. `python3 tools/screen.py --all` screens the whole tree.
- **NLLB** is CC BY-NC 4.0. A model fine-tuned on a team's text stays private; whether its drafts may be published
  under another licence is a question for the publisher, not settled by this code.

Licences: code MIT (`LICENSE`), docs CC0 (`LICENSE-docs`).
