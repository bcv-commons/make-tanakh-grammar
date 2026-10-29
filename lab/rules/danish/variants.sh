#!/bin/bash
# rung 4: eng_v9 switches on Danish, held-out B, E6 (E5 alongside where the switch touches it)
cd "$(dirname "$0")/.."
PY=~/sil-study/.venv/bin/python; export PYTHONPATH="$MAKE_TANAKH_WORK/scripts" T=dan
run() { env "$@" STAGES=e5,e6 N_B=800 $PY danish/run.py 2>/dev/null | grep '"on": "B"' | sed "s|^{|{\"variant\": \"$*\", |"; }
run POST_CELL=
run FORM_ROLE= GOV_KEY=
run CHOICE_CTX=
run PRE_LEX=
run HEB_SFX=
run MID_KEYS=
run ART= 
run PRE_LEX= ENDINGS=learn
