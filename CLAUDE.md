# make-tanakh-grammar: notes for Claude

The rules-engine lab and the grammar analysis of the make-tanakh family. Read `RELATIONS.md` first (how this repo relates
to make-tanakh and the work repo), then `docs/rules-engine-lab.md` (the plan) and `lab/rules/RUN.md` (the log).

## Setup

- `. ./env.sh` before any run: `MAKE_TANAKH_WORK` (the work repo, default `~/dev/make-tanakh-work`) and `PYTHONPATH`
  (its `scripts/`), `BCV_COMMONS` (the bcv-commons checkouts: bcv-query, lexeme-aligner; default `~/dev/bcv-commons`).
  Lab code reads them only through these settings; never write a path of this box into code.
- Interpreters: `~/sil-study/.venv/bin/python` (sacrebleu, pyarrow, huggingface_hub) for the lab; `/usr/bin/python3`
  (PyYAML) for the toolkit's scripts.
- `MAKE_TANAKH_PRIVATE` (env.sh; default `./private`, never tracked): corpora, run outputs, Step A results, everything
  from a protected text. Code reads and writes them through it (`PRIV` = `$MAKE_TANAKH_PRIVATE/rules`), never by a
  path of its own; `private/` mirrors `lab/` (`lab/rules/X` -> `private/rules/X`).
- Corpora are built into `private/rules/data/` by `lab/rules/data/build*.py` and the rungs' `build*.py`.
- `.gitignore` is an allowlist; the pre-commit hook (`core.hooksPath .githooks`) runs `tools/screen.py`, which refuses
  protected text and data. A Kuni form admitted on purpose goes into `tools/screen_allow.txt`, with its reason.

## Binding rules

- **The user commits and pushes.** Don't commit unless asked.
- **No Bible text in git**, nor anything built from one (corpora, dumps, run outputs: `.gitignore`). HEBM95 (© Bible
  Society in Israel) and the Kuni text (NC-ND) never leave the box; BHSA data (CC BY-NC) is never sent or published;
  TBTA data is treated as non-free. Quotes in reports follow the work repo's `docs/licensing.md` (short, credited).
- **Measure only the engine's components** (word choice, form, function words, order, chrF as summary) with paired
  bootstraps; held-out splits are never read while tuning (lab test chapters GEN 22, 37, 44).
- **Outward-facing actions need the user's go:** Hugging Face pushes (`publish_analysis.py push`), notes to bcv-commons
  repos, issues.
- **Tools that prove themselves go to make-tanakh** (RELATIONS.md, section 5); log each in `PROMOTIONS.md`.
- Data changes (stores, alignments, drafts) belong in the work repo, not here.
