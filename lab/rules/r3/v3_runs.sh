#!/bin/bash
# eng_v3: dev and held-out B measures (NT nogospels, OT), detectors and auto rules, swap tests; then the OT bootstrap of round 3
cd "$MAKE_TANAKH_GRAMMAR/lab/rules"
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/r3" "$P/results/auto"   # run outputs, never in git (env.sh)
PY=~/sil-study/.venv/bin/python
export PYTHONPATH="$MAKE_TANAKH_WORK/scripts"
cat > r3/v3_measure.py <<'PYEOF'
import json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../eng_v3"))
import engine as E, cells as CL, final_eval as FE, metamorphic2 as M2, rules as RU  # noqa
lang, on = sys.argv[1], sys.argv[2]
if lang == "ot":
    import heb_run as HR
    CL.contexts = HR.heb_contexts; C = HR.HebCorpus(); tr = C.split("train"); refs = C.split("dev")
    if on == "B":
        refs = random.Random(8).sample(tr, 1500); tr = [r for r in tr if r not in set(refs)]
else:
    C = E.Corpus()
    if on == "B":
        os.environ["HOLD"] = "1"
    tr, refs = M2.hold(C)
for st in ("e1", "e2", "e5", "e6", "e7"):
    res, _ = E.measure(C, FE.build(C, tr, st), refs)
    print(json.dumps({"engine": "v3", "lang": lang, "on": on, "stage": st, **{k: res[k] for k in FE.KEYS}}, ensure_ascii=False), flush=True)
PYEOF
for l in nt ot; do for o in dev B; do $PY r3/v3_measure.py $l $o; done; done > "$P/r3/v3_measures.jsonl" 2> "$P/r3/v3_measures.err"
(cd auto && $PY auto.py ../eng_v3 v3 > "$P/results/auto/v3.log" 2>&1)
(cd eng_v3 && STAGES=e5,e6,e7 $PY metamorphic.py > "$P/r3/v3_person.log" 2>&1; HOLD=1 STAGES=e5,e6,e7 $PY metamorphic2.py > "$P/r3/v3_features_B.log" 2>&1)
(cd eng_v3 && $PY rules.py test "$P/rules/auto_v3.jsonl" > "$P/r3/v3_autorules.txt" 2>&1)
(cd r3 && $PY boot_B.py ot e6 HEB_SFX=1 LEX_ART=1 CTX_EXTRA=noun.after_cstr >> "$P/r3/boot_B.txt" 2>&1)
echo done
