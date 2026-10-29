#!/bin/bash
# context variants for round 3 (gov, participant fields), dev only
cd "$MAKE_TANAKH_GRAMMAR/lab/rules"/r3
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/r3" "$P/results/auto"   # run outputs, never in git (env.sh)
for v in "" pron.gov "pron.gov,det.gov" "pron.gov,det.gov,adj.gov" verb.p_subj "verb.p_subj,verb.p_rival" "pron.p_ref,pron.p_psubj" "pron.gov,pron.p_psubj,pron.p_rival" "pron.gov,det.gov,verb.p_subj,noun.gov"; do
  CTX_EXTRA="$v" ~/sil-study/.venv/bin/python variant.py
done > "$P/r3/variants${HOLD:+_B}.jsonl" 2> "$P/r3/variants${HOLD:+_B}.err"
echo done
