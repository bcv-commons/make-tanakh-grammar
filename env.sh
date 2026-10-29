# Source this before running the lab:  . ./env.sh
# MAKE_TANAKH_WORK: the work repo (a make-tanakh copy with the projects' data); its scripts/ are the toolkit the lab imports.
# MAKE_TANAKH_PRIVATE: corpora, run outputs, Step A results and everything from a protected text; never in git.
# BCV_COMMONS: the folder holding the bcv-commons repos (bcv-query, lexeme-aligner).
# LEXEME_ALIGNER: the pinned aligner (submodule vendor/lexeme-aligner); ALIGNER_DATA: what its fetch-inputs downloads.
export MAKE_TANAKH_GRAMMAR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
export MAKE_TANAKH_WORK="${MAKE_TANAKH_WORK:-$HOME/dev/make-tanakh-work}"
export MAKE_TANAKH_PRIVATE="${MAKE_TANAKH_PRIVATE:-$MAKE_TANAKH_GRAMMAR/private}"
export BCV_COMMONS="${BCV_COMMONS:-$HOME/dev/bcv-commons}"
export LEXEME_ALIGNER="${LEXEME_ALIGNER:-$MAKE_TANAKH_GRAMMAR/vendor/lexeme-aligner}"
export ALIGNER_DATA="${ALIGNER_DATA:-$MAKE_TANAKH_PRIVATE/aligner-data}"
export PYTHONPATH="$MAKE_TANAKH_WORK/scripts${PYTHONPATH:+:$PYTHONPATH}"
