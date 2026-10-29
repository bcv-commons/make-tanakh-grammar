#!/bin/bash
# ending learner: eng_v4's switches on the working engine, ENDINGS off / learn / learn + ENDCLASS, on B
cd "$MAKE_TANAKH_GRAMMAR/lab/rules"/r3
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/r3" "$P/results/auto"   # run outputs, never in git (env.sh)
PY=~/sil-study/.venv/bin/python
export PYTHONPATH="$MAKE_TANAKH_WORK/scripts" HOLD=1 MID_KEYS=3 HEB_SFX=1 LEX_ART=1 CHOICE_CTX=1 PRE_LEX=3
for cfg in "|" "learn|" "learn|1"; do e=${cfg%%|*}; c=${cfg#*|}
  ENDINGS=$e ENDCLASS=$c OT_DB=data/vamvas_ot.db FUNC_FILE=data/vamvas_func.txt CTX_EXTRA="pron.gov,noun.after_cstr,det.poss" $PY heb_variant.py | sed "s/^{/{\"corpus\": \"vamvas\", \"ENDINGS\": \"$e\", \"ENDCLASS\": \"$c\", /"
  ENDINGS=$e ENDCLASS=$c CTX_EXTRA="pron.gov,noun.after_cstr,det.poss" $PY heb_variant.py | sed "s/^{/{\"corpus\": \"bsb-ot\", \"ENDINGS\": \"$e\", \"ENDCLASS\": \"$c\", /"
  ENDINGS=$e ENDCLASS=$c CTX_EXTRA="pron.gov,det.poss" $PY variant.py | sed "s/^{/{\"corpus\": \"bsb-nt\", \"ENDINGS\": \"$e\", \"ENDCLASS\": \"$c\", /"
done
