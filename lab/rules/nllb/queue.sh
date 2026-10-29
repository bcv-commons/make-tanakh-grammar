#!/bin/bash
# one GPU process at a time: nogospels first (the engine's honest pool), then nt (memory test); models kept (never deleted)
PY=~/sil-study/.venv/bin/python; T="$MAKE_TANAKH_WORK/scripts"/nllb/train.py
for p in nogospels nt; do
  d=~/bsb-nllb/rules-en/$p
  echo "$(date -Is) start $p"
  HF_HOME=~/sil-study/hf $PY $T --data $d/data --out $d/run > $d/train.log 2>&1
  echo "$(date -Is) end $p exit $?"
  mkdir -p ~/models/nllb-finetuned/grc-eng-bsb-$p && cp -al $d/run/model/. ~/models/nllb-finetuned/grc-eng-bsb-$p/ 2>/dev/null
done
