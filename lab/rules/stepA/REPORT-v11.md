# Step A on lexeme-aligner's v1.1 Kuni layers (2026-10-28)

Public version: figures and method. The score files, their examples and the full report stay local
(`$MAKE_TANAKH_PRIVATE/rules/stepA/`): the Kuni text (CC BY-NC-ND) and our drafts' words never leave the box.

The Kuni Ruth 1–4 drafts of 2026-10-14 were scored against the human Ruth again. The alignments are lexeme-aligner's new
layers in `bcv-commons/full-alignments-llm` v1.1: Jev checked them clause by clause, using our modules. The whole-word layer
is `kvg_wbt+llm+jev-v4` and the morphed one `kvg-m_wbt+llm+jev-v4`. Local copies are in the work repo's
`scratch/incoming/full-alignments-llm-v1.1/`. No agents were used; the scripts are `score_ruth.py` and `verbs.py`
(`STEPA_LAYER=<dir>`, `STEPA_STEADY=all3`).

## 1. The alignment decides more than the drafts do

|  | links | Kuni words per Hebrew word | same link as the early layer |
|---|---|---|---|
| early (NT bridge, 2026-10-27) | 824 | 1.19 | — |
| v1.1 whole words | 835 | 1.32 | 47% |
| v1.1 morphed | 845 | 1.29 | 40% |

The two v1.1 layers agree with each other on 39% of links. The same drafts score quite differently depending on the layer:

| layer | all classes: word choice / form | verbs: word choice / form / any word of the link |
|---|---|---|
| early | 0.583 / 0.465 | 0.540 / 0.403 / 0.449 |
| v1.1 whole | 0.571 / 0.402 | 0.526 / 0.325 / 0.417 |
| v1.1 morphed | 0.523 / 0.378 | 0.478 / 0.269 / 0.379 |

Part of the drop comes from wider links: Jev adds auxiliaries, so "all the link's words present" gets harder. The new
"any word of the link" measure takes the width out, and the v1.1 layers stay lower even by that measure.

Which layer is right can't be told without a Kuni reader. Two checks:
- **Names:** a Hebrew name linked to its look-alike Kuni word: early 94.5%, whole 93.4%, morphed 93.3%. No difference.
- **The Septuagint route:** the Hebrew word's LXX Greek, then how our NT alignment renders that Greek in Kuni.
  - Verbs: early 35%, v1.1 29%.
  - Nouns: early 57%, v1.1 49%.
  - The early layer was built from these priors, so this check favours it; it doesn't show the early layer is better.

## 2. The steady core gives the same answer every time

The steady core is the links all three layers share: 232 links, 49 of them verbs.

| subset | links | word choice | form | verbs: choice / form |
|---|---|---|---|---|
| early 5 of 5 runs (2026-10-27) | 215 | 0.726 | 0.614 | 0.772 / 0.509 |
| all three layers alike | 232 | 0.703 | 0.612 | 0.776 / 0.510 |

Verbs on the core:

| outcome | early 5 of 5 | all three alike |
|---|---|---|
| exact | 51% | 51% |
| tone only | 10.5% | 10.2% |
| part of the rendering (auxiliary missing) | 14% | 10% |
| other stem | 19% | 20% |
| affixes | 2% | 6% |

So: the drafters choose the right verb about three times in four. They write its human form half the time. The misses are
tone, the say-verb frame (an auxiliary missing; examples in the local `ruth_verbs_detail.txt`), and other words. This
matches the 2026-10-27 reading, now on a second alignment.

## 3. What follows for Step A

- For Kuni, the component measures are only as good as the alignment. Measure on the core where the layers agree, or with
  several layers side by side; never on one layer alone.
- The morphed layer is the one that links negation suffixes, but it is not more stable for verbs.
- Ruth remains half a clean test (the wiki learned the say-verb frames from the human Ruth). A clean measure needs a fresh
  draft of a held-out book (Jonah: the v1.1 layers cover it) and the user's go for a drafting agent.

Local files:
- `ruth_stepA_early.txt`, `ruth_stepA_v11_whole.txt`, `ruth_stepA_v11_morphed.txt`, `ruth_stepA_all3.txt`;
- `ruth_verbs_all3.txt`, `ruth_verbs_all3_detail.txt`.

## 4. Addendum: the team's divine-name decision (2026-10-28)

The human Ruth writes *Yawe* (18 times); the team decided "Evezøza everywhere" (T-answers of 2026-10-26, `wiki/team-input.md`),
as the drafts write. `score_ruth.py` now reads the human *Yawe* as *Evezøza* (`TEAM`). On the core of 232 links: word choice
0.703 → 0.759, form 0.612 → 0.668; nouns 0.648 → 0.722 exact; verbs unchanged. All links: form 0.402 → 0.422.
Local file: `ruth_stepA_all3_team.txt`.
