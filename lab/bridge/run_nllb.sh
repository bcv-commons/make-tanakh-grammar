#!/bin/sh
# Hebrew -> Danish NLLB fine-tune on the DFB data (build_nllb_data.py), one GPU process at a time; the model is kept in
# ~/models/nllb-finetuned/<name> (never deleted). MODEL=<dir> continues from a saved model (default: NLLB-600M).
# Usage: . ./env.sh; [BATCH= ACCUM= MAXLEN= MODEL=] sh lab/bridge/run_nllb.sh <data dir under private/rules/nllb> <name> [steps]
set -e
D=$MAKE_TANAKH_PRIVATE/rules/nllb/$1; OUT=~/models/nllb-finetuned/$2; STEPS=${3:-1000}
mkdir -p "$OUT"
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ~/sil-study/.venv/bin/python ~/sil-study/nllb/train_nllb.py --data "$D" --out "$OUT" --model "${MODEL:-facebook/nllb-200-distilled-600M}" \
  --src-code heb_Hebr --trg-code dan_Latn --init-lang dan_Latn --steps "$STEPS" --batch ${BATCH:-4} --accum ${ACCUM:-16} --max-len ${MAXLEN:-128} --keep > "$D/train_$2.log" 2>&1
tail -5 "$D/train_$2.log"
