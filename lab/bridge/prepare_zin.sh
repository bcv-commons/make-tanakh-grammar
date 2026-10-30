#!/bin/sh
# Zinza prepared the way Kuni was (the whole-scope route): the free Zinza NT (zin_wbt, CC BY-SA 4.0, the work repo's
# import/CC-BY-SA/zin/zin_wbt) exported as align-text text, aligned by words, split into parts by the published segmenter
# (bcv-commons/language-analysis zin/54882f7b, the latest), aligned again on the parts view, and built into Greek -> Zinza engine
# corpora by words and by parts. No Jev here: JEV=1 adds it on the parts run with MAX_USD (default 0.01 = estimate only).
#   . ./env.sh; sh lab/bridge/prepare_zin.sh
set -e
LAB=$(pwd); A=$MAKE_TANAKH_PRIVATE/align/zin_all; S=$BCV_COMMONS/lexeme-aligner; B=$MAKE_TANAKH_PRIVATE/hf/language-analysis/zin/54882f7b/bundle
mkdir -p $A
/usr/bin/python3 lab/bridge/export_kvg_text.py --src $MAKE_TANAKH_WORK/import/CC-BY-SA/zin/zin_wbt/text --out $A/text
[ -f $A/out_words/align-text-run.json ] || $S/.venv/bin/lexeme-aligner align-text --text $A/text --edition zin_wbt --iso zin --lang-name Zinza \
    --data $ALIGNER_DATA --out $A/out_words > $A/words.log 2>&1
echo "words run done"
U=$A/out_words/text-usj
(cd $S && .venv/bin/python $LAB/lab/bridge/export_kvg_split.py $B $A/split zin_wbt $U) 2>&1 | tail -2 | cut -c1-300
(cd $S/pipeline && ../.venv/bin/python -c "
from pathlib import Path; import lexeme_aligner.target_parts as tp
m = tp.write_view(Path('$U'), Path('$A/view'), tp.load_parts('$A/split/words.parquet')); print('view books', len(m), 'verses', sum(len(v) for v in m.values()))")
JEVARGS=""; [ "${JEV:-0}" = 1 ] && JEVARGS="--jev --max-usd ${MAX_USD:-0.01}"
set -a; . $MAKE_TANAKH_WORK/.env; set +a
$S/.venv/bin/lexeme-aligner align-text --usj $A/view --edition zin-m_wbt --iso zin --lang-name Zinza --data $ALIGNER_DATA \
    --out $A/out_parts --force $JEVARGS > $A/parts.log 2>&1 || echo "parts run exit $? (an estimate above MAX_USD stops before sending)"
tail -3 $A/parts.log | cut -c1-200
/usr/bin/python3 lab/bridge/fold_view_layer.py text --view $A/view --out $A/view_text
/usr/bin/python3 lab/bridge/build_nt_corpus.py --layer $A/out_words/compact/z/zin/zin_wbt --text $A/text --out $MAKE_TANAKH_PRIVATE/rules/data/zin_nt_words.db | tail -1 | cut -c1-200
/usr/bin/python3 lab/bridge/build_nt_corpus.py --layer $A/out_parts/compact/z/zin/zin-m_wbt --text $A/view_text --out $MAKE_TANAKH_PRIVATE/rules/data/zin_nt_parts.db | tail -1 | cut -c1-200
echo "zin prepared"
