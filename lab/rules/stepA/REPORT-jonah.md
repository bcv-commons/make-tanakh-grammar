# Step A clean test: Kuni Jonah 1-4, held out (2026-10-28)

Public version: figures and method. The score files and the full report stay local (`$MAKE_TANAKH_PRIVATE/rules/stepA/`):
the Kuni text (CC BY-NC-ND) and our drafts' words never leave the box.

One book agent drafted Jonah 1-4 in `local_output/kvg/jon_test` (today's store and wiki without Jonah: `lab/heldout/setup_jon.py`,
`lab/heldout/heldout_scrub.py` with HELDOUT_BOOK_ONLY=1; all 38 team decisions kept; ~254k tokens, 164 calls, 44 min). Scored like Ruth
(`STEPA_BOOK=JON STEPA_DRAFT=local_output/kvg/jon_test/jon`, team map Yawe -> Evezøza). Local files: `jon_stepA_{early,v11_whole,v11_morphed,all3}.txt`,
`jon_verbs_all3.txt`.

| | Ruth (2026-10-14 drafts) | Jonah (2026-10-28 drafts) |
|---|---|---|
| core links (all three layers alike) | 232 | 138 |
| core: word choice / form | 0.759 / 0.668 | 0.833 / 0.754 |
| core nouns: choice / form | 0.750 / 0.722 | 0.875 / 0.848 |
| core verbs: choice / form (n) | 0.776 / 0.510 (49) | 0.737 / 0.316 (19) |
| all links (v1.1 whole): choice / form | 0.589 / 0.422 | 0.564 / 0.423 |
| all verbs: exact / tone only / auxiliary missing / other stem | 32.5% / 8.9% / 7.9% / 38.8% | 28.3% / 6.4% / 7.5% / 48.1% |
| chrF (summary) | 39.1 | 39.9 |

Reading: nouns and names better on the core; verbs not better. Tone-only misses fell a little (8.9% -> 6.4%), the say-verb
frame (auxiliary missing) is unchanged, and other-stem misses rose: Jonah's vocabulary (sea, ship, storm, the plant) is further
from the NT than Ruth's. Two books, two stores, and only 19 core verbs in Jonah: no claim of a gain or loss beyond that.
