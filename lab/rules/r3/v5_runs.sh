#!/bin/bash
# eng_v5 (defaults: learned endings, corpus from lexeme-aligner's BSB layer): dev and B, then the swap tests on B
cd "$MAKE_TANAKH_GRAMMAR/lab/rules"
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/r3" "$P/results/auto"   # run outputs, never in git (env.sh)
PY=~/sil-study/.venv/bin/python
export PYTHONPATH="$MAKE_TANAKH_WORK/scripts"
for l in nt ot; do for o in dev B; do $PY r3/v5_measure.py $l $o; done; done > "$P/r3/v5_measures.jsonl" 2> "$P/r3/v5_measures.err"
cd eng_v5 && HOLD=1 STAGES=e6 $PY metamorphic2.py > "$P/r3/v5_features_B.log" 2>&1
