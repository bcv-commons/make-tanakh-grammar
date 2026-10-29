#!/bin/bash
# E8 (memory only where it agrees with E6) against E6 and E7: measures on dev and on held-out B, the person and feature swaps
cd "$MAKE_TANAKH_GRAMMAR/lab/rules"/r3
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/r3" "$P/results/auto"   # run outputs, never in git (env.sh)
PY=~/sil-study/.venv/bin/python
{ STAGES=e6,e7,e8pre,e8lex $PY variant.py; HOLD=1 STAGES=e6,e7,e8pre,e8lex $PY variant.py; } > "$P/r3/e8.jsonl" 2> "$P/r3/e8.err"
(cd ../engine && STAGES=e6,e7,e8pre,e8lex $PY metamorphic.py > "$P/r3/e8_person.log" 2>&1)
(cd ../engine && HOLD=1 STAGES=e6,e7,e8pre,e8lex $PY metamorphic2.py > "$P/r3/e8_features_B.log" 2>&1)
echo done
