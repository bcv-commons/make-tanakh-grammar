#!/bin/bash
# detectors + auto rounds on the three frozen engines, then every rule file through its engine's rules.py test (dev only)
cd "$MAKE_TANAKH_GRAMMAR/lab/rules"
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/r3" "$P/results/auto"   # run outputs, never in git (env.sh)
PY=~/sil-study/.venv/bin/python
for v in 0 1 2; do (cd auto && $PY auto.py ../eng_v$v v$v); done
t() { (cd eng_v$1 && echo "== $2 on eng_v$1" && $PY rules.py test "$P/rules/$2" | tail -7); }
{ t 0 auto_v0.jsonl; t 0 en_bsb_r1.jsonl; t 1 auto_v1.jsonl; t 2 auto_v2.jsonl; t 2 en_bsb_r2.jsonl; t 2 en_bsb_r1.jsonl; } > "$P/results/auto/ruletests.txt" 2>&1
echo done
