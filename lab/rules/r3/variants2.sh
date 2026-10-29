#!/bin/bash
# round 3, second set (held-out B): node rules for nouns / articles, the clause's subject continuity for conjunctions
cd "$MAKE_TANAKH_GRAMMAR/lab/rules"/r3
P="$MAKE_TANAKH_PRIVATE/rules"; mkdir -p "$P/r3" "$P/results/auto"   # run outputs, never in git (env.sh)
for v in "" noun.prule "noun.nrule,noun.prule" det.prule "noun.prule,det.prule" conj.clause_subj conj.prule "pron.gov,noun.prule,det.prule,conj.clause_subj"; do
  HOLD=1 CTX_EXTRA="$v" ~/sil-study/.venv/bin/python variant.py
done > "$P/r3/variants2_B.jsonl" 2> "$P/r3/variants2_B.err"
echo done
