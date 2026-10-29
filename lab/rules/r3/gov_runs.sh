#!/bin/bash
# Greek case gap: eng_v5's switches on the working engine, Hebrew -> Vamvas, B: plain / FORM_ROLE / FORM_ROLE + GOV_KEY
cd "$MAKE_TANAKH_GRAMMAR/lab/rules"/r3
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/r3" "$P/results/auto"   # run outputs, never in git (env.sh)
PY=~/sil-study/.venv/bin/python
export PYTHONPATH="$MAKE_TANAKH_WORK/scripts" HOLD=1 MID_KEYS=3 HEB_SFX=1 LEX_ART=1 CHOICE_CTX=1 PRE_LEX=3 ENDINGS=hybrid \
  OT_DB=data/vamvas_ot.db FUNC_FILE=data/vamvas_func.txt CTX_EXTRA="pron.gov,noun.after_cstr,det.poss"
for cfg in "|" "1|" "1|1"; do r=${cfg%%|*}; g=${cfg#*|}
  FORM_ROLE=$r GOV_KEY=$g $PY heb_variant.py | sed "s/^{/{\"corpus\": \"vamvas\", \"FORM_ROLE\": \"$r\", \"GOV_KEY\": \"$g\", /"
done > "$P/r3/gov_B.jsonl" 2> "$P/r3/gov_B.err"
