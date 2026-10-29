# NLLB instrument tests on CPU, 2026-10-26

Model `grc-eng-bsb-nogospels` (NLLB-600M, Greek -> BSB, 2,500 steps); dev verses MRK 3, 9, 12 (127), held out for the model
and for eng_v5. CPU, 3 threads, 14 minutes in all (`cpu_tests.py`, figures `cpu_tests.json`). No punctuation in any candidate.

**T1 judge.** Mean log-probability per token: BSB reference -2.07; eng_v5 E2 -5.41, E5 -5.11, E6 -5.26, E7 -5.15.
- It ranks the reference first in 99% of verses.
- Between two engine stages that differ, its order agrees with chrF in 66% of 691 pairs (chance 50%).
- Its order of the stages (E5 > E7 > E6 > E2) is nearly chrF's (E7 37.6 > E5 37.6 > E6 37.2 > E2 34.9).
- A weak per-verse judge of engine output; a fair judge of stages on average.

**T2 contrast** (one minimal edit of the reference; preference for the original):

| edit | pairs | with the Greek | empty source | margin with / without |
|---|---|---|---|---|
| tense (said -> says ...) | 88 | 96.6% | 88.6% | 0.30 / 0.17 |
| article dropped | 81 | 100% | 98.8% | 0.44 / 0.36 |
| noun number | 32 | 100% | 84.4% | 0.30 / 0.21 |

Most of the preference is English fluency (the empty source already prefers the original). The Greek adds to it, most for
tense and number (the margin nearly doubles for tense), least for the article.

**T3 memory.** chrF on 127 training verses 79.7, on dev 59.0. Word for word: 27 of 127 training verses (21%), 1 of 127 dev.
Much of its output on seen verses is recall, so as a judge it must only be used on verses it was not trained on.
