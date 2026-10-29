#!/bin/bash
# eng_v4 on the corpus from lexeme-aligner's BSB layer v1.0 (data/nt_la.db, ot_la.db): dev and B
cd "$MAKE_TANAKH_GRAMMAR/lab/rules"
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/r3" "$P/results/auto"   # run outputs, never in git (env.sh)
PY=~/sil-study/.venv/bin/python
export PYTHONPATH="$MAKE_TANAKH_WORK/scripts" CORPUS_DB=data/nt_la.db OT_DB=data/ot_la.db
for l in nt ot; do for o in dev B; do $PY r3/v4_measure.py $l $o; done; done > "$P/r3/v4la_measures.jsonl" 2> "$P/r3/v4la_measures.err"
