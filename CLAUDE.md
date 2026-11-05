# make-tanakh-grammar: notes for Claude

The production repository: drafting from the Hebrew and Greek in a team's wording, and the language analysis the drafters
draw on. It restarted on 2026-11-05 with a clean history; the research record is the private `make-tanakh-research`.
Read `README.md` first.

## Setup

- `. ./env.sh` before any run. Code reads other repositories and data only through its settings (`MAKE_TANAKH_WORK`,
  `MAKE_TANAKH_PRIVATE`, `BCV_COMMONS`); never write a path of this box into code.
- `MAKE_TANAKH_PRIVATE` (default `./private`, never tracked): corpora, run outputs, everything from a protected text.
- `.gitignore` is an allowlist; the pre-commit hook (`core.hooksPath .githooks`) runs `tools/screen.py`.

## Binding rules

- **The user commits and pushes.** Don't commit unless asked.
- **This repository is public. No Bible text in git**, nor anything built from one (corpora, dumps, run outputs, word
  forms of a protected translation). A form admitted on purpose goes into `tools/screen_allow.txt`, with its reason.
- **The closed list holds.** Every step that builds a pool of a team's text, trains a model or scores a draft asks
  `shared/holdout.py` first. Never draft, score or open a closed chapter without the user's go.
- **Production imports nothing from the research repository.** Research may import production, never the reverse. Code is
  brought over only when it runs here on its own; scoring and experiments stay in research.
- **Outward-facing actions need the user's go:** pushes to Hugging Face, publishing to a language repository, notes and
  issues in other repositories.
- Never write "OT" or "Old Testament" in prose: Tanakh, Hebrew, Septuagint.
