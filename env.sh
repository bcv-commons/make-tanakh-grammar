# Source this before running anything:  . ./env.sh
# MAKE_TANAKH_WORK: the work repo (a make-tanakh copy with the projects' data); its scripts/ are the toolkit.
# MAKE_TANAKH_PRIVATE: corpora, run outputs and everything from a protected text; never in git (default ./private).
# BCV_COMMONS: the folder holding the bcv-commons repos (bcv-query, lexeme-aligner).
export MAKE_TANAKH_GRAMMAR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# env.local.sh (never tracked): this box's own settings, read first; e.g. a MAKE_TANAKH_PRIVATE shared with another checkout.
[ -f "$MAKE_TANAKH_GRAMMAR/env.local.sh" ] && . "$MAKE_TANAKH_GRAMMAR/env.local.sh"
export MAKE_TANAKH_WORK="${MAKE_TANAKH_WORK:-$HOME/dev/make-tanakh-work}"
# MAKE_TANAKH_PUBLISHER: who this checkout publishes as; a language repo's .tanakh/publisher.json must name it.
export MAKE_TANAKH_PUBLISHER="${MAKE_TANAKH_PUBLISHER:-make-tanakh-grammar}"
export MAKE_TANAKH_PRIVATE="${MAKE_TANAKH_PRIVATE:-$MAKE_TANAKH_GRAMMAR/private}"
# MAKE_TANAKH_IMPORT: the imported editions, filed by licence (import/README.md); their texts are never in git.
export MAKE_TANAKH_IMPORT="${MAKE_TANAKH_IMPORT:-$MAKE_TANAKH_GRAMMAR/import}"
export BCV_COMMONS="${BCV_COMMONS:-$HOME/dev/bcv-commons}"
# LEXEME_ALIGNER: lexeme-aligner, a core tool, as the submodule external/lexeme-aligner at its pin (shared/pins.py), with its own
# .venv inside it (python3 tools/setup.py --aligner makes it).
export LEXEME_ALIGNER="${LEXEME_ALIGNER:-$MAKE_TANAKH_GRAMMAR/external/lexeme-aligner}"
# DRAFTER_HOLDOUT: chapters held out of every evidence pool and training (shared/closed.json names them and why;
# shared/holdout.py refuses a setting that opens one).
export DRAFTER_HOLDOUT="${DRAFTER_HOLDOUT:-LUK:1,2,15;PHP:3;ACT:1;MAT:21}"
export PYTHONPATH="$MAKE_TANAKH_GRAMMAR:$MAKE_TANAKH_WORK/scripts${PYTHONPATH:+:$PYTHONPATH}"
# ANTHROPIC_KEY_FILE: the Anthropic API key (mode 600, outside the repo); deliberately NOT exported as ANTHROPIC_API_KEY.
export ANTHROPIC_KEY_FILE="${ANTHROPIC_KEY_FILE:-$HOME/.config/anthropic/api_key}"
