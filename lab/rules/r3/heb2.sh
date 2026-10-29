#!/bin/bash
# Hebrew, held-out B, with the suffix: the lexical article, the construct-chain field; Greek: the lexical article
cd "$MAKE_TANAKH_GRAMMAR/lab/rules"/r3
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/r3" "$P/results/auto"   # run outputs, never in git (env.sh)
export PYTHONPATH="$MAKE_TANAKH_WORK/scripts" HOLD=1 HEB_SFX=1
PY=~/sil-study/.venv/bin/python
{ LEX_ART=1 $PY heb_variant.py; CTX_EXTRA=noun.after_cstr $PY heb_variant.py; LEX_ART=1 CTX_EXTRA=noun.after_cstr $PY heb_variant.py; } > "$P/r3/heb2_B.jsonl" 2> "$P/r3/heb2_B.err"
LEX_ART=1 MID_KEYS=1 CTX_EXTRA=pron.gov $PY variant.py > "$P/r3/gr_lexart_B.jsonl" 2> "$P/r3/gr_lexart_B.err"
echo done
