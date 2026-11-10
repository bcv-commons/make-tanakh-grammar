# make-tanakh-grammar: notes for Claude

The production repository: drafting from the Hebrew and Greek in a team's wording, and the language analysis the drafters
draw on. It restarted on 2026-11-05 with a clean history; the research record is the private `make-tanakh-research`.
Read `README.md` first.

## Setup

- `. ./env.sh` before any run. Code reads other repositories and data only through its settings (`MAKE_TANAKH_WORK`,
  `MAKE_TANAKH_PRIVATE`, `BCV_COMMONS`); never write a path of this box into code.
- `MAKE_TANAKH_PRIVATE` (default `./private`, never tracked): corpora, run outputs, everything from a protected text.
- Throwaway work goes in `private/scratch/`: a run label `tmp-*` lands there by itself. It is deleted when a check is done,
  without an rm list; `python3 tools/clean_scratch.py [--yes]` lists or clears leftovers. Everything else is deleted only by rm list.
- `.gitignore` is an allowlist; the pre-commit hook (`core.hooksPath .githooks`) runs `tools/screen.py`.
- `python3 tools/setup.py` checks the box; `python3 -m unittest discover -s tests -p "test_*.py"` runs the unit tests;
  `tests/parity.py` compares prompts with the research repository (legacy mode) where that repository is present.
- LLM runs go through the `claude` CLI on the subscription (`shared/llm.py`); at most two processes at once.

## Binding rules

- **The user commits and pushes.** Don't commit unless asked.
- **This repository is public. No Bible text in git**, nor anything built from one (corpora, dumps, run outputs, word
  forms of a protected translation). A form admitted on purpose goes into `tools/screen_allow.txt`, with its reason.
- **The closed list holds.** Every step that builds a pool of a team's text, trains a model or scores a draft asks
  `shared/holdout.py` first. Never draft, score or open a closed chapter without the user's go.
- **Production imports nothing from the research repository.** Research may import production, never the reverse. Code is
  brought over only when it runs here on its own. One yardstick lives here (`drafting/devcheck.py`: a draft against the
  team's text on dev chapters); arms, oracles, experiments and every read of a closed chapter stay in research.
- **Rights before data moves.** A step that sends a team's text anywhere asks `shared/rights.py` first.
- **Outward-facing actions need the user's go:** pushes to Hugging Face, publishing to a language repository, notes and
  issues in other repositories.
- Never write "OT" or "Old Testament" in prose: Tanakh, Hebrew, Septuagint.
