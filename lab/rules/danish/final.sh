#!/bin/bash
# rung 4 final table (2026-10-28): eng_v9 and eng_v10 (eng_v9 + NOWORD) on the rebuilt Danish corpus and the same verses in
# BSB and Vamvas; Danish also with ENDINGS=learn. Stages e1 e5 e6 e7 on B and dev; dumps of E6 for the bootstrap.
cd "$(dirname "$0")/.."
PY=~/sil-study/.venv/bin/python; export PYTHONPATH="$MAKE_TANAKH_WORK/scripts"
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/danish/dumps"   # DUMP= is read below $P (run.py); never in git
for t in dan bsb vamvas; do
  for eng in eng_v9 eng_v10; do
    ENGINE=$eng T=$t STAGES=e1,e5,e6,e7 DUMP=danish/dumps/final_${t}_${eng} $PY danish/run.py 2>/dev/null | sed "s|^{|{\"engine\": \"$eng\", |"
  done
done
ENGINE=eng_v10 ENDINGS=learn T=dan STAGES=e5,e6,e7 DUMP=danish/dumps/final_dan_eng_v10_learn $PY danish/run.py 2>/dev/null | sed "s|^{|{\"engine\": \"eng_v10 ENDINGS=learn\", |"
for t in dan bsb vamvas; do $PY danish/boot.py "$P/danish/dumps/final_${t}_eng_v9.e6.json" "$P/danish/dumps/final_${t}_eng_v10.e6.json"; done
$PY danish/boot.py "$P/danish/dumps/final_dan_eng_v10.e6.json" "$P/danish/dumps/final_dan_eng_v10_learn.e6.json"
$PY danish/boot.py "$P/danish/dumps/final_dan_eng_v10.e6.json" "$P/danish/dumps/final_dan_eng_v10.e5.json"
$PY danish/boot.py "$P/danish/dumps/final_bsb_eng_v10.e6.json" "$P/danish/dumps/final_bsb_eng_v10.e5.json"
