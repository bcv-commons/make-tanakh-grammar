# Rung 4: Hebrew OT -> Danish (2026-10-28, overnight, scripts only)

**Corpus.** Our own Danish OT drafts (`export/dan/dan_BSB`, CC0) with their `.align` files: only verse lines the drafting or
alignment agents made or checked (profile b), only chapters whose text hash matches the draft. `danish/build_ot.py` ->
`data/dan_ot.db` (the schema of `data/ot.db`): **5,989 verses, 78,440 Hebrew words linked**, 18 books (1-2 Sam, 1-2 Kgs, Prov,
Josh 658, Neh, Gen 21-50 parts, Ezra, Hos, Est, Dan, Amos, Ecc, Mic, Joel, Mal, Lev 1). Daniel's and Ezra's Aramaic is not in
the lab's Hebrew corpus (`ot.db`), so it is left out; the lab's test chapters (Gen 22, 37, 44) are left out. Function words
derived from the alignment as for Vamvas (`data/dan_func.txt`, 179 words: pronouns, prepositions, conjunctions, numbers, a few
names that only ever take a prefix's links).

**Caution.** These are machine drafts: the engine is measured on reproducing our agents' Danish, not a human translation.
Den Frie Bibel, aligned by lexeme-aligner (the user, 2026-10-29), is the real test; `danish/build_ot.py` reads our `.align`
files, and a DFB builder follows `vamvas/build_ot.py` (a full-alignments-llm layer on the edition's text).

**Design.** Equal data: the same Hebrew verses with three targets, Danish, the BSB (English) and Vamvas (Greek): the 5,920
training verses all three corpora have, less a held-out sample B of 800 (seed 8); dev = Genesis 24 (67 verses). `danish/run.py`
(T=dan|bsb|vamvas, ENGINE=eng_v9|eng_v10), `danish/final.sh`, `danish/final.jsonl`; paired bootstraps `danish/boot.py`.

## 1. The engine carries over to Danish without Danish code

Held-out B, 800 verses, chrF (summary) and the component measures:

| target | stage | word choice | form | fn words P / R | order tau | chrF |
|---|---|---|---|---|---|---|
| Danish | E1 baseline | 0.586 | 0.496 | 0.625 / 0.366 | 0.905 | 37.93 |
| Danish | E5 | 0.592 | 0.525 | 0.616 / 0.361 | 0.916 | **38.93** |
| Danish | E6 (eng_v10) | 0.562 | 0.493 | 0.601 / 0.340 | 0.916 | 37.19 |
| English | E5 | 0.595 | 0.512 | 0.642 / 0.496 | 0.904 | **39.71** |
| English | E6 (eng_v10) | 0.605 | 0.512 | 0.654 / 0.474 | 0.904 | 38.55 |
| Greek | E5 | 0.480 | 0.344 | 0.639 / 0.573 | 0.946 | 44.33 |
| Greek | E6 (eng_v10) | 0.488 | 0.347 | 0.644 / 0.571 | 0.946 | 44.33 |

- Danish lands where English does on the same data (E5 38.9 vs 39.7; chrF is not comparable across languages in absolute
  terms, Greek's long words score higher). Order is as good (tau 0.92).
- Danish's weak point is the function words' recall (0.36 vs English 0.50): the engine leaves out Danish small words
  more than English ones (not yet broken down by word).
- Every eng_v9 switch carries over or is neutral (each switched off on Danish E6): the pronoun-suffix key (HEB_SFX) is worth
  +1.7 chrF, the case keys (FORM_ROLE, GOV_KEY) +0.3, PRE_LEX +0.2, POST_CELL / CHOICE_CTX under +0.1, MID_KEYS / ART 0
  (`danish/variants2.jsonl`, on the corpus before the final Joshua). ART=learn picks up "af"/"den" on Danish (its definite article is a suffix), harmlessly.
- E6 is below E5 on Danish (-1.73 [-2.11, -1.37]) **and on English** on these verses (-1.15 [-1.58, -0.71]), and on English
  even with its full 21,735 training verses (41.43 vs 40.42, `danish/full_pool.jsonl`): not a Danish problem; with this
  amount of data E5 is the stage to use. More data helps all: English +1.7, Greek +1.9 from 5k to 22k verses.

## 2. One general fix, found on Danish: eng_v10 = eng_v9 + NOWORD

E6 wrote stems that are no words (*kong* for *kongen/konger*, *forbandels*): a rule's form not in the corpus fell back to the bare
stem. NOWORD (`eng_v10/gen6.py`): when the bare stem is no corpus word either, the lemma's commonest attested head. Paired
bootstrap, E6, B:

| target | eng_v10 - eng_v9 |
|---|---|
| Danish | **+0.12** [0.07, 0.17] |
| English (BSB OT) | **+0.05** [0.02, 0.08] |
| Greek (Vamvas) | **+0.35** [0.28, 0.43] |

ENDINGS=learn (endings learned from the target's vocabulary) helps Danish E6 too, like Vamvas earlier and unlike English. So
**ENDINGS=auto**: the English hand list where it fits the target (it splits >= 15% of the word types seen twice: BSB 0.26, KJV
0.24), else learned endings (Danish 0.08; Vamvas, HEBM95 0.00). Paired bootstrap, E6, auto against hybrid (eng_v9's default):

| target | auto - hybrid |
|---|---|
| Danish (B, rung 4) | **+0.28** [0.11, 0.45] |
| HEBM95 NT (B, rung 2's set) | **+0.11** [0.04, 0.18] |
| Vamvas (B, rung 4) | +0.12 [-0.05, 0.28] |
| BSB OT (B, rung 4) | 0.00 (the gate keeps hybrid) |

Both frozen as **eng_v10** = eng_v9 + NOWORD + ENDINGS=auto (defaults; `eng_v10/cells.py` header).

## 3. What Danish needs that the engine doesn't have (E6 nouns on B, `danish/nouns.py`)

| noun head | share |
|---|---|
| right | 60.9% |
| another word (synonym; much of it variation inside our own drafts) | 25.0% |
| genitive -s (*jødernes X* vs *X af jøderne*: the construction differs, not the ending) | 6.0% |
| definiteness (*vejen* vs *vej*; the Hebrew article or the construct chain decides) | 5.0% |
| other ending (number, compounds) | 2.6% |

Tried and not kept: **REFL** (the reflexive *sin/sit/sine* when the possessor is the clause's subject, cue: a 3rd-person suffix
agreeing with the clause's finite verb): written possessives right 76% with and without it (`danish/refl_check.py`); the cue is
too weak, a subject-reference field (participants) would be needed. E5 vs E6 losses (`danish/gap_B.txt`) also show possessive
gender agreement (*min hus* for *mit hus*) and imperatives (*spørg* for *spørge*).

## 4. Next (for the user's go)

1. **DFB:** build `data/dfb_ot.db` from lexeme-aligner's DFB layer and rerun `danish/run.py` with T=dfb: the human Danish;
   compare the engine's figures on DFB with those on our drafts (same verses where both exist) and our drafts with DFB.
2. Danish definiteness and the genitive from the construct chain (after_cstr + the article), measured on DFB, not on our drafts.
