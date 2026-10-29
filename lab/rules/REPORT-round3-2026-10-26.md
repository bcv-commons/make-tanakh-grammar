# Rules-engine lab, round 3 (agent-free) and rung 1c (KJV), 2026-10-26

Follows `REPORT-2026-10-26.md` (day 1) and `auto/CALIBRATION.md` (detectors). No LLM and no agent in this round. Code in
`engine/` (switches by environment variable), the frozen result `eng_v3/`, runs in `r3/`, rung 1c in `kjv/`. Copies of the
engine before the round: `engine/*.r3.py`. The test chapters (Mark 5, 10, 15; Genesis 22, 37, 44) were not read.

**New measuring set, held-out B:** 1,500 training verses (seed 8, the detectors' sample B) taken out of the pool, the engine
retrained without them. Dev (127 NT / 91 OT verses) moves ±0.2 chrF by noise; B is 12 times larger. Every decision below was
taken on B, with a paired bootstrap (1,000 resamples) for the changes kept.

## 1. What was tried, what was kept (B, E6 unless noted)

| capability | field / change | result on B | kept |
|---|---|---|---|
| participant ids (`scripts/participants.py --mentions`, all 27 NT books, `engine/parts.py`) | verb: subject same / new / group as the previous verb's (`p_subj`), another person active (`p_rival`) | exact ±0.000, chrF ±0.0 | no |
| | pronoun: referent's last mention (`p_ref`), is the previous subject (`p_psubj`) | −0.001 | no |
| | conjunction: its clause's subject switch (`clause_subj`, δέ "but") | ±0.000 | no |
| | article: head noun's referent mentioned before (`head_ref`) | ±0.000 | no |
| governor | pronoun governed by a preposition (`pron.gov`: "you" not "your" in ἐν σοί) | exact +0.004, chrF +0.14 | **yes** |
| | articles, adjectives, nouns (`gov`), node / parent rules (`nrule`, `prule`) | ±0.000 to −0.3 (the article's key fragments) | no |
| article backoff | steps between (ὁ, morph, context) and (ὁ, morph): article + head noun + parent rule, + head noun, + parent rule (`MID_KEYS`) | chrF +0.15, function-word R +0.005 | **yes** |
| lexical article (TBTA's "takes the article") | a noun with "the" in ≥ 80% of its renderings gets it, ≤ 5% loses it (`LEX_ART`) | Greek ±0; Hebrew +0.36 | **yes** |
| Hebrew pronoun suffix | the suffix's person / number / gender in the noun's cell (`HEB_SFX`): "his statutes", "my" | Hebrew E6 +2.06, E5 +0.40 | **yes** |
| Hebrew construct chain | the word before is a noun in construct (`after_cstr`: "of Israel") | Hebrew E6 +0.80 (with the article), E5 +0.77 | **yes** |
| E8 = E7's memory only where it agrees with E6 (same function words; or also the same English word) | | = E6 (37.01 / 37.05 against 37.02); E7 37.71 | no |

Bootstrap of the kept changes on B (chrF, ON − OFF): Greek E6 **+0.29 [0.22, 0.36]**, E5 +0.27 [0.20, 0.34]; Hebrew E6, all
three together, **+3.31 [3.12, 3.49]**; the suffix alone E6 +2.06 [1.89, 2.23], E5 +0.40 [0.33, 0.48].

## 2. eng_v3 (the kept changes on by default)

| | word choice | form | function words P / R | order τ | chrF |
|---|---|---|---|---|---|
| NT nogospels, dev, E6 v2 → v3 | 0.580 → 0.580 | 0.494 → 0.494 | 0.586 / 0.481 → 0.593 / 0.485 | 0.873 | 35.80 → 35.89 |
| NT nogospels, B, E5 / E6 / E7 (v3) | 0.591 / 0.597 / 0.590 | 0.507 / 0.519 / 0.513 | 0.635 / 0.489, 0.644 / 0.457, 0.635 / 0.489 | 0.865 | 38.32 / 37.31 / 37.98 |
| OT, dev, E5 / E6 (day 1 → v3) | | | E6 R 0.371 → 0.503 | 0.879 | E5 37.4 → 39.0, E6 34.5 → 38.4 |
| OT, B, E5 / E6 / E7 (v3) | 0.606 / 0.613 / 0.605 | 0.520 / 0.521 / 0.519 | 0.646 / 0.510, 0.644 / 0.457, 0.646 / 0.507 | 0.898 | 40.99 / 38.39 / 40.70 |

The NT dev gain is small (dev is 127 verses); B is the reference: OT E5 39.82 → 40.99, E6 35.08 → 38.39 with round 3.

**Swap tests** (`engine/metamorphic2.py`, new; attested forms only: εἰμί has no aorist, a deponent's future is middle), on B,
share of swaps that leave the rest of the rendering unchanged — future / aorist / noun plural:
E5 0.34 / 0.70 / 0.88, **E6 1.00 / 0.96 / 1.00**, E7 0.87 / 0.90 / 0.94. Marked correctly (the form right): E5 0.39 / 0.74 /
0.94, E6 0.79 / 0.76 / 0.88, E7 0.80 / 0.59 / 0.92. Person swaps unchanged: E6 keeps the English verb in 100%. E6 is still
the only stage that behaves like a rule system; E7's memory buys reference score at its cost, and irregular plurals are
where memory helps E6 most.

**Detectors on eng_v3** (`results/auto/v3.md`): D1's "function words only after a preposition" shape fell from 13 lemmas /
225 tokens to 12 / 141 (σύ, αὐτός after a preposition gone); pronoun accuracy on B 0.511 → 0.557; D3 finds nothing over 20 B
tokens; D4 0.38 invented forms per 1,000 words. Auto rules on v3: exact 0.4254 → 0.4382 on dev, chrF +0.05.

## 3. What we learned

1. **Participant ids carry no token-level signal for English.** The BSB's subject continuity is real but small (named subject
   after a switch 13-17% against 6-8%; "and [verb]" with the subject dropped 13% against 0%) and spread over a small pool
   (1,241 third-singular statements without a subject in the honest pool). The agents' "~120 dev differences" were mostly
   differences the engine cannot fix by a field: English drops or names the subject by style. Detector D3 was right to see
   nothing. Participant ids will matter for languages that mark switch-reference or obviation (Kuni, perhaps), not for
   English; the field stays available (`CTX_EXTRA=verb.p_subj`).
2. **The article is the largest error class left, and it is lexical.** Article + noun function words are right in 48% of
   phrases; the errors are real, not alignment artefacts (phrase-level 0.49). The head noun decides most of it ("the
   Sanhedrin", "God"), and its referent's earlier mention makes it *less* likely (35% against 46-52%: English drops the
   article with known names). The backoff steps fix a little; the rest is a lexicon feature per noun, as TBTA's.
3. **Hebrew needs the word's own parts in the cell**, as the Greek needs the governor: the pronoun suffix and the construct
   chain gave +3.3 chrF, the largest gain of any change so far. E6 on Hebrew is still 2.6 behind E5 (38.4 / 41.0 on B).
4. **E7's gain over E6 is all function words the cell rule misses** (E8 test): memory that agrees with E6 gains nothing.
   Most of those are genitive "of" (151 tokens on B) and "the" (83): the article question above.
5. **A literal translation fits the engine better (rung 1c).** See below.

## 4. Rung 1c: Greek and Hebrew → KJV

Data from lexeme-aligner, read today (`kjv/SOURCES.md`): the KJV NT linked to the TR, with the Nestle 1904 ids of the same
words where TR and Nestle agree (`kjv/build_nt.py` → `data/kjv_nt.db`, 7,903 verses, 119,316 links), and the KJV OT layer
(`kjv/build_ot.py` → `data/kjv_ot.db`, 22,716 verses, 287,374 Hebrew words linked). Text from helloAO `eng_kjv`; every
fingerprint matched. The same engine (eng_v3's switches) with the KJV's function words added (thou, thee, ye, hath, unto …);
no rule written for the KJV.

| E5 (dev) | word choice | function words P / R | order τ | chrF |
|---|---|---|---|---|
| NT nogospels → BSB | 0.575 | 0.587 / 0.522 | 0.874 | 36.5 |
| NT nogospels → KJV | 0.670 | 0.697 / 0.568 | 0.919 | 41.9 |
| NT nt → BSB / KJV | 0.680 / 0.769 | 0.625 / 0.563, 0.708 / 0.586 | 0.882 / 0.922 | 43.0 / 46.7 |
| OT → BSB / KJV | 0.614 / 0.704 | 0.678 / 0.505, 0.732 / 0.676 | 0.880 / 0.941 | 39.0 / 49.0 |

On B the same: NT nogospels E5 38.3 / 43.5, OT 41.0 / 50.0. The KJV keeps the source's order (on the OT τ 0.93 before any order
rule) and one rendering per lemma far more often; the order rules add little on the KJV OT (+0.01 τ) and much on its
NT (0.85 → 0.92). Stage order is the same as on the BSB (E5 ≥ E7 > E6 on reference scores).

**Caveat:** the KJV NT layer covers 81.8% of the KJV's words (TR-only words have no Nestle id; some added words are not
decided in the layer, e.g. "it came to pass" in RUT 1:1 is linked as "Now … pass"), against 98.9% for the BSB tables; the OT
layer 92.5% (BSB 95.6%). Token measures run on the linked words only, so they are on an easier set for the KJV; chrF is over
the whole verse in both cases. A KJV spellout table (thou / ye, -est / -eth) was not needed as a separate step: the cells learn
the forms from the data, as they learn the BSB's.

## 5. Next

1. **The article as a lexicon feature per noun**, learned from the corpus (keeps / drops "the", "of" in a genitive chain), the
   TBTA way; it is now the largest remaining error class in both directions of the NT.
2. **Hebrew E6:** diagnose the remaining 2.6 against E5 (verb function words: "and he", "will").
3. **The NLLB instrument tests** when the two models finish (training: nogospels at step ~1,500 of 5,000, early stopping
   likely before 3,000; then nt).
4. **Rung 1c follow-up:** what the engine gets wrong on the KJV that it gets right on the BSB, and the reverse; pin the
   datasets to a tag when one holds the KJV.
5. Kept for languages that need it: the participant fields, `gov`, the node rules (all switchable by `CTX_EXTRA`).
